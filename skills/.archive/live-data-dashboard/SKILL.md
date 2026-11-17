---
name: live-data-dashboard
description: >-
  Build self-contained HTML dashboards that aggregate live data from multiple
  web sources. Covers multi-source scraping strategy (Wikipedia API, Google News
  RSS, news sites), CORS proxy handling, fallback data preloading, and
  auto-refresh UI patterns. The result is a single-file HTML page the user can
  open in any browser — no server, no install.
category: software-development
tags:
  - dashboard
  - scraping
  - data-aggregation
  - wikipedia
  - news
  - fallback
  - CORS
---

# Live Data Dashboard

Build a self-contained `.html` dashboard that fetches live data from web sources and displays it in a clean, refreshable UI. The user opens the file directly in their browser — no server or tools needed.

## When to Use

- User asks for a "dashboard" or "live view" of data from multiple sources
- Data is public but not behind a restrictive login
- The user wants something they can open, refresh, and share as a file

## Architecture Pattern

```
┌─────────────────────────────────────────────┐
│  Single HTML file (self-contained)          │
│                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Card 1   │  │ Card 2   │  │ Card 3   │  │
│  └──────────┘  └──────────┘  └──────────┘  │
│                                             │
│  JavaScript fetch layer:                    │
│  ┌─ Primary: Wikipedia API ─────────────┐   │
│  ├─ Secondary: Google News RSS          │   │
│  ├─ Fallback: preloaded verified data   │   │
│  └─ Proxy: CORS proxy for file://       │   │
└─────────────────────────────────────────────┘
```

## Step-by-Step

### 1. Research Data Sources

Before writing code, find what sources are available and test them. Common patterns:

| Source | When | Method |
|--------|------|--------|
| Wikipedia API | Structured data exists | `action=parse&page=<title>&prop=text&format=json` |
| Google News RSS | Current headlines needed | `https://news.google.com/rss/search?q=<query>&hl=en-IN&gl=IN` |
| Government site | Official results | Usually behind bot-detection (Akamai, Cloudflare) |
| News sites | Human-readable articles | JS-heavy, unreliable for scraping |

**Pitfall**: Government election sites (e.g., `results.eci.gov.in`) are behind **Akamai** CDN. Curl and bots get `Access Denied`. Always test with `curl -sI` first. If blocked, fall back to Wikipedia + news.

**Pitfall**: Wikipedia pages for current events have results tables with empty `Won` columns during the counting day. Preload fallback data from confirmed news headlines.

### 2. Fetch Data from Wikipedia API

Use the REST endpoint for machine-readable content:

```
https://en.wikipedia.org/w/api.php?action=parse
  &page=<PageTitle>
  &prop=text
  &format=json
  &origin=*
```

Parse the returned HTML looking for `.wikitable` tables. Filter for tables containing "seat" or "won". Extract party names from the first column, seat counts from the last column.

**Pitfall**: Wikipedia table rows alternate between alliance-header rows (`<th colspan>`) and party-data rows (`<td>`). Track `currentAlliance` as you iterate so you can assign parties without obvious names.

**Pitfall**: On macOS, `grep -P` doesn't exist. Use `grep -E` or Python's `re` module instead.

### 3. Handle CORS for file:// Pages

When the HTML dashboard is opened as a local file (`file://`), JavaScript `fetch()` calls to external APIs are blocked by CORS. Solutions:

- **Best**: Use a public CORS proxy: `https://api.allorigins.win/raw?url=<encoded_url>`
- **Fallback**: `https://corsproxy.io/?<url>`
- Warn the user that if the proxy is down, data won't load (fallback data still shows)

### 4. Preload Fallback Data

Before attempting live fetches, embed verified fallback data in the JavaScript. This ensures the dashboard always shows *something* useful:

```js
const FALLBACK = {
  'State Name': {
    updated: 'May 4, 2026',
    status: 'Counting in Progress',
    parties: [
      { id: 'bjp', seats: 175, status: 'leading' },
      ...
    ]
  }
};
```

**Where fallback data comes from**: News headlines collected during the research phase. Each headline was verified from multiple sources before embedding.

### 5. Dashboard UI Template

Dark theme, card-based layout:

```
┌─ Card Header ──────────────────────────┐
│  🟢🔴 State Name    120 seats · 61 to win│
├────────────────────────────────────────┤
│  ▌ BJP    ████████████████░  78  LEADING│
│  ▌ TMC    ██████████░░░░░░  42         │
│  ▌ Others ██░░░░░░░░░░░░░░  3          │
├────────────────────────────────────────┤
│  🏆 BJP crosses majority mark!        │
└────────────────────────────────────────┘
```

Key CSS choices:
- `background: #13131a` for dark card, `#1a1a24` for rows
- `seat-bar-fill` uses `transition: width 0.6s ease` for smooth updates
- Leading party gets green left border (`border-left: 3px solid #22c55e`)
- Winner gets green background tint (`background: #1a2e1a`)

### 6. Auto-Refresh

`setInterval(refreshData, 5 * 60 * 1000)` for auto-refresh. Manual button for immediate refresh. Show "Last updated: HH:MM:SS IST" timestamp.

### 7. File Delivery

On macOS, `write_file` may fail on `~/Desktop/` due to sandbox restrictions. Workaround:

```python
# Write to /tmp first
write_file(path='/tmp/dashboard.html', content=html_content)
# Then copy
terminal("cp /tmp/dashboard.html ~/Desktop/Dashboard_Name.html")
terminal("open ~/Desktop/Dashboard_Name.html")
```

### 7a. Critical: LEADING vs WON Distinction

During counting day, **every data point is a lead/trend, not a final result** until the Election Commission formally declares the seat. Never mark a party as "WON" unless the ECI has officially declared that seat/result. The user will call you out on this.

**Rules of thumb:**
- **LEADING**: Party is ahead in trends/counting. Use for all data on counting day until final declaration.
- **WON / DECLARED**: Only after ECI formally declares. Typically 24-48 hours after counting day for all seats.
- **TRAILING**: Party behind the leader but in a competitive position.
- **Majority crossover ≠ win**: A party crossing the majority mark in trends is LEADING (crossed majority), not WON.

Implementation pattern — show this distinction in the UI:
```js
// In render function
if (isDeclaredByECI) {
  badge = '<span class="badge badge-winner">✓ WON</span>';
} else if (leads && crossedMajority) {
  badge = '<span class="badge badge-leading">LEADING (crossed majority)</span>';
} else if (leads) {
  badge = '<span class="badge badge-leading">LEADING</span>';
} else if (trailing) {
  badge = '<span class="badge badge-trailing">TRAILING</span>';
}
```

Add a prominent notice banner at the top of the dashboard:
```
📢 COUNTING IN PROGRESS — All figures are LEADING TRENDS.
No results have been formally declared by the ECI.
```

**Pitfall**: Seat counts swing dramatically during counting as different regions report. A party may appear to be at 120 seats at 9 AM and 80 at 10 AM when South Bengal seats come in. Always note the data source timestamp.

### 7b. Browser-Based Scraping for JS-Heavy News Sites

When `curl` and `web_extract` fail against JS-heavy news sites (NDTV, Indian Express live blogs, The Hindu live coverage), use the browser tool:

```python
1. browser_navigate(url=live_blog_url)
2. browser_console(expression="document.body.innerText")  # Extracts full rendered text
3. Parse headlines, seat counts, and key names from the output
```

**Why `browser_console` works**: It runs JavaScript in the context of the loaded page, returning the fully rendered DOM text. This bypasses JS-heavy paywalls and lazy-loaded content that simple HTML requests can't access.

**Best sources for JS-heavy sites**:
- Indian Express live blogs: minute-by-minute coverage with exact seat counts, margin details, candidate names
- The Hindu live blogs: broader state-level trends with specific numbers
- Google News: use RSS for structured headlines, then browser-scrape individual articles

**Rate limiting**: If collecting data for multiple states, space out browser_navigate calls by 2-3 seconds to avoid bot detection. Some sites (NDTV) will 403 if you request too fast.

Cross-reference data from at least **two sources** before embedding as fallback. Google News RSS provides headlines; individual articles provide the detailed numbers.

### 7c. Data Verification Pattern for Counting Day

```
1. Google News RSS → get headlines with seat numbers
2. Browser-scrape 2-3 live blogs → get detailed constituency-level data
3. Wikipedia API → check if results tables have been populated
4. Cross-reference all three → if 2 of 3 agree, embed as fallback
5. Label everything "LEADING (not declared)" until ECI confirms
```

### 7d. Dual-Rendering Pattern (Show Immediately, Upgrade When Available)

Don't make the user wait for live fetches. Use this pattern:

```js
// 1. Start with verified fallback data immediately
let data = JSON.parse(JSON.stringify(VERIFIED));
renderAll(data);  // Shows instantly

// 2. Then attempt live fetches in background
for (const stateKey of Object.keys(STATES)) {
  const wiki = await fetchWikiResults(stateKey);
  if (wiki && Object.keys(wiki).length > 0) {
    data[stateKey] = upgradeWithWikiData(data[stateKey], wiki);
  }
}

// 3. Re-render with any fresh data
renderAll(data);
```

This means the user sees cards within milliseconds, and they get upgraded as data arrives. Don't show a loading spinner while fetching — show data first, upgrade silently.

### 7e. Concurrent Data Gathering for Multiple States

When collecting data for N states/regions, run independent queries in parallel:

```python
# Parallel: Wikipedia lookups (independent)
# Parallel: Google News RSS queries (independent)
# Sequential: Browser scraping (rate-limited per site)
```

Wikipedia API calls and Google News RSS are independent per state — use parallel loops. Browser scraping should be sequential with 2-3s delays between navigations to avoid bot detection.

The data collection pattern from this session (May 4, 2026):
1. **Wikipedia API** for WB, TN, KL (parallel) → got table structure, empty Won columns
2. **Google News RSS** for each state (parallel) → got headlines with seat numbers
3. **Browser scrape Indian Express** live blogs (sequential) → got detailed verified data
4. Cross-referenced all three → embedded as VERIFIED fallback

### 7f. Google News Query Strategy for Election Seat Counts

To find the latest seat numbers from news headlines, use targeted queries:

```
https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN
```

Effective query patterns (ranked by reliability):
```
1. "{state} election result 2026 {top_party} seats"  → Most targeted
2. "{state} final result 2026 seats"                  → Best for final tally
3. "ECI {state} results declared 2026"                → Official results
4. "{state} election results 2026 live"               → Broad coverage
```

Extract seat numbers from RSS titles using regex:
```python
titles = re.findall(r'<title[^>]*>(.*?)</title>', rss_html)
for title in titles[1:8]:  # Skip first (Google News itself)
    print(title[:250])
```

## Verifying the Dashboard Works

1. The file opens in the browser without errors
2. Cards render with fallback data immediately
3. Clicking "Refresh" attempts live fetch and updates cards
4. The summary banner at top shows winner/leader for each state
5. Responsive: works on mobile (single column) and desktop (3 columns)

## Pitfalls

- **ECI / government sites** block bots at the CDN level. Use Wikipedia API + news RSS as primary sources, not ECI directly.
- **Wikipedia tables** during live events often have empty `Won` cells; the table structure (alliance headers, empty rows) makes parsing fragile
- **CORS proxies** are unreliable — always embed fallback data as a safety net
- **File path permissions** on macOS: `write_file` may silently fail on `~/Desktop/`. Always verify with a `ls -la` or use `/tmp` + `cp`
- **SSL handshake timeouts** can affect `web_search` and `web_extract` tools; have a terminal-based curl fallback ready
- **Google News RSS** returns XML, not HTML — use `DOMParser` to parse it client-side
- **Seat distribution**: Some seats go to "Others / Unclear" if news reports don't break them down by party. Include an "Others" row in the card rather than leaving a gap
- **LEADING vs WON is not a minor detail**: Users WILL correct you if you mark trending data as final. On counting day, NO seat is "WON" until ECI formally declares. Always use "LEADING" / "TRAILING" / "TRENDING" badges. The only exception is when you're viewing results 48+ hours after counting day and the ECI has declared all seats.
- **Seat trends are volatile on counting day**: A 9 AM trend showing BJP at 150 seats can dip to 120 by 10 AM when a different region's votes come in. Always timestamp your data and note that it's a snapshot. Don't assume a trend is the final tally.

## References

See `references/election-data-sources.md` for known Indian election data sources, their quirks, and endpoints.

See `references/tn-election-2026-data.md` for the verified data from the May 4, 2026 TN/WB/KL elections.
