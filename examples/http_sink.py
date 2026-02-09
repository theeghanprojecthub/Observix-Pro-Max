from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(body)
        except Exception:
            payload = body
        print(payload)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")


def main() -> None:
    server = HTTPServer(("127.0.0.1", 9000), Handler)
    print("http sink listening on http://127.0.0.1:9000/ingest")
    server.serve_forever()


if __name__ == "__main__":
    main()
