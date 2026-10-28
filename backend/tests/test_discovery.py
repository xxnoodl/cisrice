import socket
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from app.modules.discovery.feeds import (
    FeedError,
    FeedItem,
    canonical_url,
    feed_url,
    parse_feed,
    public_addresses,
)
from app.modules.discovery.schemas import SourceCreate
from app.modules.discovery.scoring import score_item

RSS = b"""<rss version="2.0"><channel><title>Fixture</title>
<item><guid>one</guid><title>Technology update</title>
<link>https://example.org/story#one</link>
<category>Technology</category>
<description>Useful research</description></item>
<item><guid>two</guid><title>Technology update</title>
<link>https://example.org/other</link></item>
<item><title>Unsafe</title>
<link>javascript:alert(1)</link></item>
</channel></rss>"""
ATOM = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry>
<id>yt:video:test</id><title>Channel video</title>
<link rel="alternate" href="https://www.youtube.com/watch?v=test"/>
<published>2026-10-28T00:00:00Z</published></entry></feed>"""


def test_parse_rss_atom_and_unsafe_xml() -> None:
    items = parse_feed(RSS)
    assert len(items) == 2 and items[0].topics == ["Technology"]
    assert items[0].published_at is None
    assert parse_feed(ATOM)[0].identifier == "yt:video:test"
    for value in [
        b"<html/>",
        b"<rss>",
        b'<!DOCTYPE foo [<!ENTITY x SYSTEM "file:///etc/passwd">]><rss><channel>&x;</channel></rss>',
        b" " * (2 * 1024 * 1024 + 1),
    ]:
        with pytest.raises(FeedError):
            parse_feed(value)
    assert (
        len(
            parse_feed(
                b"<rss><channel>"
                + b"<item><title>x</title><link>https://example.org</link></item>" * 250
                + b"</channel></rss>"
            )
        )
        == 200
    )


def test_urls_and_dns_rebinding_restrictions() -> None:
    assert canonical_url("https://EXAMPLE.org:443/story#fragment") == "https://example.org/story"
    assert feed_url("youtube", "UC" + "a" * 22).startswith("https://www.youtube.com/xml/feeds/")
    for url in [
        "file:///etc/passwd",
        "https://user:secret@example.org",
        "https://example.org:8443/",
        "https://example.org/\r\nx",
        "http://example.org/feed",
    ]:
        with pytest.raises(FeedError):
            feed_url("rss", url)
    for address in [
        "127.0.0.1",
        "::1",
        "169.254.169.254",
        "192.168.1.2",
        "100.64.0.1",
        "224.0.0.1",
        "::ffff:127.0.0.1",
        "2002:7f00:1::",
        "64:ff9b::a00:1",
    ]:
        with (
            patch.object(
                socket,
                "getaddrinfo",
                return_value=[
                    (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
                    (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443)),
                ],
            ),
            pytest.raises(FeedError),
        ):
            public_addresses("example.org")


def test_scoring_missing_signals_and_configurable_weights() -> None:
    item = FeedItem("id", "https://example.org/", "Tech news", "", datetime.now(UTC), [])
    score, components = score_item(item, ["tech"], 1, True)
    assert score == 100
    assert components["shares"] is None and components["saves"] is None
    assert (
        score_item(item, ["other"], 1, True, {k: float(k == "relevance") for k in components})[0]
        == 0
    )
    with pytest.raises(ValueError):
        SourceCreate(
            name="a",
            kind="rss",
            address="https://example.org/",
            policy_note="Allowed",
            policy_confirmed=True,
            weights={"relevance": 100},
        )


def test_fetch_pins_tls_target_rejects_redirect_and_limits_body() -> None:
    from unittest.mock import MagicMock

    from app.modules.discovery.feeds import MAX_BYTES, fetch_feed

    transport = MagicMock()
    response = transport.getresponse.return_value
    response.status = 200
    response.getheader.return_value = "identity"
    response.read1.side_effect = [b"<rss><channel/></rss>", b""]
    with (
        patch("app.modules.discovery.feeds.public_addresses", return_value=["8.8.8.8"]),
        patch("app.modules.discovery.feeds.socket.create_connection") as connect,
        patch("app.modules.discovery.feeds.ssl.create_default_context") as tls,
        patch("app.modules.discovery.feeds.http.client.HTTPSConnection", return_value=transport),
    ):
        assert fetch_feed("https://example.org/feed") == b"<rss><channel/></rss>"
        connect.assert_called_once_with(("8.8.8.8", 443), timeout=8)
        assert tls.return_value.wrap_socket.call_args.kwargs["server_hostname"] == "example.org"
        response.status = 302
        with pytest.raises(FeedError, match="redirected"):
            fetch_feed("https://example.org/feed")
        response.status = 200
        response.read1.side_effect = [b"x" * (MAX_BYTES + 1)]
        with pytest.raises(FeedError, match="2 MiB"):
            fetch_feed("https://example.org/feed")
    assert transport.close.called


def test_score_unavailable_when_config_excludes_all_known_signals() -> None:
    item = FeedItem("id", "https://example.org/", "News", "", None, [])
    _, components = score_item(item, [], 0.5, True)
    weights = {key: float(key == "shares") for key in components}
    assert score_item(item, [], 0.5, True, weights)[0] is None
