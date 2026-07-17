from __future__ import annotations
import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from src.llm_client import LLMClient
from src.agent.react_loop import InvestigativeAgent
from src.reporting import ReportGenerator, EvidenceExplainer
from src.verification import ScoringOrchestrator, ContradictionDetector
from src.config import OPENAI_API_KEY, FIRECRAWL_API_KEY

app = FastAPI(title="OSINT Investigative Agent API")
_last_ledger = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    query: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/status")
async def status():
    return {
        "status": "ok",
        "has_bazaarlink": bool(OPENAI_API_KEY),
        "has_firecrawl": bool(FIRECRAWL_API_KEY)
    }


@app.post("/api/investigate")
async def investigate(
    req: QueryRequest,
    x_bazaarlink_key: str | None = Header(None),
    x_firecrawl_key: str | None = Header(None)
):
    global _last_ledger

    # API key validation — fallback to env variables if headers not provided
    bazaarlink_key = x_bazaarlink_key or OPENAI_API_KEY
    firecrawl_key = x_firecrawl_key or FIRECRAWL_API_KEY

    if not bazaarlink_key:
        raise HTTPException(
            status_code=401,
            detail="BazaarLink API key is required. Please set it in the configuration."
        )
    if not firecrawl_key:
        raise HTTPException(
            status_code=401,
            detail="Firecrawl API key is required. Please set it in the configuration."
        )

    llm = LLMClient(api_key=bazaarlink_key)
    agent = InvestigativeAgent(llm, firecrawl_key=firecrawl_key)
    result = await agent.investigate(req.query)

    ledger = result["ledger"]

    # ── Multi-Agent Scoring Pipeline ─────────────────────────────────────────
    # ScoringOrchestrator internally:
    #   1. Runs CrossReferencer  (builds corroboration links)
    #   2. Phase 1 parallel: SourceTagger + Temporal + NetworkGraph
    #   3. Phase 2 serial:   Adversarial (needs graph from Phase 1)
    #   4. Applies geometric CS = (SA×TF)×(CC×NI)×100 to every claim
    orchestrator = ScoringOrchestrator()
    orchestrator.score_all(ledger)

    # ── Contradiction detection (uses updated scores) ─────────────────────────
    all_claims = ledger.get_all_claims()
    contradictions = ContradictionDetector().find_contradictions(ledger)

    # ── Serialise claims with full scoring breakdown ──────────────────────────
    claims_out = []
    for c in sorted(all_claims, key=lambda x: x.confidence_raw, reverse=True):
        claims_out.append({
            # Core
            "id":         c.claim_id,
            "text":       c.text,

            # New geometric scoring
            "confidence_raw":   round(c.confidence_raw, 1),   # 0–100
            "confidence":       round(c.confidence, 4),        # 0.0–1.0 (backwards compat)
            "confidence_state": c.confidence_state,            # logic state string

            # Component breakdown — for the frontend score bar
            "score_breakdown": {
                "source_authority":      round(c.source_authority, 3),
                "temporal_factor":       round(c.temporal_factor, 3),
                "corroboration_score":   round(c.corroboration_score, 3),
                "network_independence":  round(c.network_independence, 3),
            },

            # Temporal metadata
            "claim_type":   c.claim_type,
            "decay_lambda": c.decay_lambda,

            # Echo chamber flag
            "echo_chamber": c.echo_chamber,

            # Scoring reasoning (per-agent notes)
            "scoring_notes": c.scoring_notes,

            # Source info
            "source": {
                "source_type":    c.source.source_type,
                "url":            c.source.source_url,    # ← used by SourceBadge
                "source_url":     c.source.source_url,
                "retrieval_tool": c.source.retrieval_tool,
                "title":          c.source.title or "",
                "snippet":        (c.source.snippet or "")[:200],
            },

            # Relationship links
            "corroborating_claim_ids": c.corroborating_claim_ids,
            "contradicting_claim_ids": c.contradicting_claim_ids,
        })

    # ── Serialise contradictions ──────────────────────────────────────────────
    contradictions_out = []
    for cd in contradictions:
        contradictions_out.append({
            "id_a":         cd["claim_a"]["id"],
            "id_b":         cd["claim_b"]["id"],
            "severity":     cd["severity"].upper(),
            "reason":       cd.get("reason", ""),
            "confidence_a": cd["confidence_a"],
            "confidence_b": cd["confidence_b"],
        })

    # ── Serialise unique sources (deduped by URL) ─────────────────────────────
    sources_out = []
    seen_source_urls = set()
    for c in all_claims:
        url = c.source.source_url
        if url and url not in seen_source_urls:
            seen_source_urls.add(url)
            sources_out.append({
                "source_type": c.source.source_type,
                "title":       c.source.title or c.source.source_type,
                "url":         url,
            })

    _last_ledger = ledger

    return {
        "query":           req.query,
        "claims":          claims_out,
        "contradictions":  contradictions_out,
        "sources":         sources_out,
        "report":          str(result.get("report", "") or ""),
        "report_confidence": result.get("report_confidence", 0.0),
        "claim_count":     len(claims_out),
        "source_count":    len(sources_out),
        # Summary stats for dashboard
        "stats": {
            "verified_facts":   sum(1 for c in all_claims if c.confidence_state == "VERIFIED_FACT"),
            "breaking_claims":  sum(1 for c in all_claims if c.confidence_state == "BREAKING_CLAIM"),
            "active_disputes":  sum(1 for c in all_claims if c.confidence_state == "ACTIVE_DISPUTE"),
            "debunked":         sum(1 for c in all_claims if c.confidence_state == "DEBUNKED"),
            "echo_chambers":    sum(1 for c in all_claims if c.echo_chamber),
        },
    }


class ExplainRequest(BaseModel):
    claim_id: str


@app.post("/api/explain")
async def explain_claim(req: ExplainRequest):
    if not _last_ledger:
        return {"error": "No investigation data available. Run an investigation first."}
    explainer = EvidenceExplainer(_last_ledger)
    explanation = explainer.explain_claim(req.claim_id)
    return {"claim_id": req.claim_id, "explanation": explanation}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
