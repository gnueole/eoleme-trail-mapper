import os
import socket
import ipaddress
import re
from urllib.parse import urlparse

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
        addr_info = socket.getaddrinfo(hostname, None)
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
