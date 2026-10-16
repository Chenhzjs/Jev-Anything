#!/usr/bin/env bash
set -euo pipefail

export DISPLAY=:99
export NO_AT_BRIDGE=0 GTK_A11Y=atspi TERM=xterm-256color
export CHROME_DISABLE_SANDBOX=1
export XDG_RUNTIME_DIR="/tmp/runtime-gui2tui"
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
Xvfb "$DISPLAY" -screen 0 800x500x24 -ac +extension GLX +render -noreset >/tmp/xvfb.log 2>&1 &
xvfb_pid=$!
trap 'kill "$xvfb_pid" 2>/dev/null || true' EXIT
for attempt in {1..50}; do
    if xdpyinfo >/dev/null 2>&1; then break; fi
    sleep 0.1
done
xdpyinfo >/dev/null

dbus-run-session -- bash -lc 'exec "$@"' bash "$@"
