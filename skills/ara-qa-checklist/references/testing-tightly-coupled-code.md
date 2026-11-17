# Testing Tightly-Coupled Code

**Problem:** Code that calls LLMs, WhatsApp APIs, Whisper models, or creates its own DB sessions is hard to test — every call goes through a live dependency that fails in CI, costs money, or hangs.

**Pattern: Layer-cake testing** — extract pure logic → test helpers → mock external deps → test endpoints.

---

## 1. Extract Pure Logic First

Before you can test anything, pull pure string-transformation, validation, and computation out of functions that also have side effects.

```python
# BAD — logic mixed with I/O
def _ava_auto_respond(lead, message, ...):
    response = call_llm(messages)
    import re
    ava_reply = re.sub(r'\[TOOL_CALL:.*?\]', '', response)
    wa.send_message_sync(phone, ava_reply)

# GOOD — extract then test
def _strip_tool_markers(text: str) -> str:
    import re
    text = re.sub(r'\[TOOL_CALL:\s*\{.*?\}\s*\]', '', text, flags=re.DOTALL)
    text = re.sub(r'\[(SEARCH|FETCH_URL|CADENCE_TRIGGER|WHATSAPP|KB):.*?\]', '', text)
    text = re.sub(r'POST /api/[^\s]+', '', text)
    return text.strip()

def _ava_auto_respond(lead, message, ...):
    response = call_llm(messages)
    ava_reply = _strip_tool_markers(response)
    wa.send_message_sync(phone, ava_reply)
```

**When to extract:** If a function calls 2+ external dependencies (LLM + WhatsApp + DB), and you can't test most of its logic without mocking all of them, extract the pure parts.

---

## 2. Watch Out for Local Imports

Python functions sometimes do `from module import func` inside their body. This means patching at the module level won't work.

```python
# In server.py — function does a local import:
def _ava_auto_respond(...):
    from induction_engine import call_llm   # ← local import!
    response = call_llm(messages)

# In your test — patch the SOURCE module, not the consumer:
@patch("induction_engine.call_llm")   # ✓ works
@patch("server.call_llm")              # ✗ won't work (local import overrides it)
```

**Rule:** Patch at the module where the function is *defined*, not where it's *imported*. The function's `from X import Y` creates a local reference to `X.Y`, so `X.Y` is what you mock.

---

## 3. Test Pure Helpers First (No Mocks)

Pure function tests are fast, deterministic, and don't need fixtures:

```python
class TestStripToolMarkers:
    def test_strips_tool_call(self):
        from server import _strip_tool_markers
        result = _strip_tool_markers('Hello [TOOL_CALL: {"tool":"x"}] Done')
        assert "TOOL_CALL" not in result
        assert "Hello" in result

    def test_nested_braces(self):
        from server import _strip_tool_markers
        result = _strip_tool_markers('[TOOL_CALL: {"args": {"nested": {"a": 1}}}]')
        assert result == ""

    def test_preserves_normal_text(self):
        from server import _strip_tool_markers
        assert _strip_tool_markers("Hi there!") == "Hi there!"
```

**Aim for:** Edge cases + normal paths + empty/malformed input. These tests prevent regressions in the extraction itself.

---

## 4. Mock External Dependencies for Integration Tests

Use `@patch` or `patch()` for LLM calls, WhatsApp sends, Whisper transcription, etc.

### For DB-backed functions that create their own DB

Some functions do `from database import init_db; db = init_db()` inside the function body. Patch `database.init_db` to return a seeded test DB:

```python
def _seed_test_db():
    db = database.init_db("/tmp/test.db")
    lead = Lead(id="test_001", phone="9876543210", ...)
    db.add(lead)
    db.commit()
    return db

@patch("database.init_db", return_value=seeded_db)
def test_handler(mock_init_db):
    result = _handle_inbound_whatsapp(phone="919876543210", ...)
    assert result is not None
```

### For functions imported at module level (not local imports)

```python
# Module-level: from whatsapp_sidecar_client import wa
@patch("whatsapp_sidecar_client.wa.send_message_sync")
def test_sends_message(mock_wa):
    mock_wa.return_value = {"status": "sent", "msg_id": "abc"}
    result = _some_function_that_sends(...)
    mock_wa.assert_called_once()
```

---

## 5. Use TestClient for Endpoint Tests

FastAPI's `TestClient` lets you POST to real endpoints with mocked internals:

```python
class TestEndpoint:
    @patch("database.init_db")
    @patch("server._handle_owner_coach_whatsapp")
    def test_routing(self, mock_coach, mock_init_db):
        from server import app
        from fastapi.testclient import TestClient
        client = TestClient(app)

        resp = client.post("/api/whatsapp/inbound", json={
            "phone": "919999999999",
            "message": "Follow up",
            "owner_reply": True,
            "remote_jid": "919999999999@s.whatsapp.net",
        })
        assert resp.status_code == 200
        mock_coach.assert_called_once()
```

**Key detail:** `TestClient` imports your FastAPI `app` object, so all module-level imports happen exactly once at import time. Patching module-level references (`server.wa.send_message_sync`) works fine, but local imports inside functions need patching at the source module.

---

## 6. Seeded Test DB Pattern

For DB-backed tests, create a dedicated test database per test class (or per test, if isolation matters):

```python
@pytest.fixture(autouse=True)
def setup(self):
    import database
    from pathlib import Path
    test_path = "/tmp/test_inbound_webhook.db"
    p = Path(test_path)
    if p.exists():
        p.unlink()
    database._engines = {}  # Reset engine cache

    db = database.init_db(test_path)
    # Seed: tenant, admin user, lead, conversation
    ...
    self._db_patcher = patch("database.init_db", return_value=db)
    self._db_patcher.start()
    yield
    self._db_patcher.stop()
    db.close()
    os.unlink(test_path)
```

**Cleanup:** Always unlink the test DB file in teardown. Use `try/finally` or pytest fixtures with yield.

---

## 7. Patch Verification Checklist

When a mocked test fails with "function not called" or unexpected behaviour, check:

| Symptom | Likely cause |
|---------|-------------|
| Mock not called even though code should call it | Wrong patch target — check for local `from X import Y` inside the function |
| Mock called but returns None instead of return_value | Wrong patch path — the mock is replacing a different reference than what the code uses |
| Real function runs instead of mock | Module imported before patch applied — patch must be active before the module-level import runs |
| Test works alone but fails in suite | Shared mutable state (DB, global dicts) leaking between tests — use fresh fixtures per test class |
| All-tool response test receives real LLM output | `induction_engine.call_llm` wasn't patched — happens when function does local `import` |
