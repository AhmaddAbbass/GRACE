"""
Minimal search facade you can import anywhere:

    from web_search.searcher import WebSearch
    ws = WebSearch(provider="auto", top_n=5)  # auto picks SerpAPI/Tavily if keys exist, else DDG
    results = ws.search("best open data portals 2025", k=5)
    for r in results:
        print(r["title"], "->", r["url"])

Normalized result schema (list of dicts):
{
  "title": str,
  "url": str,
  "snippet": str,
  "source": "serpapi" | "tavily" | "ddg",
  "position": int,                 # 1-based rank
  "score": float | None            # provider score if available
}
"""
from __future__ import annotations

import os
import sys
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from .providers import ddg_search, serpapi_search, tavily_search  # package import
except ImportError:  # Executed when run as a loose script
    CURRENT_DIR = Path(__file__).resolve().parent
    if str(CURRENT_DIR) not in sys.path:
        sys.path.insert(0, str(CURRENT_DIR))
    from providers import ddg_search, serpapi_search, tavily_search  # type: ignore

_DEFAULTS = {
    "provider": "auto",            # "auto" | "ddg" | "serpapi" | "tavily"
    "top_n": 5,
    "region": "us-en",
    "safesearch": "moderate",      # "off" | "moderate" | "strict" (ddg)
    "timeout": 10,                 # seconds (per request)
    "max_retries": 1,
}

_ENV_KEYS = (
    "SERPAPI_API_KEY",
    "TAVILY_API_KEY",
    "SEARCH_PROVIDER",
    "SEARCH_REGION",
    "SEARCH_SAFETY",
    "SEARCH_TOPN",
)


class WebSearch:
    def __init__(
        self,
        *,
        provider: str = _DEFAULTS["provider"],
        top_n: int = _DEFAULTS["top_n"],
        region: str = _DEFAULTS["region"],
        safesearch: str = _DEFAULTS["safesearch"],
        timeout: int = _DEFAULTS["timeout"],
        max_retries: int = _DEFAULTS["max_retries"],
        serpapi_api_key: Optional[str] = None,
        tavily_api_key: Optional[str] = None,
        env_path: Optional[str] = None,
    ):
        """Create a web search helper.

        If provider="auto", the priority is SerpAPI ? Tavily ? DuckDuckGo depending on which keys are set.
        """
        env_candidate = env_path or (Path(__file__).parent / ".env")
        self._maybe_load_env(env_candidate)

        self.provider = (os.getenv("SEARCH_PROVIDER") or provider or "auto").lower()
        self.top_n = int(os.getenv("SEARCH_TOPN") or top_n)
        self.region = os.getenv("SEARCH_REGION") or region
        self.safesearch = os.getenv("SEARCH_SAFETY") or safesearch
        self.timeout = timeout
        self.max_retries = max_retries

        self.serpapi_api_key = serpapi_api_key or os.getenv("SERPAPI_API_KEY")
        self.tavily_api_key = tavily_api_key or os.getenv("TAVILY_API_KEY")

    # -- public API ----------------------------------------------------
    def search(self, query: str, k: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return a list of normalized search hits."""
        k = int(k or self.top_n)
        provider = self._select_provider()

        for attempt in range(1 + self.max_retries):
            try:
                if provider == "serpapi":
                    return serpapi_search(query, k, api_key=self.serpapi_api_key, timeout=self.timeout)
                if provider == "tavily":
                    return tavily_search(query, k, api_key=self.tavily_api_key, timeout=self.timeout)
                return ddg_search(query, k, region=self.region, safesearch=self.safesearch, timeout=self.timeout)
            except Exception:
                if attempt >= self.max_retries:
                    raise
                time.sleep(0.3 * (attempt + 1))
        return []

    # -- helpers -------------------------------------------------------
    def _select_provider(self) -> str:
        if self.provider in ("ddg", "serpapi", "tavily"):
            if self.provider == "serpapi" and not self.serpapi_api_key:
                raise RuntimeError("SERPAPI_API_KEY not set but provider='serpapi'")
            if self.provider == "tavily" and not self.tavily_api_key:
                raise RuntimeError("TAVILY_API_KEY not set but provider='tavily'")
            return self.provider

        if self.serpapi_api_key:
            return "serpapi"
        if self.tavily_api_key:
            return "tavily"
        return "ddg"

    def _maybe_load_env(self, env_file: Path) -> None:
        try:
            if Path(env_file).exists():
                for line in Path(env_file).read_text(encoding="utf-8").splitlines():
                    s = line.strip()
                    if not s or s.startswith("#") or "=" not in s:
                        continue
                    key, value = s.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key in _ENV_KEYS and key not in os.environ:
                        os.environ[key] = value
        except Exception:
            pass
