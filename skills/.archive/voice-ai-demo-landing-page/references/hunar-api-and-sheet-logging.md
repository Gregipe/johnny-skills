# Hunar API + Google Sheets Logging Contract

Condensed from reading the reference repo (`Bajaj-HF-Voice-AI`). This is the load-bearing backend contract; a re-brand touches the frontend but leaves this intact.

## Hunar API

- Base: `https://api.voice.hunar.ai/external/v1`
- Auth: `X-API-Key` header (server-side only, from `.dev.vars` `HUNAR_API_KEY`).
- `POST /calls/` — create a call. Body forwarded verbatim. Client sends `{agent_id, callee_name, mobile_number, custom_data}`.
- `GET /calls/{id}/` — poll status. Returns call object with `status`, `started_at`, `ended_at`, `duration_seconds`, `user_speech_duration`, `engagement_status`, `answered_by`, `call_ended_by`, `recording_url`, `result` (object with agent-defined fields).

## Google Sheets logging (`/api/log`)

Flow: parse `GOOGLE_SERVICE_ACCOUNT_JSON` from env → build RS256 JWT in pure JS (WebCrypto `crypto.subtle.sign`) → exchange at `oauth2.googleapis.com/token` (grant type `jwt-bearer`) → append via `sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{RANGE}:append`.

The row is **23 hardcoded columns**, tail-driven by the agent's `result` fields:

```
Logged At, Call ID, Name, Number, City, Loan Amount (L), Language,
Status, Engagement, Duration (s), User Speech (s), Answered By, Call Ended By,
Started At, Ended At, Recording URL,
Concern, Summary, Callback, Callback Time, Existing Loan, Interest Level,
Existing Loan Bank, Existing Loan Characteristics
```

The last 8 are `result.*` fields — **these will differ per agent**, so a new client's agent means a new schema. A generic flatten (core call fields + iterate `result` keys) is the migration-proof choice.

## Endpoints (worker routes)

| Route | Method | Effect |
|-------|--------|--------|
| `/api/calls` | POST | proxy create-call → Hunar |
| `/api/calls/:id` | GET | proxy status poll → Hunar |
| `/api/log` | POST | append call row → Sheets |
| `/api/sheets/init` | GET | write header row (one-time setup; no auth — re-runs append dupes) |
| `/api/debug-key` | GET | **leaks first 50 chars of the service-account private key** — remove before prod |
| everything else | — | `env.ASSETS.fetch(request)` (static) |

CORS: `*`, methods GET/POST/OPTIONS.

## Client-side logging cadence

On terminal status the frontend: re-polls up to 8×3s for the `result` object → `POST /api/log` → waits 5 min → fetches final data → `POST /api/log` again. Net effect: **two rows per call** (initial + 5-min final). Any report built off this sheet needs dedup.

## Switching to a new agent (checklist)

1. `const AGENT.id` in `index.html` → new UUID.
2. `SHEET_ID` / `SHEET_RANGE` in `src/index.js` → new sheet/tab.
3. `/api/log` column array → new agent's `result` schema (or go generic).
4. `wrangler.jsonc` `name` → new worker name.
