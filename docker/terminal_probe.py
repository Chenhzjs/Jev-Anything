"""Execute one advertised GUI2TUI operation and verify via read-only AT-SPI."""

import json
import os
import time
from pathlib import Path

import gi
import pexpect
import pyte

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi
from atspi_probe import walk


def checked():
    desktop = Atspi.get_desktop(0)
    apps = [desktop.get_child_at_index(i) for i in range(desktop.get_child_count())]
    app = next(a for a in apps if a.get_name() == os.environ.get("JEV_APP", "jev-fixture"))
    app.clear_cache()
    matches = [n for n in walk(app) if n.get_name() == "Enable dark mode" and n.get_role_name() == "check box"]
    assert len(matches) == 1, "Exact checkbox must be present"
    matches[0].clear_cache()
    return matches[0].get_state_set().contains(Atspi.StateType.CHECKED)


def main():
    screen = pyte.Screen(240, 50)
    stream = pyte.Stream(screen)
    app_name = os.environ.get("JEV_APP", "jev-fixture")
    terminal = pexpect.spawn("gui2tui", ["--session", "desktop", "--layout", "flat", "--app", app_name], encoding="utf-8", dimensions=(50, 240), timeout=1)
    transcript = []

    def pump():
        try:
            chunk = terminal.read_nonblocking(65536, timeout=0.1)
            transcript.append(chunk)
            stream.feed(chunk)
        except pexpect.TIMEOUT:
            pass
        return "\n".join(screen.display)

    def wait(text):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            frame = pump()
            if text in frame:
                return frame
        raise AssertionError("GUI2TUI did not display " + repr(text))

    try:
        assert not checked(), "Fixture must start unchecked"
        wait("? Help")
        terminal.send("\x1bOR")
        wait("Command palette")
        terminal.send("Enable dark mode")
        wait("Action: click")
        # Select only an exact public operation rendered by the running TUI.
        found = False
        for _ in range(30):
            frame = pump()
            selected = [line for line in frame.splitlines() if "> " in line]
            if any("Enable dark mode" in line and "Action: click" in line for line in selected):
                found = True
                break
            terminal.send("\x1b[B")
            time.sleep(0.15)
        assert found, "Exact public operation was not selected"
        terminal.send("\r")
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not checked():
            pump()
        assert checked(), "Public AT-SPI readback did not confirm CHECKED"
        print(json.dumps({"status": "passed", "driver": "gui2tui_pty", "before_checked": False, "after_checked": True}))
    finally:
        output = Path("/tmp/jev-evidence")
        output.mkdir(exist_ok=True)
        (output / "terminal.txt").write_text("\n".join(screen.display))
        (output / "terminal.ansi").write_text("".join(transcript))
        terminal.close(force=True)


if __name__ == "__main__":
    main()
