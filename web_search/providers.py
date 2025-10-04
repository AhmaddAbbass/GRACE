"""
Provider-specific search functions.
Each returns the normalized schema (list[dict] with title/url/snippet/source/position/score).
"""
from __future__ import annotations
import requests
from typing import List, Dict, Any, Optional

# --- DuckDuckGo (no key, via duckduckgo_search) -------------------------
def ddg_search(query: str, k: int, *, region: str = "us-en", safesearch: str = "moderate", timeout: int = 10) -> List[Dict[str, Any]]:
    try:
        from duckduckgo_search import DDGS
    except Exception as e:
        raise RuntimeError("duckduckgo_search is not installed. pip install duckduckgo_search") from e

    results: List[Dict[str, Any]] = []
    pos = 0
    with DDGS(timeout=timeout) as ddgs:
        for hit in ddgs.text(query, region=region, safesearch=safesearch, timelimit=None, max_results=k):
            pos += 1
            results.append({
                "title":   hit.get("title") or "",
                "url":     hit.get("href") or hit.get("url") or "",
                "snippet": hit.get("body") or "",
                "source":  "ddg",
                "position": pos,
                "score":   None,
            })
    return results[:k]

# --- SerpAPI (Google results) -------------------------------------------
def serpapi_search(query: str, k: int, *, api_key: str, timeout: int = 10) -> List[Dict[str, Any]]:
    if not api_key:
        raise RuntimeError("SERPAPI_API_KEY required for serpapi_search")
    params = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "num": min(k, 10),      # SerpAPI per-page cap; could paginate if needed
    }
    r = requests.get("https://serpapi.com/search.json", params=params, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    org = data.get("organic_results") or []
    out: List[Dict[str, Any]] = []
    for i, hit in enumerate(org[:k], 1):
        out.append({
            "title":   hit.get("title") or "",
            "url":     hit.get("link") or "",
            "snippet": hit.get("snippet") or "",
            "source":  "serpapi",
            "position": i,
            "score":   hit.get("position") or None,
        })
    return out

# --- Tavily --------------------------------------------------------------
def tavily_search(query: str, k: int, *, api_key: str, timeout: int = 10) -> List[Dict[str, Any]]:
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY required for tavily_search")
    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": k,
        "include_answer": False,
        "search_depth": "basic",
    }
    r = requests.post("https://api.tavily.com/search", json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    results = data.get("results") or []
    out: List[Dict[str, Any]] = []
    for i, hit in enumerate(results[:k], 1):
        out.append({
            "title":   hit.get("title") or "",
            "url":     hit.get("url") or "",
            "snippet": hit.get("content") or hit.get("snippet") or "",
            "source":  "tavily",
            "position": i,
            "score":   hit.get("score") or None,
        })
    return out
