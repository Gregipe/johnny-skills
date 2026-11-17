# Testing FastAPI + SQLAlchemy Apps (ARA Patterns)

Common mocking pitfalls and patterns specific to ARA's architecture.

## Local Import Patching

ARA functions frequently use **function-local imports**:

```python
def _ava_auto_respond(...):
    from induction_engine import call_llm    # <- LOCAL import
    response = call_llm(messages, ...)
```

When you patch `server.call_llm`, it has **no effect** — the function resolves `call_llm` from `induction_engine` at runtime via the local import. You must patch the **source module**:

```python
# WRONG — silently does nothing:
with patch("server.call_llm", return_value="..."):
    _ava_auto_respond(...)

# RIGHT:
with patch("induction_engine.call_llm", return_value="..."):
    _ava_auto_respond(...)
```

### Debugging tip
If your mock seems to be ignored and the real function is called:
1. Check if the target function does `from X import Y` locally
2. If so, patch `X.Y`, not the consumer module

### Which functions have local imports
- `_ava_auto_respond` -> `from induction_engine import call_llm` (patch `induction_engine.call_llm`)
- `_handle_inbound_whatsapp` -> `from database import init_db, Lead, Conversation` (patch `database.init_db`)
- Most voice pipeline functions -> `from whatsapp_sidecar_client import wa` (patch `whatsapp_sidecar_client.wa`)
- Various routes -> `from induction_engine import call_llm` (patch `induction_engine.call_llm`)

## Background Threads in Tests

ARA spawns daemon threads for background work (`_run_extraction`, `analyze_conversation`, `_detect_stage_changes`, etc.). These call `call_llm` (if mocked) and `init_db()`, interfering with test assertions.

### Pattern: Prevent threads from running

```python
with patch("threading.Thread.start", return_value=None):
    function_that_spawns_threads()
```

This prevents thread execution entirely. Without this, background threads overwrite your mock's `call_args` and create DB sessions that trigger integrity errors.

### Pattern: Track thread health

The `_track_thread_wrapper` helper wraps thread functions with health tracking visible at `/api/thread-health`. Use it for any new background thread:

```python
t = threading.Thread(
    target=_track_thread_wrapper,
    args=("my_task", _request_id_var.get(), _my_fn, arg1, arg2),
    daemon=True
)
t.start()
```

## Pipeline E2E Smoke Test Template

Test a full pipeline (webhook -> handler -> LLM -> WhatsApp) by mocking the entry points:

```python
def test_full_pipeline(self):
    db = seed_test_db()

    with patch("induction_engine.call_llm", return_value="LLM response"):
        with patch("whatsapp_sidecar_client.wa.send_message_sync",
                   return_value={"status": "sent", "msg_id": "test"}):
            with patch("threading.Thread.start", return_value=None):
                with patch("database.init_db", return_value=db):
                    function_under_test(...)

    # Assert side effects on the test db, not return values
    assert db.query(...).count() == expected
```

Key principles:
- **Seed a real DB** with `database.init_db(test_path)` — don't mock the DB
- **Mock the boundaries** (LLM, WhatsApp, threading)
- **Assert on DB state** (conversation logged, stage changed) — this is the real behavior
- **Clean up** `db.close()` and `os.unlink(test_path)` in finally block

## FastAPI TestClient Gotchas

- `TestClient(app)` triggers app startup (lifespan events, background threads). If the app starts real services (WhatsApp sidecar), the test will hang.
- **Fix**: Call handler functions directly instead of via TestClient when the app startup is problematic.
- For simple endpoint tests (no startup side effects), TestClient works fine:
  ```python
  client = TestClient(app)
  resp = client.post("/api/whatsapp/voice-inbound", json={...})
  ```
- Rule of thumb: use TestClient for stateless routes where you just need HTTP in/out. Use direct function calls when you need to control DB state or prevent side effects.

## DB Fixture Pattern

Create a clean DB per test, using the real `TENANT_ID` from config:

```python
TENANT_ID = "3e736242"  # from app/config.py
db = database.init_db("/tmp/test_xxx.db")
tenant = Tenant(id=TENANT_ID, name="Test")
db.add(tenant)
# ... seed other data
db.commit()
```

Always use the real `TENANT_ID` in fixtures — the code uses this as a global constant, and custom IDs won't match.

### Cleanup pattern

```python
import os
test_db_path = "/tmp/test_xxx.db"
try:
    # ... test logic ...
finally:
    db.close()
    if os.path.exists(test_db_path):
        os.unlink(test_db_path)
```

## Test types used in this codebase

### _strip_tool_markers() tests (test_voice_pipeline.py)
Pure function tests for `_strip_tool_markers()` — the canonical way to clean LLM responses before sending to users. Tests cover:
- `[TOOL_CALL:]` with nested braces and escaped quotes
- `[SEARCH:]`, `[FETCH_URL:]`, `[CADENCE_TRIGGER:]`, `[WHATSAPP:]`, `[KB:]` markers
- Multiple markers in one response
- Raw API path leaks (`POST /api/...`)
- Empty strings, only-marker responses, normal text passthrough

### _parse_tool_calls() adversarial tests (test_tool_parser.py)
The balanced-brace parser needs tests for:
- `}` and `]` inside JSON string values (would break a regex parser)
- Escaped quotes inside strings
- Multiple tool calls with garbage text between them
- Incomplete tool calls (no closing brace) -- must not crash
- Unicode/emoji, deep nesting (10+ levels), flat structure (no nested `args` key)
- Malformed JSON -- must be silently skipped
- No false positives on random braces in prose

### Webhook routing tests (test_inbound_webhook.py)
Test branching logic by mocking leaf handlers and asserting which one was called:
```python
with patch("server._handle_owner_coach_whatsapp") as mock_coach:
    client.post("/api/whatsapp/inbound", json={...})
    mock_coach.assert_called_once()
```
Also test the actual handler logic with a real seeded DB:
- Lead found by phone -> conversation logged + stage advanced
- Repetitive message gate blocks identical messages within 5 minutes
- Different message passes the gate
- Dormant lead re-engages -> stage advanced to engaged
- Unknown lead silently dropped

### Auto-respond tests (test_auto_respond.py)
The `_ava_auto_respond` function now executes tool calls before sending:
- LLM response sent via WhatsApp
- Tool markers stripped after execution
- Conversation logged with tool-call results
- Stage advanced (new->engaged, reached_out->engaged)
- All-tool LLM response -> fallback message sent
- LLM failure -> skipped
- WhatsApp failure -> returns False

### Enforcer condition tests (test_enforcer.py)
The pre-execution enforcer in agent_chat checks if the user has data-keyword intent without a corresponding tool call. Tests document edge cases:

- **Corrections to proposals do NOT fire the enforcer** (`TestNamingCorrectionOnProposal`) -- "All good except..." contains no data keywords
- **Create commands with questions fire the enforcer** (`TestCreateLeadEnforcer`) -- "create a new lead" has intent but LLM asks "what company?" instead of executing
- **Phantom-lookup patterns documented** (`TestPhantomLookup`) -- "already in the system", "currently archived", "found in the system" are caught by the new regex
- **30-char window bug documented** (`TestPhantomWindowBug`) -- long responses with separated claim verbs and data fields slip through
- **PENDING prefix format** (`TestToolPendingStorage`) -- DB stores [PENDING] prefix for unexecuted tool calls
- **Auto-confirm on details** (`TestAutoConfirmOnDetails`) -- when previous assistant asked for details and user provides matching fields, tool auto-executes

## Phantom-Update Detection (anti-hallucination)

ARA has **three layers** of protection against the LLM claiming changes it didn't make:

### Layer 1: agent_chat (line ~4620)
After the LLM responds, a regex scans the response for phrases like "I've updated", "has been corrected", "changed the email" etc. If found AND no corresponding `[TOOL_CALL: update_lead/create_lead/update_deal/create_deal]` block exists, the response is auto-fixed:
```python
update_claim_re = re.compile(
    r"(?i)(?:i[''']v[em]|i have|has been|updated|corrected|changed|"
    r"set\s+(?:the|her|his|their|your)?\s*(?:email|phone|name))"
    r".{0,30}(?:email|phone|name|stage|status|notes|company)",
)
```
The LLM is called again with a corrective prompt to add the missing `[TOOL_CALL:]`.

### Layer 2: _ava_auto_respond (line ~7810)
The same regex runs in the auto-respond path. If a phantom update is detected AND no tool call was executed, the response is replaced with a safe fallback:
```
"Thanks for your message, {name}! I'll check with my team and get back to you on this."
```
This is stricter than agent_chat because auto-respond sends messages autonomously -- there's no human to catch a hallucination.

### Layer 3: Phantom-lookup detection (line ~4935)
The LLM also claims to have "checked the system" or "found a lead in the system" without any lookup tool. A separate regex catches these patterns:
```python
_lookup_claim_re = re.compile(
    r"(?i)(?:already\s+(?:in|exists?)|found\s+(?:in|the)|checked\s+(?:the|in)|"
    r"currently\s+archived|archived\s+in|looked\s+up|searched\s+(?:the|for)|"
    r"in\s+the\s+system|under\s+that\s+name)"
)
```
When detected, the LLM is re-called with a fix prompt that says "You CANNOT look up leads -- acknowledge the correction and re-propose."

### Known limitation: 30-char window
The update claim regex has a 30-character window between the claim verb and the data field. Long responses can exceed this window and slip through.

## Auto-Confirm Pattern (June 2026)

When the previous assistant message asked for details ("Full name?", "Company?", "Email?", "Phone?") and the user provides matching fields, the tool auto-executes without requiring a separate "yes" keyword.

**How to test:**
```python
def test_prior_question_triggers_auto_confirm(self):
    messages = [
        {"role": "assistant", "content": "Can you share your full name, company, and email?"},
    ]
    user_msg = "Name - Sahib\nCompany - Bajaj Finance\nemail - sahib@bajajfinance.com"
    tool_names = {"create_lead"}

    _prev_msgs = [m for m in messages if m.get("role") == "assistant"]
    _last_a = _prev_msgs[-1].get("content", "")
    _detail_askers = ["Full name?", "Company?", "Email", "Phone", "Can you share",
                       "full name", "any notes", "contact info"]
    _prev_asked = any(p in _last_a for p in _detail_askers)

    _has_fields = any(k in user_msg.lower() for k in ["name", "company", "email", "phone"])
    assert _prev_asked and _has_fields and len(user_msg) > 30
```

## PENDING Prefix Pattern (June 2026)

When a tool call is not confirmed, the DB stores `[PENDING - awaiting your confirmation]` before the original response. This prevents the LLM from hallucinating that unexecuted tools were completed.

**How to test:**
```python
def test_pending_prefix_in_db_response(self):
    response_original = "Got it, creating the lead.\n\n[TOOL_CALL: create_lead...]"
    db_response = "[PENDING - awaiting your confirmation]\n" + response_original
    assert db_response.startswith("[PENDING")
    assert "[TOOL_CALL:" in db_response
```

## Canonical Tool-Stripping Function: `_strip_tool_markers()`

Defined at line ~2580 in server.py. Used in 4 places (auto-respond, voice confirm, voice re-send, voice inbound):

```python
def _strip_tool_markers(text: str) -> str:
    import re as _re
    text = _re.sub(r'\[TOOL_CALL:\s*\{.*?\}\s*\]', '', text, flags=_re.DOTALL)
    text = _re.sub(r'\[(SEARCH|FETCH_URL|CADENCE_TRIGGER|WHATSAPP|KB):.*?\]', '', text)
    text = _re.sub(r'POST /api/[^\s]+', '', text)
    return text.strip()
```

Always use this function instead of inline regex for stripping tool markers. It handles:
- Nested braces in JSON payloads (via DOTALL and balanced-brace logic in the parser)
- Multiple marker types
- API path leaks
