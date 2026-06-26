from __future__ import annotations

from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class DiagnosticHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = (
            "OK from Process Project diagnostic server\n"
            f"remote={self.client_address[0]}:{self.client_address[1]}\n"
            f"path={self.path}\n"
            f"time={datetime.now().isoformat()}\n"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        print(
            f"{datetime.now().isoformat()} {self.client_address[0]}:"
            f"{self.client_address[1]} {fmt % args}",
            flush=True,
        )


def main() -> None:
    ThreadingHTTPServer(("0.0.0.0", 8000), DiagnosticHandler).serve_forever()


if __name__ == "__main__":
    main()
