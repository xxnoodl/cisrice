import http.client
import socket
import ssl
import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from app.core.network import NetworkPolicyError, canonical_url, public_addresses
from app.modules.acquisition.storage import MediaError


def download(
    url: str,
    destination: Path,
    limit: int,
    heartbeat: Callable[[int], None],
    reserve: Callable[[int], None],
) -> None:
    """HTTPS only, DNS pinned per hop, bounded streaming; no cookies/proxies/credentials."""
    started = time.monotonic()
    for _ in range(4):
        normalized = canonical_url(url)
        parsed = urlsplit(normalized)
        if parsed.scheme != "https":
            raise NetworkPolicyError("https_required")
        host = parsed.hostname or ""
        connection = http.client.HTTPSConnection(host, timeout=8)
        try:
            address = public_addresses(host)[0]
            raw = socket.create_connection((address, 443), timeout=8)
            try:
                connection.sock = ssl.create_default_context().wrap_socket(
                    raw, server_hostname=host
                )
            except BaseException:
                raw.close()
                raise
            connection.request(
                "GET",
                parsed.path + ("?" + parsed.query if parsed.query else ""),
                headers={
                    "User-Agent": "Cisrice/0.1 (authorized media acquisition)",
                    "Accept-Encoding": "identity",
                },
            )
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                if not location:
                    raise MediaError("invalid_redirect")
                url = urljoin(normalized, location)
                heartbeat(5)
                continue
            if response.status != 200:
                try:
                    retry_after = int(response.getheader("Retry-After", "0"))
                except ValueError:
                    try:
                        retry_date = parsedate_to_datetime(response.getheader("Retry-After", ""))
                        retry_after = max(0, int((retry_date - datetime.now(UTC)).total_seconds()))
                    except (ValueError, TypeError, OverflowError):
                        retry_after = 0
                if retry_after > 86400:
                    raise MediaError("source_rate_limit_requires_manual_wait")
                raise MediaError("source_http_" + str(response.status), retry_after)
            if response.getheader("Content-Encoding", "identity").lower() != "identity":
                raise MediaError("compressed_media_not_supported")
            try:
                length = int(response.getheader("Content-Length", "0"))
            except ValueError:
                raise MediaError("invalid_content_length") from None
            if length < 0 or length > limit:
                raise MediaError("media_size_limit")
            reserve(length or min(limit, 1024 * 1024))
            size, last_heartbeat = 0, 0.0
            with destination.open("xb") as handle:
                while True:
                    if time.monotonic() - started > 300:
                        raise MediaError("download_timeout")
                    chunk = response.read1(min(65536, limit + 1 - size))
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > limit:
                        raise MediaError("media_size_limit")
                    reserve(len(chunk))
                    handle.write(chunk)
                    if time.monotonic() - last_heartbeat > 1:
                        heartbeat(min(80, 5 + int(75 * size / length)) if length else 10)
                        last_heartbeat = time.monotonic()
                handle.flush()
            if size == 0 or (length and length != size):
                raise MediaError("partial_download")
            heartbeat(80)
            return
        except (OSError, http.client.HTTPException):
            raise MediaError("network_unavailable") from None
        finally:
            connection.close()
    raise MediaError("too_many_redirects")
