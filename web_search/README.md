
# web_search – tiny, pluggable search tool

A minimal search helper you can drop into any project. It supports:
- **DuckDuckGo** (default, no API key)
- **SerpAPI** (Google results) – requires `SERPAPI_API_KEY`
- **Tavily** – requires `TAVILY_API_KEY`

It returns a **normalized schema** so you can swap providers without changing your code.

## Install

```bash
pip install duckduckgo_search requests
# (optional) if you want SerpAPI: no extra lib needed (uses requests)
# (optional) if you want Tavily: no extra lib needed (uses requests)
````

## Quick start

```python
from web_search.searcher import WebSearch

ws = WebSearch(provider="auto", top_n=5)  # auto picks serpapi/tavily if keys exist, else ddg
results = ws.search("open data portals 2025", k=5)
for r in results:
    print(r["title"], "->", r["url"])
```

**Normalized result dict**:

```json
{
  "title": "string",
  "url": "https://...",
  "snippet": "string",
  "source": "ddg | serpapi | tavily",
  "position": 1,
  "score": 0.87
}
```

## .env (optional)

Create a `.env` file inside `web_search/` (the code will auto-load it):

```
# Provider: auto | ddg | serpapi | tavily
SEARCH_PROVIDER=auto
SEARCH_REGION=us-en
SEARCH_SAFETY=moderate
SEARCH_TOPN=5

# Optional provider keys
SERPAPI_API_KEY=your_serpapi_key_here
TAVILY_API_KEY=your_tavily_key_here
```

## Run the demo

```bash
python web_search/demo.py
```

## Notes

* If you force `provider="serpapi"` or `"tavily"`, make sure the corresponding API key is set.
* DuckDuckGo uses `duckduckgo_search` under the hood — no API key required.
* The tool is intentionally small and dependency-light. Extend `providers.py` if you need more engines.

```

---

## `web_search/.env`
```

# You can leave this file as-is (defaults).

# Set keys only if you want SerpAPI or Tavily.

SEARCH_PROVIDER=auto
SEARCH_REGION=us-en
SEARCH_SAFETY=moderate
SEARCH_TOPN=5

SERPAPI_API_KEY=
TAVILY_API_KEY=



---

### How to use with your agent
- Initialize once anywhere: `ws = WebSearch(provider="auto", top_n=5)`
- In your tool registry, expose a function like:
  - `web_search(query: str, k: int = 5) -> List[Result]` that just calls `ws.search(query, k)`
- The agent can now call this tool regardless of which backend you enable by env.

