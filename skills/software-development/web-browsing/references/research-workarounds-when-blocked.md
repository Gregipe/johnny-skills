# Research Workarounds — When Search Engines Block You

Common failure modes and proven workarounds for web research when automated tools hit CAPTCHAs, IP blocks, or rate limits.

## Blocking Patterns

| Search Engine | Block Signal | Likelihood |
|--------------|-------------|------------|
| Google | CAPTCHA wall (sorry/index) or empty results | Very High |
| DuckDuckGo | "Select all squares containing a duck" CAPTCHA | High (after a few queries) |
| Bing | Captcha redirect or empty results | Moderate |
| StartPage | Empty results from curl | High |

## Hermes Tool Failure: `web_search` SSL Timeout

The built-in `web_search` tool (not the browser) consistently fails with this error in certain environments:

```
Error searching web: _ssl.c:999: The handshake operation timed out
```

This is a recurring environment-level TLS issue, not a content block. Appears across multiple sessions regardless of query. **Do NOT retry web_search more than twice** when you see this error — it's not transient, and retries waste time.

**Immediate fallback chain when web_search SSL-timeouts:**
1. **terminal + curl to Wikipedia API** (most reliable for factual research — open, generous rate limits, structured JSON)
2. **browser_navigate** (works for Wikipedia, news sites, company pages — but not Google/DuckDuckGo which block)
3. **terminal + curl to HN API** (`https://hacker-news.firebaseio.com/v0/`) for tech news
4. **terminal + curl with realistic User-Agent** to specific sites (static HTML pages only)
5. **Knowledge bridging** — state what you know from training data, flag gaps, ask the user

❌ Do NOT retry web_search more than twice in a row. The SSL timeout is an environment issue, not a transient glitch.

## Workarounds (in preference order)

### 1. Wikipedia API (most reliable)
Wikipedia's API is completely open with generous rate limits. Use the `action=query` endpoint:

```
# Get a page extract (summary)
curl -s "https://en.wikipedia.org/w/api.php?action=query&titles=Page_Name&prop=extracts&exintro&explaintext&format=json"

# Search for pages
curl -s "https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=query+terms&format=json&srlimit=10"

# Get full text
curl -s "https://en.wikipedia.org/w/api.php?action=query&titles=Page_Name&prop=extracts&explaintext&format=json"
```

Parse with: `python3 -c "import sys,json; d=json.load(sys.stdin); ..."`

### 2. Direct site fetching with proper User-Agent
Some sites accept curl with a realistic browser User-Agent:
```
curl -sL "https://site.com/page" -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
```

Works best for static HTML pages. Most modern sites (news, companies) are JavaScript SPAs — curl gets skeleton only. Use browser tool for those.

### 3. Browser tool (agent-browser)
Navigate to DuckDuckGo HTML mode when CAPTCHAs block:
```
https://duckduckgo.com/html/?q=<query>
```
This sometimes skips the JS CAPTCHA. If CAPTCHA'd, close and reopen browser session.

### 4. Bing search via curl
Sometimes works with proper headers — parse with regex for `<li class="b_algo">` blocks.

### 5. Open APIs
- Wikipedia API (reliable, generous limits)
- HackerNews API: `https://hacker-news.firebaseio.com/v0/`
- GitHub API: for code, company repos, projects
- NewsAPI (requires key): `https://newsapi.org/v2/`

## When All Else Fails: Knowledge Bridging
1. Use pre-training knowledge — state what you know, flag gaps
2. Ask the user targeted questions to fill critical gaps
3. Compile partial research + logical inference
4. Document what's verified vs. inferred so user can validate

## PDF Delivery Pattern (for Telegram)
```
# Install
pip3 install fpdf2

# Generate: fpdf2 with Helvetica (no unicode bullets — use dashes)
# Use new_x="LMARGIN", new_y="NEXT" (fpdf2 2.5+)
# Send via MEDIA:/path/to/file.pdf in response or send_message
```
