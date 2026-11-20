#!/bin/sh
# Run an mpremote command on the board with the local src/ folder mounted, e.g.
#   tools/board_run.sh exec "import patterns; patterns.preview('comets')"
#   tools/board_run.sh run experiments/sandbox.py
#
# Ctrl-C normally only quits mpremote on this computer while the board keeps
# animating. Here Ctrl-C also interrupts the board and turns the LEDs off.
PORT=${PORT:-$(ls /dev/cu.usbmodem* 2>/dev/null | head -1)}
cd "$(dirname "$0")/.." || exit 1

err=$(mktemp)
stopped=
trap 'stopped=1' INT

mpremote connect "$PORT" mount src "$@" 2>"$err"
rc=$?

if [ -n "$stopped" ]; then
    # Connecting again interrupts the program on the board; then blank the LEDs.
    mpremote connect "$PORT" mount src exec "from leds import Display; Display().off()" >/dev/null 2>&1
    echo
    echo "stopped, LEDs off"
    rc=0
else
    cat "$err" >&2   # only show mpremote's own errors if it wasn't a Ctrl-C
fi
rm -f "$err"
exit $rc
