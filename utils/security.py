import os
import socket
import ipaddress
import re
import urllib.request
import threading
from urllib.parse import urlparse
from contextlib import contextmanager

_original_getaddrinfo = socket.getaddrinfo
_dns_local = threading.local()

def get_pinned_getaddrinfo(original_getaddrinfo):
    def custom_getaddrinfo(host, port, *args, **kwargs):
        pinned = getattr(_dns_local, 'pinned', None)
        if pinned and host in pinned:
            return original_getaddrinfo(pinned[host], port, *args, **kwargs)
        return original_getaddrinfo(host, port, *args, **kwargs)
    return custom_getaddrinfo

# Global monkey-patch for thread-safe DNS pinning
socket.getaddrinfo = get_pinned_getaddrinfo(socket.getaddrinfo)

@contextmanager
def pinned_dns(hostname: str, ip: str):
    if not hasattr(_dns_local, 'pinned'):
        _dns_local.pinned = {}
    _dns_local.pinned[hostname] = ip
    try:
        yield
    finally:
        if hostname in _dns_local.pinned:
            del _dns_local.pinned[hostname]

def get_version() -> str:
    """
    Reads version from public/version.js
    """
    try:
        version_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public", "js", "version.js")
        with open(version_path, "r", encoding="utf-8") as f:
            content = f.read()
            m = re.search(r"VERSION\s*=\s*['\"]([^'\"]+)['\"]", content)
            if m:
                return m.group(1)
    except Exception:
        pass
    return "1.0.0"

# Hosts allowed through when name resolution itself is unavailable — an
# offline or DNS-restricted development container. Matched as domains, never as
# raw string suffixes: "evilgoogle.com".endswith("google.com") is True, so the
# old suffix test handed the allow-list to anyone who registered such a name.
TRUSTED_DOMAINS = ('utmb.world', 'google.com', 'github.com')


def is_trusted_domain(hostname: str) -> bool:
    """True if hostname is one of TRUSTED_DOMAINS or a subdomain of one."""
    host = (hostname or "").lower().rstrip('.')
    return any(host == domain or host.endswith('.' + domain) for domain in TRUSTED_DOMAINS)


def _is_forbidden_ip(ip_str: str) -> bool:
    ip = ipaddress.ip_address(ip_str)
    return (ip.is_private or
            ip.is_loopback or
            ip.is_multicast or
            ip.is_reserved or
            ip.is_link_local or
            ip.is_unspecified)


def is_safe_url(url: str) -> bool:
    """
    Validates URL scheme and checks resolved IP to prevent SSRF against private addresses.

    Resolution is attempted for every host, trusted or not — a trusted name that
    resolves into the private range is still refused. The allow-list applies
    only when resolution is impossible (offline/restricted development), so it
    can no longer be used to skip the check on a host that does resolve.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        # Prevent DNS rebinding and internal network requests by resolving the IP
        try:
            addr_info = _original_getaddrinfo(hostname, None)
        except Exception:
            return is_trusted_domain(hostname)

        for addr in addr_info:
            if _is_forbidden_ip(addr[4][0]):
                return False
        return True
    except Exception:
        return False

def safe_urlopen(url, *args, **kwargs):
    """
    Acts as a wrapper for urllib.request.urlopen, ensuring the resolved IP is safe (SSRF protection)
    and pinning the connection to it to prevent DNS Rebinding (TOCTOU) attacks.
    """
    if isinstance(url, urllib.request.Request):
        url_str = url.full_url
    else:
        url_str = url

    parsed = urlparse(url_str)
    if parsed.scheme not in ('http', 'https'):
        raise ValueError("Invalid URL scheme")
    
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Invalid hostname")
        
    # Resolve and validate IP using original resolver. A trusted domain is only
    # exempt when resolution is impossible at all (offline/restricted dev
    # container) — never as a way to skip validation on a host that resolves.
    try:
        addr_info = _original_getaddrinfo(hostname, None)
    except Exception as err:
        if is_trusted_domain(hostname):
            return urllib.request.urlopen(url, *args, **kwargs)
        raise ValueError(f"Failed to resolve host: {err}")

    safe_ip = None
    for addr in addr_info:
        ip_str = addr[4][0]
        if _is_forbidden_ip(ip_str):
            raise ValueError("Unsafe URL resolved to private/reserved IP address")
        safe_ip = ip_str
        break  # Pin to the first resolved IP

    if not safe_ip:
        raise ValueError("No IP resolved for host")

    with pinned_dns(hostname, safe_ip):
        return urllib.request.urlopen(url, *args, **kwargs)
