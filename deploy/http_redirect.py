"""
v8.1: HTTP→HTTPS редирект на 8082 порту.
Запускается вторым процессом (systemd unit bit-technolog-http-redirect).
Принимает HTTP на 8082, делает 301 redirect на https://<host>:8081<path>

Production: 217.114.7.5
- uvicorn (https) на 8081
- http_redirect (http) на 8082 → 301 → https://...:8081
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse

class RedirectHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        host = self.headers.get("Host", "217.114.7.5:8082")
        # Убираем порт из host если есть
        if ":" in host:
            host = host.split(":")[0]
        # Build https URL
        new_url = f"https://{host}:8081{self.path}"
        self.send_response(301)
        self.send_header("Location", new_url)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        # POST тоже редиректим (на 308 = Permanent + method)
        host = self.headers.get("Host", "217.114.7.5:8082")
        if ":" in host:
            host = host.split(":")[0]
        new_url = f"https://{host}:8081{self.path}"
        self.send_response(308)  # Permanent, preserves method
        self.send_header("Location", new_url)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format, *args):
        pass  # suppress access log

if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8082), RedirectHandler).serve_forever()
