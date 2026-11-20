"""Tiny async HTTP server: OTA file updates + app routes.

OTA endpoints (require header X-OTA-Token: <credentials.OTA_TOKEN>):
    GET    /ota/files              -> {"/path.py": [size, sha256], ...}
    PUT    /ota/file?path=/x.py    body = file contents, header X-SHA256 = hex digest
    DELETE /ota/file?path=/x.py
    POST   /ota/reset              -> reboots after the reply is sent
    GET    /ota/log                -> last crash traceback (/error.log)
    GET    /ota/info

Uploads go to <path>.part, are verified against X-SHA256 and then renamed into
place, so an interrupted transfer never leaves a half-written module behind.
Use tools/ota.py on your computer rather than calling these by hand.
"""
import asyncio
import binascii
import gc
import hashlib
import json
import os
import sys
import time

import machine

LOG_FILE = "/error.log"
_BOOT = time.ticks_ms()
_REASONS = {200: "OK", 400: "Bad Request", 401: "Unauthorized", 404: "Not Found",
            413: "Payload Too Large", 500: "Internal Server Error"}


def uptime_s():
    return time.ticks_diff(time.ticks_ms(), _BOOT) // 1000


def log_exception(e, context=""):
    print("!!", context)
    sys.print_exception(e)
    try:
        with open(LOG_FILE, "w") as f:
            f.write("%s (uptime %ds)\n" % (context, uptime_s()))
            sys.print_exception(e, f)
    except OSError:
        pass


def _unquote(s):
    if "%" not in s and "+" not in s:
        return s
    parts = s.replace("+", " ").split("%")
    out = bytearray(parts[0].encode())
    for p in parts[1:]:
        try:
            out.append(int(p[:2], 16))
            out.extend(p[2:].encode())
        except ValueError:
            out.extend(("%" + p).encode())
    return out.decode()


def _parse_qs(qs):
    q = {}
    for part in qs.split("&"):
        if part:
            k, _, v = part.partition("=")
            q[_unquote(k)] = _unquote(v)
    return q


def _hex(b):
    return binascii.hexlify(b).decode()


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024)
            if not chunk:
                break
            h.update(chunk)
    return _hex(h.digest())


def _walk(d=""):
    for entry in os.ilistdir(d or "/"):
        path = d + "/" + entry[0]
        if entry[1] == 0x4000:
            yield from _walk(path)
        else:
            yield path


def _safe_path(p):
    if not p.startswith("/") or ".." in p or p.endswith("/"):
        raise ValueError("bad path: %r" % p)
    return p


def _makedirs(path):
    cur = ""
    for part in path.split("/")[1:-1]:
        cur += "/" + part
        try:
            os.mkdir(cur)
        except OSError:
            pass


async def _read_body(reader, length):
    data = b""
    while len(data) < length:
        chunk = await reader.read(length - len(data))
        if not chunk:
            break
        data += chunk
    return data


async def _respond(writer, status, payload=None, ctype=None):
    if isinstance(payload, (dict, list)):
        payload = json.dumps(payload)
        ctype = ctype or "application/json"
    if payload is None:
        payload = b""
    if isinstance(payload, str):
        payload = payload.encode()
    head = "HTTP/1.0 %d %s\r\nContent-Type: %s\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % (
        status, _REASONS.get(status, ""), ctype or "text/plain", len(payload))
    writer.write(head.encode())
    writer.write(payload)
    await writer.drain()


async def _reset_soon():
    await asyncio.sleep_ms(400)
    machine.reset()


class Server:
    def __init__(self, token, port=80):
        self.token = token
        self.port = port
        self.routes = {}

    def route(self, method, path, handler):
        """handler(query: dict, body: bytes) -> (status, payload[, content_type])"""
        self.routes[(method, path)] = handler

    async def start(self):
        self._srv = await asyncio.start_server(self._client, "0.0.0.0", self.port)
        print("HTTP/OTA server on port", self.port)

    async def _client(self, reader, writer):
        try:
            await self._handle(reader, writer)
        except Exception as e:
            sys.print_exception(e)
            try:
                await _respond(writer, 500, {"error": repr(e)})
            except Exception:
                pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            gc.collect()

    async def _handle(self, reader, writer):
        line = await reader.readline()
        if not line:
            return
        try:
            method, target, _ = line.decode().split(" ", 2)
        except ValueError:
            return await _respond(writer, 400, {"error": "bad request line"})
        path, _, qs = target.partition("?")
        query = _parse_qs(qs)
        headers = {}
        while True:
            h = await reader.readline()
            if not h or h in (b"\r\n", b"\n"):
                break
            k, _, v = h.decode().partition(":")
            headers[k.strip().lower()] = v.strip()
        length = int(headers.get("content-length") or 0)

        if path.startswith("/ota/"):
            if not self.token or headers.get("x-ota-token") != self.token:
                return await _respond(writer, 401, {"error": "missing or wrong X-OTA-Token"})
            if method == "PUT" and path == "/ota/file":
                try:
                    _safe_path(query.get("path", ""))  # validate before consuming the body
                except ValueError as e:
                    await _read_body(reader, length)
                    return await _respond(writer, 400, {"error": str(e)})
                return await _respond(writer, *(await self._upload(reader, query, headers, length)))
            await _read_body(reader, length)
            try:
                result = self._ota(method, path, query)
            except (ValueError, OSError) as e:
                result = 400, {"error": str(e)}
            return await _respond(writer, *result)

        handler = self.routes.get((method, path))
        if handler is None:
            return await _respond(writer, 404, {"error": "no route %s %s" % (method, path)})
        if length > 4096:
            return await _respond(writer, 413, {"error": "body too large"})
        body = await _read_body(reader, length)
        return await _respond(writer, *handler(query, body))

    def _ota(self, method, path, query):
        if method == "GET" and path == "/ota/files":
            return 200, {p: [os.stat(p)[6], _sha256_file(p)] for p in _walk()}
        if method == "DELETE" and path == "/ota/file":
            p = _safe_path(query.get("path", ""))
            os.remove(p)
            return 200, {"deleted": p}
        if method == "POST" and path == "/ota/reset":
            asyncio.create_task(_reset_soon())
            return 200, {"reset": True}
        if method == "GET" and path == "/ota/log":
            try:
                with open(LOG_FILE) as f:
                    return 200, f.read()
            except OSError:
                return 200, "(no errors logged)\n"
        if method == "GET" and path == "/ota/info":
            fs = os.statvfs("/")
            return 200, {"platform": sys.platform, "version": sys.version,
                         "machine": sys.implementation._machine if hasattr(sys.implementation, "_machine") else "",
                         "uptime_s": uptime_s(), "mem_free": gc.mem_free(),
                         "fs_free": fs[0] * fs[3], "reset_cause": machine.reset_cause()}
        return 404, {"error": "unknown OTA call"}

    async def _upload(self, reader, query, headers, length):
        path = _safe_path(query.get("path", ""))
        expected = headers.get("x-sha256")
        tmp = path + ".part"
        _makedirs(path)
        h = hashlib.sha256()
        remaining = length
        with open(tmp, "wb") as f:
            while remaining:
                chunk = await reader.read(min(1024, remaining))
                if not chunk:
                    raise OSError("connection closed mid-upload")
                h.update(chunk)
                f.write(chunk)
                remaining -= len(chunk)
        digest = _hex(h.digest())
        if expected and digest != expected:
            os.remove(tmp)
            return 400, {"error": "sha256 mismatch", "got": digest}
        try:
            os.rename(tmp, path)
        except OSError:
            try:
                os.remove(path)
            except OSError:
                pass
            os.rename(tmp, path)
        print("OTA: wrote", path, length, "bytes")
        return 200, {"path": path, "size": length, "sha256": digest}
