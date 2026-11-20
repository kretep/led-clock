#!/usr/bin/env python3
"""Over-the-air deploy and control for the LED clock (stdlib only).

    python3 tools/ota.py push              # upload changed files from src/, then reboot
    python3 tools/ota.py push --force      # upload everything
    python3 tools/ota.py push --no-reset   # upload only
    python3 tools/ota.py ls | rm /x.py | reset | log | info
    python3 tools/ota.py mode              # list modes
    python3 tools/ota.py mode comets       # switch mode (also: mode next)
    python3 tools/ota.py brightness 0.3

Host: --host, or $LEDCLOCK_HOST, or <HOSTNAME>.local from src/config.py.
Token: OTA_TOKEN from src/credentials.py.
"""
import argparse
import hashlib
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
SKIP = re.compile(r"(\.example\.py$|^\.|__pycache__|\.pyc$)")


def _setting(filename, name):
    try:
        with open(os.path.join(SRC, filename)) as f:
            m = re.search(r'^%s\s*=\s*["\']([^"\']*)["\']' % name, f.read(), re.M)
            return m.group(1) if m else None
    except FileNotFoundError:
        return None


class Device:
    def __init__(self, host, token):
        self.host, self.token = host, token

    def call(self, method, path, query=None, data=None, headers=None, timeout=15):
        url = "http://%s%s" % (self.host, path)
        if query:
            url += "?" + urllib.parse.urlencode(query)
        h = {"X-OTA-Token": self.token or ""}
        h.update(headers or {})
        req = urllib.request.Request(url, data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
        except urllib.error.HTTPError as e:
            sys.exit("%s %s -> HTTP %d: %s" % (method, path, e.code, e.read().decode(errors="replace")))
        except (urllib.error.URLError, socket.timeout) as e:
            sys.exit("cannot reach %s: %s" % (self.host, getattr(e, "reason", e)))
        try:
            return json.loads(body)
        except ValueError:
            return body.decode(errors="replace")


def local_files():
    out = {}
    for dirpath, dirnames, filenames in os.walk(SRC):
        dirnames[:] = [d for d in dirnames if not SKIP.search(d)]
        for fn in filenames:
            if SKIP.search(fn):
                continue
            full = os.path.join(dirpath, fn)
            out["/" + os.path.relpath(full, SRC).replace(os.sep, "/")] = full
    return out


def cmd_push(dev, args):
    files = local_files()
    if "/credentials.py" not in files:
        print("warning: src/credentials.py not found locally; the copy on the board is left as is")
    # Syntax-check everything locally first: a broken main.py/ota.py/wifi.py
    # would take the board off the network (USB needed to recover).
    for dev_path, full in files.items():
        if full.endswith(".py"):
            with open(full) as f:
                try:
                    compile(f.read(), full, "exec")
                except SyntaxError as e:
                    sys.exit("syntax error, nothing uploaded: %s:%s: %s" % (full, e.lineno, e.msg))
    remote = {} if args.force else dev.call("GET", "/ota/files")
    changed = []
    for dev_path, full in sorted(files.items()):
        with open(full, "rb") as f:
            data = f.read()
        digest = hashlib.sha256(data).hexdigest()
        if remote.get(dev_path, [None, None])[1] != digest:
            changed.append((dev_path, data, digest))
    if not changed:
        print("device is up to date")
        return
    for dev_path, data, digest in changed:
        print("  -> %-24s %6d bytes" % (dev_path, len(data)))
        dev.call("PUT", "/ota/file", {"path": dev_path}, data,
                 {"X-SHA256": digest, "Content-Type": "application/octet-stream"})
    print("uploaded %d file(s)" % len(changed))
    if not args.no_reset:
        dev.call("POST", "/ota/reset", data=b"")
        print("rebooting... ", end="", flush=True)
        time.sleep(4)
        for _ in range(20):
            try:
                with urllib.request.urlopen("http://%s/api/status" % dev.host, timeout=2) as r:
                    s = json.loads(r.read())
                print("back up, mode=%s" % s.get("mode"))
                return
            except Exception:
                time.sleep(1)
        print("not answering yet - check `python3 tools/ota.py log` or the serial console")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host", default=os.environ.get("LEDCLOCK_HOST"))
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("push")
    sp.add_argument("--force", action="store_true")
    sp.add_argument("--no-reset", action="store_true")
    sub.add_parser("ls")
    sub.add_parser("reset")
    sub.add_parser("log")
    sub.add_parser("info")
    sub.add_parser("rm").add_argument("path")
    sub.add_parser("mode").add_argument("name", nargs="?")
    sub.add_parser("brightness").add_argument("value", type=float)
    args = p.parse_args()

    host = args.host or "%s.local" % (_setting("config.py", "HOSTNAME") or "ledclock")
    name, _, port = host.partition(":")
    try:  # resolve once (mDNS lookups can be slow on macOS)
        host = socket.gethostbyname(name) + (":" + port if port else "")
    except OSError:
        sys.exit("cannot resolve %s - pass --host <ip> (the IP is printed on the serial console)" % host)
    dev = Device(host, _setting("credentials.py", "OTA_TOKEN"))

    if args.cmd == "push":
        cmd_push(dev, args)
    elif args.cmd == "ls":
        for path, (size, _) in sorted(dev.call("GET", "/ota/files").items()):
            print("%7d  %s" % (size, path))
    elif args.cmd == "rm":
        print(dev.call("DELETE", "/ota/file", {"path": args.path}))
    elif args.cmd == "reset":
        print(dev.call("POST", "/ota/reset", data=b""))
    elif args.cmd == "log":
        print(dev.call("GET", "/ota/log"))
    elif args.cmd == "info":
        print(json.dumps(dev.call("GET", "/ota/info"), indent=2))
    elif args.cmd == "mode":
        if args.name:
            print(dev.call("POST", "/api/mode", {"name": args.name}, data=b""))
        else:
            s = dev.call("GET", "/api/status")
            for m in s["modes"]:
                print(("* " if m == s["mode"] else "  ") + m)
    elif args.cmd == "brightness":
        print(dev.call("POST", "/api/brightness", {"value": args.value}, data=b""))


if __name__ == "__main__":
    main()
