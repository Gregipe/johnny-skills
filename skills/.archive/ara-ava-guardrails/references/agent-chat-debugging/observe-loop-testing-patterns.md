# Observe-Loop Testing Patterns

Patterns for testing ARA's `_run_observe_loop` under controlled conditions, developed during the June 2026 four-fix cycle.

## 1. Mock LLM Response Injection

**Problem:** Testing retry logic, downgrade behavior, or specific exit paths in the observe loop requires specific LLM outputs that are impossible to trigger reliably with real prompts.

**Pattern:** Add a `_mock_responses=None` parameter to `_run_observe_loop`. When non-empty, each LLM call pops from this list instead of calling the real LLM.

```python
# In server.py, before the LLM call:
if _mock_responses and len(_mock_responses) > 0:
    out = _mock_responses.pop(0)
else:
    out = _ie.call_llm_with_tools(...)

# In tests:
mock1 = {"text": "Heres the WhatsApp Ill send...", "tool_calls": [], "raw_tool_calls": [], "error": None}
mock2 = {"text": "Ive sent the WhatsApp...", "tool_calls": [], "raw_tool_calls": [], "error": None}
result = _run_observe_loop(messages, tools_schema, db, wa, tenant_id, user_msg, channel,
                           _mock_responses=[mock1, mock2])
```

**Uses:**
- Force retry-exhaustion path (two successive prose-only responses → downgrade)
- Test honest-downgrade language ("drafted, not sent")
- Verify exactly-one-retry guard (no unbounded looping)

**Pitfall:** The mock dict MUST include all keys that downstream code accesses: `text`, `tool_calls`, `raw_tool_calls`, `error`. Missing keys cause `KeyError` not `None` fallback.

## 2. Sidecar Inbox Kill-and-Replay

**Problem:** Proving `inboxWrite` precedes `forward` requires killing the sidecar mid-flight between the write and the HTTP POST. A clean restart does NOT reproduce the race condition.

**Pattern:**
1. Inject a temporary sleep (`await new Promise(r => setTimeout(r, 5000))`) between `inboxWrite` and the forward call
2. Insert a test message into `inbox_messages` with `processed=0` (simulating what inboxWrite would have written)
3. Kill the sidecar: `systemctl kill ara-whatsapp-sidecar`
4. Verify the message survived in the DB with `processed=0`
5. Remove the injected delay, restart sidecar
6. Verify replay: message marked `processed=1`, log shows "Inbox replay: N unprocessed messages"
7. Remove test messages from DB

**Two-message variant:** Insert 2 messages, kill, restart. Both must end `processed=1`.

**Pass conditions:**
- Durable write survives process death
- Replay fires on restart (check `journalctl | grep "Inbox replay"`)
- Both messages survive in the two-message variant

## 3. Line-Positioned Log Capture

**Problem:** Time-windowed journalctl (`--since 8s ago`) is unreliable for capturing tier classification logs. The log line often arrives after the 8s window closes, producing "unknown" tier. This caused 9 false negatives in the regression battery.

**Pattern:** Use line-positioned capture instead of time-windowed:

```bash
# BEFORE sending the message, record the current journal cursor
CURSOR=$(journalctl -u ara-server -n 1 --show-cursor -q | grep '^-- cursor:' | cut -d' ' -f3-)

# Send the message via curl...

# Read from that cursor forward, with timeout
journalctl -u ara-server --after-cursor="$CURSOR" --no-pager
```

**Or with line count:**
```bash
BEFORE=$(journalctl -u ara-server -n 1 --no-pager | grep -o '\[.*\]' | head -1)
# ... send message ...
journalctl -u ara-server --no-pager | awk "/$BEFORE/{found=1; next} found"
```

**Anti-pattern:** `journalctl --since 5s ago | grep TIER:` — races the log write. Always use cursor or line-count positioning.

## 4. Test Infrastructure Triage

When a test battery produces failures, triage into three categories before reporting:

1. **Real failures** — the code behavior is wrong. Fix the code.
2. **Infra false negatives** — the test tooling is wrong (timing, SSH from Python subprocess, log capture window). The code is correct but the test can't observe it. Fix the test infrastructure, not the code.
3. **Assertion false positives** — the test passed but the assertion was too weak (e.g., "chains multiple tools" for a command that took 6 tools with 3 duplicate reads). Tighten the assertion, re-run.

A test that passes for the wrong reason is more dangerous than a test that fails. The Amardeep "re-list" bug originally passed because the test only checked "no error" — not "no re-list."

## 5. Two-Decoupled-Surfaces Problem

The fundamental architecture issue: the LLM produces text AND tool_calls in the same response, but nothing enforces agreement between them. "Here's the WhatsApp Ill send" + tool_calls=[] is valid output. The old regex guards (Fix 2) papered over this; the real fix is in the observe-loop exit logic catching described-but-uncalled writes.
