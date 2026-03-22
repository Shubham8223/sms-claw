"""Web tools: search and browse."""

from __future__ import annotations

import httpx
from langchain_core.tools import tool

from sms_claw.core.config import get_settings
from sms_claw.core.logging import get_logger
from sms_claw.tools.registry import register_tool

log = get_logger(__name__)
_s = get_settings()


@register_tool
@tool
async def web_search(query: str) -> str:
    """Search the internet for current information — news, facts, prices, weather."""
    try:
        if _s.search_provider == "tavily" and _s.tavily_api_key:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": _s.tavily_api_key,
                        "query": query,
                        "search_depth": "basic",
                        "max_results": 3,
                        "include_answer": True,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("answer"):
                    return data["answer"]
                return "\n".join(
                    f"- {r['title']}: {r['content'][:200]}"
                    for r in data.get("results", [])[:3]
                )

        if _s.search_provider == "serpapi" and _s.serpapi_api_key:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://serpapi.com/search",
                    params={"q": query, "api_key": _s.serpapi_api_key, "num": 3},
                )
                resp.raise_for_status()
                snippets = [
                    r.get("snippet", "")
                    for r in resp.json().get("organic_results", [])[:3]
                ]
                return "\n".join(f"- {s}" for s in snippets if s)

        return "Search not configured. Set TAVILY_API_KEY or SERPAPI_API_KEY."
    except Exception as exc:
        log.error("web_search_error", query=query, error=str(exc), exc_info=True)
        return f"Search failed: {exc}"


@register_tool
@tool
async def web_browse(url: str) -> str:
    """Fetch a URL and return its summarised text content."""
    try:
        import trafilatura
        from bs4 import BeautifulSoup

        async with httpx.AsyncClient(
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; Dispatch/1.0)"},
            timeout=20,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        text = trafilatura.extract(
            resp.text, include_comments=False, include_tables=False
        )
        if not text:
            text = BeautifulSoup(resp.text, "html.parser").get_text(
                separator=" ", strip=True
            )

        return (
            (text[:1200].strip() + "…")
            if text and len(text) > 1200
            else (text or "No content found.")
        )
    except Exception as exc:
        log.error("web_browse_error", url=url, error=str(exc), exc_info=True)
        return f"Could not browse {url}: {exc}"
