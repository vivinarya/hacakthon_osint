from __future__ import annotations
import asyncio
import json
import sys
import os
import shutil
import math
from functools import lru_cache
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))

import uvicorn
from fastapi import FastAPI, Header, HTTPException, UploadFile, File
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


# ── Datasets API ──────────────────────────────────────────────────────────────

USER_UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "datasets", "user_uploads")
os.makedirs(USER_UPLOADS_DIR, exist_ok=True)

@lru_cache(maxsize=5)
def load_dataset(file_path: str):
    if file_path.endswith('.csv'):
        return pd.read_csv(file_path)
    elif file_path.endswith(('.xls', '.xlsx')):
        return pd.read_excel(file_path)
    elif file_path.endswith('.json'):
        return pd.read_json(file_path)
    else:
        raise ValueError("Unsupported file format")

@app.get("/api/datasets")
async def list_datasets():
    datasets = []
    if os.path.exists(USER_UPLOADS_DIR):
        for f in os.listdir(USER_UPLOADS_DIR):
            if not f.startswith('.') and not f.startswith('~'):
                file_path = os.path.join(USER_UPLOADS_DIR, f)
                if os.path.isfile(file_path):
                    size_mb = os.path.getsize(file_path) / (1024 * 1024)
                    datasets.append({
                        "id": f,
                        "name": f,
                        "type": "uploaded",
                        "size_mb": round(size_mb, 2)
                    })
    return {"datasets": datasets}

@app.post("/api/datasets/upload")
async def upload_dataset(file: UploadFile = File(...)):
    if not file.filename.endswith(('.csv', '.xlsx', '.xls', '.json')):
        raise HTTPException(status_code=400, detail="Unsupported file format. Please upload CSV, Excel, or JSON.")
    
    file_path = os.path.join(USER_UPLOADS_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return {"status": "success", "filename": file.filename}

class DatasetSearchRequest(BaseModel):
    dataset_id: str
    keyword: str = ""
    page: int = 1
    page_size: int = 50

@app.post("/api/datasets/search")
async def search_dataset(req: DatasetSearchRequest):
    file_path = os.path.join(USER_UPLOADS_DIR, req.dataset_id)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    try:
        df = load_dataset(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading dataset: {str(e)}")
        
    if req.keyword:
        mask = df.astype(str).apply(lambda x: x.str.contains(req.keyword, case=False, na=False)).any(axis=1)
        df = df[mask]
        
    total_records = len(df)
    total_pages = math.ceil(total_records / req.page_size) if req.page_size > 0 else 1
    
    start_idx = (req.page - 1) * req.page_size
    end_idx = start_idx + req.page_size
    
    page_data = df.iloc[start_idx:end_idx].fillna("").to_dict(orient="records")
    
    return {
        "columns": df.columns.tolist(),
        "data": page_data,
        "total_records": total_records,
        "total_pages": total_pages,
        "page": req.page,
        "page_size": req.page_size
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
