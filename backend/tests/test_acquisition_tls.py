"""Exercise the real resolver/proxy/HTTPS client against generated owned media.

Only test destination routing and certificate trust are substituted; no internet,
real account or third-party media is used.
"""

import shutil
import socket
import ssl
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from test_media_storage import clip as clip

from app.integrations.acquisition_http import download
from app.integrations.ytdlp import inspect_media


def test_real_resolver_proxy_and_https_transfer_of_owned_fixture(
    tmp_path: Path, clip: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not shutil.which("openssl"):
        pytest.skip("OpenSSL CLI required for isolated TLS fixture")
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-days",
            "1",
            "-subj",
            "/CN=fixture.example",
            "-addext",
            "subjectAltName=DNS:fixture.example",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
        timeout=20,
    )
    content = clip.read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_HEAD(self):
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()

        def do_GET(self):
            self.do_HEAD()
            self.wfile.write(content)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    original = socket.create_connection
    trust = ssl.create_default_context(cafile=str(cert))

    def connect(address, *args, **kwargs):
        if address == ("8.8.8.8", 443):
            address = ("127.0.0.1", server.server_port)
        return original(address, *args, **kwargs)

    original_popen = subprocess.Popen
    diagnostic = tmp_path / "resolver-diagnostic.log"
    diagnostic_stream = diagnostic.open("wb")

    def launch(*args, **kwargs):
        kwargs["stderr"] = diagnostic_stream
        return original_popen(*args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", launch)
    try:
        monkeypatch.setattr(socket, "create_connection", connect)
        for module in ["ytdlp", "acquisition_proxy", "acquisition_http"]:
            monkeypatch.setattr(
                "app.integrations." + module + ".public_addresses", lambda _: ["8.8.8.8"]
            )
        monkeypatch.setenv("SSL_CERT_FILE", str(cert))
        try:
            target = inspect_media("https://fixture.example/owned.mp4", lambda _: None)
        except Exception:
            diagnostic_stream.flush()
            raise AssertionError(diagnostic.read_text()) from None
        assert target == "https://fixture.example/owned.mp4"
        monkeypatch.setattr(
            "app.integrations.acquisition_http.ssl.create_default_context", lambda: trust
        )
        destination = tmp_path / "download.part"
        download(target, destination, 1024**2, lambda _: None, lambda _: None)
        assert destination.read_bytes() == content
    finally:
        diagnostic_stream.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
