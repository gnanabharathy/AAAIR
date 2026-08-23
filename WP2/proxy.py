from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.parse import unquote
import sys

class ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        target = unquote(self.path.lstrip('/'))
        if not target.startswith('http'):
            self.send_response(400)
            self.end_headers()
            return
        try:
            req = Request(target, headers={'User-Agent': 'Mozilla/5.0'})
            with urlopen(req, timeout=15) as resp:
                body = resp.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self.send_response(500)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(str(e).encode())

    def log_message(self, format, *args):
        print(f"  {args[0]} {args[1]}")

port = 8765
print(f"Proxy running at http://localhost:{port}")
HTTPServer(('', port), ProxyHandler).serve_forever()