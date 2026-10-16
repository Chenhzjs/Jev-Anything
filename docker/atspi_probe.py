#!/usr/bin/env python3
"""Read-only proof that a GTK application is visible on the AT-SPI bus."""

import json
import os
import sys
import time

import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi


def walk(node, depth=0):
    yield node
    if depth >= 8:
        return
    try:
        count = node.get_child_count()
        for index in range(count):
            yield from walk(node.get_child_at_index(index), depth + 1)
    except Exception:
        return


def main():
    deadline = time.time() + 15
    while time.time() < deadline:
        apps = []
        for index in range(Atspi.get_desktop(0).get_child_count()):
            app = Atspi.get_desktop(0).get_child_at_index(index)
            if app and app.get_name():
                apps.append(app)
        app = next((a for a in apps if a.get_name() == os.environ.get("JEV_APP", "jev-fixture")), None)
        if app is not None:
            nodes = list(walk(app))
            print(json.dumps({"application": app.get_name(), "nodes": len(nodes), "roles": sorted({n.get_role_name() for n in nodes}), "root": app.get_name()}, ensure_ascii=False))
            return 0
        time.sleep(0.2)
    print("AT-SPI application discovery timed out", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
