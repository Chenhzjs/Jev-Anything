#!/usr/bin/env python3
"""Run the first live Docker acceptance checks inside the Linux container."""

import json
import os
import subprocess
import sys
import time


def run(*args, check=True):
    print("$", " ".join(args), flush=True)
    result = subprocess.run(args, text=True, capture_output=True, timeout=120)
    if check and result.returncode:
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        result.check_returncode()
    return result


def main():
    # The entrypoint owns the session environment; direct invocations inherit
    # it in normal container use. Fail with a useful diagnostic otherwise.
    missing = [name for name in ("DISPLAY", "DBUS_SESSION_BUS_ADDRESS") if not os.environ.get(name)]
    if missing:
        raise SystemExit("Missing graphical session environment: " + ", ".join(missing)
                         + "; run through the Docker entrypoint or export the live session variables.")
    fixture = "/opt/jev-anything/fixture.py"
    fixture_env = os.environ.copy()
    fixture_env["JEV_APP"] = "jev-live-check"
    os.environ["JEV_APP"] = "jev-live-check"
    fixture_proc = subprocess.Popen(["python3", fixture], env=fixture_env)
    try:
        time.sleep(2)
        probe = run("python3", "/opt/jev-anything/atspi_probe.py")
        print("AT-SPI:", probe.stdout.strip())
        probe_json = json.loads(probe.stdout)
        assert probe_json["nodes"] >= 3

        listed = run("gui2tui", "inspect", "--list")
        print("GUI2TUI LIST:", listed.stdout[:1200])
        assert listed.returncode == 0

        inspected = run("gui2tui", "inspect", "--", "--app", "jev-live-check", "--dump-scene")
        print("GUI2TUI SCENE:", inspected.stdout[:1800])
        assert inspected.returncode == 0
        assert "Enable dark mode" in inspected.stdout
        operated = run("python3", "/opt/jev-anything/terminal_probe.py")
        print("GUI2TUI ACTION:", operated.stdout)
        print(run("python3", "-m", "unittest", "discover", "-s", "/opt/jev-anything/tests", "-v").stderr)
        print(json.dumps({"status": "passed", "checks": ["xvfb", "dbus", "atspi", "gui2tui_discovery", "gui2tui_scene", "gui2tui_pty_action", "atspi_readback", "unit_tests"]}))
    finally:
        fixture_proc.terminate()
        fixture_proc.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
