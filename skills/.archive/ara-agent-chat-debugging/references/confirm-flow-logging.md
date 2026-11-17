# Confirmation Flow Logging

When debugging "I said yes and she did something completely different" or "she didn't create the action I asked for", add structured logging at 6 decision points.

## Quick Setup

```python
# Near the top of server.py
_cf_log = logging.getLogger("ara.confirm")
```

Then add log calls at each point below. Watch with:
```bash
journalctl -u ara-server -f | grep CONFIRM-FLOW
```

## 6 Trace Points

| # | Location | What to log |
|---|----------|-------------|
| 1 | `_prune_pending_actions` | `"CONFIRM-FLOW prune: cancelled %d stale"` |
| 2 | `_live_pending_for_tenant` | `"CONFIRM-FLOW live-pending: id=%s title=%s tools=%s"` or `"NONE"` |
| 2b | Echo detection gate | `"CONFIRM-FLOW echo-detected: suppressing classification, msg[:80]=%s"` |
| 3 | After `_classify_confirmation` | `"CONFIRM-FLOW verdict: %s for pending id=%s"` |
| 4 | After creating pending ActionItem | `"CONFIRM-FLOW created-pending: id=%s tools=%s"` |
| 5 | Before executing tools | `"CONFIRM-FLOW executing: %d tool(s)"` |
| 6 | Each tool execution | `"CONFIRM-FLOW exec: tool=%s due_at=%s"` |

## Log Patch Reference

The live-pending function needs careful patching — the `return` must come AFTER the log:

```python
# ❌ BROKEN — log after return (dead code)
return db.query(ActionItem).filter(...).first()
if _live: ...  # never reached

# ✅ CORRECT — capture, log, then return
_live = db.query(ActionItem).filter(...).first()
if _live:
    _cf_log.info(...)
return _live
```

## Sample Output

Normal flow:
```
CONFIRM-FLOW prune: cancelled 2 stale
CONFIRM-FLOW live-pending: NONE
CONFIRM-FLOW created-pending: id=d1da41ab tools=[{"tool":"create_action",...}]
CONFIRM-FLOW live-pending: id=d1da41ab ...
CONFIRM-FLOW verdict: confirm for pending id=d1da41ab
CONFIRM-FLOW executing: 1 tool(s)
CONFIRM-FLOW exec: tool=create_action due_at=2026-06-16
```

TTL expiration (user replied too late):
```
CONFIRM-FLOW prune: cancelled 1 stale
CONFIRM-FLOW live-pending: NONE
→ "yes" falls through to regular LLM processing
→ LLM may hallucinate unrelated response
```

## Common Failure Modes

| Log pattern | Root cause |
|-------------|-----------|
| `verdict: confirm` then 500 crash | Tool handler bug (e.g., string `due_at` instead of datetime) |
| `prune: cancelled 1` before `live-pending: NONE` | PENDING_TTL too short — user's "yes" arrived after expiry |
| `live-pending: NONE` on "yes" | Expired pending action (TTL) OR wrong tenant |
| `created-pending` but no follow-up `executing` | LLM used `[ACTION: ASK]` — waiting for user to reply "yes" |
| `exec: tool=create_action` succeeds but `due_at=N/A` | Tool call has no `due_at` argument |
