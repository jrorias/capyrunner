"""Tiny local webhook so other tools can push notifications.

POST http://127.0.0.1:<port>/notify
     JSON: {"title": "...", "body": "...", "source": "..."}
     or form/plain text body (used as title)
Optional header X-Token: <token> when a token is set.
GET  /health -> ok
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from PySide6.QtCore import QObject, Signal


class WebhookBridge(QObject):
    received = Signal(str, str, str)   # title, body, source (delivered on GUI thread)


class WebhookServer:
    def __init__(self, bridge: WebhookBridge):
        self.bridge = bridge
        self.httpd: ThreadingHTTPServer | None = None
        self.error: str | None = None

    def start(self, port: int, token: str = "") -> bool:
        self.stop()
        bridge = self.bridge

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # keep stdout quiet
                pass

            def _reply(self, code: int, msg: str):
                data = msg.encode()
                self.send_response(code)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self._reply(200 if self.path == "/health" else 404, "ok" if self.path == "/health" else "not found")

            def do_POST(self):
                if self.path.rstrip("/") != "/notify":
                    return self._reply(404, "not found")
                if token and self.headers.get("X-Token") != token:
                    return self._reply(401, "bad token")
                length = min(int(self.headers.get("Content-Length") or 0), 64_000)
                raw = self.rfile.read(length).decode("utf-8", "replace")
                ctype = self.headers.get("Content-Type", "")
                title, body, source = "", "", "webhook"
                try:
                    if "json" in ctype or raw.lstrip().startswith("{"):
                        d = json.loads(raw or "{}")
                        title, body = str(d.get("title", "")), str(d.get("body", d.get("message", "")))
                        source = str(d.get("source", source))
                    elif "form" in ctype:
                        q = parse_qs(raw)
                        title = q.get("title", [""])[0]
                        body = q.get("body", [""])[0]
                        source = q.get("source", [source])[0]
                    else:
                        title = raw.strip()
                except ValueError:
                    return self._reply(400, "invalid json")
                if not title:
                    return self._reply(400, "title required")
                bridge.received.emit(title[:200], body[:2000], source[:40])
                self._reply(200, "ok")

        try:
            self.httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        except OSError as e:
            self.error = f"Webhook could not start on port {port}: {e}"
            self.httpd = None
            return False
        self.error = None
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        return True

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
