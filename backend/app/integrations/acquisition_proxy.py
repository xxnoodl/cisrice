"""Loopback CONNECT proxy for the metadata resolver, with pinned public destinations."""

import select
import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import cast
from urllib.parse import urlsplit

from app.core.network import NetworkPolicyError, canonical_url, public_addresses


class Proxy(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 8

    def __init__(self, address: tuple[str, int], handler: type[BaseHTTPRequestHandler]) -> None:
        self.guard = threading.Lock()
        self.remaining = 20
        super().__init__(address, handler)


class Tunnel(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        # Extracted/signed URLs and HTTP headers must never enter logs.
        pass

    def do_CONNECT(self) -> None:
        upstream = None
        try:
            self.connection.settimeout(8)
            server = cast(Proxy, self.server)
            with server.guard:
                if server.remaining <= 0:
                    raise NetworkPolicyError("proxy_request_limit")
                server.remaining -= 1
            if len(self.path) > 2048:
                raise NetworkPolicyError("proxy_target_too_long")
            target = urlsplit(canonical_url("https://" + self.path))
            host = target.hostname or ""
            if target.path != "/" or target.query:
                raise NetworkPolicyError("invalid_proxy_target")
            upstream = socket.create_connection((public_addresses(host)[0], 443), timeout=8)
            self.send_response(200)
            self.end_headers()
            transferred = 0
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline and transferred <= 8 * 1024 * 1024:
                ready, _, _ = select.select([self.connection, upstream], [], [], 1)
                for source in ready:
                    chunk = source.recv(65536)
                    if not chunk:
                        return
                    transferred += len(chunk)
                    (upstream if source is self.connection else self.connection).sendall(chunk)
        except (OSError, ValueError):
            # Suppress exception details (they can contain provider-signed URLs).
            self.close_connection = True
        finally:
            if upstream is not None:
                upstream.close()


@contextmanager
def metadata_proxy() -> Iterator[str]:
    server = Proxy(("127.0.0.1", 0), Tunnel)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:" + str(server.server_port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
