"""URL validation to prevent SSRF and restrict outbound requests to safe targets."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeURLError(ValueError):
    """Raised when a URL targets an internal, private, or blocked host."""


_BLOCKED_HOSTS = frozenset(
    {
        "metadata.google.internal",
        "metadata.google",
    }
)

_BLOCKED_PATH_PREFIXES = (
    "/latest/meta-data",
    "/computeMetadata",
    "/metadata",
)

_ALLOWED_SCHEMES = frozenset({"http", "https"})


def validate_url(url: str) -> str:
    """Validate a URL is safe for outbound fetching.

    Blocks:
    - Non-HTTP(S) schemes (file://, ftp://, data:, etc.)
    - Private/internal IP ranges (127.x, 10.x, 172.16-31.x, 192.168.x, ::1, fe80::, etc.)
    - Cloud metadata endpoints (169.254.169.254, metadata.google.internal)
    - Link-local addresses

    Returns the validated URL string, or raises UnsafeURLError.
    """
    if not url or not url.strip():
        raise UnsafeURLError("URL is empty")

    parsed = urlparse(url)

    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeURLError(f"Scheme '{parsed.scheme}' is not allowed. Use http:// or https://.")

    hostname = parsed.hostname
    if not hostname:
        raise UnsafeURLError("URL has no hostname")

    hostname_lower = hostname.lower()
    if hostname_lower in _BLOCKED_HOSTS:
        raise UnsafeURLError(f"Host '{hostname}' is blocked (cloud metadata)")

    for prefix in _BLOCKED_PATH_PREFIXES:
        if parsed.path.startswith(prefix):
            raise UnsafeURLError(f"Path '{parsed.path}' is blocked (cloud metadata)")

    addr: ipaddress.IPv4Address | ipaddress.IPv6Address | None
    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        addr = _resolve_hostname(hostname)

    if addr is not None:
        _check_ip(addr, hostname)

    return url


def _resolve_hostname(hostname: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Resolve hostname to IP for validation. Returns None if resolution fails."""
    try:
        info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        if info:
            ip_str = info[0][4][0]
            return ipaddress.ip_address(ip_str)
    except (socket.gaierror, OSError, ValueError):
        pass
    return None


def _check_ip(
    addr: ipaddress.IPv4Address | ipaddress.IPv6Address,
    original_host: str,
) -> None:
    """Raise UnsafeURLError if the IP is private, loopback, or link-local."""
    if addr.is_loopback:
        raise UnsafeURLError(f"Host '{original_host}' resolves to loopback address {addr}")
    if addr.is_private:
        raise UnsafeURLError(f"Host '{original_host}' resolves to private address {addr}")
    if addr.is_link_local:
        raise UnsafeURLError(f"Host '{original_host}' resolves to link-local address {addr}")
    if addr.is_reserved:
        raise UnsafeURLError(f"Host '{original_host}' resolves to reserved address {addr}")
    if isinstance(addr, ipaddress.IPv4Address) and addr == ipaddress.ip_address("169.254.169.254"):
        raise UnsafeURLError(f"Host '{original_host}' resolves to cloud metadata endpoint {addr}")
