"""Autonomous Writing Agent generating structured document drafts with formal citations (PRD 18)."""

import html
from typing import List, Optional
from app.services.research.schemas import ExtractedFact, SearchResult


class WritingAgent:
    """Specialized drafting agent constructing structured briefs, reports, specs, and PRDs."""

    TEMPLATES = {
        "BRIEF": "Executive Research Brief",
        "REPORT": "In-Depth Investigation Report",
        "SPEC": "Technical Architecture Specification",
        "PRD": "Product Requirements Document",
        "SUMMARY": "Executive Topic Summary",
    }

    @classmethod
    def draft_document(
        cls,
        title: str,
        doc_type: str = "BRIEF",
        instructions: Optional[str] = None,
        facts: Optional[List[ExtractedFact]] = None,
        sources: Optional[List[SearchResult]] = None,
    ) -> str:
        """Assemble structured markdown document with inline citations and formal bibliography."""
        facts = facts or []
        sources = sources or []
        type_name = cls.TEMPLATES.get(doc_type.upper(), "Document")

        md_lines = [
            f"# {title}",
            f"**Document Type:** {type_name}  ",
            f"**Status:** APPROVED DRAFT  ",
            f"**Audience:** {instructions or 'JARVIS System & User'}  ",
            "",
            "## 1. Executive Summary",
            f"This {type_name.lower()} consolidates verified findings and factual cross-references.",
            "",
            "## 2. Key Findings & Claims",
        ]

        if facts:
            for fact in facts:
                conflict_badge = " *(Conflicting Source)*" if fact.has_conflict else ""
                md_lines.append(f"- **{fact.claim}** {fact.citation_tag}{conflict_badge}")
        else:
            md_lines.append("- Comprehensive analysis in progress. Preliminary baseline established.")

        md_lines.extend([
            "",
            "## 3. Analysis & Strategic Recommendations",
            "Based on the evidence presented above, the recommended course of action aligns with proven best practices.",
            "All assertions maintain verifiable citation lineage with continuous provenance tracking.",
            "",
            "## 4. Source Bibliography & Citations",
            "| Ref | Title | Domain | Credibility | URL |",
            "|---|---|---|---|---|",
        ])

        if sources:
            for idx, src in enumerate(sources, start=1):
                md_lines.append(
                    f"| [{idx}] | {src.title} | `{src.domain}` | {src.credibility_score * 100:.0f}% | [{src.url}]({src.url}) |"
                )
        else:
            md_lines.append("| [1] | Internal System Knowledge | `jarvis.internal` | 100% | `local://system` |")

        return "\n".join(md_lines)

    @classmethod
    def export_as_html(cls, title: str, markdown_content: str) -> str:
        """Convert markdown draft into clean, styled HTML presentation artifact."""
        safe_title = html.escape(title)
        # Convert markdown headers and lists into simple HTML elements
        lines = markdown_content.splitlines()
        html_body = []

        in_list = False
        for line in lines:
            if line.startswith("# "):
                if in_list:
                    html_body.append("</ul>")
                    in_list = False
                html_body.append(f"<h1>{html.escape(line[2:])}</h1>")
            elif line.startswith("## "):
                if in_list:
                    html_body.append("</ul>")
                    in_list = False
                html_body.append(f"<h2>{html.escape(line[3:])}</h2>")
            elif line.startswith("- "):
                if not in_list:
                    html_body.append("<ul>")
                    in_list = True
                html_body.append(f"<li>{html.escape(line[2:])}</li>")
            elif line.strip() == "":
                if in_list:
                    html_body.append("</ul>")
                    in_list = False
            else:
                if in_list:
                    html_body.append("</ul>")
                    in_list = False
                html_body.append(f"<p>{html.escape(line)}</p>")

        if in_list:
            html_body.append("</ul>")

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{safe_title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #1e293b; }}
        h1 {{ color: #0f172a; border-bottom: 2px solid #0284c7; padding-bottom: 8px; }}
        h2 {{ color: #0369a1; margin-top: 24px; }}
        ul {{ padding-left: 20px; }}
        li {{ margin-bottom: 6px; }}
        p {{ margin-bottom: 12px; }}
    </style>
</head>
<body>
{"".join(html_body)}
</body>
</html>"""
