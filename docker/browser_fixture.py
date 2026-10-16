"""Launch a small accessible Epiphany page for the live browser proof."""
import html
import json
import os
import pathlib
import subprocess
import sys
import time

from jev_anything.scenarios import SCENARIOS


scenario = sys.argv[1] if len(sys.argv) > 1 else "browser-home"
config = SCENARIOS[scenario]
context = os.environ.get("JEV_CONTEXT", config["context"])
actions = config["actions"]
buttons = "".join(
    f'<button id="{html.escape(identity)}" data-effect="{html.escape(effect or "")}">{html.escape(label)}</button>'
    for identity, label, effect in actions
)
if scenario == "browser-tictactoe":
    board = '<div role="grid" aria-label="Tic-Tac-Toe board">' + "".join(
        f'<button id="{html.escape(identity)}" aria-label="{html.escape(label)}">.</button>'
        for identity, label, _ in actions
    ) + "</div>"
    buttons = board
page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{html.escape(config['window_title'])}</title>
<style>body{{font:20px sans-serif;margin:40px;color:#17201f}}button{{display:block;margin:12px 0;padding:12px 18px;font-size:18px}}[role=grid]{{display:grid;grid-template-columns:repeat(3,90px);gap:8px}}[role=grid] button{{width:90px;height:90px}}</style></head>
<body><main><h1>{html.escape(config['title'])}</h1><p id="context">{html.escape(context)}</p><div id="actions">{buttons}</div><p id="status">Ready</p></main>
<script>document.querySelectorAll('button').forEach((button)=>button.addEventListener('click',()=>{{
  if (button.dataset.effect) document.getElementById('status').textContent=button.dataset.effect;
  else {{ button.textContent='X'; button.setAttribute('aria-label', button.id + ' occupied'); button.disabled=true; document.getElementById('status').textContent='Move: X at ' + button.id.replaceAll('-', ' '); }}
}}));</script></body></html>"""
path = pathlib.Path("/tmp/jev-anything-browser.html")
path.write_text(page, encoding="utf-8")
subprocess.run(["pkill", "-f", "epiphany.*jev-anything-browser"], check=False)
subprocess.run(
    ["gsettings", "set", "org.gnome.Epiphany", "ask-for-default", "false"],
    check=False,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
profile = "/tmp/jev-anything-epiphany-profile"
subprocess.run(["rm", "-rf", profile], check=False)
command = ["epiphany", "--private-instance", f"--profile={profile}", f"file://{path}"]
subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.5)
