# Daily WhatsApp Morning Brief (cron `00fbbc53fd87`)

Recurring Hermes cron job (`30 7 * * *`, deliver: `local`) that sends Greg a WhatsApp morning
brief sourced from **production ARA**. Runs every day — this is the accumulated working recipe.

## Key facts

- **Recipient:** Greg's own WhatsApp `919582549236` (also confirmed as the authenticated user in
  the sidecar `/status` response).
- **Source of truth:** production ARA on Hetzner (`root@46.224.132.99`), **NOT localhost**.
  Localhost ARA is frozen since ~June 2026 — its `/api/actions` returns stale May test rows.
- **Send channel:** Baileys sidecar `POST /send` with body `{"phone": "...", "text": "..."}`.
  Returns `{"ok":true,"msgId":"<hex>"}` — verify a real `msgId` before reporting success.
  Do **NOT** use `/api/notify-owner` — it returns a false-positive `sent:true` and queues
  messages that never drain while the sidecar is disconnected.

## Run recipe

1. **Time gate** — only 07:00–22:00 IST (the schedule already fires at 07:30 IST).
2. **Health + sidecar check** (via `ssh root@46.224.132.99 '...'`):
   - `systemctl is-active ara-server ara-whatsapp-sidecar ara-tunnel`
   - `curl -s localhost:8766/api/health` → expect `sc_status:ok`, `db_status:ok`. A
     `system:"degraded"` label alongside core+DB OK is a known long-standing flag — surface it
     in the brief, do not abort.
   - `curl -s localhost:8767/status` → require `connected:true, authenticated:true`. If
     `awaiting_scan`, delivery is impossible — report the failure honestly and tell Greg to
     re-link via `https://qr.move78.work/link`.
3. **Gather data** from prod DB `/opt/ara/ara.db` (Python `sqlite3` — the `sqlite3` CLI is NOT
   installed on Ubuntu; transfer scripts via base64-over-ssh, never `scp`):
   - **Overdue** — `action_items` where `tenant_id='3e736242'`, `due_at < now`, outcome_state
     not resolved, **`owner='human'`**, excluding Ava's auto items, `Reminder:`-prefixed titles,
     and `[REGRESSION]` test rows. This recipe yields 18; the raw count including Ava/test rows
     is 27. Top 3 (Jun 19): "Follow Up", "Review", "Get Infosec Approval".
   - **Today** — `scheduled_actions` where `scheduled_at` is in today's IST window
     (= UTC `[yesterday 18:30, today 18:30)`). Historically 0 — newest row is Jul 15.
   - **Learnings** — `skills` and `ava_insights` with `created_at` in the last 24h. Store frozen
     since Jun 29 → typically 0.
   - **Objections** — `conversations` in the last 24h (0 = no new objections surfaced).
   - **Noise flag** — `learning_notifications`: `action_reminder` type accumulates **18/night**
     (one per overdue item, fired ~00:00 IST) and is never acknowledged (1,221 unacknowledged as
     of Sep 17). Worth surfacing as system noise.
4. **Compose** the brief (tight, ~90s read), send via `/send`, and confirm the returned `msgId`.

## Timezone note

DB stores dates as naive UTC strings (`'2026-06-19 05:30:00'`). Compare against
`datetime.utcnow()` (naive), never timezone-aware. Today's IST window in UTC = previous day
18:30 → today 18:30. Display in IST in the human-facing brief.

## Schema & transfer pitfalls (verified Sep 2026)

- **`action_items` has NO `lead_id`/`lead_name` columns.** It uses `action_type`, `ref_type`,
  `ref_id`, `deal_id`, `due_type`, `status`, `resolved_at`, `pending_tool_calls`. Overdue filter:
  `owner='human'`, exclude `outcome_state IN ('resolved','done','completed','cancelled','dismissed')`
  and `Reminder:`-prefixed / `[REGRESSION]` titles. Raw count ~37 → filtered 18.
- **`learning_notifications` uses `notif_type`, NOT `type`.** (`notif_type='action_reminder'`).
- **`skills` stores content in `key` + `value`, NOT `summary`.** SELECT `key`,`value`,`category`,
  `confidence`,`created_at`.
- **Write a defensive gather script** that probes `PRAGMA table_info(t)` and SELECTs only columns
  that exist (`sel(table, wanted)` helper). A hardcoded `SELECT lead_id...` crashes with
  `no such column`. A reusable version lives at `scripts/daily-brief-gather.py` — transfer it via
  base64-over-ssh and run `python3` on the server.
- **Never hand-write base64 for emoji/UTF-8 message text.** Manual base64 silently produced wrong
  glyphs (☰/📁/📠 instead of ☀️/📅/🧠). Write the message to a plain UTF-8 file, then
  `B64=$(base64 < file | tr -d '\n')`, pass it as a remote env var, and `base64.b64decode` on the
  server before POSTing.
- **Send without curl quoting hell:** POST `/send` from a small `urllib` script over ssh (no
  `requests` dependency assumed), body `{"phone":"919582549236","text":...}`. Verified response
  shape is `{"ok":true,"msgId":"<hex>"}`.

## Prior-run pattern

Read the last few outputs in `~/.hermes/profiles/johnny/cron/output/00fbbc53fd87/` to see the
exact message format and any one-off flags from the most recent runs (e.g. the Sep 15 sidecar
`awaiting_scan` failure, the Sep 16 successful send).
