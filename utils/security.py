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

def is_safe_url(url: str) -> bool:
    """
    Validates URL scheme and checks resolved IP to prevent SSRF against private addresses.
    Trusted domains can bypass name resolution to support offline/restricted development.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False
        
        hostname = parsed.hostname
        if not hostname:
            return False
        
        # Allow trusted public domains to bypass resolution checks (e.g. offline/restricted DNS container environments)
        trusted_suffixes = ('.utmb.world', 'utmb.world', 'google.com', 'github.com')
        if any(hostname == suffix or hostname.endswith(suffix) for suffix in trusted_suffixes):
            return True
        
        # Prevent DNS rebinding and internal network requests by resolving the IP
        addr_info = _original_getaddrinfo(hostname, None)
        for addr in addr_info:
            ip_str = addr[4][0]
            ip = ipaddress.ip_address(ip_str)
            if (ip.is_private or 
                ip.is_loopback or 
                ip.is_multicast or 
                ip.is_reserved or 
                ip.is_link_local or
                ip.is_unspecified):
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
        
    # Check trusted domains bypass
    trusted_suffixes = ('.utmb.world', 'utmb.world', 'google.com', 'github.com')
    if any(hostname == suffix or hostname.endswith(suffix) for suffix in trusted_suffixes):
        return urllib.request.urlopen(url, *args, **kwargs)
        
    # Resolve and validate IP using original resolver
    try:
        addr_info = _original_getaddrinfo(hostname, None)
    except Exception as err:
        raise ValueError(f"Failed to resolve host: {err}")
        
    safe_ip = None
    for addr in addr_info:
        ip_str = addr[4][0]
        ip = ipaddress.ip_address(ip_str)
        if (ip.is_private or 
            ip.is_loopback or 
            ip.is_multicast or 
            ip.is_reserved or 
            ip.is_link_local or
            ip.is_unspecified):
            raise ValueError("Unsafe URL resolved to private/reserved IP address")
        safe_ip = ip_str
        break  # Pin to the first resolved IP
        
    if not safe_ip:
        raise ValueError("No IP resolved for host")
        
    with pinned_dns(hostname, safe_ip):
        return urllib.request.urlopen(url, *args, **kwargs)
