# DuckDuckGo Web Search (Free, No API Key)

Search the web using DuckDuckGo's HTML search endpoint directly. No API key, no signup, no rate limits for moderate usage. Perfect for AI agents that need live search without a paid service.

## When to Use

- Adding web search to an LLM-powered agent without paying for Tavily/SerpAPI
- Building a `[SEARCH: query]` → results pipeline
- Any scenario where search volume is <100 queries/day

## Core Technique

Two approaches — prefer `urllib.request` for maximum SSL compatibility, `httpx` if already a dependency.

### urllib.request (most reliable, no extra deps)

```python
import urllib.request, urllib.parse, ssl
from lxml import html


url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
ctx = ssl.create_default_context()
resp = urllib.request.urlopen(req, timeout=15, context=ctx)
body = resp.read()


tree = html.fromstring(body)
results = []
for result in tree.cssselect(".result"):
    title_el = result.cssselect(".result__title a")
    snippet_el = result.cssselect(".result__snippet")
    if title_el:
        title = title_el[0].text_content().strip()
        href = title_el[0].get("href", "")
        snippet = snippet_el[0].text_content().strip() if snippet_el else ""
        results.append(f"- [{title}]({href})\n  {snippet[:300]}")
```

### httpx (if already in the project)

```python
import httpx
from lxml import html

params = {"q": query}
headers = {"User-Agent": "Mozilla/5.0"}
resp = httpx.get(
    "https://html.duckduckgo.com/html/",
    params=params,
    headers=headers,
    timeout=10,
    follow_redirects=True
)
resp.raise_for_status()
tree = html.fromstring(resp.text.encode())
# ... same CSS selection as above
```

## Key Details

| Detail | Value |
|--------|-------|
| **Endpoint** | `https://html.duckduckgo.com/html/` |
| **Method** | GET with URL params |
| **User-Agent** | `"Mozilla/5.0"` — shorter UA works better (long UA got 202 status) |
| **Redirects** | `follow_redirects=True` required |
| **Parsing** | `lxml.html.fromstring(resp.text.encode())` — encode needed for proper parsing |
| **CSS Selectors** | `.result` (each result block), `.result__title a` (title + link), `.result__snippet` (description) |
| **Timeout** | 10 seconds typically sufficient |

## Two-Stage LLM Pipeline

Best practice for integrating into an agent chat:

```
1. LLM responds to user, may include [SEARCH: query]
2. Backend detects [SEARCH: ...] marker
3. Backend calls DuckDuckGo, gets results
4. Backend re-calls LLM with results injected as context
5. LLM generates final response incorporating search data
```

## URL Fetching (sibling capability)

Add `[FETCH_URL: https://...]` alongside SEARCH to let the agent read specific pages:

```python
url_match = re.search(r'\[FETCH_URL:\s*(.*?)\]', response)
if url_match:
    url = url_match.group(1).strip()
    content = fetch_url(url)
```

**fetch_url implementation** — uses the same `urllib.request` + lxml pattern:

```python
def fetch_url(url):
    import urllib.request, ssl
    from lxml import html as lh
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=20, context=ctx)
    body = resp.read()
    tree = lh.fromstring(body)
    for el in tree.cssselect("script, style, nav, footer, header"):
        el.drop_tree()
    text = tree.text_content().strip()
    import re
    text = re.sub(r'\s+', ' ', text)
    return text[:4000]
```

## Why Not the DDGS Library?

The `ddgs` / `duckduckgo_search` Python library (v9.x) routes through Mojeek as its search backend, which may be blocked or unreachable from certain networks. Direct HTML endpoint avoids this dependency.

```bash
# Don't use — routes through Mojeek
pip install ddgs

# Instead — use httpx + lxml (already commonly installed)
pip install httpx lxml cssselect
```

## Pitfalls

- **User-Agent sensitivity** — Full Chrome UA string (`Mozilla/5.0 (Macintosh; Intel...)`) returns 202 status (challenge page). Short `"Mozilla/5.0"` returns 200.
- **Status 202** — Means DDG served a challenge/captcha. Usually fixed by using a simpler User-Agent and `follow_redirects=True`.
- **CSS selectors break** — DuckDuckGo occasionally changes their HTML structure. The `.result`, `.result__title a`, `.result__snippet` selectors have been stable since 2023 but are not guaranteed.
- **`lxml.html.fromstring`** — Pass `resp.text.encode()` (bytes), not `resp.text` directly, when the HTML has encoding declarations. Failing to encode can produce empty parsing results.
- **Rate limiting** — No hard limit documented, but >10 queries/minute may get temp-blocked for a few minutes. Space agent queries by at least 6 seconds.
- **Deprecation warning** — If using the old `duckduckgo_search` library, you get `RuntimeWarning: This package has been renamed to ddgs`. Ignore it and switch to direct HTTP.
- **`lxml` is a required runtime dependency, not optional** — `from lxml import html` runs at call time (inside the function body), so it won't fail on import. This means the first search attempt silently fails with a caught exception if `lxml` isn't installed, and the caller gets a "Search failed" message with no obvious import error. Unlike most dependencies where you get an `ImportError` at startup, this one hides. Always verify `pip install lxml` in the target environment: `python3 -c "from lxml import html; print('ok')"`.
- **httpx SSL handshake timeout** — On some macOS machines, httpx fails to connect to DuckDuckGo's HTTPS endpoint with `_ssl.c:999: The handshake operation timed out` while curl and urllib.request work fine. If httpx times out, switch to the urllib.request approach above — it's more reliable across Python/SSL configurations.
- **`cssselect` dependency required** — `lxml.html.cssselect()` needs the `cssselect` package. Without it, `tree.cssselect(".result")` raises `ImportError: cssselect does not seem to be installed`. Run `pip install cssselect` if you hit this.
