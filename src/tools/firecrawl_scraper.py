from __future__ import annotations
from firecrawl import FirecrawlApp
from .base import BaseTool, ToolResult
from src.config import FIRECRAWL_API_KEY

# Note: FirecrawlApp is instantiated dynamically inside tool runs to support user-supplied API keys


class FirecrawlScraperTool(BaseTool):
    name = "firecrawl_scraper"
    description = "Scrape a URL using Firecrawl and return clean markdown content"

    async def run(self, params: dict) -> ToolResult:
        url = params.get("url", "")
        formats = params.get("formats", ["markdown"])
        if not url:
            return ToolResult(success=False, error="No URL provided")
        firecrawl_key = params.get("firecrawl_key") or FIRECRAWL_API_KEY
        if not firecrawl_key:
            return ToolResult(success=False, error="No Firecrawl API key provided")
        try:
            local_app = FirecrawlApp(api_key=firecrawl_key)
            result = local_app.scrape_url(url, formats=formats, timeout=60000)
            markdown = getattr(result, "markdown", "")
            html = getattr(result, "html", "")
            metadata = getattr(result, "metadata", None)
            source_url = getattr(metadata, "source_url", url) if metadata else url
            title = getattr(metadata, "title", "") if metadata else ""
            return ToolResult(
                success=True,
                data={"markdown": markdown, "html": html, "metadata": metadata},
                source_type="firecrawl_scrape",
                source_url=source_url,
                title=title or url,
                snippet=markdown[:500] if markdown else "",
                raw_text=markdown[:10000] if markdown else "",
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), source_url=url)


class FirecrawlSearchTool(BaseTool):
    name = "firecrawl_search"
    description = "Search the web using Firecrawl's LLM-optimized search"

    async def run(self, params: dict) -> ToolResult:
        query = params.get("query", "")
        limit = params.get("limit", 5)
        if not query:
            return ToolResult(success=False, error="No query provided")
        firecrawl_key = params.get("firecrawl_key") or FIRECRAWL_API_KEY
        if not firecrawl_key:
            return ToolResult(success=False, error="No Firecrawl API key provided")
        try:
            local_app = FirecrawlApp(api_key=firecrawl_key)
            result = local_app.search(query, limit=limit)
            web_results = getattr(result, "web", [])
            if not web_results:
                data = getattr(result, "data", [])
                web_results = data if data else []
            snippets = []
            urls = []
            for r in web_results[:limit]:
                desc = getattr(r, "description", "") or getattr(r, "snippet", "")
                link = getattr(r, "url", "") or getattr(r, "link", "")
                title = getattr(r, "title", "")
                snippets.append(f"- {title}: {desc[:300]}")
                if link:
                    urls.append(link)
            return ToolResult(
                success=True,
                data=web_results,
                source_type="firecrawl_search",
                source_url=urls[0] if urls else "",
                title=f"Firecrawl search: {query}",
                snippet="\n".join(snippets),
                raw_text="\n".join(snippets),
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class FirecrawlMapTool(BaseTool):
    name = "firecrawl_map"
    description = "Map URLs from a website to discover pages"

    async def run(self, params: dict) -> ToolResult:
        url = params.get("url", "")
        if not url:
            return ToolResult(success=False, error="No URL provided")
        firecrawl_key = params.get("firecrawl_key") or FIRECRAWL_API_KEY
        if not firecrawl_key:
            return ToolResult(success=False, error="No Firecrawl API key provided")
        try:
            local_app = FirecrawlApp(api_key=firecrawl_key)
            result = local_app.map_url(url)
            links = result.get("links", []) if isinstance(result, dict) else getattr(result, "links", [])
            return ToolResult(
                success=True,
                data=links,
                source_type="firecrawl_map",
                source_url=url,
                title=f"Sitemap: {url}",
                snippet=f"Found {len(links)} pages",
                raw_text="\n".join(links[:100]) if links else "",
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), source_url=url)


class FirecrawlExtractTool(BaseTool):
    name = "firecrawl_extract"
    description = "Extract structured data from a URL using LLM extraction"

    async def run(self, params: dict) -> ToolResult:
        url = params.get("url", "")
        prompt = params.get("prompt", "Extract all meaningful content from this page")
        if not url:
            return ToolResult(success=False, error="No URL provided")
        firecrawl_key = params.get("firecrawl_key") or FIRECRAWL_API_KEY
        if not firecrawl_key:
            return ToolResult(success=False, error="No Firecrawl API key provided")
        try:
            local_app = FirecrawlApp(api_key=firecrawl_key)
            result = local_app.scrape_url(
                url,
                formats=[{"type": "json", "prompt": prompt}],
                timeout=60000,
            )
            json_data = getattr(result, "json", {})
            markdown = getattr(result, "markdown", "")
            return ToolResult(
                success=True,
                data={"json": json_data, "markdown": markdown},
                source_type="firecrawl_extract",
                source_url=url,
                title=getattr(getattr(result, "metadata", None), "title", "") or url,
                snippet=str(json_data)[:500] if json_data else markdown[:500],
                raw_text=str(json_data)[:10000] if json_data else (markdown[:10000] if markdown else ""),
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), source_url=url)
