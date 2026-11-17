# Production Hardening Patterns (June 2026)

Compilation of reliability infrastructure built for ARA's Hetzner deployment.
Run the QA checklist at `references/full-system-qa.md` after any infrastructure change.

## 1. Webhook Idempotency (Message Dedup)

### How It Works

`_handle_inbound_whatsapp` now accepts `message_id` from the Baileys sidecar.
Dedup uses the existing `_coach_processed_ids` dict from `app/dedup.py`:

1. **message_id check** — If present, check `_coach_processed_ids` dict
2. **content-hash fallback** — If no message_id, compute `(phone, md5(message))` and check `_coach_processed_hashes`
3. **TTL cleanup** — Stale entries pruned at `_COACH_ID_TTL` (60s) before each check
4. **File persistence** — `_try_save_dedup()` persists every check

### What It Prevents

Webhook retries from WhatsApp when the sidecar re-sends the same message.
Without this, the same inbound message creates duplicate conversations,
duplicate auto-responds, and duplicate stage transitions.

### Verification

```bash
ssh root@46.224.132.99 "journalctl -u ara-server --no-pager -n 200 | grep 'Duplicate message_id\|Duplicate content hash'"
```

### Tests

`tests/test_inbound_dedup.py` — 5 tests covering message_id, content hash,
different IDs, different content, and phone-only dedup.

## 2. Graceful Degradation (WA Queue)

### How It Works

`_send_or_queue(phone, text)` in server.py:
1. Retries `wa.send_message_sync` up to 3 times with 0.5s backoff
2. If all retries fail, queues to `/opt/ara/whatsapp_queue.json`
3. `/api/whatsapp/drain-queue` endpoint retries queued messages
4. Hermes cron `wa-queue-drain` runs every 5min
5. Messages dropped after 10 failed retries

### What It Prevents

Outbound WhatsApp messages lost when the sidecar is down (restart, reconnect).
Without this, auto-responses, coaching replies, and alerts are silently dropped.

### Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/whatsapp/queue-length` | Returns `{"queued": N}` |
| `POST /api/whatsapp/drain-queue` | Retries all queued messages |

### Verification

```bash
curl -s http://localhost:8766/api/whatsapp/queue-length
```

### Cron

Hermes profile `johnny`, job `wa-queue-drain`: `no_agent=true`, `every 5m`.
Script: `wa-queue-drain.sh` — `curl -s -X POST http://localhost:8766/api/whatsapp/drain-queue`

### Tests

`tests/test_wa_queue.py` — 6 tests covering empty queue, single message,
retention on failure, queue length endpoint, send_or_queue send/queue.

## 3. Database Backup

### How It Works

`/opt/ara/scripts/ara-backup.sh`:
1. Copies `/opt/ara/ara.db` to `/opt/ara/backups/ara-YYYYMMDD.db`
2. Compresses with gzip
3. Deletes backups older than 7 days

### Schedule

VPS crontab: `0 3 * * *` (daily at 3 AM IST)

### Verification

```bash
ssh root@46.224.132.99 'ls -la /opt/ara/backups/'
```

## 4. API Rate Limiting

### How It Works

In-memory FastAPI middleware:

| Endpoint Pattern | Rate Limit |
|-----------------|------------|
| `/api/whatsapp/inbound` | 10 req/min |
| `/api/whatsapp/` | 20 req/min |
| `/api/tenants/`, `/api/leads/`, `/api/threads/`, `/api/deals/` | 30 req/min |

Returns HTTP 429 with `Retry-After: 60` header. Resets on restart.

## 5. Error Logging Infrastructure

- **Error log:** `/opt/ara/logs/error.log` (5MB rotating, 3 backups, includes request_id)
- **Request-ID:** 12-char hex UUID per request, in every log line + response header
- **Thread health:** `/api/thread-health` tracks background thread status
- **Error log tail:** `/api/error-log?n=50` returns last N error lines

## 6. Auto-Respond Hallucination Prevention

Tool calls in `_ava_auto_respond` are now EXECUTED before markers are stripped.
Phantom-update detector: ack → re-prompt → execute → follow-up.
Prompt no longer allows prose-only claims about data changes.

Tests: `tests/test_auto_respond_ext.py` (8 tests).

## 7. Cron Job Pattern: no_agent Always Output

Hermes no_agent cron jobs with empty stdout show "error" status even if
the script ran correctly. Fix: always produce output:
```bash
echo "[ok] No errors found"
```
Applied to: `error-watcher`, `ARA daily watchdog`.

## 8. SQLite Write Retry

`_db_retry(max_attempts=3, base_delay=0.1)` decorator retries on
"database is locked" errors with exponential backoff (0.1s, 0.2s, 0.4s).

## Test Inventory

| File | Count | Area |
|------|-------|------|
| test_auto_respond.py | 15 | Auto-respond happy path |
| test_auto_respond_ext.py | 8 | Tool execution, phantom detection |
| test_bug_regression.py | 4 | Duplicate checks |
| test_dedup.py | 16 | Dedup persistence |
| test_e2e_smoke.py | 1 | Full pipeline smoke |
| test_inbound_dedup.py | 5 | Webhook dedup |
| test_inbound_webhook.py | 14 | Inbound routing |
| test_tool_parser.py | 20 | Tool-call parsing |
| test_voice_pipeline.py | 20 | Voice pipeline |
| test_wa_queue.py | 6 | Queue drain |
| **Total** | **216** | All deterministic |
