"""Source quality evaluator and untrusted content sanitizer for research security (PRD 17.3, 17.4)."""

import re
from typing import List, Optional
from app.services.research.schemas import SearchResult


class SourceValidator:
    """Evaluates source credibility and sanitizes web content against prompt injection."""

    HIGH_CREDIBILITY_DOMAINS = {
        "gov", "edu", "nih.gov", "nist.gov", "csrc.nist.gov", "mayoclinic.org",
        "nvidia.com", "docs.nvidia.com", "deepmind.com", "research.deepmind.com",
        "owasp.org", "w3.org", "ietf.org", "who.int",
    }

    SUSPICIOUS_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions?", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.IGNORECASE),
        re.compile(r"(###\s*)?system\s*:\s*", re.IGNORECASE),
        re.compile(r"disregard\s+system\s+policy", re.IGNORECASE),
        re.compile(r"reveal\s+your\s+(secret|api\s*key|password|prompt)", re.IGNORECASE),
        re.compile(r"<script.*?>.*?</script>", re.IGNORECASE | re.DOTALL),
    ]

    @classmethod
    def evaluate_credibility(cls, domain: str, has_author: bool = False) -> float:
        """Score source credibility based on domain reputation and authority (PRD 17.4)."""
        clean_domain = domain.lower().strip()
        score = 0.70  # Baseline neutral web credibility

        # High authority TLDs and official institutions
        if any(clean_domain.endswith(f".{tld}") or clean_domain == tld for tld in ["gov", "edu", "org"]):
            score += 0.15

        if any(clean_domain == hd or clean_domain.endswith(f".{hd}") for hd in cls.HIGH_CREDIBILITY_DOMAINS):
            score += 0.10

        if has_author:
            score += 0.05

        return min(1.0, round(score, 2))

    @classmethod
    def score_credibility(cls, url_or_domain: str, author_or_publisher: Optional[str] = None) -> float:
        """Convenience method to extract domain and score credibility."""
        domain = url_or_domain.split("://")[-1].split("/")[0].split("?")[0]
        return cls.evaluate_credibility(domain, has_author=bool(author_or_publisher))

    @classmethod
    def sanitize_content(cls, raw_text: str) -> str:
        """Alias for sanitize_untrusted_content."""
        return cls.sanitize_untrusted_content(raw_text)

    @classmethod
    def sanitize_untrusted_content(cls, raw_text: str) -> str:
        """Strip dangerous prompt injection payloads and untrusted directives (PRD 17.3)."""
        if not raw_text:
            return ""

        sanitized = raw_text
        for pattern in cls.SUSPICIOUS_PATTERNS:
            sanitized = pattern.sub("[REDACTED_UNTRUSTED_INSTRUCTION]", sanitized)

        # Strip unprintable or ASCII control characters
        sanitized = "".join(ch for ch in sanitized if ch >= " " or ch in "\n\r\t")
        return sanitized.strip()

    @classmethod
    def validate_and_rank_sources(cls, sources: List[SearchResult]) -> List[SearchResult]:
        """Validate, sanitize, and sort sources by credibility."""
        processed = []
        for src in sources:
            cred = cls.evaluate_credibility(src.domain, has_author=bool(src.author_or_publisher))
            clean_snippet = cls.sanitize_untrusted_content(src.snippet)
            clean_title = cls.sanitize_untrusted_content(src.title)

            processed.append(
                SearchResult(
                    title=clean_title,
                    url=src.url,
                    domain=src.domain,
                    snippet=clean_snippet,
                    credibility_score=max(cred, src.credibility_score),
                    author_or_publisher=src.author_or_publisher,
                )
            )

        # Sort highest credibility first
        processed.sort(key=lambda x: x.credibility_score, reverse=True)
        return processed
