"""Security validator and sanitization engine for browser web interactions.

Guards against:
- SSRF (Server-Side Request Forgery) and loopback access.
- Cloud metadata endpoint probing.
- Private network RFC 1918 exposure.
- Non-HTTP(S) URI schemes (file://, javascript:, data:, etc.).
- Prompt injection in retrieved untrusted DOM content.
"""

import ipaddress
import re
import urllib.parse
from typing import Tuple
from app.core.exceptions import ValidationError


BLOCKED_HOSTNAMES = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "ip6-localhost",
    "ip6-loopback",
    "169.254.169.254",
    "metadata.google.internal",
    "instance-data",
}

BLOCKED_SCHEMES = {"file", "javascript", "data", "ftp", "gopher", "file-download", "about"}

# Indirect prompt injection markers to neutralize
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"<\s*system\s*>", re.IGNORECASE),
    re.compile(r"<\s*/\s*system\s*>", re.IGNORECASE),
    re.compile(r"\[\s*SYSTEM\s*\]", re.IGNORECASE),
    re.compile(r"\[\s*/\s*SYSTEM\s*\]", re.IGNORECASE),
    re.compile(r"\[\s*INST\s*\]", re.IGNORECASE),
    re.compile(r"\[\s*/\s*INST\s*\]", re.IGNORECASE),
    re.compile(r"<\|\s*im_start\s*\|>", re.IGNORECASE),
    re.compile(r"<\|\s*im_end\s*\|>", re.IGNORECASE),
    re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(?:all\s+)?prior\s+instructions", re.IGNORECASE),
]


class BrowserSecurityValidator:
    """Validator enforcing sandbox boundaries on web browsing actions."""

    @classmethod
    def validate_url(cls, url: str) -> str:
        """Validate target URL against SSRF, loopback, private IPs, and dangerous schemes.

        Returns normalized clean URL if safe, raises ValidationError if dangerous.
        """
        if not url or not isinstance(url, str):
            raise ValidationError("Target URL cannot be empty.")

        url_clean = url.strip()
        parsed = urllib.parse.urlparse(url_clean)

        scheme = (parsed.scheme or "").lower()
        if scheme not in ("http", "https"):
            raise ValidationError(
                f"Blocked dangerous URL scheme '{scheme}'. Only 'http' and 'https' protocols are permitted."
            )

        hostname = (parsed.hostname or "").lower()
        if not hostname:
            raise ValidationError("Target URL missing valid host name.")

        # Check explicitly blocked hostnames
        if hostname in BLOCKED_HOSTNAMES:
            raise ValidationError(
                f"Access to '{hostname}' is blocked by sandbox SSRF and loopback security policies."
            )

        # Check IP ranges
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_loopback:
                raise ValidationError(f"Loopback IP address '{hostname}' is blocked.")
            if ip.is_private:
                raise ValidationError(f"Private network address '{hostname}' is blocked.")
            if ip.is_link_local:
                raise ValidationError(f"Link-local address '{hostname}' is blocked.")
            if ip.is_reserved or ip.is_multicast or ip.is_unspecified:
                raise ValidationError(f"Reserved or multicast address '{hostname}' is blocked.")
        except ValueError:
            # Hostname is a domain name, not a numeric IP
            pass

        return url_clean

    @classmethod
    def sanitize_untrusted_text(cls, text: str) -> str:
        """Sanitize raw DOM text by escaping boundary tags and neutralizing injection markers."""
        if not text:
            return ""

        sanitized = text.replace("</untrusted_content>", "&lt;/untrusted_content&gt;")
        sanitized = sanitized.replace("<untrusted_content", "&lt;untrusted_content")

        for pattern in PROMPT_INJECTION_PATTERNS:
            sanitized = pattern.sub("[FILTERED_PROMPT_DIRECTIVE]", sanitized)

        return sanitized

    @classmethod
    def wrap_untrusted_content(cls, raw_text: str, source_url: str) -> str:
        """Wrap untrusted web text in security delimiter tags (PRD 17.3, 20.3)."""
        clean_text = cls.sanitize_untrusted_text(raw_text)
        safe_url = source_url.replace('"', "%22")
        return f'<untrusted_content source="{safe_url}">\n{clean_text}\n</untrusted_content>'
