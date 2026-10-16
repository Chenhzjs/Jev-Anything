"""A local test application. No external effects or application-specific adapter."""

import gi
import os
from jev_anything.scenarios import SCENARIOS

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

scenario_name = os.environ.get("JEV_SCENARIO", "preferences")
config = SCENARIOS[scenario_name]
GLib.set_prgname(os.environ.get("JEV_APP", config["app"]))
window = Gtk.Window(title=config["window_title"])
window.set_default_size(800, 500)
window.set_border_width(32)
box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
box.add(Gtk.Label(label=config["title"], xalign=0))
context = Gtk.Label(label=os.environ.get("JEV_CONTEXT", config["context"]), xalign=0)
context.set_line_wrap(True)
box.add(context)
status = Gtk.Label(label="Ready", xalign=0)
if scenario_name == "tictactoe":
    board = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    action_by_cell = {identity: (label, effect) for identity, label, effect in config["actions"]}
    for row in range(1, 4):
        line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        for column in range(1, 4):
            identity = f"cell-{row}-{column}"
            if identity in action_by_cell:
                label, effect = action_by_cell[identity]
                button = Gtk.Button(label=label)
                button.set_size_request(220, 62)
                button.connect("clicked", lambda _, text=effect: status.set_text(text))
                line.pack_start(button, True, True, 0)
            else:
                mark = {"cell-1-1": "X", "cell-1-3": "O", "cell-2-2": "X", "cell-3-1": "O", "cell-3-3": " "}[identity]
                cell = Gtk.Label(label=mark)
                cell.set_size_request(220, 62)
                line.pack_start(cell, True, True, 0)
        board.pack_start(line, False, False, 0)
    box.add(board)
else:
    for identity, label, effect in config["actions"]:
        button = Gtk.CheckButton(label=label) if identity == "c-theme" else Gtk.Button(label=label)
        if effect and identity != "c-theme":
            button.connect("clicked", lambda _, text=effect: status.set_text(text))
        box.add(button)
box.add(status)
window.add(box)
window.connect("destroy", Gtk.main_quit)
window.show_all()
Gtk.main()
