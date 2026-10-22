"""Recebe um PNG por POST (data URL) e grava na pasta do teste. So para a captura do E.9."""
import base64, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
PASTA = Path(__file__).resolve().parent
class R(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*"); self.send_header("Access-Control-Allow-Headers", "*")
    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()
    def do_POST(self):
        nome = Path(self.path.strip("/") or "captura.png").name
        corpo = self.rfile.read(int(self.headers["Content-Length"])).decode()
        (PASTA / nome).write_bytes(base64.b64decode(corpo.split(",", 1)[1]))
        self.send_response(200); self._cors(); self.end_headers(); self.wfile.write(b"ok")
HTTPServer(("127.0.0.1", 8799), R).serve_forever()
