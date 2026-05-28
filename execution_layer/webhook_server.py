"""
Lightweight webhook server that receives pipeline results and serves them to the dashboard.
The pipeline POSTs to /update, the dashboard GETs /markets (or uses polling).

Runs on localhost — not exposed externally.
"""
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

logger = logging.getLogger(__name__)

_latest_data: list[dict] = []
_lock = threading.Lock()


def get_latest_markets() -> list[dict]:
    with _lock:
        return list(_latest_data)


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/update":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
                with _lock:
                    global _latest_data
                    _latest_data = data
                logger.info(f"Webhook received {len(data)} market updates.")
                self._respond(200, {"status": "ok", "markets": len(data)})
            except json.JSONDecodeError as e:
                self._respond(400, {"error": str(e)})
        else:
            self._respond(404, {"error": "not found"})

    def do_GET(self):
        if self.path == "/markets":
            self._respond(200, get_latest_markets())
        elif self.path == "/health":
            self._respond(200, {"status": "running"})
        else:
            self._respond(404, {"error": "not found"})

    def _respond(self, code: int, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        logger.debug(f"[webhook] {format % args}")


def start_webhook_server(port: int = 8765) -> HTTPServer:
    """Starts the webhook server in a background thread. Returns the server object."""
    server = HTTPServer(("localhost", port), WebhookHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Webhook server running on localhost:{port}")
    return server


if __name__ == "__main__":
    from config.settings import WEBHOOK_PORT
    logging.basicConfig(level=logging.INFO)
    srv = start_webhook_server(WEBHOOK_PORT)
    logger.info(f"Webhook server started on port {WEBHOOK_PORT}. Press Ctrl+C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
