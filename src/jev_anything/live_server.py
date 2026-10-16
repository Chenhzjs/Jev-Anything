"""Docker-only live workbench with an incremental event stream."""
import json
import threading
import time
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from .live import LiveSession
from .scenarios import SCENARIOS

ROOT = Path("/opt/jev-anything/web")
events = []
lock = threading.Lock()
busy = threading.Lock()
paused = threading.Event()
session = None


def emit(event):
    with lock:
        event["sequence"] = len(events)
        events.append(event)


def release_busy():
    """Release the current request gate without masking a concurrent reset."""
    try:
        busy.release()
    except RuntimeError:
        # Tests and embedders may replace the process-local lock while a
        # rejected request is unwinding. The request is already rejected.
        pass


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def respond(self, data, mime="application/json", status=200):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/config":
            self.respond(json.dumps({"fixtures": {key: {"app": value["app"], "title": value["title"], "context": value["context"]} for key, value in SCENARIOS.items()}}).encode())
        elif path == "/api/events":
            with lock:
                data = json.dumps(events).encode()
            self.respond(data)
        elif path == "/api/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                cursor = max(0, int(self.headers.get("Last-Event-ID", "-1")) + 1)
            except ValueError:
                cursor = 0
            if cursor > len(events):
                cursor = 0
            try:
                while True:
                    with lock:
                        batch = events[cursor:]
                    for event in batch:
                        self.wfile.write(f'id: {event["sequence"]}\ndata: {json.dumps(event)}\n\n'.encode())
                        cursor += 1
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
                    time.sleep(0.2)
            except (BrokenPipeError, ConnectionResetError):
                pass
        elif path == "/api/frame":
            self.respond(json.dumps({"terminal": session.frame, "busy": busy.locked(), "paused": paused.is_set()}).encode())
        elif path == "/api/gui.png":
            data = subprocess.run(["python3", "/opt/jev-anything/capture.py"], capture_output=True, check=True, timeout=5).stdout
            self.respond(data, "image/png")
        elif path == "/favicon.ico":
            self.respond(b"", "image/x-icon", 204)
        elif path in {"/", "/style.css", "/app.js"}:
            name = "index.html" if path == "/" else path[1:]
            self.respond((ROOT/name).read_bytes(), {"index.html": "text/html; charset=utf-8", "style.css": "text/css", "app.js": "text/javascript"}[name])
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/pause":
            paused.set()
            self.respond(b'{"paused":true}')
            return
        if parsed.path not in {"/api/run", "/api/reset"}:
            self.send_error(404)
            return
        if not busy.acquire(blocking=False):
            self.respond(b'{"error":"busy"}', status=409)
            return
        query = parse_qs(parsed.query)
        if parsed.path == "/api/reset":
            fixture = query.get("fixture", ["preferences"])[0]
            if fixture not in SCENARIOS:
                self.respond(json.dumps({"error": "unknown_fixture", "fixtures": list(SCENARIOS)}).encode(), status=400)
                release_busy()
                return
        if parsed.path == "/api/run" and not query.get("goal", [""])[0].strip():
            self.respond(b'{"error":"goal_required"}', status=400)
            release_busy()
            return
        if parsed.path == "/api/run":
            requested_fixture = query.get("fixture", [None])[0]
            if requested_fixture is not None and requested_fixture not in SCENARIOS:
                self.respond(json.dumps({"error": "unknown_fixture", "fixtures": list(SCENARIOS)}).encode(), status=400)
                release_busy()
                return
            if requested_fixture is not None and session is not None and requested_fixture != session.scenario:
                self.respond(b'{"error":"fixture_must_be_reset_first"}', status=409)
                release_busy()
                return

        def work():
            try:
                paused.clear()
                if parsed.path == "/api/reset":
                    session.reset(query.get("fixture", ["preferences"])[0], query.get("context", [None])[0])
                    emit({"kind": "reset", "timestamp": time.time()})
                else:
                    session.run(query.get("goal", ["Enable dark mode"])[0], emit, query.get("provider", ["jev"])[0], query.get("scenario", ["normal"])[0], paused.is_set,
                                request_id=query.get("request_id", [None])[0], reverse_options=query.get("reverse", ["false"])[0] == "true")
            except Exception as exc:
                emit({"kind": "error", "reason": str(exc), "timestamp": time.time()})
            finally:
                release_busy()
        threading.Thread(target=work, daemon=True).start()
        self.respond(b'{"status":"started"}', status=202)


def main():
    global session
    session = LiveSession()
    ThreadingHTTPServer(("0.0.0.0", 8787), Handler).serve_forever()


if __name__ == "__main__":
    main()
