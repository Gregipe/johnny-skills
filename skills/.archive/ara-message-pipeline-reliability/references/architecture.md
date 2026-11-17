# ARA Message Pipeline — Gap Analysis & Recovery Flow

## Recovered from (June 11, 2026 reliability push)

### Gap 1: Crash mid-processing
**Before:** In-memory dict. Server crash after message_id registered but before processing → message lost permanently.  
**After:** `processed_messages` table with two-phase status (`processing` → `done` / `failed`). On crash, status stays `processing`. Next webhook with same msg_id finds `processing`, waits 3s, reclaims it.

### Gap 2: Simultaneous webhooks (race condition)
**Before:** In-memory dict check-then-set pattern — two concurrent checks can both pass before either sets the flag.  
**After:** `INSERT INTO processed_messages (message_id, 'processing')` — UNIQUE constraint. Only one INSERT succeeds. The other gets IntegrityError and drops cleanly.

### Gap 3: Sidecar unreachable
**Before:** Exception propagated from `_req()` in whatsapp_sidecar_client.py. Message dropped.  
**After:** `_send_or_queue()` retries 3x, then queues to JSON file. Cron drains every 5 minutes.

### Gap 4: Delivery unknown
**Before:** `send_message_sync` returns `{"status":"sent"}` — no record of what was sent to whom.  
**After:** `SentMessage` table tracks every outbound msg_id. `/api/whatsapp/unconfirmed` shows messages stuck >2min.

### Gap 5: Sidecar crash between receive and forward (CLOSED June 11)
**Before:** Sidecar receives WS message in RAM, calls `trackForwarded(msg.id)`, then fire-and-forget `sendToARA()`. Crash between track and send → message lost. Sidecar on-disk dedup (5s debounce) makes it worse: if crash happens within 5s of receiving, dedup is persisted → message never retried.

**After:** `pending.json` at `/opt/ara/whatsapp-sidecar/pending.json`. Sync `fs.writeFileSync` persists the message **before** any forward attempt. On successful HTTP 200 from server, entry deleted. On restart, `loadPending()` replays all un-forwarded messages. 1-hour TTL, 1000-msg cap.

## Recovery Sequence per Failure Mode

| Failure Mode | Recovery Sequence | Time to Recover |
|-------------|------------------|-----------------|
| Webhook retry (duplicate msg_id) | UNIQUE constraint → INSERT fails → dropped cleanly | ~50μs |
| Server crash mid-processing | Status='processing' on disk; retry webhook waits 3s, finds stale, reclaims | 3s + next retry |
| Server crash after processing | Status='done' on disk; retry webhook finds 'done' → dropped | ~50μs |
| Sidecar crash before forward | `pending.json` persists before send; replay on restart | Next restart |
| Sidecar temporarily unreachable | Queue message, drain cron retries every 5min | 0-5 min |
| Sidecar down for hours | Queue accumulates. Drops after 10 retries (~50min). | ~50 min then drops |
| LLM hallucination (phantom update) | Ack → re-prompt → execute tool → follow-up | ~1-3s |
| LLM fails to produce tool call | Ack → re-prompt → tool still missing → "sorry, couldn't process" | ~2-4s |
| DB locked (SQLite busy) | `_db_retry` decorator, exponential backoff (0.1s, 0.2s, 0.4s) | ~0.7s max |
| Rate limit exceeded | HTTP 429 with Retry-After header | 60s window reset |
| Data loss | Daily backup at 3AM IST, 7-day retention | Next backup cycle |

## Health Endpoint Response

```json
{
  "system": "ok",
  "sc_status": "ok",
  "queued": 0,
  "unconfirmed": 0,
  "db_status": "ok"
}
```

- `system`: "ok" | "degraded" | "down"
- `sc_status`: sidecar connectivity
- `queued`: messages in `wa_queue.json` (sidecar down scenario)
- `unconfirmed`: `SentMessage` rows >2min old with no delivery check
- `db_status`: database SELECT 1 health
