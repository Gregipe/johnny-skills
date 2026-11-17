# Indian Election Data Sources

Verified sources and their quirks, as of May 2026.

**⚠️ CRITICAL**: On counting day, ALL data from every source is "LEADING TRENDS", not final results. No source will say "WON" until ECI formally declares. Wikipedia's `Won` column stays empty for 24-48 hours after counting starts.

---

## Government / Official

### ECI Results Site — `results.eci.gov.in`
- **Status**: Blocked by Akamai CDN. All programmatic access (curl, browser bots) gets HTTP 403 `Access Denied`.
- **Workaround**: None from server-side. User's real browser may work if they open it directly.
- **URL patterns**: `results.eci.gov.in/AcResults/` for assembly results (behind Akamai).

### ECI Voter Turnout App
- Mobile app with API backend. Not documented here — requires app reverse-engineering.

---

## Wikipedia (Best Programmatic Source)

### API Endpoint
```
https://en.wikipedia.org/w/api.php?action=parse&page=<PageTitle>&prop=text&format=json&origin=*
```

### Known Election Pages (2026)
| State | Page Title |
|-------|-----------|
| West Bengal | `2026_West_Bengal_Legislative_Assembly_election` |
| Tamil Nadu | `2026_Tamil_Nadu_Legislative_Assembly_election` |
| Kerala | `2026_Kerala_Legislative_Assembly_election` |
| Assam | `2026_Assam_Legislative_Assembly_election` |
| Puducherry | `2026_Puducherry_Legislative_Assembly_election` |

### Page Structure
- **Infobox**: `<table class="infobox">` — has summary data (turnout, previous election, current seats)
- **Results table**: `.wikitable` containing "Party", "Seats", "Won" columns
- **Results section**: Section index varies by page — use `prop=sections` API to find it
- **Caveat**: During counting day, `Won` column is often empty. Data fills in over 24-48 hours.
- **Query sections first**: `action=parse&page=<PageTitle>&prop=sections&format=json` — the returned `sections[index].line` tells you which section is "Results" vs "Seat projections"

---

## News Sources

### Google News RSS (Reliable for Headlines)
```
https://news.google.com/rss/search?q=<query>&hl=en-IN&gl=IN
```
- Returns XML with `<item>` elements containing `<title>` and `<link>`
- Titles contain seat numbers in headlines — good for quick scanning
- Works without API key
- **Limitation**: Headlines only, no detailed numbers

### Indian Express Live Blogs (Best Detail)
- URL pattern: `https://indianexpress.com/elections/<state>-assembly-election-results-2026-live-updates/`
- **Access method**: `browser_navigate(url)` → `browser_console(expression='document.body.innerText')`
- Renders full minute-by-minute coverage including exact seat counts, margin details, candidate names
- **Why it works**: The browser tool executes JavaScript, so the live blog renders fully
- Best source for: detailed trend data, constituency-level leads, margin percentages

### The Hindu Live Blogs
- URL pattern: `https://www.thehindu.com/elections/<state>-assembly/`
- Similar access pattern to Indian Express
- Good for: broader state-level trends with specific numbers

### Other News Sites (Unreliable for Scraping)
| Site | Bot Handling | Notes |
|------|-------------|-------|
| Times of India | Heavy JS | Unscrapeable |
| NDTV | Heavy JS | 403 on server-side, may work via browser |
| India Today | Moderate | Some pages load without JS |
| Economic Times | Heavy JS | Often 404 on result URLs |
| Hindustan Times | Heavy JS | Often 404 on result URLs |
| Republic World | Moderate | Browser access works |

### Browser Scraping Protocol
When curl/web_extract fail against JS-heavy news sites:
```python
1. browser_navigate(url=live_blog_url)
2. Wait for page to load (2-5 seconds)
3. browser_console(expression="document.body.innerText")
4. Parse the returned text for seat numbers, party names, lead margins
5. Cross-reference with Google News RSS headlines
```

---

## CORS Proxies

```javascript
// Primary (used in dashboard HTML for file:// pages)
const PROXY = 'https://api.allorigins.win/raw?url=';
function proxyUrl(url) { return PROXY + encodeURIComponent(url); }

// Fallback
// https://corsproxy.io/?<url>
```

---

## Date Reference: 2026 State Elections

| State | Election Date | Counting Day | Total Seats | Majority |
|-------|--------------|-------------|-------------|----------|
| Kerala | April 9 | May 4 | 140 | 70 |
| Assam | April 9 | May 4 | 126 | 63 |
| Tamil Nadu | April 23 | May 4 | 234 | 118 |
| West Bengal | April 23 & 29 | May 4 | 294 | 148 |
| Puducherry | April 9 | May 4 | 30 | 16 |
