from __future__ import annotations
import json
import httpx
from bs4 import BeautifulSoup
from .base import BaseTool, ToolResult
from src.config import TAVILY_API_KEY, SERPER_API_KEY, FIRECRAWL_API_KEY
from .firecrawl_scraper import FirecrawlSearchTool


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web for recent information on a topic"

    async def run(self, params: dict) -> ToolResult:
        query = params.get("query", "")
        max_results = params.get("max_results", 5)
        if not query:
            return ToolResult(success=False, error="No query provided")

        providers = []
        user_firecrawl_key = params.get("firecrawl_key")
        if TAVILY_API_KEY:
            providers.append(lambda: self._tavily_search(query, max_results))
        if SERPER_API_KEY:
            providers.append(lambda: self._serper_search(query, max_results))
        if FIRECRAWL_API_KEY or user_firecrawl_key:
            providers.append(lambda: FirecrawlSearchTool().run({
                "query": query,
                "limit": max_results,
                "firecrawl_key": user_firecrawl_key
            }))
        providers.append(lambda: self._duckduckgo_search(query, max_results))

        last_error = "No search providers available"
        for provider in providers:
            result = await provider()
            if result.success:
                return result
            if result.error:
                last_error = result.error

        return ToolResult(success=False, error=last_error)

    async def _duckduckgo_search(self, query: str, max_results: int) -> ToolResult:
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")
                results = []
                snippets = []
                urls = []
                for node in soup.select(".result")[:max_results]:
                    title_node = node.select_one(".result__title")
                    snippet_node = node.select_one(".result__snippet")
                    link_node = node.select_one(".result__url")
                    title = title_node.get_text(" ", strip=True) if title_node else ""
                    body = snippet_node.get_text(" ", strip=True) if snippet_node else ""
                    href = ""
                    if title_node and title_node.find("a"):
                        href = title_node.find("a").get("href", "")
                    if not href and link_node:
                        href = link_node.get_text(" ", strip=True)
                    if href and href.startswith("//"):
                        href = f"https:{href}"
                    snippets.append(f"- {title}: {body[:300]}")
                    if href:
                        urls.append(href)
                    results.append({"title": title, "body": body, "href": href})
            if not results:
                return ToolResult(success=False, error=f"No web results found for '{query}'")
            return ToolResult(
                success=True,
                data=results,
                source_type="web_search",
                source_url=urls[0] if urls else "",
                title=f"Web search: {query}",
                snippet="\n".join(snippets),
                raw_text=json.dumps(results, indent=2),
            )
        except Exception as e:
            return ToolResult(success=False, error=f"DuckDuckGo search failed: {e}")

    async def _tavily_search(self, query: str, max_results: int) -> ToolResult:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={"api_key": TAVILY_API_KEY, "query": query, "max_results": max_results},
                )
                resp.raise_for_status()
                data = resp.json()
                results = data.get("results", [])
                if not results:
                    return ToolResult(success=False, error=f"Tavily returned no results for '{query}'")
                urls = [r.get("url", "") for r in results]
                snippets = "\n".join(
                    f"- {r.get('title', '')}: {r.get('content', '')[:500]}"
                    for r in results
                )
                return ToolResult(
                    success=True,
                    data=results,
                    source_type="web_search",
                    source_url=urls[0] if urls else "",
                    title=f"Web search: {query}",
                    snippet=snippets,
                    raw_text=json.dumps(data, indent=2),
                )
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    async def _serper_search(self, query: str, max_results: int) -> ToolResult:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://google.serper.dev/search",
                    json={"q": query, "num": max_results},
                    headers={"X-API-KEY": SERPER_API_KEY},
                )
                resp.raise_for_status()
                data = resp.json()
                results = data.get("organic", [])
                if not results:
                    return ToolResult(success=False, error=f"Serper returned no results for '{query}'")
                snippets = "\n".join(
                    f"- {r.get('title', '')}: {r.get('snippet', '')[:500]}"
                    for r in results
                )
                return ToolResult(
                    success=True,
                    data=results,
                    source_type="web_search",
                    source_url=data.get("organic", [{}])[0].get("link", ""),
                    title=f"Web search: {query}",
                    snippet=snippets,
                    raw_text=json.dumps(data, indent=2),
                )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
