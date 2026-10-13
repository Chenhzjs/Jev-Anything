"""Zero-dependency localhost workbench server."""

from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .engine import DemoEngine

ROOT = Path(__file__).parents[2] / "web"
EVENTS: list[dict] = []
LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_: object) -> None:
        return

    def send_bytes(self, content: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/events":
            with LOCK:
                body = json.dumps(EVENTS[-100:], ensure_ascii=False).encode()
            self.send_bytes(body, "application/json; charset=utf-8")
            return
        name = "index.html" if parsed.path == "/" else parsed.path.lstrip("/")
        path = ROOT / name
        if path.is_file() and ROOT in path.parents:
            content_type = "text/html; charset=utf-8" if path.suffix == ".html" else "text/css; charset=utf-8"
            self.send_bytes(path.read_bytes(), content_type)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/run":
            self.send_error(404)
            return
        query = parse_qs(parsed.query)
        goal = query.get("goal", ["打开设置并启用深色模式"])[0]
        stale = query.get("stale", ["0"])[0] == "1"
        engine = DemoEngine(live=False)
        with LOCK:
            EVENTS.clear()
        for event in engine.run(goal, force_stale=stale):
            with LOCK:
                EVENTS.append(event)
            time.sleep(0.18)
        self.send_bytes(b'{"status":"ok"}', "application/json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Jev Anything workbench: http://localhost:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()

