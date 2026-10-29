"""Bounded feed adapter. No embedded resource is fetched."""

import hashlib
import http.client
import re
import socket
import ssl
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from xml.etree.ElementTree import Element, ParseError

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import fromstring

from app.core.network import NetworkPolicyError as FeedError
from app.core.network import canonical_url, public_addresses

MAX_BYTES = 2 * 1024 * 1024
ATOM = "{http://www.w3.org/2005/Atom}"


def feed_url(kind: str, value: str) -> str:
    if kind == "youtube":
        if not re.fullmatch(r"UC[A-Za-z0-9_-]{22}", value):
            raise FeedError("YouTube requires a channel ID starting with UC (24 characters)")
        return "https://www.youtube.com/xml/feeds/videos.xml?channel_id=" + value
    result = canonical_url(value)
    if not result.startswith("https://"):
        raise FeedError("Feed requests require HTTPS")
    return result


def fetch_feed(value: str) -> bytes:
    """Pin DNS resolution; TLS still verifies the original hostname. No proxy/redirect."""
    url = urlsplit(feed_url("rss", value))
    host = url.hostname or ""
    connection = http.client.HTTPSConnection(host, timeout=8)
    try:
        addresses = public_addresses(host)
        raw = socket.create_connection((addresses[0], 443), timeout=8)
        try:
            connection.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
        except BaseException:
            raw.close()
            raise
        connection.request(
            "GET",
            url.path + ("?" + url.query if url.query else ""),
            headers={
                "User-Agent": "Cisrice/0.1 (user-selected feed research)",
                "Accept-Encoding": "identity",
            },
        )
        response = connection.getresponse()
        if 300 <= response.status < 400:
            raise FeedError("Feed redirected; register the publisher's final HTTPS feed URL")
        if response.status != 200:
            raise FeedError(f"Feed returned HTTP {response.status}; check source access and policy")
        if response.getheader("Content-Encoding", "identity").lower() != "identity":
            raise FeedError("Compressed feed responses are unsupported")
        chunks: list[bytes] = []
        size = 0
        deadline = time.monotonic() + 15
        while True:
            if time.monotonic() > deadline:
                raise FeedError("Feed transfer exceeded its time budget")
            chunk = response.read1(min(65536, MAX_BYTES + 1 - size))
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
            size += len(chunk)
            if size > MAX_BYTES:
                raise FeedError("Feed exceeds the 2 MiB limit")
    except (OSError, http.client.HTTPException):
        raise FeedError("Feed connection failed; check connectivity and retry later") from None
    finally:
        connection.close()


@dataclass(frozen=True)
class FeedItem:
    identifier: str
    url: str
    title: str
    summary: str
    published_at: datetime | None
    topics: list[str]


def date(value: str) -> datetime | None:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            result = parsedate_to_datetime(value)
        except (ValueError, TypeError, OverflowError):
            return None
    try:
        return result.astimezone(UTC) if result.tzinfo else None
    except (OverflowError, ValueError):
        return None


def content(node: Element, name: str) -> str:
    return (node.findtext(name) or "").strip()


def parse_feed(data: bytes) -> list[FeedItem]:
    if len(data) > MAX_BYTES:
        raise FeedError("Feed exceeds the 2 MiB limit")
    try:
        root = fromstring(data, forbid_dtd=True)
    except (ParseError, DefusedXmlException, LookupError):
        raise FeedError("Invalid or unsafe feed XML") from None
    atom = root.tag == ATOM + "feed"
    if not atom and (root.tag != "rss" or root.find("channel") is None):
        raise FeedError("Supported formats are RSS 2.0 and Atom")
    result = []
    nodes = root.findall(ATOM + "entry" if atom else "channel/item")
    for node in nodes[:200]:
        prefix = ATOM if atom else ""
        link = content(node, "link")
        if atom:
            link = next(
                (
                    x.get("href", "")
                    for x in node.findall(ATOM + "link")
                    if x.get("rel", "alternate") == "alternate"
                ),
                "",
            )
        try:
            canonical_url(link)
        except FeedError:
            continue
        title = content(node, prefix + "title")[:1000]
        if not title:
            continue
        topics = [
            x.get("term", "") if atom else (x.text or "") for x in node.findall(prefix + "category")
        ]
        result.append(
            FeedItem(
                identifier=content(node, prefix + ("id" if atom else "guid"))[:2048] or link,
                url=link,
                title=title,
                summary=content(node, prefix + ("summary" if atom else "description"))[:4000],
                published_at=date(content(node, prefix + ("published" if atom else "pubDate"))),
                topics=[x.strip()[:100] for x in topics[:10] if x.strip()],
            )
        )
    return result


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
