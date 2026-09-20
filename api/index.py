from http.server import BaseHTTPRequestHandler
from pathlib import Path


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Vercel's Python preset is currently using this conventional entrypoint
        # for the project root. Serve the dashboard HTML from the repository root.
        html_path = Path(__file__).resolve().parent.parent / "index.html"
        try:
            body = html_path.read_bytes()
        except OSError:
            body = b"<!doctype html><title>Zerqen</title><h1>Zerqen dashboard unavailable</h1>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def log_message(self, format, *args):
        return
