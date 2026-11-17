---
name: travel-booking
description: "Use when planning or booking Greg's trips — hotels, flights."
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
   often quote without driver allowance, then add ₹400–500/day after you engage.

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
