"""De designpreview serveren zonder cache, want Chrome houdt modules anders vast.

    python tools/serve.py            # http://127.0.0.1:8899/preview.html
    python tools/serve.py 9000       # op een andere poort

`preview.html` staat in `.gitignore` en hoort niet in de repo: het is een lokaal
harnas dat de serverkant nabootst, geen onderdeel van wat de klant installeert.
"""

import functools
import http.server
import pathlib
import socketserver
import sys

MAP = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "domotiapp_coach" / "frontend"
POORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8899


class Geen(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()

    def log_message(self, *a):
        pass


socketserver.TCPServer.allow_reuse_address = True
print(f"http://127.0.0.1:{POORT}/preview.html   (map: {MAP})")
if not (MAP / "preview.html").exists():
    print("let op: preview.html staat er niet; die is lokaal en niet in de repo.")
with socketserver.TCPServer(("127.0.0.1", POORT), functools.partial(Geen, directory=str(MAP))) as srv:
    srv.serve_forever()
