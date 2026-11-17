---
name: travel-booking
description: "Use when planning or booking Greg's trips — hotels, flights, options."
version: 1.0.0
author: Johnny
license: MIT
metadata:
  hermes:
    tags: [travel, booking, hotels, trips, planning, family]
    category: productivity
---

# Travel Booking for Greg

## When to Use

- Greg asks for hotel, flight, or itinerary help for a personal or family trip
- Researching a destination, building a stay shortlist with costs, or setting up a booking for him

Greg plans personal and family trips (hills, religious/cultural destinations) and expects Johnny to
research, shortlist, and set up bookings — while Greg stays the decision-maker and the payer.

## Workflow

1. **Prefs BEFORE searching — Greg asks for this explicitly.** Use the clarify tool, ≤5 questions:
   who's traveling (solo/couple/family + kids' ages) · budget per night · stay style (hotel/resort/
   homestay/no preference) · what matters most (multi-select: view / comfort / trek access / price) ·
   how far to take it (shortlist only / help book the winner / full plan). Never search first and guess.
2. **Research** — web_search for the destination's options, then verify live rates on official
   property sites or an OTA. See `references/ota-hotel-booking-sites.md` for which sites work headless
   and how to pull live per-room totals for exact dates.
3. **Shortlist format (WhatsApp)** — 3-5 named options. Each: what it is, per-night price with taxes,
   stay-length total, one honest pros/cons line tied to his stated priorities. End with ONE
   recommendation and why. Flag peak-season price pressure against his budget band — never hide it.
   Label estimates vs live-verified quotes.
4. **Booking handoff** — his default is "set everything up, I pay myself". Collect: guest names as per
   ID, kids' ages, phone + email, room category. Produce a READY-TO-PAY link with dates and occupancy
   pre-applied plus the exact total, and list what he must enter at checkout (guest names, breakfast
   add-on). Offer the property's direct WhatsApp/UPI line as fallback when OTAs block.
5. **Follow through** — confirm the reservation after he pays; add it to his calendar (no back-to-back
   rule) and the dashboard Tasks board if it becomes a to-do.

## Ground Transport (cabs, drivers)

Airport transfers and multi-day driver hires follow the same shape as hotels:

1. Research regional operators via web/Instagram/Facebook — collect name, phone/WhatsApp number,
   and one line of reliability evidence (Google-verified reviews, app, established brand).
2. Recommend a split when it fits: an app-based aggregator (e.g. Wizzride for Meghalaya) for the
   fixed airport-transfer leg, a local operator for the multi-day car+driver package.
3. Draft ONE enquiry message covering: dates, pickup point and time (flight landing + 30 min),
   passenger count + kid ages, route by nights, preferred car class, and four asks — total cost,
   driver food/lodging allowance in or out, fuel/tolls/parking in or out, advance % and payment
   method. The identical message to every vendor is what makes quotes comparable.
4. Sending the enquiry to any vendor is external comms — Greg's confirmation first. If he asks,
   send it via the WhatsApp gateway bridge (see whatsapp-gateway-ops skill); replies land on HIS
   phone, not in the agent chat.
5. When quotes return, compare itemized totals and flag driver-allowance surprises — operators
   often quote without driver allowance, then add ₹400–500/day after you engage. Vendor wording
   like "everything included" or "driver night charge included" still leaves driver FOOD
   ambiguous: night charge covers lodging only. Get food in/out confirmed in writing before
   accepting any quote, and ask for advance % and payment method if the reply omits them.
6. Benchmark quotes against `references/ne-india-cab-rates.md` — the TTAA official rate chart,
  street-level daily bands, and known Meghalaya vendor contacts with WhatsApp numbers.
7. **Train running status (Indian Railways)** — when a trip or pickup hinges on a train
  (meeting someone at the station, catching one), use `references/india-train-running-status.md`:
  the site that actually works headless, the blocked ones to skip, and how to read live delay
  plus per-station ETAs into a meet-time recommendation.

## Flight Tickets (PDFs Greg sends)

When Greg sends a flight ticket/PNR PDF (or any itinerary):

1. **Parse** — `read_file` extracts text-layer ticket PDFs directly; OCR only if scanned.
2. **File** — update the trip working file (`/root/trips/<trip>-<dates>.md`) with the full record: PNR, flight numbers, times, seats, baggage, fare, payment card last-4 (redacted), and traveler names. Note per-traveler seats and which PNR covers whom.
3. **Verify dates against OTHER arrangements** — the ticket date is the truth, not what Greg said earlier. If a pickup (driver) or hotel was told a different date, flag the mismatch immediately and tell him to correct it.
4. **Flag the gotchas** — extract and surface only the ones that bite: codeshare segments with counter-only check-in (no web check-in), tight connections (calculate layover and give the one practical move), baggage weight limits, and the payment-card-at-check-in rule when the payer differs from the passenger.
5. **Set one-time flight-status crons** — one per travel day, firing ~3h before departure (IST): prompt instructs web_check of flight status and a short WhatsApp brief (status, connection pressure, counter/gate timings). One-shot cron schema: `schedule` = ISO timestamp, omit `repeat` (repeat is an integer count; the string 'once' fails validation).

## Destination Notes

Per-destination depth lives in `references/` — see `references/meghalaya-destination-notes.md` for the Meghalaya corridors, guide rules, November daylight math, and the itinerary gap checklist. Create one topical file per recurring destination; extend it on every trip instead of re-researching from scratch.

## Trip Options & Ranking

When Greg asks for destination OPTIONS ("give me a few options", "think laterally", "rank them") rather than one destination's logistics, follow `references/trip-options-ranking.md`: lateral-option generation, the 4-axis scoring (activity/relaxation/connectivity/affordability), per-person transport costing for group trips, and December-peak fare research.

## Rules

- **Greg pays, always.** Setup and prep are Johnny's; money movement is Greg's. Never enter or handle
  card details, never confirm or charge anything on his behalf — hand over the final payment step.
- **Kids change room math** — suites often cap at 2 adults + 1 child; check max occupancy and extra-bed
  policy before recommending, and ask ages when children are involved.
- **Quote the live number for HIS dates** — aggregator prices swing hard by channel and season
  (e.g. hill-station peak months); stale search snippets mislead. Verify, then quote with source.
- **WhatsApp replies stay human** — no tool narration or command noise; short status lines while working
  (see user-interaction-style skill).
- Prefer self-pay booking links over creating reservations from Johnny's own browser session —
  a half-finished agent-side reservation can duplicate or clash with Greg's own booking.
- **Car-class recommendations must be quantified** — when recommending between classes (e.g.
  Ertiga vs Innova), give the concrete differences (legroom, ride quality, luggage capacity)
  and say outright that the cheaper class is viable. Greg challenges recommendations that read
  as taste rather than tradeoff.
- **Working file per trip** — save `/root/trips/<trip>-<dates>.md` with the itinerary,
  quote table (vendor, car, price, negotiated), vendor contacts, and the pre-lock checklist
  (driver food allowance, advance %). Update it as quotes and plans change so any session
  can pick the thread up.
- **Verify the actual day of week before quoting weekly schedules.** Mass timings, market days
  (Mapusa is Friday, Anjuna Wednesday), ferry timetables and museum closures are weekly — compute
  today's real weekday from the current date before citing them. Trip days blur for everyone,
  and Greg catches wrong-day claims instantly.
- **Price transport per person for group trips.** With 6-8 travelers, flights ×N usually dwarf
  two SUVs × 4 days — a drive option can save ₹50k+ per trip. Compute the total family transport
  bill for every option before ranking affordability, and present both per-person and total numbers.
