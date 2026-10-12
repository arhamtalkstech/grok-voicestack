"""Blocks HTTP tools and MCP servers from reaching private networks unless allowlisted."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

from voicestack.config import get_settings


class BlockedDestination(Exception):
    pass


def _allowlisted(host: str, addresses: list[str]) -> bool:
    for entry in get_settings().ssrf_allowlist:
        entry = entry.strip()
        if not entry:
            continue
        if entry == host or (entry.startswith("*.") and host.endswith(entry[1:])):
            return True
        try:
            net = ipaddress.ip_network(entry, strict=False)
        except ValueError:
            continue
        if any(ipaddress.ip_address(a) in net for a in addresses):
            return True
    return False


async def check_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise BlockedDestination(f"Only http(s) URLs are allowed, got {parsed.scheme!r}")
    host = parsed.hostname
    if not host:
        raise BlockedDestination("URL has no host")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise BlockedDestination(f"Cannot resolve {host}: {exc}") from exc
    addresses = sorted({info[4][0] for info in infos})
    if _allowlisted(host, addresses):
        return
    for addr in addresses:
        ip = ipaddress.ip_address(addr)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise BlockedDestination(f"{host} resolves to a private address ({addr}). Add it to SSRF_ALLOWLIST to allow it.")
