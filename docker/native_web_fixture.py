"""Validation only: independent pages, HTTP request oracle and browser startup.
The native adapter does not import this file or any page-specific information.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from urllib.parse import parse_qs, urlparse
from html import escape

PAGES = {
    '/preferences': '''<title>Preferences Lab</title><main><h1>Display preferences</h1>
<label><input id="theme" type="checkbox" onchange="document.getElementById('status').textContent=this.checked?'Dark mode enabled':'Dark mode disabled'"> Enable dark mode</label>
<p id="status" role="status">Dark mode disabled</p></main>''',
    '/catalog': '''<title>Catalog Lab</title><main><h1>Search the catalog</h1>
<form action="/results"><label>Search query <input name="q" type="search"></label>
<button type="submit">Search catalog</button></form></main>''',
    '/navigation': '''<title>Navigation Lab</title><nav><a href="/help">Help</a> <a href="/destination">Installation guide</a></nav>
<main><h1>Documentation index</h1><p>Choose a document.</p></main>''',
    '/destination': '<title>Installation guide</title><main><h1>Installation guide</h1><p>Installation instructions are now open.</p></main>',
    '/help': '<title>Help</title><h1>Help center</h1>',
}
REQUESTS = []

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        if url.path == '/oracle':
            body = json.dumps(REQUESTS).encode()
            content_type = 'application/json'
        else:
            REQUESTS.append(self.path)
            content_type = 'text/html; charset=utf-8'
            page = PAGES.get(url.path, '<h1>Not found</h1>')
            if url.path == '/results':
                query = parse_qs(url.query).get('q', [''])[0]
                page = '<title>Catalog results</title><main><h1>Catalog results</h1><p>Results for: ' + escape(query) + '</p></main>'
            body = ('<!doctype html><meta charset="utf-8">' + page).encode()
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8765/preferences')
    parser.add_argument('--exec-agent', action='store_true')
    parser.add_argument('--oracle', action='store_true')
    args = parser.parse_args()
    if args.exec_agent or args.oracle:
        env = json.loads(Path('/tmp/native-session.json').read_text())
        os.environ.update(env)
        if args.oracle:
            import pyatspi
            rows = []
            queue = [a for a in pyatspi.Registry.getDesktop(0) if 'firefox' in a.name.lower()]
            while queue:
                node = queue.pop(0)
                try:
                    role = node.getRoleName()
                    if role in ('check box', 'document web', 'heading', 'paragraph', 'status bar'):
                        try:
                            text = node.queryText().getText(0, -1)
                        except NotImplementedError:
                            text = None
                        rows.append({'role': role, 'name': node.name, 'text': text,
                                     'checked': node.getState().contains(pyatspi.STATE_CHECKED)})
                    queue.extend(node[i] for i in range(node.childCount) if node[i] is not None)
                except Exception:
                    continue
            print(json.dumps(rows))
            return
        for _ in range(100):
            if Path('/tmp/native-ready').exists():
                break
            time.sleep(.2)
        os.execv('/gui2tui-agent', ['/gui2tui-agent', '--session', 'desktop', '--app', 'Firefox'])
    os.environ.update(DISPLAY=':98', GTK_A11Y='atspi', NO_AT_BRIDGE='0',
                      MOZ_ACCESSIBILITY_ATSPI_ENABLED='1', XDG_RUNTIME_DIR='/tmp/jev-runtime')
    Path('/tmp/jev-runtime').mkdir(mode=0o700, exist_ok=True)
    session_env = {key: os.environ[key] for key in ('DISPLAY', 'GTK_A11Y', 'NO_AT_BRIDGE', 'MOZ_ACCESSIBILITY_ATSPI_ENABLED', 'XDG_RUNTIME_DIR', 'DBUS_SESSION_BUS_ADDRESS')}
    Path('/tmp/native-session.json').write_text(json.dumps(session_env))
    Path('/tmp/native-session.json').chmod(0o600)
    server = ThreadingHTTPServer(('0.0.0.0', 8765), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with open('/tmp/xvfb.log', 'w') as log:
        display = subprocess.Popen(['Xvfb', ':98', '-screen', '0', '1280x900x24', '-ac'], stdout=log, stderr=log)
    for _ in range(50):
        if Path('/tmp/.X11-unix/X98').exists():
            break
        time.sleep(.1)
    profile = Path('/tmp/jev-firefox-profile')
    profile.mkdir(exist_ok=True)
    (profile / 'user.js').write_text('user_pref("accessibility.force_disabled", -1);\nuser_pref("browser.shell.checkDefaultBrowser", false);\nuser_pref("browser.startup.homepage_override.mstone", "ignore");\nuser_pref("datareporting.policy.dataSubmissionPolicyBypassNotification", true);\n')
    with open('/tmp/firefox.log', 'w') as log:
        browser = subprocess.Popen(['firefox-esr', '--no-remote', '--profile', str(profile), args.url], stdout=log, stderr=log)
    import pyatspi
    for _ in range(100):
        if any('firefox' in app.name.lower() for app in pyatspi.Registry.getDesktop(0)):
            Path('/tmp/native-ready').touch()
            break
        time.sleep(.2)
    try:
        browser.wait()
    finally:
        display.terminate()
        server.shutdown()

if __name__ == '__main__':
    main()
