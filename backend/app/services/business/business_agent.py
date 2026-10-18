"""Business & Productivity Agent coordinator enforcing scope boundaries and analytical pipelines."""

from typing import Any, Dict, List, Optional, Tuple
from app.contracts.common import PrivacyScope
from app.contracts.privacy import PrivacyPolicyEnforcer
from app.services.business.engines import (
    BusinessReportGenerator,
    CompetitorAnalysisEngine,
    LeadResearchEngine,
)


class BusinessAgent:
    """Agent orchestrating lead generation, competitor intelligence, and executive reporting."""

    def __init__(self):
        self._leads = LeadResearchEngine()
        self._competitors = CompetitorAnalysisEngine()
        self._reports = BusinessReportGenerator()
        self._enforcer = PrivacyPolicyEnforcer()

    def verify_business_scope_isolation(self, target_scope: PrivacyScope) -> bool:
        """Enforce strict firewall preventing business data from leaking into incompatible scopes."""
        return self._enforcer.is_scope_compatible(
            source_scope=PrivacyScope.BUSINESS,
            target_scope=target_scope,
        )

    def research_and_score_lead(
        self,
        company_name: str,
        industry: str,
        website: Optional[str] = None,
        contact_email: Optional[str] = None,
        auto_enrich: bool = True,
        custom_notes: Optional[str] = None,
    ) -> Tuple[int, str]:
        """Compute lead fit score and assemble firmographic intelligence."""
        score = self._leads.calculate_lead_score(
            company_name=company_name,
            website=website,
            contact_email=contact_email,
            industry=industry,
        )

        notes = custom_notes or ""
        if auto_enrich:
            enriched = self._leads.enrich_lead_data(
                company_name=company_name,
                industry=industry,
                website=website,
            )
            notes = f"{notes}\n\n{enriched}".strip() if notes else enriched

        return score, notes

    def analyze_competitor_profile(
        self,
        name: str,
        website: str,
        market_segment: str,
        initial_strengths: Optional[List[str]] = None,
        initial_weaknesses: Optional[List[str]] = None,
        initial_pricing: Optional[str] = None,
        auto_analyze: bool = True,
    ) -> Tuple[List[str], List[str], Optional[str], str]:
        """Generate comprehensive competitor threat analysis."""
        strengths = initial_strengths or []
        weaknesses = initial_weaknesses or []
        pricing = initial_pricing
        threat_level = "MEDIUM"

        if auto_analyze:
            gen_s, gen_w, gen_p, gen_t = self._competitors.analyze_competitor(
                name=name,
                website=website,
                market_segment=market_segment,
            )
            strengths = list(set(strengths + gen_s))
            weaknesses = list(set(weaknesses + gen_w))
            pricing = pricing or gen_p
            threat_level = gen_t

        return strengths, weaknesses, pricing, threat_level

    def generate_executive_report(
        self,
        title: str,
        report_type: str,
        target_companies: Optional[List[str]] = None,
        key_objectives: Optional[str] = None,
    ) -> Tuple[str, str, List[str]]:
        """Generate formatted executive business intelligence report."""
        return self._reports.compile_report(
            title=title,
            report_type=report_type,
            target_companies=target_companies,
            key_objectives=key_objectives,
        )
