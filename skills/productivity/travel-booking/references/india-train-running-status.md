# Indian Railways Live Train Running Status (headless)

## What works

**ConfirmTkt is the reliable, first-choice target.** Navigate the browser to
`https://www.confirmtkt.com/train-running-status/<train-number>` (e.g. `/11029`). It
server-renders the live status: departure time and delay at origin, last reported station with
delay minutes, and a per-station schedule showing scheduled vs expected arrival/departure with
the delay column per stop. That table is everything you need — no JS interaction required.

## What does NOT work (skip these)

- `whereismytrain.in/train/<number>` — 404; their URL pattern differs from the obvious guess.
- RailYatri (`railyatri.in/live-train-status/<number>`) — Akamai bot wall, empty render.
- Ixigo (`ixigo.com/trains/<number>`) — rate-limits headless sessions quickly.
- `etrain.info/train/<name>-<number>/live` — page shell renders but the live table sits behind a
  JS spinner; extraction comes back empty.
- NTES official (enquiry.indianrail.gov.in) — Angular app, needs JS state; only worth it if
  ConfirmTkt is down.

## Reading the result into an answer

1. Grep the page text for the origin station's departure line — compare scheduled vs actual to
   see how late the train LEFT (out-of-gate delay usually grows along the run).
2. Find the destination station's row — expected arrival/departure time plus its delay column.
   Report the EXPECTED time, the delay, and whether the delay is building or recovering across
   recent stations.
3. Verify the page's "today" date matches the current date — some pages default the date picker;
   if the last-updated timestamp is stale, the train may have already terminated and you are
   reading yesterday's run.
4. For meet-time advice: ETA at station + ~15 min platform-to-cab + drive time to the venue
   (Google Maps directions in the browser, add a traffic buffer) → propose a round meeting time
   that absorbs a further ~10 min of train slippage.
