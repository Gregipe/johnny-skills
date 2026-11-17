---
name: web-browsing
description: "Browser automation for web research, flight search, price comparison, and scraping. Covers bot detection, Google Flights navigation, and agent-browser setup."
version: 1.2.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [browser, web, scraping, research, flights, automation]
---

# Web Browsing & Browser Automation

## Setup

Install the browser before using any `browser_*` tools:
```bash
agent-browser install
```
This downloads Chrome to `~/.agent-browser/browsers/`. Without it, all `browser_navigate` calls fail with "Auto-launch failed: Chrome not found."

Verify it's installed:
```bash
ls ~/.agent-browser/browsers/
```

## Tool Reference

| Tool | Use |
|------|-----|
| `browser_navigate(url)` | Navigate to URL, returns page snapshot |
| `browser_snapshot()` | Get current page element tree |
| `browser_click(ref)` | Click element by ref ID |
| `browser_type(ref, text)` | Type into a field |
| `browser_press(key)` | Press a key (Enter, Tab, Escape…) |
| `browser_console(expression)` | Run JS in the page + capture return value |
| `browser_vision(question)` | Screenshot + vision analysis |

## SPA Navigation via browser_console

Single-page apps (SPAs) with sidebar navigation using inline `onclick` handlers on `<div>` elements often fail to register in the browser accessibility tree. When `browser_click(ref)` returns success but the page content doesn't change, the click silently missed the correct handler.

### The Pattern

Instead of relying on `browser_click` for SPA sidebar nav that may not register in the accessibility tree:

```
# Call the JS navigation function directly:
browser_console(expression='showPage("integrations")')
```

This works because SPA sidebar handlers are regular JS functions in global scope — `browser_console` calls them directly, bypassing the DOM event layer.

#### Fallback: Function Not Globally Accessible

Sometimes SPA navigation functions are trapped inside a template closure (e.g., Jinja2/Python `render_template()`). Calling `showPage("integrations")` via `browser_console` fails with `ReferenceError: showPage is not defined`.

**Workaround:** Query the DOM element with the matching onclick handler and dispatch a click directly:

```
browser_console(expression="document.querySelector('[onclick*=\"integrations\"]').click()")
```

This fires the actual click handler on the DOM element. The `*=` CSS selector matches partial attribute values — adapt the string to match your target nav item.

**Alternative when onclick attribute isn't the right hook:** Some SPA frameworks use synthetic events rather than `onclick` attributes. Find the element by text content:

```
browser_console(expression="Array.from(document.querySelectorAll('.nav-item')).find(el => el.textContent.includes('Integrations'))?.click()")
```

**Another alternative:** If you know the page URL for a given SPA view, navigate to it directly via `browser_navigate`. The ARA dashboard uses `/integrations` as a raw endpoint (just pretty-print output), but some SPAs support direct routing — worth trying before falling into endless click-debug cycles.

### Inspecting Dynamic Content After Navigation

The accessibility tree snapshot (`browser_snapshot()`) may continue showing the old page after SPA navigation — the a11y tree lags behind DOM updates or only captures what was there at page load. Verify what actually rendered:

```
browser_console(expression="document.body.innerHTML.substring(0, 500)")
```

Or for a specific content area:

```
browser_console(expression='document.getElementById("centerPanel").innerHTML.substring(0, 500)')
```

The `substring(0, N)` technique is essential because full `innerHTML` can be massive (>50K chars) and gets truncated by the tool. Start with 200-500 chars to confirm the right page is showing, then expand as needed with a larger substring or target specific elements.

If you want to check for specific card/content presence, search the full DOM for content markers:

```
browser_console(expression="document.body.innerHTML.indexOf('email-gmail') > -1 ? 'has Gmail' : 'no Gmail'; document.body.innerHTML.indexOf('int-config-panel') > -1 ? 'has config panel' : 'no config panel'")
```

Returns composite strings you can scan for — more efficient than manual substring inspection.

### When to Use

- Sidebar uses `<div onclick="showPage('X')">` instead of `<a>` or `<button>` elements
- `browser_click(ref)` returns success but snapshot content doesn't change
- Snapshot keeps showing the same view after clicking different nav items
- Need to verify a dynamic view rendered correctly after SPA navigation

### Anti-Patterns

- Always try `browser_click` first — it simulates real user interaction. Fall back to `browser_console` only when clicks don't produce the expected DOM changes.
- Don't loop on retries if `browser_click` plus the fallback pattern both don't navigate — the SPA may use synthetic React/Vue events that need a different approach (try `browser_vision` with `annotate=true` to find clickable refs, or navigate to the SPA's direct URL if it supports routing).
- Don't rely on `browser_snapshot` alone to confirm SPA navigation — always cross-check with `browser_console` and DOM inspection via `innerHTML`.
- Don't rely on `browser_vision` alone for page content — it may fail silently in local/stealth mode (timeout). Use DOM inspection as the primary content verification method, and vision as a supplement for spatial layout.

## Bot Detection — Which Sites Block Scraping

**High block rate (CAPTCHA / 403 / empty response):**
- Skyscanner → CAPTCHA wall
- MakeMyTrip → HTTP2 protocol error or empty
- EaseMyTrip → 502
- Ixigo → "too many requests"
- Most flight booking sites → JavaScript-rendered, need real browser sessions

**Usually works:**
- Google Flights → works with `browser_navigate` + form interaction
- Google News (news.google.com) → reliable for news gathering. See "News Research via Google News Browser" section.
- Wikipedia, news sites → generally open
- Airline direct sites (IndiGo, Air India) → usually work

## Bot Detection — Which Sites Block Scraping

### Verified Blocked (May 2026)
- **Google Search** — CAPTCHA wall after 1-2 requests. Returns `/sorry/index` page. Browser stealth mode without residential proxies does NOT bypass.
- **DuckDuckGo** — CAPTCHA wall ("Select all squares containing a duck") after 1-2 requests from non-residential IPs. The HTML-mode endpoint (`html.duckduckgo.com/html`) also blocks.
- **Bing** — Curl requests return empty/redirected content. Browser may work but not consistently.
- **Skyscanner / MakeMyTrip / Ixigo** — All block aggressively (CAPTCHA, HTTP2 errors, "too many requests").

### Workaround: Search API & Web Extract SSL/Timeout Failures → Browser Fallback

`web_search` and `web_extract` can fail with `_ssl.c:999: The handshake operation timed out` or DNS errors — this is a transient infra issue, not a permanent block. When they do, the browser tool (`browser_navigate`) is a reliable fallback because it uses a full Chrome process with TLS session reuse.

**Fallback chain:**
1. If `web_search` fails → try `browser_navigate` to Google News or Wikipedia
2. If `web_extract` fails → try `browser_navigate` to the target URL directly
3. If `browser_navigate` to a new URL also times out → fall back to the Google News homepage (`news.google.com`) topic navigation, which is the most reliable entry point. Avoid Google News search URLs (`/search?q=...`) which can also time out.
4. If all browser navigation fails → try `browser_console` fetch or read from the already-loaded snapshot text

**Known working fallback targets (SSL timeout resistant):**
- `news.google.com` — always works, no CAPTCHA
- `wikipedia.org` — always works, Wikipedia API also an option
- Direct company/blog sites — usually work if the origin server isn't rate-limiting

### Solution: Search APIs Instead of Scraping
Instead of scraping search engines via the browser, use dedicated search APIs:

| API | Cost | Speed | Best For |
|-----|------|-------|----------|
| **Tavily** (tavily.com) | Free 1K/mo, $20 for 5K | Fast (~500ms) | AI agent search + content extraction. Native Hermes backend. |
| **Brave Search** (brave.com/search/api) | Free 2K/mo, $5 for 15K | Fast (~500ms) | General search. Privacy-focused independent index. |
| **Serper.dev** | Free 2.5K/mo, $50 for 50K | Fast (~1s) | Google-quality results. Best price/performance. |
| **Exa** (exa.ai) | Free 1K/mo, $20/mo | Very fast (~300ms) | Semantic/neural search by meaning. |
| **Firecrawl** (firecrawl.dev) | Free 500/mo, $20/mo | Medium | Deep website crawling + content extraction. |

### Setup in Hermes
```bash
# Set Tavily as the search backend
export TAVILY_API_KEY="your-key"
hermes config set web.backend tavily
```

### When Browser Search Still Makes Sense
- Google Flights (reliable, works with browser_navigate)
- Wikipedia (no blocking, Wikipedia API also available)
- Direct site navigation (company websites, documentation)
- Sites with simple HTML that don't use aggressive bot detection

### Scraping X/Twitter Timelines Without Login

X walls off anonymous access hard. As of Sept 2026: `x.com` direct → login wall; `xcancel.com` → suspended (X Corp C&D); `sotwe`/`lightbrd`/`TwitterWebViewer` → Cloudflare-blocked; Nitter instances → dead. **`tweetviewer.com/<handle>` still worked**: `browser_navigate` → `browser_console` async JS loop clicking "Load more" + extracting/deduplicating tweets → append JSONL via terminal. Caveats: relative timestamps only (no time-series), no engagement counts, "most recent N" not true top-N. For 500+ posts, split into ~275-item chunks and fan out parallel `delegate_task` subagents (file toolset) that each return a topic→count+description+verbatim-examples taxonomy, then synthesize. Full recipe: `references/x-timeline-scraping-and-categorization.md`.

---

## News Research via Google News Browser

Google News (`news.google.com`) is the most reliable way to gather topical news when search APIs and web_extract are down. The browser tool renders it without CAPTCHA even from non-residential IPs.

### Navigation Pattern
```
1. browser_navigate("https://news.google.com")
2. Click relevant topic tab (Technology, Business, India, etc.) by ref
3. For sub-topics (AI, Entrepreneurship), click the inner tablist tab — these usually work (succeeded May 8, 13, 14, 2026; failed May 10, 2026). After clicking, call `browser_snapshot(full=True)` to confirm the view switched. If the snapshot still shows "Latest" content, read from the parent tab instead.
4. Scan headline text from the snapshot
5. Optional: scroll down (browser_scroll) to load more, then browser_snapshot(full=True) — NOTE: scrolling may not load new content into the snapshot (see Pitfalls).
```

### Topic Tabs to Use
| Tab Ref Label | What You Get |
|---------------|--------------|
| Technology → Artificial Intelligence | AI-specific news (models, funding, policy) |
| Technology → Latest | General tech headlines |
| Business → Latest | Live market data (Sensex, Nifty, Nikkei 225 indexes with % change) — appears in the snapshot as button/link text right below the heading |
| Business → Entrepreneurship | Indian startup funding, founder stories |
| Business → Markets | Deeper market coverage |
| India | Political/economic news for India context |
| Science | Research breakthroughs |

**Navigation hint for cron briefings:** After clicking the Business tab, the snapshot at "Latest" already includes index values (e.g. "Sensex 74,608.98 +0.07% +49.74"). Extract these before drilling into sub-tabs. If you need startup funding news, click the Entrepreneurship sub-tab. You can navigate multiple tabs in sequence within one session — Technology → AI for AI news, then Business → Entrepreneurship for startup news.

### Reading Headlines
Headlines appear as `link` elements in the snapshot with text like:
```
link "Chrome Is Quietly Installing a 4GB AI Model on Your Computer—And Putting It Back If You Delete It - Decrypt - Yesterday"
```
The snapshot includes the source (Decrypt) and recency (Yesterday). Extract the headline text and use that to decide which stories to dig into.

### Pitfalls
- **Shadow DOM**: Google News uses shadow DOM components. `browser_console` queries like `document.querySelectorAll` may return null. Read headlines from the snapshot text instead.
- **Sub-tab clicks may silently fail**: Clicking inner sub-tabs (e.g., Technology → Artificial Intelligence, Business → Entrepreneurship) returns success but the view may not switch. The snapshot continues showing "Latest". This is inconsistent — worked on May 8, 13, and 14, 2026 but failed on May 10, 2026. The AI sub-tab under Technology seems most reliable; Entrepreneurship under Business is hit-or-miss. If the snapshot doesn't change after a sub-tab click, read headlines from the broader "Latest" tab instead — don't retry the click.
- **browser_scroll may not load new content**: After `browser_scroll(direction='down')` + `browser_snapshot(full=True)` on Google News, the snapshot may be identical to the pre-scroll version. Google News uses virtual scrolling / infinite feed that the DOM snapshot may not capture. Read whatever headlines are visible in the initial snapshot and move on — don't loop on scrolling attempts.
- **browser_vision times out in local/stealth mode**: Screenshot-based analysis (`browser_vision`) may fail with "Failed to take screenshot (local mode): Command timed out after 30 seconds" when running without residential proxies. Do NOT rely on it for Google News content extraction — read headlines from the snapshot text instead.
- **Google News search URLs may timeout**: Navigating to `https://news.google.com/search?q=<query>` can time out (observed May 10, 2026). Use the main page topic navigation (`news.google.com` → click tabs) as the primary route.
- **No article body extraction**: The snapshot gives headlines and sources, not article text. For full article content, either navigate to the article link or use `web_extract` if it's working.
- **Google News is regional**: The `hl=en-IN&gl=IN&ceid=IN:en` query params matter. Navigate to `news.google.com` directly and it auto-detects region.

---

## Google Flights — Navigation Pattern

Google Flights is the most reliable live flight price source. Use this sequence:

### One-Way Flight Search
```
1. browser_navigate("https://www.google.com/travel/flights")
2. Switch to One Way: click ticket type combobox → select "One way"
3. Set destination: type in "Where to?" combobox → select from dropdown (click city name, not airport)
4. Set date: click Departure textbox → type "Jun 1" → press Enter
5. Click Search button
6. Wait for results → browser_snapshot(full=True)
```

### Reading Results
Results appear as list items with this pattern in the snapshot:
```
"From 6644 Indian rupees. Nonstop flight with IndiGo. Leaves ... at 5:35 AM ... arrives at 7:30 AM ... Total duration 1 hr 55 min."
```

To see prices across dates, click the Departure textbox on the results page — a calendar appears with per-day prices.

### Price Calendar Extraction
After opening the calendar, prices show as button text like:
```
"Thursday, June 4, 2026 , 5452 Indian rupees"
```
The page also announces the cheapest day in a StaticText element:
```
"The cheapest price shown is 5452 Indian rupees on Thu, Jun 4."
```

### Pitfalls
- **Date gets set to wrong field**: When the form has both Departure and Return fields, typing "Jun 8" into Departure might populate Return. Switch to "One way" first to avoid confusion.
- **Destination dropdown**: Always click the city name option (e.g. "Kochi, Kerala"), not the specific airport — the airport option sometimes doesn't resolve the city correctly in all contexts.
- **Results tab**: Switch to "Cheapest" tab (not "Best") to see price-sorted results.
- **Loading delay**: After clicking Search, call `browser_snapshot(full=True)` — the `full=True` parameter waits for the full page including dynamic content. Without it you may get a "Loading results" snapshot with no flight data.
- **browser_console returns null**: Google Flights uses shadow DOM and React, so `document.querySelectorAll` often returns nothing useful. Read prices from the snapshot text instead.

### Round-Trip vs One-Way
For flexible date searches (user can go any day in a range), use **One way** search:
- Avoids the confusing dual-date form
- Price calendar shows cheapest day clearly
- Then do a separate search for the return leg if needed

## Checking Live Prices Programmatically

For API-based price lookups (no browser needed), try:
- **Google Flights URL with encoded params** — unreliable, params are opaque
- **Kayak / Skyscanner APIs** — require paid API keys
- **Airline direct APIs** — IndiGo, Air India have booking APIs but require auth

Recommendation: use the browser tool with Google Flights — it's free, live, and reliable.

## Flight History (Past Performance) — Data Sources

For per-day historical flight status (on-time/delayed/cancelled over 2-3 weeks):

1. **FlightAware date pages** — best source. `https://www.flightaware.com/live/flight/<ICAO>/history/<YYYYMMDD>/<HHMM>Z/<ORIG>/<DEST>` (e.g. SEJ704, 1130Z = 17:00 IST dep). The raw HTML embeds `var trackpollBootstrap = {...}` — brace-match extract and json-parse it: main flight = first key in `flights`, fields `cancelled`, `flightStatus`, `takeoffTimes`/`landingTimes`/`gateDepartureTimes`/`gateArrivalTimes` (each has `scheduled`/`estimated`/`actual` epochs). CRITICAL: on cancelled pages `actual` is null and the estimated time sits in the "Gate Departure" slot — innerText alone can't distinguish cancelled from operated; trust the JSON flags. "Unknown Flight" title = no record that day.
2. **FlightAware rate-limits hard**: per-IP quota of ~6-9 raw curls, then every request returns a 146KB "Error" page (persists 30+ min). Browser sessions get Cloudflare "Just a moment" challenges that the automation browser cannot pass. Spread fetches across IPs (VPS) and extract EVERYTHING in one pass before the quota dies; don't waste the budget on re-fetches.
3. **FlightAware `/live/flight/<ICAO>/history`** (no date) shows the anonymous activity-log table (last ~14 days) server-rendered in browser innerText — good for the recent cancellation streak.
4. **FR24 API** (works via web_extract, no key): `https://api.flightradar24.com/common/v1/flight/list.json?query=SG704&fetchBy=flight&page=1&limit=50` — ~16 records (8 past days + 8 future), `status.text` Scheduled/Canceled, scheduled/real epochs, `page.more=false` when exhausted. fr24.com HTML and Flightera/Radarbox/Airportia are Cloudflare-blocked.
5. **Trip.com (VariFlight)** `us.trip.com/flights/status-sg705` — history table covers only ~7 days; ignores date query params. **FlightStats** shows current day only (history is paid). **OpenSky** historical = account-gated. **ixigo** = blocked.

Pitfall: sources disagree on TODAY's status (stale caches); trust the majority of FlightAware + FR24 + FlightStats.

### flight-search-india (archived)
This skill was merged into web-browsing as a narrow use case. The flight-search-india pattern (India-specific flight search via Google Flights) is now covered in the "Google Flights — Navigation Pattern" section above. The key insight preserved:

- **Only Google Flights works in India** — MakeMyTrip, Skyscanner, Ixigo, EaseMyTrip all block with CAPTCHAs or HTTP2 errors
- **Use One Way mode** — avoids return date confusion
- **Read calendar prices from snapshot** — no JS needed, appears as "Thursday, June 4, 2026 , 5452 Indian rupees"

### live-data-dashboard (archived)
This skill was merged as the dashboard is a consumer of web-browsing patterns, not a peer skill. The key insight preserved:

- **Self-contained HTML dashboard pattern**: Single-file HTML with fallback data that renders immediately, then upgrades with live fetches
- **CORS for file:// pages**: Use `https://api.allorigins.win/raw?url=<encoded_url>` proxy
- **Dual-rendering**: Show fallback data instantly, then background-fetch to upgrade
- **LEADING vs WON distinction**: Never mark trending data as "WON" until officially declared

The skill was archived because its core value (HTML dashboard building with fallback data) is a specific APPLICATION of web scraping patterns already covered in web-browsing.

## References
- `references/google-flights-bom-cok-jun2026.md` — BOM→COK June 2026 price data captured this session
- `references/google-news-ai-briefing-pattern.md` — worked example of Google News navigation for AI/Indian business news gathering (May 8, 2026)
- `references/research-workarounds-when-blocked.md` — workarounds for Google/DuckDuckGo CAPTCHA blocks, Wikipedia API fallback, and PDF delivery to Telegram
- `references/x-timeline-scraping-and-categorization.md` — X/Twitter no-login scraping (mirror landscape, async load-more loop, JSONL dedupe, relative-timestamp caveats) + parallel subagent topic-categorization pipeline
