# Parallel Code Paths — The Hidden Fix Gap

## The Pattern

A guard (validation, duplicate check, confirmation prompt, auth) exists in the codebase but **didn't fire** — yet a `grep` shows it's there and tests pass.

**Likely root cause:** There are multiple entry points to the same operation. The guard is wired into one path, not the others.

## Classic Example: ARA Lead Creation

The `check_duplicate_lead()` function exists and works correctly. The REST API route (`POST /api/tenants/{id}/leads`) calls it. Tests verify it returns 409 on duplicate.

But there's a **second** path — the `agent_chat` tool-call handler. When Ava executes `[TOOL_CALL: create_lead]`, the handler at line 3240 directly constructs `Lead(...)` and calls `db.add(lead)` — **without ever calling `check_duplicate_lead()`**. The duplicate passes through silently.

**Test coverage gap:** The tests only import and test the REST route handler (`from server import create_lead`). The inline tool-call handler at line 3240 is never exercised in any test.

**Result:** A voice note transcription → Ava's agent decides to create a lead → goes through the tool-call path → duplicate created silently.

## Detection Flow

When a guard exists but the bug still happened:

1. **Map ALL entry points** to the operation:
   ```
   REST routes → check server.py for @app.post/@app.get handlers
   Agent tool calls → check agent_chat for tool_name == "X" branches
   Voice pipeline → check whatsapp_voice_inbound / _ava_auto_respond
   Scheduler → check _execute_action paths
   Direct DB access → check for inline db.add() outside of route handlers
   ```

2. **For EACH entry point, check** whether the guard is called. A function existing at line 753 means nothing — what matters is which callers actually invoke it.

3. **Check the test file** — does it import and test the route handler, or the inline code path? If it imports the route handler function but the agent tool-call path has its own inline code, the test proves nothing about the path that actually fired.

## Common Variants in ARA

| Operation | Path A (guarded) | Path B (unguarded) |
|-----------|-------------------|---------------------|
| Create lead | `POST /api/tenants/{id}/leads` → `create_lead()` calls `check_duplicate_lead()` | `agent_chat` tool handler `create_lead` inline at line 3240 — no check |
| Send WhatsApp | Public API route | Agent tool call `send_whatsapp` in agent_chat |
| Update lead | `PUT /api/leads/{id}` → validates | Tool handler inline `update_lead` — may skip validation |
| Schedule action | REST API route | Agent tool call via `schedule_message` / `schedule_follow_up` |

## Prevention

### During code review:
When merging a fix that adds a guard to a route/endpoint:
- **Search for ALL callers** of the guarded operation, not just the route
- Agent tool-call handlers, scheduler execution paths, and voice pipeline are common bypasses

### During test design:
- Don't just test the route handler function — test the **entry point** the user actually hits
- For agent-driven operations, write tests that call `execute_tool()` directly with `db=test_db` and `wa=None` — this tests the tool dispatch logic without running the full LLM chain
- A test that imports `create_lead()` and asserts 409 proves the route works, not that the agent path does
- When you find inline tool-handler code that calls `db.add(lead)` directly (not through the route handler), write tests that exercise that inline code with the same duplicate-phone/email scenarios

### Testing strategy for parallel-path fixes

When you've identified that a guard exists in Path A but not Path B, your test suite must cover **both paths**:

1. **Test Path A (the already-guarded route):** Usually already covered. Verify the existing test still passes after the fix.

2. **Test Path B (the unguarded inline code):** Find the entry point. For agent tool handlers, call `execute_tool()` directly:
   ```python
   def test_tool_handler_rejects_duplicate(self, test_db, test_lead):
       from server import execute_tool
       result = execute_tool(
           "create_lead",
           {"name": "Duplicate Phone Guy", "phone": test_lead.phone},
           db=test_db, wa=None, tenant_id=test_lead.tenant_id,
       )
       assert "⚠️" in result  # Rejected
       assert "Cannot create lead" in result
   ```

3. **Test the entry points that feed into Path B:** For the voice pipeline path (🎤 → agent_chat → tool handler), test the endpoint with FastAPI TestClient + mocked dependencies:
   ```python
   @patch("server._get_whisper_model")
   @patch("requests.post")
   @patch("whatsapp_sidecar_client.wa.send_to_jid")
   def test_transcript_sent_to_agent_chat(self, mock_jid, mock_post, mock_whisper):
       client = TestClient(app)
       resp = client.post("/api/whatsapp/voice-inbound", json={...})
       assert resp.json()["status"] == "ok"
   ```

4. **Add a regression test that would have caught the bug before the fix:** Simulate the exact scenario that failed in production. For the duplicate lead bug, this means creating a lead via the REST route, then calling `execute_tool('create_lead')` with the same phone, and verifying it's rejected.

### Testing the webhook routing (another parallel-path pattern)

The `whatsapp_inbound_webhook` at `/api/whatsapp/inbound` has 6+ branching paths (owner reply coaching, owner DM to lead, owner self-inbound, known lead inbound, unknown lead, missing fields). Test these with:

1. **Mock `database.init_db` to return a seeded test DB** — patch at the module level (`"database.init_db"`) since the function does `from database import init_db` inside its body.

2. **Use the global TENANT_ID** in seed data (e.g. `"3e736242"`) since the webhook uses the module-level constant, not a fixture.

3. **Separate routing from integration:** 
   - **Routing tests:** Mock leaf handlers (`_handle_inbound_whatsapp`, `_handle_owner_coach_whatsapp`, `_log_owner_reply`) and verify which one gets called based on the input. Use `TestClient` + `POST` for the full request path.
   - **Integration tests:** Test the leaf handler directly with a real seeded DB by patching `database.init_db`. Don't mock the internal logic — test the actual lead lookup, stage transition, repetitive-message gate.

4. **Clean up test DBs:** Each seeded test DB creates a `.db` file. Delete it in `finally` or a teardown fixture to avoid file-system pollution.

## The Voice Confirmation Variant

The same pattern applies to **confirmation prompts**:

- **System prompt says:** "When 🎤 voice note, ask for confirmation on name/email/phone changes"
- **Reality:** This is a soft prompt instruction to the LLM, not a code-level guard
  - The LLM may interpret "update" as excluding "create" (creating a new lead isn't updating an existing one)
  - The LLM may decide the action is straightforward and skip the confirmation
- **Test:** No test verifies that a voice-note lead creation actually triggers a confirmation prompt

**Lesson:** A prompt-level instruction is not a code-level guard. If the behavior matters, it needs code enforcement — ideally at the tool handler level, not the prompt level.
