from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.network import NetworkPolicyError
from app.integrations.acquisition_http import download
from app.integrations.ytdlp import inspect_media
from app.modules.acquisition.storage import MediaError


def test_bounded_download_and_private_redirect_denied(tmp_path: Path) -> None:
    transport = MagicMock()
    response = transport.getresponse.return_value
    response.status = 200
    response.getheader.side_effect = lambda key, default=None: {
        "Content-Length": "3",
        "Content-Encoding": "identity",
    }.get(key, default)
    response.read1.side_effect = [b"abc", b""]
    with (
        patch("app.integrations.acquisition_http.public_addresses", return_value=["8.8.8.8"]),
        patch("app.integrations.acquisition_http.socket.create_connection") as connect,
        patch("app.integrations.acquisition_http.ssl.create_default_context"),
        patch(
            "app.integrations.acquisition_http.http.client.HTTPSConnection", return_value=transport
        ),
    ):
        download(
            "https://example.org/clip", tmp_path / "source", 1024, lambda _: None, lambda _: None
        )
        assert (tmp_path / "source").read_bytes() == b"abc"
        connect.assert_called_once_with(("8.8.8.8", 443), timeout=8)
    response.status = 302
    response.getheader.side_effect = lambda key, default=None: (
        "https://127.0.0.1/private" if key == "Location" else default
    )
    with (
        patch(
            "app.integrations.acquisition_http.public_addresses",
            side_effect=[["8.8.8.8"], NetworkPolicyError("private address")],
        ),
        patch("app.integrations.acquisition_http.socket.create_connection") as connect,
        patch("app.integrations.acquisition_http.ssl.create_default_context"),
        patch(
            "app.integrations.acquisition_http.http.client.HTTPSConnection", return_value=transport
        ),
    ):
        with pytest.raises(NetworkPolicyError):
            download(
                "https://example.org/clip",
                tmp_path / "blocked",
                1024,
                lambda _: None,
                lambda _: None,
            )
        assert connect.call_count == 1


def test_partial_download_and_size_limit(tmp_path: Path) -> None:
    transport = MagicMock()
    response = transport.getresponse.return_value
    response.status = 200
    response.getheader.side_effect = lambda key, default=None: (
        "10" if key == "Content-Length" else default
    )
    response.read1.side_effect = [b"abc", b""]
    with (
        patch("app.integrations.acquisition_http.public_addresses", return_value=["8.8.8.8"]),
        patch("app.integrations.acquisition_http.socket.create_connection"),
        patch("app.integrations.acquisition_http.ssl.create_default_context"),
        patch(
            "app.integrations.acquisition_http.http.client.HTTPSConnection", return_value=transport
        ),
    ):
        with pytest.raises(MediaError, match="partial_download"):
            download(
                "https://example.org/clip",
                tmp_path / "partial",
                100,
                lambda _: None,
                lambda _: None,
            )
        with pytest.raises(MediaError, match="size_limit"):
            download(
                "https://example.org/clip", tmp_path / "large", 5, lambda _: None, lambda _: None
            )


def test_ytdlp_resolver_arguments_and_drm_rejection() -> None:
    import json

    commands: list[list[str]] = []
    metadata = {"url": "https://example.org/video.mp4?temporary=signed", "protocol": "https"}

    def launch(command: list[str], **kwargs: object) -> MagicMock:
        commands.append(command)
        reader, writer = __import__("os").pipe()
        __import__("os").write(writer, json.dumps(metadata).encode())
        __import__("os").close(writer)
        process = MagicMock()
        process.stdout = __import__("os").fdopen(reader, "rb")
        process.poll.return_value = 0
        process.wait.return_value = 0
        process.__exit__.side_effect = lambda *args: process.stdout.close()
        process.returncode = 0
        process.__enter__.return_value = process
        return process

    @contextmanager
    def proxy():
        yield "http://127.0.0.1:12345"

    with (
        patch("app.integrations.ytdlp.subprocess.Popen", side_effect=launch),
        patch("app.integrations.ytdlp.metadata_proxy", proxy),
        patch("app.integrations.ytdlp.public_addresses", return_value=["8.8.8.8"]),
    ):
        assert inspect_media("https://example.org/watch", lambda _: None).startswith(
            "https://example.org/video.mp4"
        )
        assert commands[0][-2:] == ["--", "https://example.org/watch"]
        assert all(
            flag in commands[0]
            for flag in [
                "--ignore-config",
                "--no-geo-bypass",
                "--no-plugin-dirs",
                "--no-js-runtimes",
                "--no-remote-components",
                "--proxy",
            ]
        )
        metadata["has_drm"] = True
        with pytest.raises(MediaError, match="restricted"):
            inspect_media("https://example.org/watch", lambda _: None)
