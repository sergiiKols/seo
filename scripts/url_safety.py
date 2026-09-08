#!/usr/bin/env python3
"""
Canonical URL safety module for claude-seo.

Centralizes SSRF protection, DNS rebinding mitigation, and DNS-pinned HTTP
fetching. Every script in this repository that accepts a user-supplied URL
MUST validate it through this module before issuing any network request.
"""

from __future__ import annotations

import ipaddress
import re
import socket
import threading
from contextlib import contextmanager
from typing import Iterator, Optional
from urllib.parse import urlparse

try:
    import requests
except ImportError as exc:
    raise RuntimeError(
        "scripts/url_safety.py requires the 'requests' package. "
        "Install with: pip install -r requirements.txt"
    ) from exc


__all__ = [
    "URLSafetyError",
    "is_safe_ip",
    "normalize_hostname",
    "validate_url",
    "validate_url_strict",
    "safe_requests_get",
    "safe_requests_head",
    "safe_requests_session",
    "make_safe_playwright_route_handler",
]


_IPV4_OBFUSCATED_RE = re.compile(
    r"^(?:0x[0-9a-f]+|[0-9]+)(?:\.(?:0x[0-9a-f]+|[0-9]+)){0,3}$",
    re.IGNORECASE,
)


_BLOCKED_HOSTNAMES: frozenset[str] = frozenset(
    {
        "localhost",
        "ip6-localhost",
        "ip6-loopback",
        "metadata.google.internal",
        "metadata.goog",
        "metadata",
        "metadata.azure.com",
        "metadata.ec2.internal",
        "metadata.oraclecloud.com",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "169.254.169.254",
        "fd00:ec2::254",
    }
)


class URLSafetyError(ValueError):
    """Raised when a URL fails SSRF safety checks."""


def _raw_authority(url: str) -> str:
    match = re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://([^/?#]*)", url)
    return match.group(1) if match else ""


def _reject_authority_confusion(url: str, parsed) -> None:
    authority = _raw_authority(url)
    authority_lower = authority.lower()
    url_lower = url.lower()

    if "\\" in authority or "%5c" in authority_lower:
        raise URLSafetyError("URL authority contains a backslash")
    if "%" in authority:
        raise URLSafetyError("URL authority contains percent-encoding")
    if parsed.username is not None or parsed.password is not None or "@" in authority:
        raise URLSafetyError("URL userinfo is not allowed")
    if "#@" in url or "%23@" in url_lower:
        raise URLSafetyError("URL fragment/userinfo confusion refused")


def is_safe_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_reserved
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
    )


def normalize_hostname(hostname: str) -> str:
    if not hostname:
        raise URLSafetyError("Empty hostname")

    h = hostname.lower().strip()
    if h.endswith(".") and not h.endswith(".."):
        h = h[:-1]

    if _IPV4_OBFUSCATED_RE.match(h):
        try:
            packed = socket.inet_aton(h)
        except OSError as exc:
            raise URLSafetyError(
                f"Malformed IPv4 obfuscation refused: {hostname!r} ({exc})"
            ) from exc
        h = socket.inet_ntoa(packed)
    return h


def validate_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        _reject_authority_confusion(url, parsed)
        if parsed.scheme not in ("http", "https"):
            return False
        if not parsed.hostname:
            return False
        hostname = normalize_hostname(parsed.hostname)
    except URLSafetyError:
        return False
    if hostname in _BLOCKED_HOSTNAMES:
        return False
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        return True
    return is_safe_ip(hostname)


def validate_url_strict(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    _reject_authority_confusion(url, parsed)
    if parsed.scheme not in ("http", "https"):
        raise URLSafetyError(f"Invalid URL scheme: {parsed.scheme!r}")
    if not parsed.hostname:
        raise URLSafetyError("URL has no hostname")

    hostname = normalize_hostname(parsed.hostname)
    if hostname in _BLOCKED_HOSTNAMES:
        raise URLSafetyError(f"Blocked hostname: {hostname}")

    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None

    if literal is not None:
        if not is_safe_ip(hostname):
            raise URLSafetyError(f"Blocked IP literal: {hostname}")
        return url, str(literal)

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addrinfo = socket.getaddrinfo(
            hostname,
            port,
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
        )
    except (socket.gaierror, UnicodeError) as exc:
        raise URLSafetyError(f"DNS resolution failed for {hostname}: {exc}") from exc

    resolved_ips = sorted({info[4][0] for info in addrinfo})
    if not resolved_ips:
        raise URLSafetyError(f"No A records for {hostname}")

    for ip_str in resolved_ips:
        if not is_safe_ip(ip_str):
            raise URLSafetyError(
                f"DNS rebinding refused: {hostname} resolves to "
                f"non-public IP {ip_str}"
            )

    pinned = resolved_ips[0]
    return url, pinned


_dns_patch_lock = threading.Lock()


@contextmanager
def _pin_dns(hostname: str, pinned_ip: str, port: int) -> Iterator[None]:
    if not _dns_patch_lock.acquire(blocking=False):
        raise URLSafetyError(
            "DNS-pinned fetch already in progress on another thread"
        )

    original_getaddrinfo = socket.getaddrinfo
    target = hostname.lower()

    def patched(host, requested_port, *args, **kwargs):
        if host and host.lower() == target:
            family = kwargs.get("family", args[0] if args else 0)
            if family in (0, socket.AF_UNSPEC, socket.AF_INET):
                return [(
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                    socket.IPPROTO_TCP,
                    "",
                    (pinned_ip, requested_port or port),
                )]
            raise socket.gaierror(
                socket.EAI_FAIL,
                f"url_safety: address family {family} refused for pinned IPv4 host {host}",
            )

        result = original_getaddrinfo(host, requested_port, *args, **kwargs)
        for info in result:
            sockaddr = info[4]
            if not sockaddr:
                continue
            ip_str = sockaddr[0]
            if not is_safe_ip(ip_str):
                raise socket.gaierror(
                    socket.EAI_FAIL,
                    f"url_safety: refused to resolve {host!r} to non-public IP {ip_str}",
                )
        return result

    socket.getaddrinfo = patched
    try:
        yield
    finally:
        socket.getaddrinfo = original_getaddrinfo
        _dns_patch_lock.release()


def safe_requests_get(url: str, *, timeout: int = 30, **kwargs) -> requests.Response:
    norm_url, pinned_ip = validate_url_strict(url)
    parsed = urlparse(norm_url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    assert parsed.hostname is not None
    with _pin_dns(parsed.hostname, pinned_ip, port):
        return requests.get(norm_url, timeout=timeout, **kwargs)


def safe_requests_head(url: str, *, timeout: int = 30, **kwargs) -> requests.Response:
    norm_url, pinned_ip = validate_url_strict(url)
    parsed = urlparse(norm_url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    assert parsed.hostname is not None
    with _pin_dns(parsed.hostname, pinned_ip, port):
        return requests.head(norm_url, timeout=timeout, **kwargs)


@contextmanager
def safe_requests_session(url: str) -> Iterator[requests.Session]:
    norm_url, pinned_ip = validate_url_strict(url)
    parsed = urlparse(norm_url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    assert parsed.hostname is not None
    session = requests.Session()
    with _pin_dns(parsed.hostname, pinned_ip, port):
        try:
            yield session
        finally:
            session.close()


def make_safe_playwright_route_handler(blocked_resource_types: Optional[set] = None):
    blocked = set(blocked_resource_types or ())

    def handler(route, request):
        try:
            if blocked and request.resource_type in blocked:
                route.abort()
                return

            parsed = urlparse(request.url)
            if parsed.scheme not in ("http", "https"):
                route.continue_()
                return
            host = parsed.hostname
            if not host:
                route.abort()
                return

            try:
                normalized = normalize_hostname(host)
            except URLSafetyError:
                route.abort()
                return

            if normalized in _BLOCKED_HOSTNAMES:
                route.abort()
                return

            try:
                addrinfo = socket.getaddrinfo(
                    normalized,
                    None,
                    family=socket.AF_UNSPEC,
                    type=socket.SOCK_STREAM,
                )
            except socket.gaierror:
                route.abort()
                return
            ips = {info[4][0] for info in addrinfo}
            if not ips or any(not is_safe_ip(ip) for ip in ips):
                route.abort()
                return
            route.continue_()
        except Exception:
            try:
                route.abort()
            except Exception:
                pass

    return handler
