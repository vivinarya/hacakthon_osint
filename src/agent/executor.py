from __future__ import annotations
import asyncio
import json
from src.llm_client import LLMClient

TOOL_TIMEOUT = 15  # seconds per tool call
from src.evidence_ledger import EvidenceLedger, Source
from src.agent.claim_extractor import ClaimExtractor
from src.tools.base import ToolResult
from src.tools import (
    WebSearchTool, WebScraperTool, WikidataTool,
    OpenCorporatesTool, OpenSanctionsTool, WaybackTool,
    FirecrawlScraperTool, FirecrawlSearchTool, FirecrawlMapTool, FirecrawlExtractTool,
    ICIJDataTool, OFACSDNTool, GDELTTool,
)

TOOL_REGISTRY = {
    "web_search": WebSearchTool(),
    "web_scraper": WebScraperTool(),
    "wikidata": WikidataTool(),
    "opencorporates": OpenCorporatesTool(),
    "opensanctions": OpenSanctionsTool(),
    "wayback": WaybackTool(),
    "firecrawl_scraper": FirecrawlScraperTool(),
    "firecrawl_search": FirecrawlSearchTool(),
    "firecrawl_map": FirecrawlMapTool(),
    "firecrawl_extract": FirecrawlExtractTool(),
    "icij_data": ICIJDataTool(),
    "ofac_sdn": OFACSDNTool(),
    "gdelt": GDELTTool(),
}


async def _run_one_step(step: dict, llm: LLMClient, ledger: EvidenceLedger, claim_extractor: ClaimExtractor, firecrawl_key: str | None = None) -> dict:
    tool_name = step.get("tool", "web_search")
    params = step.get("params", {})
    if firecrawl_key:
        params["firecrawl_key"] = firecrawl_key
    tool = TOOL_REGISTRY.get(tool_name)
    if not tool:
        return {"step": step, "success": False, "error": f"Unknown tool: {tool_name}"}

    try:
        tool_result = await asyncio.wait_for(tool.run(params), timeout=TOOL_TIMEOUT)
    except asyncio.TimeoutError:
        tool_result = ToolResult(success=False, error=f"Tool '{tool_name}' timed out after {TOOL_TIMEOUT}s")
    claims_data = []
    if tool_result.success:
        # Some search tools return multiple article hits. Preserve them as separate
        # sources so the UI and report can show a real citation trail instead of
        # collapsing everything into a single URL.
        if isinstance(tool_result.data, list) and tool_name in {"web_search", "firecrawl_search"}:
            claims_data = []
            for item in tool_result.data[: max(1, params.get("max_results", 5))]:
                if not isinstance(item, dict):
                    if hasattr(item, "model_dump"):
                        item = item.model_dump()
                    elif hasattr(item, "dict"):
                        item = item.dict()
                    elif hasattr(item, "__dict__"):
                        item = item.__dict__
                    else:
                        continue
                item_url = item.get("href") or item.get("url") or item.get("link") or tool_result.source_url
                item_title = item.get("title") or tool_result.title
                item_snippet = item.get("body") or item.get("snippet") or item.get("description") or tool_result.snippet
                source = Source(
                    source_type=tool_result.source_type,
                    source_url=item_url or tool_result.source_url,
                    title=item_title,
                    snippet=item_snippet,
                    raw_text=item_snippet or tool_result.raw_text,
                    retrieved_at=tool_result.retrieved_at,
                    retrieval_tool=tool_name,
                )
                ledger.add_source(source)
                extracted = await claim_extractor.extract(item_snippet or "", tool_result.source_type)
                for cd in extracted:
                    claim = ledger.add_claim(
                        text=cd.get("text", ""), source=source,
                        confidence=cd.get("confidence", 0.5),
                        extraction_method=f"llm_extraction_via_{tool_name}",
                    )
                    cd["claim_id"] = claim.claim_id
                    claims_data.append(cd)
        else:
            source = Source(
                source_type=tool_result.source_type,
                source_url=tool_result.source_url,
                title=tool_result.title,
                snippet=tool_result.snippet,
                raw_text=tool_result.raw_text,
                retrieved_at=tool_result.retrieved_at,
                retrieval_tool=tool_name,
            )
            ledger.add_source(source)
            claims_data = await claim_extractor.extract(
                tool_result.snippet or tool_result.raw_text, tool_result.source_type,
            )
            for cd in claims_data:
                claim = ledger.add_claim(
                    text=cd.get("text", ""), source=source,
                    confidence=cd.get("confidence", 0.5),
                    extraction_method=f"llm_extraction_via_{tool_name}",
                )
                cd["claim_id"] = claim.claim_id
    return {
        "step": step, "success": tool_result.success,
        "source_url": tool_result.source_url,
        "snippet": tool_result.snippet[:300] if tool_result.snippet else "",
        "claims": claims_data if tool_result.success else [],
        "error": tool_result.error,
    }


def _forward_message(claim_ids: list[str], ledger: EvidenceLedger) -> dict:
    claims = [ledger.get_claim(cid) for cid in claim_ids if ledger.get_claim(cid)]
    return {"type": "direct_evidence", "claims": [
        {"id": c.claim_id, "text": c.text, "confidence": c.confidence,
         "source": c.source.source_url, "tool": c.source.retrieval_tool}
        for c in claims
    ]}


class Executor:
    def __init__(self, llm: LLMClient, ledger: EvidenceLedger, firecrawl_key: str | None = None):
        self.llm = llm
        self.ledger = ledger
        self.claim_extractor = ClaimExtractor(llm)
        self.firecrawl_key = firecrawl_key

    async def execute_plan(self, plan: list[dict], parallel: bool = True) -> list[dict]:
        if parallel and len(plan) > 1:
            tasks = [_run_one_step(s, self.llm, self.ledger, self.claim_extractor, self.firecrawl_key) for s in plan]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return [r if not isinstance(r, Exception) else {"step": {}, "success": False, "error": str(r)} for r in results]
        results = []
        for step in plan:
            r = await _run_one_step(step, self.llm, self.ledger, self.claim_extractor, self.firecrawl_key)
            results.append(r)
        return results

    async def adaptive_search(self, query: str, context: str) -> list[dict]:
        prompt = f"""Given this investigation context:
{context[:2000]}

and this follow-up question: {query}

Choose the best tool and parameters. Return JSON: {{"tool": "...", "params": {{...}}}}

Available tools: web_search, firecrawl_search, web_scraper, firecrawl_scraper, wikidata, opencorporates, opensanctions, wayback"""
        response = await self.llm.generate_json(prompt)
        if isinstance(response, dict) and "tool" in response:
            plan = [response]
        elif isinstance(response, list):
            plan = response
        else:
            plan = [{"tool": "firecrawl_search", "params": {"query": query}}]
        return await self.execute_plan(plan)
