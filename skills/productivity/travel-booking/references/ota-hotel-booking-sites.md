# OTA Hotel-Booking Sites — Headless Reality

Verified behavior for pulling live hotel rates for specific dates via the browser tool.

## Blocked (do not start here)

- **MakeMyTrip** — hotel pages render empty headlessly (no inputs, no content).
- **Expedia** — "Bot or Not?" interstitial wall even with valid `chkin/chkout` URL params.
- **Skyscanner, Ixigo, EaseMyTrip** — CAPTCHA / "too many requests" (same class).

## Working

- **Agoda** — hotel pages render headless and honor URL params:
  `?checkIn=YYYY-MM-DD&los=<nights>&rooms=1&adults=2&children=1`
  - Verify the dates landed by checking the page text shows the right check-in/check-out days.
  - Room price tiers are lazy-loaded: click the **"VIEW THIS DEAL"** button first, then read the
    page body text — `"from Rs. N"` is the cheapest total for the whole stay; per-tier totals appear
    as `"Original Price: ₹ N"` / `"₹ N"` line pairs. Map tiers to room names via nearby text.
  - The same URL with params intact is a working deep-link to hand the user — it opens with dates
    and occupancy pre-applied so he only picks the room and pays.
- **Official property sites** (e.g. resort .com/.in pages) — usually static; extract per-room
  "From INR X + Y taxes" blocks directly with web_extract.
- **Tripadvisor / Kayak** — good for cross-checking price bands and reviews, not for final totals.

## Pitfalls

- Do not trust an OTA "from ₹ N" snippet from search results — it is often off-season pricing;
  always verify with the dates applied in the live page.
- Breakfast is usually NOT in the base rate (add ~₹1,500/person/night at premium resorts); state
  the room-only vs breakfast-included split when quoting totals.
- After navigating, re-check the browser's current tab URL before scraping — a bot wall from a
  previous attempt can still be the active page and every subsequent extraction silently fails.
