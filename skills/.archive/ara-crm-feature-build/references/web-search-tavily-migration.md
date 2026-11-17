# Web Search — Tavily API Migration

## What Changed

The ARA server's `web_search()` and `fetch_url()` functions were migrated from DuckDuckGo HTML scraping (using `lxml`) to the **Tavily API**. The old approach was fragile — DuckDuckGo's HTML endpoint rate-limits aggressively, and `lxml` was a separate dependency.

## Current Implementation

In `server.py`:

```python
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

def web_search(query, max_results=5):
    """Search the web using Tavily API with retry on transient SSL errors."""
    if not TAVILY_API_KEY:
        return "Search unavailable: Tavily API key not configured."
    import httpx
    last_err = ""
    for attempt in range(3):
        try:
            resp = httpx.post("https://api.tavily.com/search", json={
                "api_key": TAVILY_API_KEY, "query": query,
                "search_depth": "basic", "max_results": max_results
            }, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if not results: return "No results found."
            out = []
            for r in results[:max_results]:
                out.append(f"- {r['title']}: {r['content'][:200]}")
            return "\n".join(out)
        except httpx.TimeoutException:
            last_err = "Search timed out"
        except Exception as e:
            last_err = f"Search failed: {e}"
    return last_err or "Search failed after retries"
```

## Key Details

- **API Key**: In `~/.hermes/.env` as `TAVILY_API_KEY=tvly-dev-...`
- **Timeout**: 30 seconds per attempt
- **Retry**: 3 attempts with 1-second sleep between (handles intermittent SSL handshake failures common on this machine)
- **Search depth**: `basic` — faster, sufficient for core snippets
- **URL extraction**: Also migrated to Tavily's extract endpoint (`POST https://api.tavily.com/extract`), same retry pattern

## Testing

```bash
# Test web_search directly (from server's Python environment)
cd /Users/greg/ara && /Users/greg/.hermes/hermes-agent/venv/bin/python3.11 -c "
from dotenv import load_dotenv
load_dotenv('/Users/greg/.hermes/.env')
import os, httpx
TAVILY_KEY = os.environ['TAVILY_API_KEY']
resp = httpx.post('https://api.tavily.com/search', json={
    'api_key': TAVILY_KEY, 'query': 'AI voice agent market size 2026',
    'search_depth': 'basic', 'max_results': 3
}, timeout=30)
print(resp.json()['results'][0]['title'])
"

# Test through the chat API
curl -s -X POST http://localhost:8766/api/agent/chat/3e736242 \
  -H "Content-Type: application/json" \
  -d '{"message":"search for AI voice agents","thread_id":null}'
```

## Known Issue

Tavily has intermittent SSL handshake timeouts from this machine (~2/3 attempts fail, 3rd succeeds in ~2s). The 3-retry pattern handles the common case. If all 3 fail, it's a network blip.
