import json
import os
import selectors
import subprocess
import sys
import time
from collections.abc import Callable
from urllib.parse import urlsplit

from app.core.network import canonical_url, public_addresses
from app.integrations.acquisition_proxy import metadata_proxy
from app.modules.acquisition.storage import MediaError


def read_metadata(process: subprocess.Popen[bytes], heartbeat: Callable[[int], None]) -> bytes:
    """Drain bounded stdout without unbounded memory or temporary-file buffering."""
    stream = process.stdout
    if stream is None:
        raise MediaError("extractor_output_unavailable")
    data = bytearray()
    deadline = time.monotonic() + 60
    with selectors.DefaultSelector() as selector:
        selector.register(stream, selectors.EVENT_READ)
        while True:
            heartbeat(2)
            if time.monotonic() > deadline:
                raise MediaError("metadata_limit_exceeded")
            for _ in selector.select(timeout=0.5):
                chunk = os.read(stream.fileno(), 65536)
                if not chunk:
                    if process.wait(timeout=5):
                        raise MediaError("extractor_unavailable_or_source_unsupported")
                    return bytes(data)
                data.extend(chunk)
                if len(data) > 4 * 1024 * 1024:
                    raise MediaError("metadata_limit_exceeded")


def inspect_media(url: str, heartbeat: Callable[[int], None]) -> str:
    """Resolve one progressive HTTPS video. Returned URL is ephemeral and never logged."""
    source = canonical_url(url)
    parsed = urlsplit(source)
    if parsed.scheme != "https":
        raise MediaError("https_required")
    try:
        public_addresses(parsed.hostname or "")
    except OSError:
        raise MediaError("network_unavailable") from None
    environment = {
        key: value
        for key, value in os.environ.items()
        if key in {"PATH", "SYSTEMROOT", "SSL_CERT_FILE", "SSL_CERT_DIR", "LANG"}
    }
    environment["YTDLP_NO_PLUGINS"] = "1"
    environment["PYTHONNOUSERSITE"] = "1"
    with metadata_proxy() as proxy:
        command = [
            sys.executable,
            "-m",
            "yt_dlp",
            "--ignore-config",
            "--compat-options",
            "no-certifi",
            "--no-plugin-dirs",
            "--no-js-runtimes",
            "--no-remote-components",
            "--no-geo-bypass",
            "--no-playlist",
            "--skip-download",
            "--dump-single-json",
            "--no-warnings",
            "--no-progress",
            "--no-cache-dir",
            "--socket-timeout",
            "8",
            "--retries",
            "0",
            "--extractor-retries",
            "0",
            "--proxy",
            proxy,
            "--format",
            "best[protocol=https]",
            "--",
            source,
        ]
        with subprocess.Popen(
            command,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        ) as process:
            try:
                output = read_metadata(process, heartbeat)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
        try:
            data = json.loads(output)
            if (
                data.get("has_drm")
                or data.get("is_live")
                or data.get("_type", "video") != "video"
                or data.get("requested_formats")
                or data.get("protocol") != "https"
            ):
                raise MediaError("unsupported_or_restricted_media")
            target = canonical_url(data["url"])
            if urlsplit(target).scheme != "https":
                raise MediaError("unsupported_media_protocol")
            return target
        except (KeyError, TypeError, ValueError):
            raise MediaError("unsupported_or_restricted_media") from None
