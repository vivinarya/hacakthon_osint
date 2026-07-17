from __future__ import annotations
from src.config import STEP_CAP
from src.llm_client import LLMClient
from src.evidence_ledger import EvidenceLedger
from src.agent.planner import Planner
from src.agent.executor import Executor, _forward_message
from src.reporting import ReportGenerator

REFLECT_PROMPT = """You are an investigative agent. Here is your investigation question:
{query}

Here is what you have learned so far:
{evidence_summary}

Do you have sufficient evidence to produce a complete report? 
- If YES, respond with: {{"decision": "report", "reasoning": "..."}}
- If NO, respond with: {{"decision": "continue", "reasoning": "...", "follow_up": "specific follow-up question"}}"""

REPORT_PROMPT = """You are an investigative analyst writing a detailed narrative report from an evidence ledger.

Use only the evidence provided below. Do not invent facts. Write in plain text prose, not JSON.
Include:
- a concise executive summary
- a detailed narrative explaining the main themes and chronology
- explicit mention of uncertainty, missing evidence, and disputed points
- references to claim IDs like [c_001] when grounding factual statements

Evidence:
{evidence_json}
"""


class InvestigativeAgent:
    def __init__(self, llm: LLMClient, firecrawl_key: str | None = None):
        self.llm = llm
        self.ledger = EvidenceLedger()
        self.planner = Planner(llm)
        self.executor = Executor(llm, self.ledger, firecrawl_key=firecrawl_key)

    async def investigate(self, query: str) -> dict:
        normalized_query = self._normalize_query(query)
        plan = await self.planner.plan(normalized_query)

        if plan:
            batch = plan[:STEP_CAP]
            await self.executor.execute_plan(batch, parallel=True)

        return await self._generate_report(normalized_query)

    async def _generate_report(self, query: str) -> dict:
        evidence_json = self.ledger.to_dict()
        generator = ReportGenerator(self.llm)
        claims, contradictions = generator.prepare_ledger(self.ledger)

        detailed_analysis = ""
        if claims:
            digest = generator.build_evidence_digest(claims, contradictions)
            prompt = REPORT_PROMPT.format(query=query, evidence_json=digest[:12000])
            detailed_analysis = await self.llm.generate_text(prompt, max_tokens=2200)

        report_text, report_confidence = generator.generate_with_confidence(
            self.ledger,
            query,
            detailed_analysis=detailed_analysis,
        )

        return {
            "query": query,
            "report": report_text,
            "report_confidence": report_confidence,
            "ledger": self.ledger,
            "claim_count": len(self.ledger.claims),
            "source_count": len(self.ledger.sources),
            "evidence_json": evidence_json,
        }

    async def explain_claim(self, claim_id: str) -> dict | None:
        claim = self.ledger.get_claim(claim_id)
        if not claim:
            return None

        corroborating = [self.ledger.get_claim(cid) for cid in claim.corroborating_claim_ids]
        contradicting = [self.ledger.get_claim(cid) for cid in claim.contradicting_claim_ids]

        return {
            "claim": claim.text,
            "confidence": claim.confidence,
            "source_url": claim.source.source_url,
            "source_type": claim.source.source_type,
            "retrieval_tool": claim.source.retrieval_tool,
            "extraction_method": claim.extraction_method,
            "snippet": claim.source.snippet[:500] if claim.source.snippet else "",
            "corroborating_claims": [{"id": c.claim_id, "text": c.text, "source": c.source.source_url}
                                      for c in corroborating if c],
            "contradicting_claims": [{"id": c.claim_id, "text": c.text, "source": c.source.source_url}
                                      for c in contradicting if c],
            "reasoning_replay": self._build_reasoning_replay(claim),
        }

    def _build_reasoning_replay(self, claim) -> str:
        parts = [
            f"Step 1: The agent used the '{claim.source.retrieval_tool}' tool to retrieve information.",
            f"Step 2: Retrieved from: {claim.source.source_url}",
            f"Step 3: The '{claim.extraction_method}' method extracted this claim from the retrieved content.",
            f"Step 4: Confidence score of {claim.confidence:.2f} was assigned based on source reliability, corroboration, and recency.",
        ]
        if claim.corroborating_claim_ids:
            parts.append(f"Step 5: This claim is corroborated by {len(claim.corroborating_claim_ids)} other independent source(s).")
        if claim.contradicting_claim_ids:
            parts.append(f"Step 6: WARNING: This claim is contradicted by {len(claim.contradicting_claim_ids)} other source(s).")
        return "\n".join(parts)

    def _summarize_evidence(self) -> str:
        lines = []
        for cid, claim in self.ledger.claims.items():
            lines.append(f"[{cid}] {claim.text[:200]} (confidence: {claim.confidence:.2f}, source: {claim.source.source_url[:80]})")
        return "\n".join(lines) if lines else "No evidence gathered yet."

    @staticmethod
    def _normalize_query(query: str) -> str:
        cleaned = query.strip()
        lower = cleaned.lower()
        prefixes = (
            "investigate ",
            "research ",
            "look into ",
            "analyze ",
            "analyse ",
            "find information on ",
        )
        for prefix in prefixes:
            if lower.startswith(prefix):
                return cleaned[len(prefix):].strip()
        return cleaned

    def get_ledger(self) -> EvidenceLedger:
        return self.ledger
