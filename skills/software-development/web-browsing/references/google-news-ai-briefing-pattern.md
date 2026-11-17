# Google News AI Briefing Pattern — Worked Example (May 8, 2026)

## Context
Cron job needed to gather: AI news, Indian business news, behavioral economics stories for a daily briefing. `web_search` and `web_extract` both failed with `_ssl.c:999: The handshake operation timed out`.

## What Worked
Browser navigation to Google News, drilling into topic tabs by ref IDs.

## Exact Sequence

### Step 1: Navigate to Google News India
```
browser_navigate("https://news.google.com")
```
- Returns full snapshot with headlines, topic tabs, source names, recency
- No CAPTCHA, no timeout

### Step 2: Click Technology tab
The Technology tab had ref=e15 in the tablist:
```
browser_click(ref="e15")
```

### Step 3: Click Artificial Intelligence sub-tab
Inside Technology, the AI tab had ref=e40:
```
browser_click(ref="e40")
```
Then `browser_snapshot(full=True)` showed AI-specific headlines.

### Step 4: Click Business tab, then Entrepreneurship
```
browser_click(ref="e14")     # Business tab
browser_snapshot(full=True)
browser_click(ref="e25")     # Entrepreneurship sub-tab
browser_snapshot(full=True)
```

### Step 5: Scroll for more content
```
browser_scroll(direction='down')
browser_snapshot(full=True)
```

## Headlines Captured (May 8, 2026)

### AI News
1. **Chrome Is Quietly Installing a 4GB AI Model on Your Computer—And Putting It Back If You Delete It** — Decrypt, Yesterday
2. **Anthropic: Higher usage limits for Claude and a compute deal with SpaceX** — Anthropic blog, Yesterday
3. **Pakistani Techie Explains How She Got Hired At Anthropic, Urges Young Engineers To Embrace AI** — NDTV, 12h ago
4. **Anthropic's Boris Cherny once again reminds 'software engineering' is dead** — Times of India, 2d ago
5. **5 new ways to explore the web with generative AI in Search** — Google blog, 2d ago
6. **OpenAI: Supercomputer networking to accelerate large scale AI training** — OpenAI, 3d ago
7. **Bull AI launches 'Deep Research' to analyze 3,000+ stocks** — ET Edge Insights, 15h ago

### Indian Business News
1. **The Cracks Are Widening at Tata Group** — Bloomberg, 18h ago
2. **30 Startups To Watch: Startups That Caught Our Eye In April 2026** — Inc42, 4d ago
3. **MedVital, BigEndian, Vobiz.ai, JobsUPI, PinSec bag early-stage funding** — VCCircle, 2d ago
4. **Startup Kadapa Initiative Launched in Andhra Pradesh** — GK Today, 4d ago

### Markets (May 8, 2026)
- Sensex: 77,844.52 (-0.15%)
- Nifty 50: 24,326.65 (-0.02%)
- Nikkei 225: 62,696.35 (-0.22%)

## Limitations
- Cannot extract full article text from Google News via snapshot
- Ref IDs change across sessions (Google News renders dynamically)
- No way to search by keyword — must use topic tabs
- 815+ lines of snapshot output to scan through
- **Sub-tab clicks may silently fail (May 10 regression)**: The AI sub-tab within Technology didn't respond to clicks on May 10, though it worked on May 8. When this happens, read from the parent "Latest" tab.
- **browser_scroll may not load more headlines**: On May 10, scrolling down produced no new content in the snapshot. Get what you can from the initial page load.
- **browser_vision fails in local mode**: Don't rely on it — snapshot text is the only reliable content source.
- **Google News search URLs timeout**: Navigating to `news.google.com/search?q=...` timed out. Stick to homepage topic navigation.

---

## Update — May 14, 2026

### What Changed
- **Both sub-tabs worked**: Technology → Artificial Intelligence AND Business → Entrepreneurship both switched views successfully after clicking.
- **Business tab market data**: Sensex (74,608.98 +0.07%), Nifty (23,412.60 +0.14%), Nikkei (63,704.12 +0.68%) were visible directly in the "Latest" snapshot without drilling to Markets sub-tab.
- **Multi-tab crawl in one session**: Navigated Home → Technology → AI → Business → Entrepreneurship in sequence. All worked. No ref ID collision.

### Headlines Captured (May 14, 2026)

#### AI / Tech
1. **AI voice startup Vapi hits $500M valuation after winning Amazon Ring over 40 rivals** — TechCrunch, 2d ago
2. **OpenAI launches the OpenAI Deployment Company to help businesses build around intelligence** — OpenAI, 3d ago
3. **Nvidia VP has a message for every company cutting jobs for AI: You will not save money** — Times of India, 14h ago
4. **Google brings agentic AI and vibe-coded widgets to Android** — TechCrunch, 2d ago
5. **SAP Launches Unified AI, Automation Suite** — WSJ, 2d ago
6. **OpenAI's Daybreak Uses Codex Security to Hunt Software Vulnerabilities** — eWeek, Yesterday
7. **CoreWeave CEO sends blunt message to Nvidia stock investors** — thestreet.com, Yesterday

#### Indian Business / Startups
1. **Rupee at 95.74, hits all-time low as oil prices pressure economy** — Times of India, 16h ago
2. **India more than doubles gold, silver tariffs to defend rupee** — Bloomberg, 16h ago
3. **India's economic strength defies foreign outflow fears, S&P Says** — Economic Times, 23h ago
4. **Instafix raises Rs 7.55 crore pre-seed from Titan Capital, 8i Ventures** — Economic Times, 20h ago
5. **Moi Soi raises first institutional round from GVFL, Wipro Consumer Ventures** — Economic Times, 20h ago
6. **Instant house help startups see bookings top three million in April** — Economic Times, 3d ago
7. **From IPL Spotlight to ₹2,000 Crore Entrepreneurial Empire** — The Quint, 14h ago
8. **Gen Z pros embrace 'portfolio careers' as side hustles surge** — Times of India, Yesterday

#### Geopolitical
- **Trump arrives in Beijing for summit with Xi Jinping** — multiple sources (Al Jazeera, BBC, Guardian), live coverage
  - Trade, tech, Taiwan, Iran war expected to dominate talks
- **Congress to announce Kerala CM pick Thursday** — multiple sources (New Indian Express, The Hindu, NDTV, TOI)

#### Markets (May 14, 2026)
- Sensex: 74,608.98 (+0.07%)
- Nifty 50: 23,412.60 (+0.14%)
- Nikkei 225: 63,704.12 (+0.68%)
- SSE: 4,256.77 (+0.33%)
