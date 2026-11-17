---
name: flight-search-india
description: "Search for cheap flights in India via browser — proven approach that avoids bot blocks."
tags: [flights, travel, india, google-flights, browser]
---

# Flight Search India

## Go Straight to Google Flights
All other Indian flight sites (MakeMyTrip, Skyscanner, Ixigo, EaseMyTrip) block bots with CAPTCHAs, HTTP2 errors, or rate limits. **Only Google Flights works reliably.**

## Step-by-Step

1. Navigate to `https://www.google.com/travel/flights` (plain URL — no encoded `tfs=` params, they get ignored)
2. **Switch to One Way immediately** if only searching outbound — avoids return date confusion
3. Type destination in "Where to?" → click the city option (not airport) from dropdown
4. Type date in "Departure" field (e.g. `Jun 1`) → press Enter
5. Click **Search**
6. When results load, **open the date picker (click the Departure field)** — it shows a full calendar with prices for every date
7. **Read prices directly from the snapshot text** — they appear as e.g. `"Thursday, June 4, 2026 , 5452 Indian rupees"` — no JS needed
8. Click the cheapest date → read flight listings from snapshot

## Pitfalls
- Don't use deep-link `tfs=` encoded URLs — Google ignores them without a valid session
- Don't use Round Trip mode when only checking outbound prices — the date picker gets confused and reassigns dates
- Don't try JavaScript to extract prices — the accessibility snapshot already contains them in plain text
- Calendar price data appears in the snapshot as `"[Day], [Month] [Date], [Year] , [price] Indian rupees"` — parse it directly
- Vision model must be `claude-3-5-haiku-20241022` (not `claude-haiku-3-5`) — wrong name causes 404

## Reading Calendar Prices from Snapshot
When the date picker is open, the snapshot rows look like:
```
"Monday, June 1, 2026 , 6644 Indian rupees"
"Tuesday, June 2, 2026 , 5974 Indian rupees"
```
Extract all June dates in one pass — no clicks needed.
