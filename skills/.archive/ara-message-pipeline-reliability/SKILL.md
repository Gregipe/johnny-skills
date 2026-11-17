---
name: ara-message-pipeline-reliability
category: software-development
description: "ARA WhatsApp message pipeline — webhook ingestion, ACID dedup, graceful degradation, delivery tracking, and reliability patterns. Covers the full path from Baileys sidecar → webhook → dedup → process → respond → track."
version: 1.0.0
---

# ARA Message Pipeline Reliability

## Architecture Overview

```\nUser → WhatsApp → Baileys Sidecar\n                         │\n                    ┌────┴──────────────────────────┐\n                    │ Phase 0: Sidecar Persistence  │\n                    │ Before sending → write to     │\n                    │ pending.json (crash-safe)     │\n                    │ On startup → replay pending   │\n                    └────────────┬──────────────────┘\n                                 ↓\n                    POST /api/whatsapp/inbound\n                    POST /api/whatsapp/voice-inbound\n                                 ↓\n                    ┌─────────────────────────────────────┐\n                    │ Phase 1: ACID Dedup                 │\n                    │ ProcessedMessage table (UNIQUE msg_id)│\n                    │ INSERT status='processing' (atomic) │\n                    └─────────────┬───────────────────────┘\n                                  ↓\n                    ┌─────────────────────────────────────┐\n                    │ Phase 2: Lead Resolution            │\n                    │ Phone lookup → name fallback        │\n                    └─────────────┬───────────────────────┘\n                                  ↓\n                    ┌─────────────────────────────────────┐\n                    │ Phase 3: Repetitive-Message Gate    │\n                    │ SequenceMatcher > 0.7 within 5min   │\n                    └─────────────┬───────────────────────┘\n                                  ↓\n                    ┌─────────────────────────────────────┐\n                    │ Phase 4: Conversation Logging       │\n                    │ INSERT Conversation row             │\n                    └─────────────┬───────────────────────┘\n                                  ↓\n                    ┌─────────────────────────────────────┐\n                    │ Phase 5: Auto-Respond (if Ava)      │\n                    │ _ava_auto_respond()                 │\n                    │   → Phantom-update detection        │\n                    │   → Tool-call execution             │\n                    │   → wa.send_message_sync()          │\n                    │   → _track_sent_message()           │\n                    └─────────────┬───────────────────────┘\n                                  ↓\n                    ┌─────────────────────────────────────┐\n                    │ Phase 6: Dedup Finalization         │\n                    │ UPDATE processed_messages status=done│\n                    │ OR status='failed' on error         │\n                    └─────────────────────────────────────┘\n\nOn SEND failure:\n                    ┌─────────────────────────────────────┐\n                    │ _send_or_queue()                    │\n                    │ → Retry 3x (0.3s gap)               │\n                    │ → Queue to wa_queue.json if down    │\n                    │ → Drain cron every 5 min            │\n                    └─────────────────────────────────────┘\n\nDelivery tracking:\n                    ┌─────────────────────────────────────┐\n                    │ SentMessage table                   │\n                    │ /api/whatsapp/unconfirmed endpoint  │\n                    └─────────────────────────────────────┘\n\nSystem status:\n                    ┌─────────────────────────────────────┐\n                    │ /api/health (dashboard pollable)    │\n                    │ Sidecar ↔ Queue ↔ Unconfirmed ↔ DB  │\n                    └─────────────────────────────────────┘\n```

## Key Patterns

### 1. ACID Dedup (Two-Phase Status)

Replace in-memory dicts with a DB-backed `processed_messages` table.

**The pattern:**
1. `INSERT INTO processed_messages (message_id, status='processing')` — atomic claim
2. UNIQUE constraint on `message_id` ensures only one thread/retry wins
3. On success: `UPDATE status='done'`
4. On failure: `UPDATE status='failed'` — retries reclaim the message
5. On existing `status='processing'`: wait briefly (up to 3s) for peer thread to finish

**Why this closes both Gap 1 and Gap 4:**
- **Gap 1 (crash between dedup and processing):** If the server crashes mid-processing, the row stays `status='processing'`. After restart, the row has no ongoing transaction — it's just data. The retry webhook finds `status='processing'`, waits 3s, finds it still `status='processing'` (because the original worker died), and reclaims it.
- **Gap 4 (race condition):** Two simultaneous webhooks with the same `message_id`. Both try to INSERT. UNIQUE constraint — only one succeeds. The loser's INSERT raises an IntegrityError, and it drops the message cleanly.

**Database model:**
```python
class ProcessedMessage(Base):
    __tablename__ = "processed_messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String, nullable=False, unique=True)
    phone = Column(String, nullable=False)
    content_hash = Column(String)
    status = Column(String, default="processing")  # processing, done, failed
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    error = Column(Text)
```

**Code placement:** Inside `_handle_inbound_whatsapp()` at `/opt/ara/server.py`.

### 2. Graceful Degradation (Queue + Drain Cron)

When the WhatsApp sidecar is unreachable, queue messages and retry.

**The pattern:**
1. `_send_or_queue(phone, text)` tries `send_message_sync` with retry (3 attempts, 0.5s gap)
2. If all retries exhaust, appends `{phone, text, created_at, retries=0}` to `/opt/ara/whatsapp_queue.json`
3. Hermes cron `wa-queue-drain` runs every 5 minutes, calls `POST /api/whatsapp/drain-queue`
4. Drain endpoint retries each queued message; removes successful ones
5. Messages dropped after 10 retry attempts (infinite queue guard)

**Code placement:** `_send_or_queue()`, `_wa_drain_queue()`, `_wa_queue_load/save` in `/opt/ara/server.py`.

### 3. Delivery Tracking (SentMessage Table)

Track every outbound message for delivery observability.

**The pattern:**
1. `_track_sent_message(msg_id, phone, text)` called after every successful `send_message_sync`
2. Writes to `sent_messages` table with `status='sent'`
3. `GET /api/whatsapp/unconfirmed` returns messages >2min without confirmation
4. Tracked per-message: msg_id, phone, text, status, confirmed, attempted count

### 5. Sidecar Crash Persistence (pending.json)

**The problem:** The Baileys sidecar receives the WhatsApp message in RAM. `trackForwarded(msg.key.id)` marks it as forwarded in-memory. Then the fire-and-forget `sendToARA()` POSTs to the server. If the sidecar crashes between `trackForwarded` and the HTTP POST completing, the message is marked as forwarded (in RAM, persisted by dedup_state.json within 5s) but never reached the server. The message is lost.

**The fix (shipped June 11 2026):**
1. `addPending(phone, name, text, ownerReply, msgId, remoteJid)` — writes to `/opt/ara/whatsapp-sidecar/pending.json` **before** any `sendToARA` call. Sync write for crash safety.
2. `sendToARA_promise()` — wraps the old `sendToARA()` in a Promise so we can `await` it.
3. On successful POST (HTTP 200 received), `removePendingByMsgId(msgId)` deletes the pending entry.
4. `sendAudioToARA_promise()` — same pattern for voice messages.
5. On sidecar startup, `loadPending()` replays all un-forwarded messages via `sendToARA_promise()`.
6. Messages older than 1 hour are dropped (stale). Cap at 1000 pending messages.

**Code placement:** `/opt/ara/whatsapp-sidecar/index.js` — the `addPending/removePending/sendToARA_promise/sendAudioToARA_promise` functions near the top, and the replay block inside `startSocket()`.

**Edge cases:**
- Sidecar restarts before pending.json is written (unlikely with synchronous `fs.writeFileSync`).
- Server is down during replay — message remains in pending.json; retries on next restart.
- Audio messages cannot be replayed (the original msg object with audio stream is gone). These are dropped on replay. Voice notes that fail to forward are a known gap.

### 6. Health Endpoint

A consolidated traffic-light endpoint at `GET /api/health` that reports:
- `system`: "ok" | "degraded" | "down" — overall status
- `sc_status`: Sidecar connectivity via `wa.is_connected`
- `queued`: Number of messages currently in `wa_queue.json`
- `unconfirmed`: Number of `SentMessage` rows from >2 min ago with `confirmed=False`
- `db_status`: Database connectivity (runs `SELECT 1`)

Designed to be polled by the dashboard for real-time pipeline health.

### 7. Channel-Agnostic Notifications

`POST /api/notify-owner` accepts a JSON payload:
```json
{
  "type": "error",
  "channel": "whatsapp",
  "subject": "Sidecar disconnected",
  "body": "WhatsApp sidecar has been down for 5 minutes."
}
```
Supported channels: `whatsapp` (sends to admin phone), `log` (always, regardless of channel). Extensible for Telegram, email, etc.

### 8. Rate Limiting (Abuse Protection)

A FastAPI middleware at module level that limits requests per-IP per-60s window:
- `/api/whatsapp/inbound`: 10/min
- `/api/whatsapp/`: 20/min  
- `/api/tenants/`, `/api/leads/`, `/api/threads/`, `/api/deals/`: 30/min

Returns HTTP 429 with `Retry-After` header when exceeded. In-memory, resets on restart.

### 9. Database Backup

Daily backup via VPS crontab at 3 AM IST:
```
0 3 * * * /opt/ara/scripts/ara-backup.sh >> /var/log/ara-backup.log 2>&1
```
- Copies `/opt/ara/ara.db` to `/opt/ara/backups/ara-YYYYMMDD.db.gz`
- 7-day retention via `find ... -mtime +7 -delete`

### 4. Phantom-Update Detection + Auto-Fix

When the LLM claims an update ("I've updated the phone number") without a `[TOOL_CALL:]` block:

1. Log the phantom update
2. Send acknowledgment ("I've noted your request")
3. Re-prompt the LLM to produce the correct `[TOOL_CALL:]`
4. Execute the fixed tool calls
5. Send follow-up with results
6. If re-prompt also fails, send "Sorry, I wasn't able to process that"

**30-char window bug:** The update regex requires the data field (email|phone|name|stage|status|notes|company) within 30 characters of the claim verb. Long responses with intervening text slip through. When debugging phantom claims, check the character distance — add a second regex pass with wider window if the response exceeds ~40 chars.

### 4b. Phantom-Lookup Detection (Added June 2026)

Separate from update claims, the LLM sometimes claims to have "checked the system" or "found a lead" without any tool call. There is no `search_lead` or `find_lead` tool.

**Detection regex (in agent_chat, server.py):**
```python
_lookup_claim_re = re.compile(
    r"(?i)(?:already\s+(?:in|exists?)|found\s+(?:in|the)|checked\s+(?:the|in)|"
    r"currently\s+archived|archived\s+in|looked\s+up|searched\s+(?:the|for)|"
    r"in\s+the\s+system|under\s+that\s+name)"
)
```

**Patterns caught:** "already in the system", "found in the system", "currently archived", "checked the system", "looked up", "searched for", "under that name".

**Fix prompt:** When detected, re-call the LLM: "There is no search_lead tool. Do NOT claim you found a lead. Acknowledge the correction and re-propose or ask what to do."

**System prompt guardrail:** "Never claim to have checked the system or found a lead in the system without a [TOOL_CALL:] block. The lead list in your context is a static snapshot — you CANNOT look up archived leads."

**Test coverage:** TestPhantomLookup (3 tests), TestPhantomWindowBug (2 tests) in test_enforcer.py.

### 4c. PENDING Prefix for Unexecuted Tool Calls (Added June 2026)

When a tool call is generated but NOT confirmed, the DB stores `[PENDING - awaiting your confirmation]` + the original response. Without this prefix, the LLM saw the raw `[TOOL_CALL:]` in history and assumed it had executed — leading to hallucinated `search_leads` calls with unrelated names on follow-up (e.g. "Arun" when the lead was named Sahib).

**Pattern:**
```python
db_response = "[PENDING - awaiting your confirmation]\n" + response_original
```

**Effect:** The LLM reads `[PENDING]` and knows the tool was not executed. On "what's the update?" it responds "awaiting your confirmation" instead of generating phantom searches.

**Test coverage:** TestToolPendingStorage (1 test) in test_enforcer.py.

## Database Resilience — Retry Patterns (Added June 2026)

ARA uses SQLite (WAL mode) which supports concurrent reads but blocks writes. This session introduced systematic retry patterns to prevent transient SQLite lock errors from killing demo-critical operations.

### The Three Retry Layers

| Layer | Where | What it protects |
|-------|-------|-----------------|
| **execute_tool() calls** | `server.py` ~line 5190 (execution loop) | Every tool call that reads/writes the DB retries 3x with 150ms backoff |
| **agent_chat db.commit()** | `server.py` ~line 5233 (message save) | The final commit that saves user/assistant messages retries 3x with 150ms backoff |
| **Tool-specific retry** | `get_lead_detail` (line ~3800) | Gets its own 3-attempt retry for resolve_lead() specifically |
| **_db_retry decorator** | `database.py` | Available for any future DB operation. Retries on `sqlite3.OperationalError` matches "locked" or "busy" |

### Pattern: Retry Every Tool in the Execution Loop

The agent_chat execution loop now wraps `execute_tool()` in a 3-attempt retry:

```python
for _ex_attempt in range(3):
    try:
        _r = execute_tool(_tn, _args, db, wa, tenant_id)
        break
    except Exception:
        if _ex_attempt < 2:
            import time as _ex_t; _ex_t.sleep(0.15)
        else:
            raise
```

This catches ANY transient DB failure — not just SQLite locks, but also connection timeouts, serialization errors, and transient read failures. **All tools benefit from this safety net.**

### Pattern: Retry on db.commit()

The agent_chat commit (saving user + assistant messages + updating thread timestamp) is the most contended write in the system:

```python
for _cm_attempt in range(3):
    try:
        db.commit()
        break
    except Exception as _cm_e:
        if _cm_attempt < 2:
            import time as _cm_t; _cm_t.sleep(0.15)
        else:
            raise _cm_e
```

**Why this commit is special:** Every message exchange (user message + assistant response) fires this commit. During a demo where multiple messages are processed simultaneously, this is the single most likely point of SQLite contention.

### The `_db_retry` Decorator Pattern

For synchronous DB operations (not in agent_chat's async loop), use the decorator:

```python
from database import _db_retry

@_db_retry(max_attempts=3, delay=0.1)
def my_db_operation(db, ...):
    ...
```

Active handles: `sqlite3.OperationalError` with "locked" or "busy" in the message. Other OperationalErrors (table not found, syntax error) propagate immediately — they're not transient.

### What NOT to Do

- ❌ Add retry to EVERY DB call — most reads never contend. Focus on writes and read-heavy tools during concurrent writes.
- ❌ Use retry as a substitute for root-cause investigation — if a specific tool consistently fails on retry, the issue is deeper than contention.
- ❌ Long backoffs (>500ms) — SQLite contention resolves within milliseconds. 150ms is generous.
- ❌ Catch-all `except` without re-raising — if retries exhaust, the error MUST propagate. Silencing persistent failures is worse than crashing.

| Gap | Layer | What it is | Priority |
|-----|-------|-----------|----------|
| Delivery confirmation | WhatsApp | `send_message_sync` confirms sidecar accepted the request, not that WhatsApp delivered it. `/api/whatsapp/unconfirmed` surfaces stuck messages but no automated retry. | Low |
| Voice note replay on crash | Sidecar | Audio messages in `pending.json` cannot be replayed on restart (original msg object gone). Voice notes that fail at sendToARA time are silently dropped. | Low |
| Queue backpressure | Server | If sidecar is down for hours, `wa_queue.json` grows indefinitely. 10-retry limit is a weak cap. | Low |

### 10. Sidecar Document Sending (`/send-document` endpoint)

WhatsApp sidecar can now send documents/attachments via the Baileys `sendMessage(jid, { document: buffer, fileName, mimetype })` API.

**Endpoint:** `POST /send-document` — accepts `{ phone, filePath, fileName, caption }`. Returns `{ ok, msgId }` or `{ ok: false, error }`.

**sendDocument function:** Mirrors `sendMessage` — cleans phone, validates file exists, maps extension to mimetype, sends via Baileys, tracks for unread marking.

**MIME type map:** PDF, DOC/DOCX, PPT/PPTX, XLS/XLSX, PNG, JPG, TXT, CSV. Falls back to `application/octet-stream`.

**Code placement:** `/opt/ara/whatsapp-sidecar/index.js` — `sendDocument()` function + `/send-document` route.

**Pitfall — EADDRINUSE on restart:** Rapid sidecar restarts leave zombie processes holding port 8767. Kill with `fuser -k 8767/tcp` before restarting. Systemd `Restart=always` with `RestartSec=10` prevents this in production.

**Pitfall — auth session corruption:** Multiple rapid restarts corrupt the Baileys auth state, requiring QR re-scan. Symptoms: "not logged in, attempting registration..." → "connection closed" in loop. Fix: wait 60s between restarts, or re-link via QR code at `/qr` endpoint.

**Pitfall — loadLastSent before logger:** The `loadLastSent()` function references `logger` but was called at module init (line 141) before `logger` initialization (line 472). Moved the call below logger init.

### 11. WhatsApp Sidecar Systemd Service

Sidecar runs as a systemd service for auto-restart on crash:

```
[Unit]
Description=WhatsApp Baileys Sidecar
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/node /opt/ara/whatsapp-sidecar/index.js
Restart=always
RestartSec=10
```

After deploy: `systemctl daemon-reload && systemctl enable whatsapp-sidecar && systemctl start whatsapp-sidecar`.

### 12. Owner Phone Guard (send_to_owner / mark_unread_owner)

WhatsApp client (`BaileysWA`) now has locked-down methods that ONLY send to Greg's admin phone (919582549236), looked up from the DB each call:

- `wa.send_to_owner(text)` — sends WhatsApp to owner, refuses all other numbers
- `wa.mark_unread_owner()` — marks owner's chat unread, refuses all other numbers

All 5 admin notification paths in server.py use these instead of `send_message_sync(admin.phone, ...)`. This prevents live hallucination from reaching wrong numbers.

### 13. IST/UTC Conversion Centralization

All 20+ ad-hoc IST↔UTC conversion sites replaced with three functions in `app/config.py`:

- `ist_to_utc(dt)` — subtracts 5:30
- `utc_to_ist(dt)` — adds 5:30
- `parse_due_at(str)` — parses ISO string, converts IST→UTC, defaults date-only to 18:00 IST

Pitfalls caught: `create_action_item` tool skipped conversion for date-only strings (`len <= 10`). `set_cron` used UTC clock as IST. Both fixed in central functions.

## Test Coverage (216 total — June 11 2026)

| Test file | Tests | What it covers |
|-----------|-------|----------------|
| `tests/test_inbound_dedup.py` | 5 | Same msg_id dropped, different msg_id processed, content-hash dedup (no msg_id), content variation passes, message_id trumps content hash |
| `tests/test_wa_queue.py` | 6 | Empty queue, single drain, retain on failure, queue length, _send_or_queue queues on down, _send_or_queue sends when up |
| `tests/test_auto_respond_ext.py` | 8 | Tool-call execution in auto-respond, phantom-update ack/fix/fail flows |
| `tests/test_auto_respond.py` | 15 | Auto-respond happy path, errors, tool stripping, lead context, stage advancement |
| `tests/test_inbound_webhook.py` | 14 | Lead resolution by phone/name, webhook routing, owner vs lead detection |
| `tests/test_voice_pipeline.py` | 20 | Voice note processing, transcription, coaching-thread routing |

**Key metric: 0 tests broken during reliability refactoring.** Every new reliability feature ships with matching tests. See `test-first-release` skill for the binding rule.

## Related Skills

- `test-first-release` — Test coverage rules (binding: every release must expand test suite)
- `whatsapp-sidecar-debugging` — Debugging the Baileys sidecar
- `ara-sidecar-reliability` — Sidecar port-conflict prevention, health-check hardening, watchdog
- `ara-qa-gate` — QA workflow run before every deploy
- `ara-production-deploy` — Deploy ARA to production Hetzner server
- `ara-server-healthcheck` — Post-restart verification

## References

- `references/document-ingestion-whatsapp.md` — WhatsApp sidecar document detection, ARA inbound endpoint, import_leads_from_text tool, and no-hallucination workflow
