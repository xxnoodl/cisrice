import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit


class NetworkPolicyError(ValueError):
    pass


def canonical_url(value: str) -> str:
    try:
        url = urlsplit(value.strip())
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.username is not None
            or url.password is not None
            or url.port not in {None, 80 if url.scheme == "http" else 443}
            or any(ord(c) < 33 or ord(c) == 127 for c in value.strip())
            or len(value) > 2048
        ):
            raise ValueError
        host = url.hostname.encode("idna").decode("ascii").lower()
        if ":" in host:
            host = "[" + host + "]"
        return urlunsplit((url.scheme, host, url.path or "/", url.query, ""))
    except (ValueError, UnicodeError):
        raise NetworkPolicyError(
            "Use a public HTTP(S) URL without credentials or custom ports"
        ) from None


def public_addresses(host: str) -> list[str]:
    addresses = list(
        dict.fromkeys(
            str(row[4][0]) for row in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        )
    )
    if not addresses or any(
        not ipaddress.ip_address(address).is_global
        or ipaddress.ip_address(address).is_multicast
        or address in {"255.255.255.255"}
        or (
            isinstance(ipaddress.ip_address(address), ipaddress.IPv6Address)
            and (
                ipaddress.IPv6Address(address).sixtofour is not None
                or ipaddress.IPv6Address(address).teredo is not None
                or ipaddress.IPv6Address(address) in ipaddress.IPv6Network("64:ff9b::/96")
            )
        )
        for address in addresses
    ):
        raise NetworkPolicyError("Feed host must resolve exclusively to public unicast addresses")
    return addresses
