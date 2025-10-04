"""
Quick demo:
  python web_search/demo.py      # direct execution
  python -m web_search.demo      # module execution
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable

try:  # Allow running as package module
    from .searcher import WebSearch
except ImportError:  # Fallback for `python web_search/demo.py`
    CURRENT_DIR = Path(__file__).resolve().parent
    if str(CURRENT_DIR) not in sys.path:
        sys.path.insert(0, str(CURRENT_DIR))
    from searcher import WebSearch  # type: ignore


LINE = "=" * 72


def format_result(rank: int, hit: dict[str, str]) -> str:
    title = hit.get("title") or "(untitled)"
    url = hit.get("url") or "(no url)"
    snippet = hit.get("snippet") or ""
    snippet_preview = snippet[:240] + ("..." if len(snippet) > 240 else "")
    source = hit.get("source") or "n/a"
    score = hit.get("score")
    score_str = f" | score: {score}" if score is not None else ""
    return (
        f"[{rank:02d}] {title}\n"
        f"    url   : {url}\n"
        f"    source: {source}{score_str}\n"
        f"    snippet: {snippet_preview}\n"
    )


def intro_banner(query: str, provider: str, top_k: int) -> None:
    print(LINE)
    print("Hello explorer!  Thanks for trying the web_search toolkit.")
    print(
        "You just asked for web results with the following settings:\n"
        f"  - query        : {query}\n"
        f"  - provider     : {provider}\n"
        f"  - results wanted: {top_k}\n"
    )
    print("Hang tight, fetching the freshest links we can find...")
    print(LINE)


def outro_banner(top_k: int) -> None:
    print(LINE)
    print("Ready for more? Here's how to plug the searcher anywhere:")
    print(
        "  1. from web_search.searcher import WebSearch\n"
        "  2. ws = WebSearch(provider='auto', top_n=5)  # tweak provider/top_n as you like\n"
        "  3. hits = ws.search('your query here', k=3)  # iterate hits, dump to JSON, feed an LLM, etc.\n"
        "  4. Swap providers on the fly (ws.provider='ddg') or pass API keys via env/.env.\n"
    )
    print(f"Enjoy the web! (Displayed the top {top_k} results above.)")
    print(LINE)


def main(args: Iterable[str] | None = None) -> None:
    ws = WebSearch(provider="auto", top_n=5)
    query = "Lebanon inflation rate 2025 site:imf.org OR site:worldbank.org"

    intro_banner(query, ws._select_provider(), ws.top_n)

    results = ws.search(query, k=ws.top_n)
    if not results:
        print("No results came back. Try a broader query or check your network/API keys.")
    else:
        for idx, hit in enumerate(results, 1):
            print(format_result(idx, hit))

    outro_banner(len(results))


if __name__ == "__main__":
    main()
