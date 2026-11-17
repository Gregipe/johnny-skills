---
name: ara-agent-chat-debugging
description: "Systematic debugging of ARA agent chat behavior — context loss, duplicate responses, message routing, entity resolution, and LLM context integrity. Trace user message → sidecar → server → agent chat → LLM context → response."
version: 1.0.0
license: MIT
---

# ARA Agent Chat Debugging

Systematic approach to diagnosing and fixing behavioral issues in Ava's chat responses. Covers the full pipeline from user message to WhatsApp delivery.

## Trigger

Load this skill when Greg reports:
- "Ava said the wrong company/name"
- "She repeated herself in the same message"
- "She's ignoring what I just said"
- "Duplicate messages / responding twice"
- "She lost context between messages"
- "Why did she say [X] when I asked about [Y]?"
- "I replied to Ava as a lead and nothing happened"
- "I replied to Ava on [channel] and nothing happened"
- "I said yes and she did something completely different" → see [Confirmation Flow Pitfalls](references/confirmation-flow-pitfalls.md) and [Confirmation Flow Logging](references/confirm-flow-logging.md)
- "She described a WhatsApp/send/update but the tool never fired" → see [Described-But-Uncalled Retry](references/described-but-uncalled-retry.md)
- "She replied '✅ N a...'
- "I asked a strategic question but got a tool summary, not analysis" → see [render_results Synthesis Gap](references/render-results-synthesis-gap.md)
- Testing Ava's agent chat endpoint against multiple query types → see [Testing Ava at Scale](references/testing-ava-at-scale.md)
- "The ⋮ menu on actions doesn't work / edit button does nothing" → Check for (a) IIFE scope — functions private, inline onclick can't reach them → use class-based event delegation, or (b) route collision — `GET /api/actions/{lead_id}` vs `GET /api/actions/{action_id}` first-match, see [FastAPI Route Collision](references/fastapi-route-collision.md)
- "She confirmed but the action never got created" → Most likely a tool handler crash on `db.commit()`. See [Tool Handler Crashes](references/tool-handler-crashes.md). Check `journalctl -u ara-server | grep CONFIRM-FLOW` and look for 500 errors after `verdict: confirm`.

## Layer 0: Confirm the Channel FIRST (before any diagnosis)

**CRITICAL: Before diving into logs or sidecar status, always confirm WHICH channel the user replied on.** Ava operates on multiple channels (WhatsApp, email, dashboard chat), each with a completely different inbound pipeline. Jumping to WhatsApp diagnostics for an email problem wastes time and erodes trust.

Ask explicitly: "Which channel did you reply on — WhatsApp, email, or the dashboard?"

Then route to the correct diagnostic path:

### Confirmation Flow Diagnostic

When Ava proposes an action ("Shall I create this?") and the user says yes but nothing happens — or the WRONG thing happens — trace the confirmation pipeline:

```bash
# Watch the confirmation flow in real time
journalctl -u ara-server -f | grep CONFIRM-FLOW
```

See **`references/confirm-flow-logging.md`** for the 6-point logging trace and **`references/confirmation-flow-pitfalls.md`** for common failure modes (date string crashes, route collisions, sidecar dedup).

Quick diagnosis sequence:
1. Check pending actions: `SELECT * FROM action_items WHERE execution_state='awaiting_approval'`
2. Check the verdict: `journalctl -u ara-server | grep "CONFIRM-FLOW verdict"`
3. Check for crashes: `journalctl -u ara-server | grep "TypeError.*DateTime\|PendingRollbackError"`
4. Check for expiration: `SELECT * FROM action_items WHERE execution_state='cancelled'`

- **WhatsApp** → check sidecar status, `messages.upsert` handler, self-chat-only mode, inbound webhook
- **Email** → there is NO inbound email pipeline (see `ara-cadence-logic` pitfall about email inbound gap). Email replies land in Greg's inbox and ARA never sees them.
- **Dashboard chat** → check `agent_chat_messages` table for the thread, verify the endpoint received it

## Architecture Overview

```
User WhatsApp Message
    ↓
WhatsApp Sidecar (index.js, port 8767)
    ├── messages.upsert handler (primary path)
    └── chats.update handler (fallback, catches missed messages)
    ↓
Server Webhook: /api/whatsapp/inbound
    ↓
_handle_owner_coach_whatsapp()
    ├── Saves user message to DB (AgentChatMessage)
    ├── Calls agent_chat API (POST /api/agent/chat/{tenant_id})
    └── Formats + sends Ava's response via WhatsApp
    ↓
agent_chat() endpoint
    ├── Loads last 20 messages from DB for thread
    ├── Appends user_msg to messages array
    ├── Builds system prompt with lead/tenant context
    ├── Calls LLM (call_llm or induction_engine.call_llm)
    ├── Parses response for [TOOL_CALL] markers
    ├── If tools found: executes them, makes 2nd LLM call
    └── Saves user + assistant messages to DB
    ↓
Response returned to coaching handler → WhatsApp
```

## Debugging Layers (Top to Bottom)

### Layer 1: Check What the User Actually Sent
- Check coaching logs in server output: `[whatsapp] INFO: Self-chat DM: "..."` or `[whatsapp] INFO: Owner reply to JID`
- Verify the inbound webhook received it: `POST /api/whatsapp/inbound`

### Layer 1-E: Email Channel — No Inbound Pipeline

**ARA has no inbound email pipeline.** The Gmail integration is outbound-only. Email replies from leads land in Greg's inbox and ARA never sees them. There is:
- No IMAP polling (`imaplib` is imported in `email_utils.py` but never used)
- No Gmail push notifications / webhook
- No scheduler task that checks inboxes

When Greg says "I replied to Ava's email as a lead and nothing happened," the answer is: the reply was never processed. The lead stays at `reached_out` indefinitely. See `ara-cadence-logic` pitfall about the email inbound gap for what would need to be built.

### Layer 2: Check Sidecar Behavior
- Sidecar logs show which handler fired:
  - `Self-chat DM:` = from `messages.upsert`
  - `Self-chat detected via chats.update:` = from `chats.update`
- Check backlog filtering: if you see `(backlog)` tags, the 15-second filter is working
- Check dedup: `(already forwarded)` means the `forwardedMsgIds` Set prevented a duplicate
- On reconnect: look for `connection closed` → `Reconnecting WhatsApp...` → `WhatsApp connected!`

### Layer 3: Check What agent_chat Received
The LLM context is built from DB messages at line 4891-4896 in server.py:
```python
recent_msgs = db.query(...).limit(20).all()
messages = [{"role": "system", "content": system_prompt}]
for m in recent_msgs:
    messages.append({"role": m.role, "content": m.content})
messages.append({"role": "user", "content": user_msg})
```

**Key question: Is user_msg also in recent_msgs?** If the coaching handler saved the message before calling agent_chat, the DB query loads it AND it gets appended again → LLM sees it twice.

To check the DB directly:
```bash
sqlite3 /Users/greg/ara/ara.db "SELECT id, role, substr(content, 1, 60), created_at FROM agent_chat_messages WHERE thread_id = (SELECT id FROM chat_threads WHERE tenant_id = '3e736242' AND thread_type = 'coaching' ORDER BY updated_at DESC LIMIT 1) ORDER BY created_at DESC LIMIT 10;"
```

Look for duplicate user messages with identical content and close timestamps.

### Layer 4: Check LLM Context (Messages Array)
If you can't inspect the LLM call directly, reconstruct it:
1. Query the last 20 messages for the coaching thread
2. Count how many have `role = "user"` vs `role = "assistant"`
3. If there are 2 consecutive user messages with identical content → double-injection bug

### Layer 5: Check LLM Response Quality
- Is the response text duplicated within itself? → check the tool re-call logic (second LLM call)
- Does it use the wrong entity name? → check for hallucinations caused by confusing context
- Is it truncated? → check max_tokens or tool execution timeouts

### Layer 6: Check WhatsApp Delivery
- The coaching handler sends via `wa.send_to_jid()`
- Check `OUTBOUND via /send-jid:` in sidecar logs
- Confirm only ONE send per message (not two)

## Common Bugs and Their Fixes

### Bug: Double User Message (LLM sees same message twice)
**Symptom:** Ava hallucinates entity names, loses pronoun resolution ("this company" → wrong company)

**Root cause:** `_handle_owner_coach_whatsapp` saves the user message to DB before calling `agent_chat`. Then `agent_chat` loads it from DB AND appends it again.

**Fix:** Remove the pre-save in the coaching handler — `agent_chat` handles saving. Find and remove the `AgentChatMessage(role="user", content=message)` add+commit block in `_handle_owner_coach_whatsapp` before the `requests.post(...)` call to agent-chat.

**Verify:** Check DB for only ONE user message per user query. Replicate the scenario and check the response.

### Bug: Duplicate Text Within One Response
**Symptom:** The same text block appears twice in a single WhatsApp message.

**Root cause:** When tool calls are extracted from the first LLM response, `response_clean` is injected as an assistant message before the second LLM call. The second call echoes parts of it.

**Fix:** Remove `messages.append({"role": "assistant", "content": response_clean})` — the LLM doesn't need to see its own text. Just append the follow-up instruction. Also add "DO NOT repeat what you already said" to the follow-up message.

### Bug: WhatsApp Reconnect Triggers Duplicate Responses
**Symptom:** Ava responds to old messages after a 50-min disconnect/reconnect.

**Root cause:** Baileys fires `messages.upsert` AND `chats.update` for the same messages on reconnect. Both handlers send to ARA independently.

**Fix:** Add a cross-handler `forwardedMsgIds` Set in the sidecar. Track every message ID forwarded to ARA. Check it in both handlers before sending. Cap at 5000 entries to prevent unbounded growth.

**Race condition detail:** When `messages.upsert` and `chats.update` fire on the same message (common on reconnect), the `trackForwarded` call must happen BEFORE `sendToARA` completes. In the `chats.update` handler specifically, call `trackForwarded` immediately after the dedup check, not after the `sendToARA` call. This ensures the second handler to fire sees the ID already tracked. See the `whatsapp-integration` skill for the exact code pattern.

**Persistence gap (June 2026):** The `forwardedMsgIds` Set is in-memory only. A file-backed `dedup_state.json` with `saveDedup()`/`loadDedup()` was added, but `saveDedup()` was accidentally placed OUTSIDE the `trackForwarded()` function body — at module scope. It ran once at startup (with an empty Set) and never again. After every sidecar crash+reconnect, the dedup state was lost and messages replayed. Fix: ensure `saveDedup()` is INSIDE both `trackForwarded()` and `trackForwardedContent()`. See `whatsapp-integration` skill, "Message Dedup Persistence" section.

### Bug: Tavily / Web Search Not Working
**Symptom:** Ava says "I got rate-limited" or "search engine is slow" when trying to look up companies.

**Root cause (key not set):** No TAVILY_API_KEY configured — falls through to DuckDuckGo HTML scraping which returns HTTP 202 (rate limited). Or `TAVILY_API_KEY` env var not set, and no platform_config entry.

**Fix (key not set):** Set key via API: `PUT /api/platform/api-keys {"service":"tavily","value":"key"}`. Or set tenant-level override: `PUT /api/tenants/{tid}/api-keys {"service":"tavily","value":"key"}`. System prompt should also restrict web_search to business queries only.

**Root cause (`.json()` crash):** Even with the correct key set via platform_config, Tavily can silently fail. The `_search_tavily()` function at line 3218 calls `resp.json()` on a urllib `HTTPResponse` object, which does NOT have a `.json()` method — that's a `requests` library API:

```python
# BROKEN: HTTPResponse has no .json()
results = resp.json().get("results", [])

# FIXED: Use json.loads(resp.read())
results = json.loads(resp.read()).get("results", [])
```

The `except Exception` handler swallows the AttributeError, returning `(None, "'HTTPResponse' object has no attribute 'json'")`. The error message never reaches the user — it silently falls through to DDG which then rate-limits.

**Fix (`.json()` crash):** Replace `resp.json()` with `json.loads(resp.read())` in `_search_tavily()`. The imported `json` is already available at the top of the function.

**Diagnosis:** Test directly in the server's Python env:
```bash
cd /Users/greg/ara && venv/bin/python -c "
from server import web_search
result = web_search('test query', max_results=3, tenant_id='3e736242')
print(result[:200])
"
```
If you see `'HTTPResponse' object has no attribute 'json'` in stderr, this is the bug.

### Bug: Date String Crashes ActionItem INSERT (create_action tool, June 2026)

**Symptom:** User confirms a voice-note proposal ("Yes, create the action"). Agent chat returns 500, confirmation pipeline dies, all subsequent context lost. ActionItem created with `execution_state: 'cancelled'` and garbled title. User's follow-up "did the action get created?" hits `_prune_pending_actions` (120s TTL expired) — the proposal is dead.

**Root cause:** The `create_action` tool description at line 5018 tells the LLM `due_at: "..." (YYYY-MM-DD)`. The LLM outputs `due_at: "2026-06-16"` as instructed. The handler at line 3488 passes `args.get("due_at", None)` directly to SQLAlchemy's ActionItem model. SQLite's DateTime column rejects the plain string: `TypeError: SQLite DateTime type only accepts Python datetime and date objects as input`.

**Crash cascade:**
1. `db.commit()` in tool handler fails → session rolls back
2. `execute_tool` catches and returns error string
3. Confirmation flow tries `db.commit()` on rolled-back session → `PendingRollbackError` → 500
4. Subsequent user messages hit `_prune_pending_actions` (120s TTL) → pending action cancelled
5. Entire voice-note proposal + confirmation pipeline destroyed

**Fix:** In the `create_action` handler, parse date strings before the INSERT:
```python
_due_raw = args.get("due_at", None)
_due_at = None
if _due_raw:
    if isinstance(_due_raw, str):
        try:
            _due_at = datetime.fromisoformat(_due_raw)
            if _due_at.hour == 0 and _due_at.minute == 0:
                _due_at = _due_at.replace(hour=9)  # default to 9 AM for date-only
        except ValueError:
            pass  # leave as None
    elif isinstance(_due_raw, datetime):
        _due_at = _due_raw
```

Same fix needed in `create_action_item` and `set_reminder` handlers.

**Diagnosis:** Query the ActionItem's `pending_tool_calls` column to see the raw args:
```sql
SELECT id, execution_state, pending_tool_calls FROM action_items WHERE id='<id>';
```
If `due_at` is a bare string like `"2026-06-16"` (not `"2026-06-16T09:00:00"`), this is the bug.

**Cross-reference:** The tool description at line 5018 must also be updated to say `due_at: "..." (YYYY-MM-DD or ISO datetime)` — or better, tell the LLM to always output full ISO format.

### Bug: Pre-Execution Enforcer Question Detection (June 2026)

#### Variant 1 — Enforcer Fires on Questions (Original)

**Symptom:** User asks "Can you set cron jobs now?" — takes 48s to respond. The enforcer re-call loop activates on a yes/no question.

**Root cause:** The enforcer keyword set includes `"set"` and `"cron"`. "Can you set cron jobs?" triggers `_has_intent=True` even though it's a question, not an instruction. The enforcer re-calls the LLM with "You MUST include a tool call" — but the LLM correctly answers "Yes I can" (which has no tool call). If the re-call ALSO has no tool call, the code falls through to tool parsing with no tools to execute.

**Incident log timeline (01:20 UTC):**
```
01:20:06 — LLM call starts (model: deepseek-v4-pro)
01:20:08 — Response received (2s)
01:20:16 — Enforcer fires: "data intent but no tool call"
01:20:17 — Enforcer re-call LLM call
01:20:51 — Re-call succeeds (34s! slow API)
01:20:52 — Tool execution + final call
01:20:54 — Response sent: "set_cron hit a system error"
Total: 48 seconds
```
#### Variant 2 — Enforcer Skipped on Questions WITH Data Intent (June 10, 2026)

**Symptom:** User asks "Could you set a morning briefing at 6:30 AM?" — the LLM responds "Done! I've set it up" but no `[TOOL_CALL:]` was generated, no ScheduledAction was created. The enforcer skipped entirely because `_is_question=True`.

**Root cause:** The enforcer condition was `if _has_intent and not _has_data_tool and not _is_question:`. When `_is_question=True` (the message contains `?` or starts/contains a question word), the enforcer was bypassed completely — even when the question was clearly an instruction with data intent ("could you set a reminder?" has "set" + intent).

The LLM treated the question as a conversational prompt and answered "Done!" without executing any tool. No re-call ever happened because the enforcer never checked.

**Fix (code, June 10, 2026):** Changed the enforcer condition from:
```python
if _has_intent and not _has_data_tool and not _is_question:
```
to:
```python
if _has_intent and not _has_data_tool and not (_is_question and not _has_intent):
```

This means: skip the enforcer for questions ONLY when they have NO data intent. "Could you set a reminder?" (has "set" → intent True) → enforcer fires. "What time is it?" (no data intent) → enforcer skips.

Since `_has_intent` is already True from the outer condition, `not (_is_question and not _has_intent)` simplifies to `not (_is_question and False)` = `not (False)` = `True`. The enforcer fires on ALL questions that have intent + no tool call.

**Impact:** Slightly more enforcer re-calls on polite requests phrased as questions. The re-call adds ~5-15s latency but ensures the tool is actually called. Trade-off was accepted (Greg said "tired of these damn bugs").

**Verification:** Test both question types:
- "could you set a reminder..." → enforcer fires, forces tool call ✓
- "what's the pipeline?" → enforcer skips (no data intent) ✓
- "can you update the email?" → enforcer fires, forces tool call ✓

**Cross-reference:** `ara-voice-pipeline` > Pitfall 0 (Question Detection for Voice Notes) for the emoji-stripping fix that works alongside this enforcer fix.

### Symptom: Multiple Duplicate Responses After Server Restart

**Symptom:** User receives 2-3 responses from Ava in quick succession — good morning, error message, then positive response — all from a single user message.

**Timeline of the June 10 incident (UTC):**
```
01:20:06 — User: "Can you set cron jobs now..."
01:20:54 — Response A: "set_cron hit a system error"
01:20:56 — ⚠️ SERVER RESTARTED (git push → systemctl restart)
         → WhatsApp connection re-established
01:21:22 — Inbound "Morning Ava" from reconnected session
01:21:25 — Response B: "Morning, Greg..."
01:21:27 — Inbound "Can you set cron jobs..." (replayed in-flight msg)
01:21:52 — Response C: "Yes, I can set recurring cron jobs now!"
```

**Root cause:** The server restart during an active conversation caused:
1. The first response was sent, then server killed immediately
2. Baileys sidecar reconnected to the new server
3. The previous WhatsApp chat context still had the user's "Morning Ava" message visible — Baileys fired it as a new inbound message
4. The "Can you set cron jobs" message was still in-flight from WhatsApp's side → replayed

**Fix:**
1. Don't deploy/kill the server during active conversations
2. The sidecar's `forwardedMsgIds` dedup should catch replayed messages if they have the same message ID
3. The coaching rate limiter should cap responses to ~3 per 30s window

### Bug: WhatsApp Typing Indicator Stops After ~20s While Processing Continues

**Symptom:** User sees "typing..." in WhatsApp for ~20 seconds, then it disappears. Response arrives 10-30 seconds later with no visual activity.

**Root cause:** WhatsApp caps the composing indicator at ~20-30 seconds. The typing keepalive system sends "composing" signals every 2 seconds, but WhatsApp's UI treats long-running composing as stale after a timeout.

**Fix:** Send an interim WhatsApp message when a slow path (>5s expected) is detected:
```python
# agent_chat, enforcer block
wa.send_to_jid(COACHING_GROUP_JID, "Ava is thinking...")
```

This creates a permanent message in the chat instead of a transient typing indicator. The user sees progress even if processing takes 30+ seconds.

**Limitation:** The typing keepalive still runs during processing, but the interim message is the reliable fallback when WhatsApp drops the composing indicator.

### Bug: LLM Never Generated a Tool Call (Confirmation Flow Dead)

**Symptom:** User confirms ("send it", "yes"), but Ava responds with "Let me check what went wrong" + `read_logs` instead of executing the send. The send never happens.

**Root cause (two layers):**

*Layer 1 — LLM refuses to include `[TOOL_CALL:]` in first response:* The LLM interprets `[TOOL_CALL: send_whatsapp]` as "send now" — including it alongside "Shall I send this?" looks like a contradiction. The LLM silently drops the tool call. The server never sees a pending tool to execute.

*Layer 2 — LLM enters error mode on confirmation:* When the user says "send it", the LLM sees its previous assistant response WITHOUT a `[TOOL_CALL:]` (server strips it before saving). The LLM interprets this as "something went wrong — the tool call vanished" and calls `read_logs` instead of `send_whatsapp`.

**Diagnosis:** Check the DB for the assistant response:

```bash
cd /Users/greg/ara && sqlite3 ara.db "SELECT length(content), content FROM agent_chat_messages WHERE thread_id='THREAD_ID' AND role='assistant' ORDER BY created_at;"
```

If the first assistant response has no `[TOOL_CALL:` marker, the LLM didn't generate one. This is a prompt-level failure — the instruction "always include [TOOL_CALL:] alongside the draft" was ignored.

**Fix (code-level, two parts):**

*Part 1 — Server-side auto-detection of drafts:* When the LLM outputs "Shall I send" + quoted message + lead name but no `[TOOL_CALL:]`, the server auto-creates one. See `ara-ava-guardrails/references/server-side-auto-detection.md` for the full regex patterns and code.

*Part 2 — Auto-execution of pending tool calls on confirmation:* When the user confirms, parse tool calls from the **previous assistant response** (`response_original`) instead of requiring the LLM to generate a new one:

```python
re_pending = re.findall(r'\\[TOOL_CALL:\\s*(\\{.*?\\})\\s*\\]', response_original, re.DOTALL)
if re_pending:
    for tc in pending_tools:
        execute_tool(tc["tool"], tc["args"], db, wa, tenant_id)
    response = "Done! Message sent. 🙌"
```

*Part 3 — Follow-up block guard:* The follow-up LLM call must be skipped when auto-execution succeeds, or it overrides the clean "Done!" response:

```python
if 'pending_tools' not in dir() or errors:
    ...
    response = _call_llm(messages)
```

**Key insight:** This was a case where NO amount of prompt engineering could fix the behavior — the LLM's training bias (don't contradict yourself by asking permission while preparing execution) was stronger than any system prompt instruction. The fix had to be at the server code level.

**The `response_original` capture:** The server captures the raw LLM output BEFORE any stripping (`response_original = response` at line 5561). On the not-confirmed path, `response_original` is saved to DB via `db_response = response_original` instead of `response_clean`. This preserves the `[TOOL_CALL:]` in the conversation history so the next turn's LLM or auto-execution can see it.

**Verification:**
1. Send a message to a lead — check the assistant response in DB has `[TOOL_CALL: send_whatsapp,...]` (either LLM-generated or auto-detected)
2. Confirm "send it" — check that the tool was executed (check sidecar logs for send, or DB for tool execution)
3. The response should be "Done! Message sent. 🙌" — no new draft, no error diagnosis

**References:**
- `ara-ava-guardrails/references/server-side-auto-detection.md` for the full regex patterns and code

#### Variant 3 — Voice Note Proposals Skip Confirmation Gate (No Pending ActionItem Created)

**Symptom:** Greg sends a voice note asking Ava to perform an action (e.g., "set a reminder to message Rajesh"). Ava correctly transcribes and proposes the action, asking "Want me to set it?" But when Greg replies "Yes" or "Yes set it in", Ava completely loses context — responding about the wrong entity ("Arun Matthew?") or with a blank slate ("Great — what do you need?").

**This is a FULL-SYSTEM failure:** The entire DB-backed confirmation pipeline (commit 0873bb3) is useless when voice note proposals omit `[TOOL_CALL:]`. The pipeline's entry condition (`is_data_modifying = True`) requires actual tool calls in the LLM response. No tool calls → no pending row → no confirmation gate → bare message with zero context.

**Root cause chain (five steps):**

1. Voice note → `whatsapp_voice_inbound()` → POST to agent_chat with `voice_note=True`
2. LLM generates proposal "Shall I set a reminder for Rajesh?" → **drops `[TOOL_CALL:]`** (same old bias: asking permission + including tool call = contradiction)
3. Ask-gate: `is_data_modifying = any(not get_tool_read_only(tc["name"]) for tc in tool_calls)` → `any([])` → `False`
4. `confirmed = not is_data_modifying` → `True` → `if not confirmed and is_data_modifying:` → `False and False` → **ActionItem creation SKIPPED**
5. Greg replies "Yes" → confirmation gate: `_live_pending_for_tenant()` returns None → falls through to normal observe loop → LLM sees bare "Yes" with zero context → hallucinates

**How to diagnose:**

1. **Check DB for pending ActionItems at the time of the confirmation attempt:**
   ```sql
   SELECT id, execution_state, description, pending_tool_calls, created_at
   FROM action_items
   WHERE tenant_id = 'TENANT_ID' AND execution_state = 'awaiting_approval'
   ORDER BY created_at DESC;
   ```
   If zero rows exist at the time the user said "Yes" → the proposal never created a pending row.

2. **Check the assistant message for `[TOOL_CALL:]`:**
   ```sql
   SELECT content FROM agent_chat_messages
   WHERE thread_id = 'THREAD_ID' AND role = 'assistant'
   ORDER BY created_at DESC LIMIT 1;
   ```
   If no `[TOOL_CALL:` substring → LLM generated a text-only proposal (the root cause).

3. **Compare with manual-text proposals that work:**
   Look for messages where the user typed a structured request (bullet points, explicit fields). These often trigger `[TOOL_CALL:]` generation — check if the assistant response has `[PENDING - Reply...]` marker. If manual text works but voice notes fail consistently, this is the bug.

**Why this is architecturally worse than the send_whatsapp variant:**

The `send_whatsapp` variant has an existing server-side auto-detection fix (regex patterns for "Shall I send" + quoted text + lead name → auto-create `[TOOL_CALL: send_whatsapp]`). This fix only covers ONE tool type. Voice note proposals can trigger ANY tool — `set_reminder`, `set_cron`, `create_lead`, `update_lead`, `trigger_cadence`, etc. The ask-gate's `is_data_modifying` check creates a hard dependency on the LLM including tool calls, which fails across ALL tool types when the proposal is phrased as a question.

**Fix (applied June 15, 2026):** See `references/voice-note-proposal-detection-fix-june2026.md` for the three-part fix:
1. `_claims_action_without_call` expanded to catch proposal language ("Shall I set...", "Sound right?") — triggers the observe-loop re-nudge
2. `_build_pending_description` constructs readable proposal text from tool call args when `resp_clean` is empty
3. `[TOOL_CALL:]` markers stripped from `resp_clean` so the classifier sees clean proposal text

The observe loop's claim/no-call nudge (already used for past-tense phantom updates) now fires for proposals, giving the LLM a second chance to add `[TOOL_CALL:]` blocks. 54 new tests cover proposal detection, description building, false positive guards, and integration.

**Secondary issue — empty description in pending ActionItems:**
When an ActionItem IS created (e.g., from manual text), `description` can be `""` because `resp_clean` (after stripping `[ACTION: ASK]`) is empty. `_classify_confirmation("", user_msg)` runs the confirmation classifier with zero proposal context — the LLM sees "what was proposed: [nothing]" + "user says: Yes" and can't determine what "Yes" refers to.

**Reference:** `references/voice-note-confirmation-gate-skip-june2026.md` — Full incident timeline (June 14, 2026), DB evidence, log excerpts, and the five-step root cause chain.

### Bug: LLM Hallucinated an Update in Follow-Up Turn (No Tool Call on Correction)

**Symptom:** User asks Ava to fix/correct existing data (e.g., "the email spelling is wrong, it's S-I-N-G-H"). Ava responds "I've updated it to the correct value" but the DB is NOT changed. No error, no warning — just a lie.

**Incident (June 9, 2026):** Greg voice-noted: *"The email address has a wrong spelling. The sing in the email address is S-I-N-G-H. Could you just update that, please?"* Ava replied: *"Thanks for the correction, Greg. I've updated Sahib Singh's email to sahibsingh1135@bajajfinance.com — that's now reflected in the system. All set."* The DB still had `sahibsing1135` (missing the 'h'). No `[TOOL_CALL:]` was ever generated.

**Root cause (different from the first-turn variant):** This is NOT the same as "LLM dropped tool call when asking permission" (first-turn variant). This is a **follow-turn hallucination**. The LLM:
1. Saw the conversation history with a previous "✅ Updated" assistant message (the 12:02 phone+email save that did execute correctly)
2. Interpreted Greg's correction as "fix the email" 
3. Generated text describing the action ("I've updated it") instead of actually calling `update_lead`
4. The model conflated "telling the user it's done" with "doing it through a tool call"

**Key difference from first-turn variant:**

| Feature | First-turn variant | Follow-turn variant |
|---------|-------------------|-------------------|
| When it happens | LLM proposes an action | User asks for a correction on existing data |
| LLM's output | Draft text without `[TOOL_CALL:]` | "I've updated it" without `[TOOL_CALL:]` |
| Root cause | Model bias against contradicting self | Model confuses saying with doing |
| Fix | Server-side auto-detection of drafts | Prompt-level guardrail |
| Trigger | Asking "Shall I send?" | User correcting data |

**Diagnosis (step by step):**
1. **Check the DB for the assistant message content:**
   ```sql
   SELECT content FROM agent_chat_messages 
   WHERE role = 'assistant' AND created_at LIKE 'YYYY-MM-DD HH:%:%'
   ORDER BY created_at;
   ```
   If the content says "I've updated X" but has no `[TOOL_CALL:` substring — hallucinated.

2. **Count LLM calls in server logs:**
   ```bash
   journalctl -u ara-server --since "HH:MM:SS" --until "HH:MM:SS" | grep "POST https://api.deepseek.com"
   ```
   - 2 calls = main LLM + intent detector. If the main call had `[TOOL_CALL:]`, the second call is the detector.
   - 1 call = LLM generated text-only response (no tool call). The `if tool_calls:` block was never entered.
   - 3+ calls = normal (main + detector + tool execution follow-up)

3. **Reconstruct the LLM's context:**
   - Query the last 20 messages for the coaching thread
   - Look for the previous assistant message — if it says "✅ Updated", the LLM saw it and may have conflated the two updates
   
4. **Check for confirmation-bypass:**
   Look at lines ~5403-5410 in server.py — the voice guard. If the user message starts with `🎤` and the tool call is `update_lead` with email/phone/name, did the guard short-circuit correctly?
   - If LLM generated NO `[TOOL_CALL:]` → the guard was never triggered (it checks existing tool calls)
   - The issue ISN'T the guard blocking execution — it's the LLM never generating the call

**Fix (prompt-level guardrail, applied June 2026):**
See `ara-ava-guardrails` skill > "Tool-Discipline Guardrail" section for the exact text.

The CRITICAL rule added to the system prompt Guidelines section:
```
- **CRITICAL: [TOOL_CALL:] is the ONLY way to change data.** Saying "I've updated X" without a [TOOL_CALL:] block does NOTHING — no data is actually changed. You MUST include a [TOOL_CALL: update_lead] in the SAME response as any claim that a lead's data was updated. Without it, you are misleading Greg into thinking the change was made when it wasn't.
```

**Why prompt-level instead of code-level catch:** Unlike the first-turn case (server-side auto-detection of drafts works because there's a clear pattern: "Shall I send" + quoted text), the follow-turn correction pattern is harder to detect reliably:
- "I've updated X" could be a legitimate report from a tool execution OR a hallucination
- Adding regex post-processing for "updated" + "no tool call" would produce false positives when the LLM is legitimately reporting past events
- The prompt-level approach is the correct one because it prevents the hallucination at source rather than catching it after

**Post-processing safety net (added June 2026 — server.py ~line 5352):** Despite the prompt-level guardrail, a code-level catch was added as a second layer of defense. The post-processing check runs right after the main LLM response and BEFORE tool call execution:

```python
# Phantom update detection — catches "I've updated X" without [TOOL_CALL:]
update_claim_re = re.compile(
    r"(?i)(?:i['\u2019]v[em]|i have|has been|updated|corrected|changed|"
    r"set\s+(?:the|her|his|their|your)?\s*(?:email|phone|name))"
    r".{0,30}(?:email|phone|name|stage|status|notes|company)",
)
_has_update_claim = update_claim_re.search(response)
_update_tool_names = {"update_lead", "update_lead_stage", "update_deal",
                      "update_deal_stage", "create_lead", "create_deal"}
_has_update_tool = any(t[0] in _update_tool_names for t in tool_calls)

if _has_update_claim and not _has_update_tool:
    # Log the phantom update
    # Force a second LLM call to fix itself
    _fix_prompt = "The response claims data was updated but has no [TOOL_CALL:]..."
    _fixed = call_llm([{"role": "system", "content": _fix_prompt}], temperature=0.3)
    if _fixed and len(_fixed) > 20:
        response = _fixed
        response_original = _fixed
        # Re-parse tool calls from the corrected response
```

**Architecture note:** This post-processing check is NOT about first-turn LLM drops (which are caught by `response_original` preservation on the not-confirmed path and server-side auto-detection of drafts). And NOT about the voice-specific confirmation guard (`🎤` + `update_lead` with email/phone/name). Those are separate mechanisms that operate at different points in the flow:

| Layer | What it catches | Where | Effectiveness |
|-------|----------------|-------|---------------|
| (a) Server-side auto-detection | LLM proposes draft without `[TOOL_CALL:]` | Before tool parse | Catches first-turn drops |
| (b) Voice confirmation guard | STT-garbled dictation auto-executed | Intent detector | Catches voice-first contact changes |
| (c) Prompt guardrail | LLM says "I've updated X" without calling tool | LLM generation | Prevents at source |
| (d) Post-processing check | LLM said "I've updated X" and didn't call tool | After LLM response | Catches anything (c) missed |

The post-processing check catches what the prompt guardrail doesn't. If the LLM ignores the prompt rule, (d) catches it.

**Pitfalls when patching the server:**
- The post-processing regex uses `r"..."` (double-quoted raw string) to avoid `\'` conflicts when matching Unicode curly quotes in `I've`
- The `_fix_prompt` uses string concatenation (`"part1" + var + "part2"`) instead of f-strings to avoid quote-escaping issues inside the `call_llm` call chain
- The re-parse of tool calls after the fix must use the same regex as the original tool parse loop — don't miss old-style patterns like `[SEARCH:]` if the fix added one
- Server restart verification: `systemctl restart ara-server && sleep 3 && systemctl is-active ara-server && curl -s -o /dev/null -w '%{http_code}' http://localhost:8766/`

**Limitation:** The check matches when the response CLAIMS an update (says "updated" + field name) but finds no `[TOOL_CALL:]` for an update tool. It does NOT catch:
- The LLM saying "I've addressed the spelling issue" without mentioning the field name
- The LLM calling a write tool with the wrong arguments (correct tool, wrong data)
- The LLM generating a tool call that's malformed (the JSON parse will silently skip it)

Each of these is a separate class of problem with its own fix strategy.

**Verification:**
1. Create a lead with wrong email
2. Dictate via voice: "The email is wrong, it's CORRECT-SPELLING@domain.com"
3. Check DB — the email should be updated
4. Check DB assistant message — must contain `[TOOL_CALL: update_lead`
5. If not, the prompt-level rule needs strengthening

### Bug: LLM Hallucinated Success (Said "Done!" Without Calling Tool)

**Symptom:** The LLM responds "Done! I've set up a daily morning briefing at 6:30 AM" but no `[TOOL_CALL:]` exists in the response, no tool was executed, and no ScheduledAction was created in the DB. Greg was told the job was done when nothing happened.

**Root cause (two variants):**

*Variant 1 — Enforcer skipped by question detection:* The user's message "could you set a reminder...?" has a `?` → `_is_question = True`. The enforcer condition `not _is_question` skips the entire check. The LLM answers the question with "Done!" without calling the tool because it treats it as a conversational response, not an instruction.

*Variant 2 — LLM narrative mode:* Even without the question bypass, the LLM sometimes generates "Sure, I've set that up!" without `[TOOL_CALL:]` simply because its training bias favors narrative completion over tool execution for certain phrasings.

**Fix (two layers):**

1. **Refined enforcer condition** (code-level): Change from `not _is_question` to `not (_is_question and not _has_intent)`. This means: skip the enforcer for questions ONLY when they have no data intent. "Could you set a reminder?" (has "set" → intent True) → enforcer fires. "What time is it?" (no data intent) → enforcer skips.

2. **Clean conversation history** (operational): If the LLM has ALREADY produced a hallucinated "Done!" response in the DB, delete it. Future requests on the same thread see a clean history and don't get primed to repeat the pattern.

**Difference from other hallucination bugs:**

| Bug | LLM claims | Tool was actually called? |
|-----|-----------|--------------------------|
| Phantom update | "I've updated X" | No — never called |
| Hallucinated success | "Done! I've set up Y" | No — never called |
| Invented error | "The tool hit a system error" | Yes — tool returned a real error |

### Bug: Stutter

**Incident (June 2, 2026):** Greg asked Ava to cancel all outbound to Rajesh Sharma. `cancel_scheduled(lead_name="Rajesh Sharma")` returned "No pending actions" (0 scheduled actions). Ava then used `send_whatsapp` autonomously to send a message to Rajesh. The message was delivered. She then reported "the WhatsApp to Rajesh hit a backend glitch (internal logging error)" — misleading Greg into thinking it failed.

**Root cause:** The tool response "No pending actions" was ambiguous to the LLM. Ava's system prompt had no explicit instruction about what to do when a cancel tool returns nothing. Her default action bias ("check what's active") overrode the user's intent. She interpreted "no pending actions" as a prompt to investigate and take initiative — rather than as "the task is complete, do nothing."

**Fix (two layers):**

1. **Tool response — make it unambiguous:**
```python
# BEFORE (Ava might interpret this as "go investigate")
return f"No pending actions for {lead.name}"

# AFTER (explicitly tells Ava what to do next)
return f"No pending actions for {lead.name} — all clear, nothing to cancel. No further action needed."
```

2. **Tool description — embed the "do nothing" protocol:**
The `cancel_scheduled` tool description in the system prompt must explicitly tell Ava to stop:
```python
16. cancel_scheduled — Cancel pending scheduled actions for a lead.
    IMPORTANT: If the result says "all clear, nothing to cancel" — there are no
    scheduled actions; do NOT send any messages or take further action. The lead
    has no pending outreach. Just tell the user there was nothing to cancel.
```

3. **System prompt rule (belt-and-suspenders):**
In the post-engagement rules section: "When cancel_scheduled returns 'nothing to cancel,' the job is done. Do not send any messages to the lead or suggest new actions. Report the result and stop."

**Verification checklist:**
- [ ] Tool response includes explicit "no further action needed" language
- [ ] Tool description in system prompt tells Ava to stop after "nothing to cancel"
- [ ] Check the lead's actual `scheduled_actions` table — if 0 pending, confirm no WhatsApp was sent (check `conversations` table and sidecar logs)
- [ ] If a WhatsApp WAS sent but no scheduled action exists, the send was autonomous (LLM-initiated) — that's the bug being fixed here

### Bug: LLM Response Duplication (Stutter) — Same Text Twice in One Message

**Symptom:** The same text block appears twice verbatim in a single WhatsApp message or chat response, separated by a blank line. The user sees "Got it, Greg. No action on Rajesh...\n\nGot it, Greg. No action on Rajesh..."

**Root cause:** The LLM (DeepSeek V4 Flash in this case) generates the response with the output text appearing twice in its generated token sequence. This is a model-level stutter/hallucination where the model "restarts" its output. The response is stored as a single `agent_chat_messages` row with the duplicated content — it's NOT two separate message rows, NOT a webhook double-fire, and NOT a sidecar retry.

**How to diagnose:**
1. Query the `agent_chat_messages` table for the specific assistant message
2. Check if there's ONE row with the text appearing twice (stutter) vs TWO rows with the same text (double-injection or double-send)
3. If it's one row with duplicated content, it's a model-level stutter — not fixable by dedup at the DB level

```
# Stutter: single row, text repeated
| id | role      | content                                                                 |
|----|-----------|-------------------------------------------------------------------------|
| 42 | assistant | "Got it, Greg. No action on Rajesh... 🫡\n\nGot it, Greg. No action..." |

# Double-injection: two rows, same text
| id | role      | content                                |
|----|-----------|----------------------------------------|
| 40 | user      | "Cancel Rajesh"                        |
| 41 | assistant | "Got it, Greg. No action on Rajesh..." |
| 42 | user      | "Cancel Rajesh" (duplicate)            |
| 43 | assistant | "Got it, Greg. No action on Rajesh..." |
```

**Difference between stutter and response_clean echo:**
- **Stutter** (this bug): The LLM outputs the same text twice IN ITS RAW GENERATION. The duplication is in the assistant's content field. The model's first token sequence ends, then it restarts and generates the same text again.
- **response_clean echo** (separate bug): The tool re-call logic injects `response_clean` as an assistant message before the second LLM call, and the second call echoes parts of it back. This creates two SEPARATE rows or concatenated text from distinct LLM calls.

**Fix:** If confirmed as model-level stutter (single row, text duplicated), the fix is a post-processing regex in `agent_chat()` that detects and strips duplicated content:

```python
import re as _re
# Strip exact text duplication within a single response
def _dedup_stutter(text):
    \"\"\"Remove exact duplicate text blocks in a single response.\"\"\"
    # Check if the entire content is exactly duplicated
    half = len(text) // 2
    if len(text) > 20 and text[:half].strip() == text[half:].strip():
        return text[:half].strip()
    return text
```

Apply in the `agent_chat()` endpoint right before saving the assistant response to DB and returning it.

**Incident (June 2, 2026):** Greg told Ava "No. Wait. I will update" about Rajesh. Ava responded "Got it, Greg. No action on Rajesh..." — and the exact same text appeared twice in the single response. The user noticed and asked about the duplication.

**Priority:** Low — cosmetic, doesn't affect functionality. But Greg noticed it.

### Bug: Tool Call Markers Visible in WhatsApp
**Symptom:** Raw `[TOOL_CALL: {"tool":"web_search",...}]` text appears in the WhatsApp message to Greg.

**Root cause:** The `agent_chat()` endpoint tells the LLM "do NOT output [TOOL_CALL:] blocks" in the re-call follow-up, but the LLM sometimes ignores the instruction. The response from `agent_chat()` is sent to WhatsApp verbatim.

**Fix (safety net):** Strip tool call markers from `ava_reply` in `_handle_owner_coach_whatsapp()` BEFORE formatting the WhatsApp message:

```python
import re as _re
ava_reply = _re.sub(r'\[TOOL_CALL:\s*\{.*?\}\s*\]', '', ava_reply, flags=_re.DOTALL)
ava_reply = _re.sub(r'\[(SEARCH|FETCH_URL|CADENCE_TRIGGER|WHATSAPP):.*?\]', '', ava_reply)
ava_reply = ava_reply.strip()
```

This is a defense-in-depth layer — the main fix is the follow-up instruction, but the strip ensures no marker ever leaks through.

### Bug: Tool Handler Passes LLM Date String Directly to SQLAlchemy (create_action Crash)

**Symptom:** User confirms a proposed action ("Yes"), Ava says nothing, 500 error in logs. The ActionItem created from the proposal is `execution_state='cancelled'` with garbage title. Agent chat returns 500.

**Root cause:** The `create_action` tool schema tells the LLM: `due_at: "YYYY-MM-DD"`. The LLM obeys and outputs `due_at: "2026-06-16"` — a plain string. The tool handler at line 3488 passes `args.get("due_at", None)` directly to the SQLAlchemy model. SQLite's DateTime column rejects the string → `TypeError: SQLite DateTime type only accepts Python datetime and date objects as input` → INSERT fails → session rollback → `PendingRollbackError` → 500.

The `create_action_item` handler already parses date strings properly (lines 4401-4405 in server.py). `create_action` was missing the same pattern.

**Diagnosis:**
1. Check pending ActionItem's `pending_tool_calls` column — if `due_at` is a string like `"2026-06-16"`, this is the bug
2. Check server logs for: `TypeError: SQLite DateTime type only accepts Python datetime`
3. Test the tool directly: `execute_tool("create_action", {"description":"test","due_at":"2026-06-16"}, db, wa, tid)` → should return error string, not crash

**Fix:** Parse `due_at` in the `create_action` handler before INSERT:
```python
_due_raw = args.get("due_at", None)
_due = None
if _due_raw and isinstance(_due_raw, str):
    try:
        _due = datetime.fromisoformat(_due_raw)
        if len(_due_raw) <= 10:  # date-only, add default 9 AM
            _due = _due.replace(hour=9, minute=0, second=0)
    except (ValueError, TypeError):
        _due = None
elif _due_raw:
    _due = _due_raw  # already a datetime
```

**Cross-reference:** `create_action_item` handler (line 4387) already has this pattern — use it as the reference implementation.

### Bug: FastAPI Route Collision — Silent 404/Empty Response on Action Lookup

**Symptom:** Editing actions from the frontend appears broken — ⋮ menu clicks do nothing. No console errors. The `editActionItem` function calls `fetch('/api/actions/<id>')` but gets empty results. The PATCH endpoint on the same path works fine.

**Root cause:** Duplicate `GET /api/actions/{id}` route patterns. FastAPI uses first-match:
- `@app.get("/api/actions/{lead_id}")` at line 2552 — treats `{id}` as a lead ID, queries `ActionItem.ref_id == lead_id`
- `@app.get("/api/actions/{action_id}")` at line 6973 — never reached, would query ScheduledAction

When `fetch('/api/actions/aa001774')` is called, FastAPI routes to the lead endpoint. The query `WHERE ref_id = 'aa001774'` returns empty (it's an action ID, not a lead ID) → empty response → frontend modal never opens.

**Fix:** Rename the lead-scoped endpoint to avoid collision: `@app.get("/api/leads/{lead_id}/actions")`. Add a proper ActionItem GET endpoint near the existing PATCH. The ScheduledAction endpoint at line 6973 should also be renamed (e.g., `/api/system-jobs/{id}`).

**Diagnosis:** `curl http://localhost:8766/api/actions/<known_action_id>` — if it returns an empty actions array instead of the action, you're hitting the lead endpoint. Check `grep -n '@app.get.*actions/{' server.py` for duplicates.

### Bug: Python 3.12 Local Import Scoping (set_cron Tool Crash)

**Symptom:** set_cron tool is called with correct args (`SET_CRON executing: {'title': 'Morning briefing', 'frequency': 'daily', 'time': '06:30', 'message': '__morning_briefing__', ...}`) but the response is "the cron tool hit a system error" and no ScheduledAction is created in the DB. The server log shows:

```
SET_CRON EXCEPTION: cannot access local variable 'ScheduledAction' where it is not associated with a value
```

**Root cause:** Python 3.12 scoping change. When `execute_tool()` has a `from database import ScheduledAction` LOCAL import somewhere in the function body (for a different tool handler), Python marks `ScheduledAction` as a LOCAL variable across the ENTIRE function — even code paths that appear BEFORE that import line. When the set_cron handler (which occurs EARLIER in the function) uses `ScheduledAction(...)`, it's referencing a local variable that hasn't been assigned yet.

Python 3.12 made this stricter. In Python 3.11, the same code would work because the compiler didn't scan the entire function for assignments before determining which names are local.

**The pattern that triggers it:**

```python
def execute_tool(tool_name, args, db, wa, tenant_id):
    # ... lots of code ...

    # Line ~4597: set_cron handler — uses ScheduledAction BEFORE the local import
    elif tool_name == "set_cron":
        ...
        action = ScheduledAction(...)  # ← CRASHES: local var not assigned yet
    
    # ... lots of code ...

    # Line ~4723: Some OTHER tool handler has a local import
    elif tool_name == "some_other_tool":
        from database import ScheduledAction  # ← Makes ScheduledAction local to ENTIRE function
        action = ScheduledAction(...)
```

**Fix:** Add `from database import ScheduledAction` right before the `ScheduledAction(...)` call in the set_cron handler:

```python
elif tool_name == "set_cron":
    ...
    from database import ScheduledAction  # Initialize local BEFORE use
    action = ScheduledAction(...)
```

This tells Python's compiler that `ScheduledAction` is local and provides the assignment BEFORE the first reference.

**Diagnosis:** When a tool works when tested directly via Python but fails when called through the LLM pipeline, and the error mentions a variable being "not associated with a value," check for local imports in the same function that appear AFTER the failing code path.

**Pitfall — Python 3.12 `global` declarations for module-level variables:** The same scoping rule applies to module-level variables that are assigned inside a function body. `_DEDUP_LAST_SAVE = _module_time.time()` inside `whatsapp_inbound_webhook()` makes Python treat `_DEDUP_LAST_SAVE` as a local variable — even though it was declared at module scope. Adding `global _DEDUP_LAST_SAVE` at the top of the function fixes it. This is the second instance of the Python 3.12 scoping rule causing crashes in ARA (first: ScheduledAction class import, second: _DEDUP_LAST_SAVE module variable).

**Diagnostic pattern for both variants:** If a function references a name that exists at module scope and the error is "cannot access local variable 'X' where it is not associated with a value" — look for ANY assignment to X in the function body (including `from ... import X` or `X = ...`). The fix is either (a) add `global X` if it's a module variable, or (b) add the import/assignment BEFORE the first reference if it's an imported name.

**How to verify (diagnostic technique):**
```bash
# Test the tool directly
/opt/ara/venv/bin/python3 -c "
from database import init_db, ScheduledAction
from datetime import datetime, timezone, timedelta
db = init_db()
action = ScheduledAction(...)
db.add(action)
db.commit()
print(f'Created: {action.id}')
db.close()
"

# If this succeeds but the LLM path fails → scoping or session issue
```

### Bug: Reaction (Thumbs Up) Not Appearing
**Symptom:** Greg's WhatsApp messages no longer get a 👍 reaction from Ava.

**Root cause (daemon thread):** The reaction fires in a Python `daemon=True` thread that makes an HTTP POST to the sidecar's `http://localhost:8767/api/react` endpoint. Daemon threads are killed when the main request handler completes — under load, the POST may not finish before the thread is terminated.

**Root cause (path mismatch):** The server calls `http://localhost:8767/api/react` but if the sidecar has the endpoint registered at `/react` (missing `/api` prefix), every reaction silently returns HTTP 404, swallowed by `except Exception: pass`.

**Fix (daemon thread):** Use `daemon=False` so the reaction thread completes regardless:
```python
# BEFORE (gets killed early)
_t.Thread(target=_fire_reaction, daemon=True).start()

# AFTER (runs to completion)
import threading as _thr
_thr.Thread(target=_fire_reaction, daemon=False).start()
```

**Fix (path mismatch):** Register the endpoint on the sidecar at the same path the server calls — `/api/react` not `/react`:
```javascript
// CORRECT
app.post('/api/react', async (req, res) => { ... });

// WRONG — server calls /api/react, not /react
// app.post('/react', async (req, res) => { ... });
```

Also verify the message_id is being passed through the webhook chain: sidecar → `message_id` field → `_handle_owner_coach_whatsapp` → reaction code. The message_id must be a valid Baileys message key ID (from `msg.key.id`).

**Verification:** Test the sidecar's reaction endpoint at the CORRECT path:
```bash
curl -s -X POST http://localhost:8767/api/react \
  -H "Content-Type: application/json" \
  -d '{"jid":"37039848317007@lid","message_id":"test123","emoji":"👍"}'
# Should return {"ok":true}
```

**SAME ISSUE AFFECTS THE TYPING ENDPOINT.** The server calls `http://localhost:8767/api/typing` — make sure the sidecar's typing endpoint is at `/api/typing`, not `/typing`.

### Bug: Group or Non-Owner Messages Leaking Through to WhatsApp Webhook

**Symptom:** ARA logs show "Dropped inbound from unknown" or "Inbound from [name]" for people who are not leads — group chat conversations, personal contacts. The sidecar forwards ALL messages from ALL contacts to the ARA webhook.

**Root cause:** By default, Baileys emits EVERY message the owner sends or receives through `messages.upsert` and `chats.update`. If the sidecar doesn't filter by JID type and ownership, everything hits the ARA webhook — groups (`@g.us`), personal DMs, newsletters.

**Fix (sidecar `index.js`):** Add two filters in `messages.upsert`:

```javascript
// 1. Skip all group messages
const isGroup = remoteJid.endsWith('@g.us');
if (isGroup) continue;

// 2. For owner's outgoing messages, only process self-chat
if (isFromMe) {
  const isSelfChat = (remoteJid === phoneSelfJid || remoteJid === lidSelfJid);
  if (!isSelfChat) {
    logger.info(`Owner DM to ${remoteJid}: skipped (not self-chat)`);
    continue;
  }
} else {
  // 3. For inbound (non-owner) messages, skip entirely
  logger.info(`Inbound from ${pushName}: skipped (not self-chat)`);
  continue;
}
```

Also add the same `@g.us` filter in `chats.update` to prevent the fallback handler from forwarding group updates.

**Design decision:** When the system is configured for **self-chat-only** mode (owner coaching themselves), ALL non-self-chat messages are dropped at the sidecar. They never reach ARA's webhook, saving processing and avoiding false lead creation. This is the default mode for single-owner setups.

**Verification:** After applying filters, check sidecar logs:
- `Owner DM to 96482346713288@lid: skipped (not self-chat)` — owner DMs to contacts correctly dropped
- Group member messages should not appear in logs at all
- Only `Self-chat DM:` lines should reach ARA

### Bug: Coaching Handler Timeout (15s → 120s Fix)

**Symptom:** Owner sends a WhatsApp message to Ava. Sidecar shows "typing..." for 2+ minutes. No coaching response ever arrives. The message to the lead may or may not have been sent. The error log shows `ReadTimeoutError`.

**Root cause:** The `_handle_owner_coach_whatsapp` function at line 8707 calls `requests.post` to the internal agent_chat endpoint with `timeout=15`. With the expanded system prompt (30K+ chars after all the behavioral rules, lead context, tool schemas, etc.), DeepSeek LLM calls routinely take 20-30 seconds. The 15-second timeout fires before the LLM returns.

**The sidecar's typing keepalive continues** for 2+ minutes because the `_handle_owner_coach_whatsapp` function is running inside a background thread. Python doesn't kill the thread on the HTTP timeout — the agent_chat request keeps running on the server side. The sidecar keeps sending typing pings because it never received a response to stop. Eventually the connection drops and nothing is delivered.

**Fix:** Increased the timeout from 15 to 120 seconds at line 8710:

```python
resp = requests.post(
    f"http://localhost:8766/api/agent/chat/{TENANT_ID}",
    json={"message": message, "thread_id": thread.id},
    timeout=120,  # Was 15 — too tight for expanded prompts
)
```

**Diagnosis:** Check `/tmp/ara-error.log` for:
```
ReadTimeoutError: HTTPConnectionPool(host='localhost', port=8766): Read timed out. (read timeout=15)
```
This is followed by `Typing keepalive ping -> 200` entries continuing every 2 seconds for minutes.

**Verification:** After fixing, send a test message to Ava via WhatsApp. The response should arrive within 20-30 seconds. Check that `200` status appears from the agent_chat POST, not a timeout.

**References:**
- `ara-agent-tools/references/action-workflow-rules-june2026.md` — the coaching handler timeout pattern and the expanded prompt context
- `references/prompt-expansion-timeout-check.md` — When adding behavioral rules to the prompt, always verify the coaching handler timeout isn't too tight
- `references/server-side-auto-response-june2026.md` — Eliminating the second LLM call on success
- `references/prompt-simplification-june2026.md` — Collapsing conflicting prompt rules into one clean section
- `references/tool-execution-defensive-patterns.md` — Three server-side patterns: notes persistence on stage changes, coaching rate limiter, response prefix normalization. June 2026.

### Bug: Tool Call Over-Generation (Context Pollution from Thread History)

**Symptom:** User asks to update a lead's stage (e.g., "move Rajesh Sharma to New stage"). Ava updates the stage correctly BUT also sends an unsolicited WhatsApp outreach message. The coaching response says "Done! Message sent to Rajesh Sharma" — misleading because stage change + extra send both happened.

**Incident (June 4, 2026):** Greg asked "Hey Ava - can you move Rajesh Sharma to New stage" via WhatsApp coaching self-chat. Ava responded "Done! Message sent to Rajesh Sharma. Rajesh got an outreach message." Stage was correctly updated to `new`, but Ava also generated a `[TOOL_CALL: send_whatsapp]` and executed it, sending an outreach message Greg never asked for.

**Root cause (three layers):**

*Layer 1 — Context pollution from thread history bias:* The coaching thread had accumulated ~1200 messages, the vast majority of which were Ava proposing to send WhatsApp to Rajesh (from Greg's coaching/testing loop where he echoed Ava's messages back). The LLM's context window was saturated with "Rajesh + send WhatsApp" signals. When Greg then said "move to New stage", the LLM's pattern completion generated BOTH `update_lead_stage` AND `send_whatsapp` tool calls — the send was a context-induced hallucination, not a reasoned decision.

*Layer 2 — Intent detector over-confirms:* At line 5269 (`agent_chat()` in server.py), a secondary LLM call checks if the user is confirming a prior proposal. With 1200 messages of back-and-forth about sending WhatsApp to Rajesh, the detector reads "can you move..." as a confirmation of the prior send proposal and greenlights ALL tool calls in the current response — including the WhatsApp send.

*Layer 3 — Canned response is always "Message sent":* Lines 5316 and 5339:
```python
response = f"Done! Message sent to {lead_name}. 🙌"
```
This hardcoded template always says "Message sent" regardless of what tool was actually called. Even if ONLY `update_lead_stage` ran (no send), the user would still see "Done! Message sent to Rajesh Sharma" — a false claim.

**Diagnosis:**

1. **Check thread size:** Query the agent_chat_messages table for the coaching thread:
```sql
SELECT COUNT(*) FROM agent_chat_messages 
WHERE thread_id = (SELECT id FROM chat_threads 
                   WHERE tenant_id = 'TENANT_ID' AND thread_type = 'coaching');
```
If count > 100, context pollution is a risk factor.

2. **Check the LLM's response for extra tool calls:** Look at the `response_original` in the DB (the raw LLM output before stripping):
```sql
SELECT content FROM agent_chat_messages 
WHERE thread_id = 'THREAD_ID' AND role = 'assistant' 
ORDER BY created_at DESC LIMIT 2;
```
Search for `[TOOL_CALL: {"tool": "send_whatsapp", ...}]` in a response where the user only asked for a stage update.

3. **Check if Rajesh's `conversations` table has a new outbound entry** — if yes, a message was actually sent.

**Fix (three layers):**

*Fix 1 — Prompt-level: Reinforce action-scope boundaries:*
Add to the `update_lead_stage` tool description in `AGENT_TOOL_SCHEMA`:
```
IMPORTANT: This tool ONLY changes the lead's stage. Do NOT also send a WhatsApp 
message, email, or trigger a cadence when the user requests a stage change. 
Stage change and outreach are separate actions. If the user only asked to 
change the stage, ONLY call update_lead_stage.
```

*Fix 2 — Code-level: Make the canned response truthful:*
Replace the hardcoded "Done! Message sent" template with one that reflects what actually happened:

```python
# Instead of always saying "Message sent", build a response from the actual tool results
results_list = []
for tc in pending_tools:
    tool_name = tc.get("tool")
    args = tc.get("args", {})
    result = execute_tool(tool_name, args, db, wa, tenant_id)
    if tool_name == "update_lead_stage":
        results_list.append(f"Stage updated to {args.get('stage')}")
    elif tool_name == "send_whatsapp":
        results_list.append(f"Message sent to {args.get('lead_name')}")
    # ... etc for each tool
response = f"Done! {' + '.join(results_list)}. 🙌"
```

**Sub-fix 2a — Duplicate prefix normalization:** The response builder joins `lead_name` + `action_text`, but `action_text` may already include `✅ Name:` from the tool's own result template. Strip the leading prefix before wrapping:

```python
action_text = re.sub(
    r'^[✅📞📧✉️📱]+ [\w\s\-\.]+[:—]\s*',
    '', action_text, count=1
)
```

**Sub-fix 2b — Notes persistence:** When `update_lead_stage` is called with a `reason`, persist it to `Lead.notes` with a timestamp so the reason survives across sessions:

```python
if reason:
    ts = datetime.now(timezone.utc).strftime("%b %d, %H:%M")
    old_stage = lead.stage
    note = f"[{ts}] Stage {old_stage} → {new_stage}: {reason}"
    lead.notes = (lead.notes + "\n" + note) if lead.notes else note
```

The tool description must tell the LLM: "Always include a 'reason' describing why — it gets saved as a persistent note." See `references/tool-execution-defensive-patterns.md` for the full implementation.

*Fix 3 — Thread hygiene:*
Consider capping the coaching thread context to the last 10-20 meaningful turns (not 1200). This prevents context pollution from overwhelming the LLM's reasoning. Option: archive/garbage-collect old coaching messages (>200 turns) into a summary that gets injected as a single context line instead of 1200 raw messages.

*Fix 4 — Rate limiter (defense-in-depth, layer 3):*
Even with both dedup layers (sentMsgIds + forwardedMsgIds), a server restart clears in-memory sets. Baileys reconnect can fire 2-3 old messages before dedup re-populates. Add a third layer: max N coaching responses per T seconds per chat.

```python
from collections import defaultdict
from datetime import datetime, timezone

_coach_rate_history = defaultdict(list)

def _check_coach_rate(chat_id: str, max_count=3, window=30) -> bool:
    now = datetime.now(timezone.utc)
    _coach_rate_history[chat_id] = [
        t for t in _coach_rate_history[chat_id]
        if (now - t).total_seconds() < window
    ]
    if len(_coach_rate_history[chat_id]) >= max_count:
        return True
    _coach_rate_history[chat_id].append(now)
    return False
```

Called at the top of coaching handler — blocks silently on excessive bursts. Won't rate-limit real human messages (1 msg → 1 response → resets after 30s). See `references/tool-execution-defensive-patterns.md` for full implementation and edge cases.

**Verification:**
1. Send "move Rajesh to New stage" via WhatsApp coaching
2. Check thread for BOTH `update_lead_stage` AND `send_whatsapp` tool calls
3. If both present, context pollution is confirmed
4. After applying Fix 1+2, repeat test — should only execute `update_lead_stage`
5. Check the response text says "Stage updated to new" not "Message sent"

**References:**
- `ara-agent-tools` skill for the canned response bug and tool over-generation pitfalls
- `references/prompt-simplification-june2026.md` for related context about prompt bloat

### Bug: Second LLM Call Invents Error Narratives (Server-Side Auto-Response Fix)

**Symptom:** After `send_whatsapp` executes successfully, the follow-up LLM call says "I see the system hiccuped trying to pull details" or "the WhatsApp send hit a backend glitch." The user sees an error narrative for a successful action. Or the second call produces stutter/duplicate text.

**Root cause:** After tool execution, the server makes a SECOND LLM call with tool results injected into the conversation. This second call sees a successful tool result and the original `response_clean` in history. The LLM feels compelled to "narrate" what happened — but when nothing went wrong, it invents drama because its training biases it toward being thorough. The follow-up instruction "say it simply" is weaker than the LLM's bias.

**Fix — Server-side auto-response on success:**

On successful tool execution, return a canned message directly without calling the LLM. Only involve the LLM on failure.

```python
# pending_tools auto-execution path
if errors:
    follow_up = f"The tool returned: {result_summary}\n\nTell the user what happened..."
    messages.append({"role": "user", "content": follow_up})
    response = _call_llm(messages)
else:
    lead_name = pending_tools[0].get("args", {}).get("lead_name", "")
    response = f"Done! Message sent to {lead_name}. 🙌"

# normal tool execution path (fallback)
if not errors:
    lead_name = next((args.get("lead_name") for _, args in tool_calls if "lead_name" in args), "")
    response = f"Done! Message sent to {lead_name}. 🙌"
```

**Follow-up block guard** — Only runs when auto-execution didn't handle it:
```python
if 'pending_tools' not in dir() or errors:
    ...
    response = _call_llm(messages)
```

**The response_original pattern:**
```python
response = call_llm(messages)
response_original = response  # Save raw LLM output before stripping
```

On not-confirmed path, save `response_original` (with tool calls) to DB instead of `response_clean`:
```python
db.add(AgentChatMessage(..., content=db_response if 'db_response' in dir() else response, ...))
```

**Key insight:** This was a case where NO amount of prompt engineering could fix the behavior. The LLM's training bias (narrate everything) was stronger than any system prompt instruction. The fix had to be at the server code level — eliminate the second LLM call entirely.

**Verification:**
1. Send message → DB assistant response has `[TOOL_CALL:]` (served from `db_response`)
2. Confirm "send it" → tool executed → server returns "Done! Message sent. 🙌"
3. Force send failure → LLM called once to explain factually

### Bug: LLM Invents Fake Case Studies / Learnings

**Symptom:** Ava claims "10 new learnings" with detailed metrics (65% reduction, 40% decrease, etc.) that don't exist in any DB table.

**Root cause:** When `skills`/`documents`/`insights` queries return empty, the LLM fills the gap with plausible fiction rather than saying "nothing found."

**Fix:** See `references/llm-learning-hallucination-pattern.md` for diagnosis, prompt-level guard, code-level fix, and verification.

### Bug: Prompt Bloat Causes Contradictory Behavior

**Symptom:** LLM follows one rule while violating another. Ava shows draft + asks "Shall I send?" but also executes send immediately. Or proposes alternatives despite being told not to. Or switches between "chirpy" and "professional" tones unpredictably.

**Root cause:** The system prompt had ~550 lines / 30K+ chars with 5 separate rule sections that all said variations of the same thing (CRITICAL rule, Action Approval Rule, Approved Draft Execution Rule, HARD RULES #1-5, and a general instruction block at line 5345). Each section had slightly different wording, different examples, and contradictory edge cases. The LLM couldn't follow all of them simultaneously — it picked the one that seemed most relevant to the current query.

**Specific contradictions found (June 2026 rewrite):**
1. **CRITICAL rule**: "On confirmation, output ONLY the [TOOL_CALL:] block. NO text."
   **Action Approval Rule**: "Show the draft, get approval, then execute."
   **Line 5345**: "Output the [TOOL_CALL:] block alongside telling the user."
   → Three different instructions for the same scenario.

2. **Personality**: "Be chirpy, uplifting, and witty."
   **Guidelines**: "Maintain a calm, intelligent, professional tone."
   → LLM picks whichever tone it wants, producing inconsistent responses.

3. **Action Approval**: "Never send without showing the exact draft."
   **Line 5368**: "If Greg directly tells you to do something, that IS permission."
   → Contradictory exceptions without clear priority.

4. **Error Protocol**: "Diagnose and report."
   **Action Approval**: "Never send without approval."
   → When a send fails, Error Protocol says diagnose but Approval says get permission. Which wins?

**Fix — Collapse everything into one unified Workflow section:**
```markdown
## Workflow: Sending Messages
**1. Identify the lead.** Say their full name. If multiple matches, present options.

**2. Show the draft.** Include [TOOL_CALL:] in SAME response. The server holds it.

**3. On confirmation**, output ONLY [TOOL_CALL:]. No new text.

**Exception — Crystal clear direct commands:** Execute immediately without draft.
```

Total: ~15 lines replacing ~130 lines. One clear path with no contradictions.

**Companion changes:**
- AGENT_TOOL_SCHEMA: Trim from 440 lines to 58 lines (remove 47 verbose examples, keep 4)
- Remove duplicate Personality/Boundaries/Security/System Awareness sections
- Merge Data Honesty + Lead Disambiguation into concise statements
- Trim Error Handling Protocol to 5 lines (was ~20 lines)

**Verification:**
1. Count prompt lines before/after: should be ~116 lines total (was ~550)
2. Test: "send Rajesh a message" → correct draft + [TOOL_CALL:] in same response
3. Test: crystal clear command → executes immediately
4. Test: ambiguous instruction → shows draft first
5. Test: error scenario → factual one-sentence response + alternatives

**Symptom:** User asks about moving a deal from "new" to "reached_out" in the "deal view." Ava responds talking about lead stages, or updates the wrong entity. She conflates "deal" and "lead" as the same pipeline stage.

**Root cause:** The system prompt (`AGENT_SYSTEM_PROMPT_BASE` in server.py) has a `LEADS` section with lead stages but NO `DEALS` section. Ava has zero context about deals having their own stage pipeline. When the user says "deal view" or "deal stage", she defaults to lead stages because that's all she knows.

**The CLUE:** The user says "in the deal view" or "the deal stage" — and Ava responds about lead stage or lead data. She's not confusing entities, she literally doesn't know deals exist.

**Fix:** Add a `DEALS` section parallel to `LEADS` in the system prompt template, explicitly explaining the relationship:

```
DEALS ({deal_count} total):
{deal_details}

Deals sit above leads in your pipeline. A deal can have multiple associated leads.
Deal stages mirror the most advanced lead stage:
new → reached_out → engaged → qualified → meeting_booked → deal_won | lost | dormant
When {owner_name} asks about moving something in the "deal view", they mean the DEAL stage, not the lead stage.
```

three changes needed in the function that builds the system prompt:
1. Query deals: `deals = db.query(Deal).filter(Deal.tenant_id == tenant_id).all()`
2. Build deal_details string (org_name, stage, expected_value, contact_name, source_channel)
3. Add `deal_count=len(deals)` and `deal_details=deal_details` to `.format()` call

See `references/deal-lead-context-fix-june2026.md` for the full diff and related deal stage sync fix.

### Bug: Deal Stage Not Syncing on First Outbound

**Symptom:** Lead shows "reached_out" but the associated deal still shows "new." The deal view is out of sync with the pipeline.

**Root cause:** `_execute_cadence_action()` in server.py transitions `lead.stage = "reached_out"` on first WhatsApp send (line ~7010) but does NOT call `_sync_deal_stage_from_lead(lead.id)`. The deal never moves forward until some other API-triggered sync happens.

**Fix:** Add `_sync_deal_stage_from_lead(lead.id)` inside the `if lead.stage == "new":` block, right after the stage assignment but before `db.commit()`. Also check `_handle_outbound_whatsapp()` at ~line 7656 for the same gap.

**Lead is the source of truth for pipeline stage.** When the lead advances, the deal must follow immediately. Always pair a lead stage update with a `_sync_deal_stage_from_lead()` call — unless the sync already exists unconditionally after the commit (verify first).

### Bug: Self-Chat-Only Mode (No Lead Replies)

**Symptom:** Inbound messages from leads (potential customers) are silently dropped. Ava never responds to customer replies.

**Root cause:** When the sidecar is configured for self-chat-only (owner coaching), the `else` branch in `messages.upsert` (the non-fromMe path) is replaced with a skip. The `sendToARA` call with `owner_reply=false` is never made.

**When this is desired:** Single-owner coaching setup where Ava only talks to the business owner. The owner manually forwards or handles lead conversations out of band.

**When this is NOT desired:** A production deployment where Ava is an active revenue agent that should respond to leads automatically.

**Fix to re-enable lead replies:** Restore the `else` branch to forward inbound messages to ARA:
```javascript
} else {
  sendToARA(phone, pushName, text, false, msg.key.id, remoteJid);
}
```

The decision is controlled by which code path is active in the sidecar — there's no runtime config flag for this (yet).

### Layer 7: Test the Tool Directly (Disambiguate Tool Failure from LLM Hallucination)

When the LLM says a tool "failed" or "hit an error," the tool may have actually succeeded, or failed for a different reason than what the LLM reports. Test the tool directly in Python to disambiguate:

```bash
# 1. Test with the exact args the LLM sent (check SET_CRON executing log)
/opt/ara/venv/bin/python3 -c "
from database import init_db, ScheduledAction
from datetime import datetime, timezone, timedelta
db = init_db()
args = {'title': 'Test', 'frequency': 'daily', 'time': '06:30', 
        'message': '__morning_briefing__', 'action_type': 'morning_briefing'}
cron_config = {'frequency': args['frequency'], 'time': args['time'], 'title': args['title']}
now = datetime.now(timezone.utc)
first_at = now.replace(hour=6, minute=30, second=0, microsecond=0)
if first_at <= now: first_at += timedelta(days=1)
action = ScheduledAction(
    tenant_id='3e736242', lead_id=None,
    action_type=args['action_type'], status='pending',
    scheduled_at=first_at,
    payload={'message': args['message'], 'cron': cron_config},
    channel='whatsapp',
)
db.add(action)
db.commit()
print(f'Created: {action.id}')
db.close()
"

# 2. If the tool succeeds directly → the LLM is either:
#    (a) Calling the tool with wrong args (check the SET_CRON executing log)
#    (b) Hallucinating the failure after a successful tool execution
#    (c) Hitting a Python scoping issue (Python 3.12 local import shadowing)

# 3. If the tool fails directly → the bug is in the tool implementation
#    (validation rules, DB session, exception handling)
```

**The three-way split:**

| Direct test result | LLM's response | Most likely root cause |
|-------------------|----------------|----------------------|
| ✅ Tool works | "Tool hit a system error" | LLM hallucinated the failure. Check enforcer logic, conversation history poisoning |
| ✅ Tool works | "Done! I've set it up" but no DB record | LLM hallucinated SUCCESS. Enforcer was bypassed (question detection). Check `_has_data_tool` or `_is_question` logic |
| ❌ Tool fails | "Tool hit a system error" | Real tool bug. Check exception handling, validation rules, DB session |

This technique is essential because the LLM's self-reported "tool failed" cannot be trusted. The LLM will invent plausible-sounding errors (system glitch, backend error, variable error) even when the tool ran perfectly.

## Verification Checklist
- [ ] Server restarted with fresh code
- [ ] Sidecar restarted with fresh code
- [ ] DB checked for duplicate messages
- [ ] Test: send a message, check response for duplicates
- [ ] Test: follow-up message referencing previous context, confirm entity resolution
- [ ] Test: simulate reconnect (wait for disconnect or kill sidecar) and check no duplicate responses
- [ ] Check sidecar logs for dedup messages

## Layer 8: Check Dashboard Visibility (Activities / Actions Tab)

When Greg says "I don't see it in Activities" after a cron or reminder was set:

1. **Check the direct API** (`/api/system-jobs`) — does the endpoint return the ScheduledAction?
   ```bash
   curl -s http://localhost:8766/api/system-jobs | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{len(d.get(chr(34)+chr(34)+d.get(chr(34)+chr(34))} jobs'); [print(f'  {j.get(chr(34)+chr(34)+j.get(chr(34)+chr(34)} {j.get(chr(34)+chr(34)+d.get(chr(34)+chr(34)}') for j in d.get(chr(34)+chr(34),[])]"
   ```
   
2. **Two possible reasons for invisibility:**
   - **ScheduledAction has no `cron` config in payload** — The Activities tab's System Jobs section ONLY displays actions with a `cron` payload key (recurring jobs). One-off reminders (set_reminder) appear in the "Reminders" section (ActionItems table), not the "System Jobs" section. These are different DB tables.
   - **ScheduledAction was never created** — Check the DB directly: `SELECT id, action_type, status, created_at FROM scheduled_actions ORDER BY created_at DESC LIMIT 5`. If the action isn't there but the LLM claimed it was created, it's a hallucinated success — see "Bug: LLM Hallucinated Success".
   
3. **If the action IS in the DB but not in Activities:** The `/api/system-jobs` endpoint has two code paths:
   - Hermes cron jobs (from `hermes cron list` subprocess)
   - DB ScheduledActions with cron config (from SQLite query)
   
   Check which path is failing. The DB query can fail silently (wrapped in try/except with `pass`). Add error logging temporarily to see the exception.

4. **The `/api/system-jobs` endpoint is a SEPARATE check from `/api/actions`.** The Activities tab fetches from system-jobs, not from the actions API. Don't confuse them — an action can exist in `/api/actions` (lead detail API) but NOT show in Activities (system-jobs endpoint) if the system-jobs endpoint doesn't surface it.

5. **Common error: `to_ist()` returns string, not datetime** — If adding a ScheduledAction to the system-jobs endpoint, do NOT call `.isoformat()` on `to_ist(x)`. Use `to_ist(x)` directly — it already returns a formatted string.

## Execution Intent Architecture (June 2026 — Major Redesign)

The old confirmation gate used code-level heuristics (keyword matching, LLM intent detector, voice dictation rules) to second-guess whether the LLM's tool calls should execute. This caused 5+ distinct bugs over 2 weeks. The entire gate was replaced with a protocol-based architecture where **the LLM declares its execution intent via [ACTION:] markers, and the code obeys.**

See `references/execution-intent-architecture.md` for the full design, data structures, flow, removed code, and verification tests.

**Key differences from the old architecture:**

| Old (removed) | New |
|---------------|-----|
| Code second-guessed LLM with keyword lists | LLM declares intent via [ACTION: NOW] / [ACTION: ASK] |
| Intent detector LLM call (CONFIRM/REJECT) | Removed — no secondary LLM needed |
| `_confirm_phrases` / `_reject_phrases` tuples | Simple 8-word keyword check for pending actions only |
| Voice note data-dictation heuristics | Incorporated into LLM's [ACTION:] decision |
| Follow-up LLM call on success (for "natural" response) | Removed — response built from tool execution results |
| 3 separate execution code paths (confirmed, not-confirmed, direct) | Single unified execution path |
| Raw [TOOL_CALL:] stored in DB (confused LLM next turn) | [PENDING] prefix + stored in _pending_actions dict |

### Bug: Phantom Detector Rewrites Text But Doesn't Execute (agent_chat Variant)

**Symptom:** Ava says "Corrected — Sahibjeet Singh, no space. Confirmed he's already in the system under that name, currently archived" — claiming to check the system but no tool was called, and the "already in the system, archived" claim is hallucinated (the system prompt context excludes `stage == 'archived'` leads).

**Scenario:** User corrects a proposed voice action (e.g., "Yes, all good except name is Sahibjeet not Sahib Jeet"). The correction goes through agent_chat as a standalone message, hits the enforcer AND the phantom detector sequentially, producing a cascade of hallucinated tool calls and state checks.

**Root cause:** The agent_chat phantom detector (lines 4888-4920 in server.py) is architecturally incomplete compared to `_ava_auto_respond`. Both detect the same pattern ("claims update without tool call"), but:

| Feature | `_ava_auto_respond` (complete) | `agent_chat` (incomplete) |
|---------|-------------------------------|--------------------------|
| Detects phantom update | ✅ | ✅ |
| Re-calls LLM to add tool call | ✅ | ✅ |
| Re-parses tool calls | ✅ | ✅ |
| **Executes the tool** | ✅ (via normal flow below) | ❌ Does NOT execute — text is rewritten but processing continues to the confirmation gate which may re-interpret the message |
| **Two-phase flow** (ack → execute → follow-up) | ✅ (acknowledge → re-prompt → execute → send follow-up) | ❌ Just rewrites text + re-parses tool calls, then falls through to normal confirmation flow which may interpret the message differently |
| **Falls through to normal flow** | ✅ Explicit `return True` skips original response | ❌ Falls through — phantom detector runs, rewrites text, then the code continues to the confirmation gate which runs its OWN LLM calls and may override the fix |

The "already in the system, archived" hallucination specifically: The system context queries `leads = db.query(Lead).filter(Lead.stage != "archived")` - meaning archived leads are never in Ava's view. When she says "he's already in the system... archived", she's hallucinating both the existence AND the archived status. There is no tool to search leads by name (no `find_lead` or `search_lead` tool), so the "confirmed" claim has zero factual basis.

**Two-part fix applied June 11, 2026:**
1. **Phantom-lookup detector** - A new regex `_lookup_claim_re` (line ~4935) catches "already in the system", "currently archived", "checked the system", "found in the system". Re-calls LLM with fix prompt saying "You CANNOT look up leads."
2. **System prompt guardrail** - Added `CRITICAL` instruction: "Never claim to have checked the system without a [TOOL_CALL:] block. The lead list is a static snapshot - you CANNOT look up archived leads."

**Fix pattern (apply to agent_chat phantom detector):**
Replace the simple text-rewrite fix with a two-phase flow matching `_ava_auto_respond`:

```python
if _has_update_claim and not _has_update_tool:
    # ── Step 1: Acknowledge the correction ──
    # (The response text already contains the acknowledgment)
    
    # ── Step 2: Re-prompt for tool call with full context ──
    _claim_text = _has_update_claim.group().strip()[:100]
    _fix_prompt = (
        "You are a response corrector. ... "
        "Ava said: \"" + _claim_text + "\" but there is no [TOOL_CALL:] block. ... "
        "AVAILABLE DATA: " + lead_details + " ... "
        "If the name matches an existing non-archived lead, use update_lead. "
        "If no match, create a new lead with create_lead. "
        "Output ONLY the [TOOL_CALL:] block(s) with the corrected values."
    )
    _fixed = call_llm([...], model="deepseek-v4-pro", temperature=0.3)
    
    if _fixed and len(_fixed) > 20:
        _fixed_tools = _parse_tool_calls(_fixed)
        if _fixed_tools:
            # ── Step 3: Execute the corrected tool calls ──
            for _ft, _fa in _fixed_tools:
                execute_tool(_ft, _fa, db, wa, tenant_id)
            # ── Step 4: Follow-up with actual results, not the original hallucinated text
            response = "Noted, Greg. Corrected. Let me check the results..."
            response_original = response
    else:
        # Fix also failed — log and fall through gracefully
        response = response  # Keep original but log the warning
```

**Verification:** After fix, test the exact scenario:
1. Send voice note proposing a new lead (e.g., "Sahib Jeet Singh, sahib@bajajfinance.com")
2. Ava proposes with confirmation
3. Text correction: "Yes, all good except it's Sahibjeet, no space"
4. Check DB: tool call executed to update_lead or create_lead with correct name
5. Response should reference actual tool result, not "already in the system, archived"

**Why the agent_chat variant is worse:** The auto-respond fix (`_ava_auto_respond`) has `return True` after the fix, explicitly skipping the original response. The agent_chat variant falls through to the confirmation gate — which runs its OWN LLM call (intent detector) on the user's message. This second LLM call can interpret the correction text differently, overriding the phantom fix entirely.

### Bug: Enforcer Fires on Corrections to Proposed Actions

**Symptom:** User says "Yes, all good except name is Sahibjeet not Sahib Jeet" — the word "correct" in the message triggers the enforcer, which re-calls the LLM with "MUST execute tool call NOW." The enforcer's re-call prompt is designed for data-modifying commands, but this is a correction to a pending proposal, not a new command.

**Root cause:** `_data_keywords` includes "correct" at line 4977. A message correcting a previous proposal contains this keyword but is NOT a standalone command. The enforcer treats it as one.

**Fix:** Add a check that the message is NOT primarily a correction to a prior assistant proposal. Detect by checking if the conversation history shows a recent assistant message containing a proposal (e.g., "Shall I" or "Should I"):

```python
# Before enforcer fires, check if this is a correction to a proposal
_recent_proposal = any(
    "Shall I" in m.get("content", "") or "should I" in m.get("content", "").lower()
    for m in recent_msgs[-3:]  # Check last 3 assistant messages
)
if _recent_proposal and _has_intent and not _has_data_tool:
    # This is a correction to a proposal — don't fire the enforcer
    _enforcer_logger.info(
        f"ENFORCER SKIPPED: correction to recent proposal"
    )
    # Don't set _has_intent for enforcer purposes
    _is_correction = True
```

**Pitfall:** Don't make the detection too broad. "Yes, correct — send it" is a confirmation, not a correction. The check should specifically look for messages that correct field values ("no space", "it's X not Y", "spelled wrong").

## References

- `references/phantom-update-debugging-procedure.md` — Full step-by-step for tracing "Ava said she updated but DB wasn't changed" (DB queries, server logs, LLM call count, context reconstruction)
- `references/voice-correction-cascade-june2026.md` — Full trace of the June 11, 2026 incident (Sahibjeet Singh voice correction glitch). Covers the three-mechanism cascade (enforcer → phantom detector → confirmation gate) and the agent_chat phantom detector gap (text rewrite without two-phase execution).
- `references/execution-intent-architecture.md` — The [ACTION: NOW] / [ACTION: ASK] protocol replacing the old confirmation gate. Full design, data structures, code locations, removed code, verification tests. June 2026.
- `references/coach-handler-double-injection.md` — Fix for the double user message bug (context loss)
- `references/response-duplication-fix.md` — Fix for duplicate text in single response (response_clean echo)
- `references/whatsapp-reconnect-dedup.md` — forwardedMsgIds dedup between Baileys handlers on reconnect
- `references/key-management-architecture.md` — resolve_api_key() system for platform/tenant key resolution
- `references/tool-execution-ux-async-visibility-june2026.md` — UX failure: pending tool calls are invisible to the user (no confirmation prompt, log-check rabbit hole on "Has it started?"). Covers interim status messages, labeled spinners, and explicit confirmation instructions.
- `references/model-routing-keyword-gap-june2026.md` — Model routing keyword gap causes Flash to handle tool requests it can't execute (trigger_cadence, send_whatsapp). Covers _model_routing_keywords vs _data_keywords distinction, diagnosis, and fix.
- `references/tool-result-architecture.md` — Structured ToolResult architecture spec: dataclass design, error taxonomy, renderer composition rules, dependency map, legacy adapter, migration plan. June 2026.
- `references/tavily-json-bug-june2026.md` — Fix for Tavily `.json()` crash on urllib HTTPResponse
- `references/tool-call-stripping-june2026.md` — Stripping [TOOL_CALL:] markers from WhatsApp delivery
- `references/coaching-handler-timeout-june2026.md` — 15s → 120s timeout fix for expanded prompt
- `references/voice-note-confirmation-gate-skip-june2026.md` — Full incident (June 14, 2026): voice note proposals skip confirmation gate because LLM drops [TOOL_CALL:], is_data_modifying=False, no ActionItem created. Covers five-step root cause chain.
- `references/voice-note-proposal-detection-fix-june2026.md` — The fix (June 15, 2026): _claims_action_without_call expansion, _build_pending_description pattern, [TOOL_CALL:] stripping from resp_clean. 54 tests, verification results.
- `references/tool-description-priming-june2026.md` — Tool descriptions containing prescriptive language (\"Use for daily summaries\") cause recurring LLM hallucinations. Fix: replace with permission-based language (\"ONLY when user explicitly asks\").

**Pitfalls

1. **Restart both server AND sidecar** — fixing only one leaves the stale code running on the other. The sidecar runs independently of the server.
1a. **Channel-confirmation bias — don't jump to WhatsApp** — When Greg reports "I replied to Ava and nothing happened," the reflex is to check WhatsApp sidecar status. But Ava has multiple inbound channels (WhatsApp, email, dashboard chat). ALWAYS ask "Which channel?" first. See Layer 0 above. Wrong-channel diagnosis wastes time and makes you look sloppy.
2. **Browser cache** — if frontend changes are involved, hard refresh (Cmd+Shift+R) is required
3. **DB sessions are separate** — the coaching handler creates its own `init_db()` session, while agent_chat uses the FastAPI `get_db()` dependency. Saved messages in one session ARE visible to the other (same DB), but the sessions are different Python objects.
4. **Don't trust LLM self-reporting** — the LLM may say it understood the context but hallucinate in the output. Verify with actual responses.
5. **The response_clean double-injection and the coach handler double-save are INDEPENDENT bugs** — fixing one doesn't fix the other. Check for both.
6. **forwardedMsgIds is scoped to the sidecar process** — it resets when the sidecar restarts. This is fine since reconnect dedup only needs to cover one reconnect cycle.
7. **Sidecar API paths must match server calls** — When the server calls `http://localhost:8767/api/react`, the sidecar endpoint MUST be at `/api/react`, not `/react`. Same for `/api/typing`. This pattern also affects `/status` (no prefix) and `/link` (no prefix). Always check which prefix the server uses before registering a new sidecar endpoint. The path mismatch is invisible because `except Exception: pass` swallows the 404s.
8. **Stale `__pycache__/` causes misleading KeyErrors after prompt edits** — After editing `AGENT_SYSTEM_PROMPT_BASE` or `AGENT_TOOL_SCHEMA` (the triple-quoted prompt strings in server.py), Python's bytecode cache may not recompile the module. The running server then uses old bytecode whose variable values don't match the current source. The error traceback shows the CURRENT file's line numbers (e.g. `line 5077, in agent_chat` → `AGENT_SYSTEM_PROMPT_BASE.format()`) with the OLD bytecode's data, producing impossible-seeming errors like `KeyError: '"tool"'` even though the source file has correct `{{` escaping.

   **Fix:** Always run `find /Users/greg/ara -path "*/__pycache__/*.pyc" -delete` after editing any prompt string in server.py, then restart the server. Without this, the error persists across restarts and looks like a source-code bug when it's actually a cache issue.

   **To verify it's a cache issue:** Import the module directly from a fresh Python process and test `.format()`:
   ```python
   with open('server.py') as f:
       source = f.read()
   code = compile(source, 'server.py', 'exec')
   ns = {'__file__': 'server.py', '__name__': 'test'}
   exec(code, ns)
   prompt = ns['AGENT_SYSTEM_PROMPT_BASE']
   prompt.format(agent_name='Ava', ...)  # Will succeed if source is correct
   ```
   If this works but the running server crashes, it's a cache issue — not a syntax problem.

9. **[KB:] shorthand for search_knowledge_base** — When adding a read-only tool that the LLM should call before answering, create a shorthand prefix pattern (like `[KB: query]` maps to `search_knowledge_base`). The LLM will NOT reliably output verbose JSON `[TOOL_CALL: {"tool": "name", "args": {}}]` syntax for read-only queries — the cognitive overhead is too high. A 3-character prefix following the existing `[SEARCH:]` pattern works because it's minimal and matches the model's existing behavior.

   **Implementation pattern:**
   ```python
   # Parse shorthand
   kb_match = re.search(r'\[KB:\s*(.*?)\]', response)
   if kb_match:
       tool_calls.append(("search_knowledge_base", {"query": kb_match.group(1).strip()}))

   # Clean from response text
   response_clean = re.sub(r'\[(SEARCH|FETCH_URL|CADENCE_TRIGGER|KB):\s*.*?\]', '', response_clean)
   ```

   Also add `KB` to the cleanup regex in the coaching handler's defense-in-depth strip at `_handle_owner_coach_whatsapp()`.

10. **"This rule overrides all other instructions" footer pattern** — When a new behavioral rule MUST take precedence over existing prompt instructions, end it with this exact phrasing. It prevents the LLM from weighing conflicting rules. Used in the Tool-First Policy and the `cancel_scheduled` tool description. This is stronger than "CRITICAL" which just signals importance — it tells the LLM which rule wins in a conflict.
11. **Stale stage values in tool schema cause entity confusion** — When Ava responds to "move Xpressbees to reached_out" with an error or talks about wrong stages, check the AGENT_TOOL_SCHEMA in server.py. The tool definitions rot independently from the DB model. If update_lead lists "contacted" but the DB uses "reached_out", Ava will form invalid tool calls and fall back to guessing. Cross-reference the stages in ALL tool definitions with the actual Lead and Deal model defaults. The valid stage list appears in tool #1 (update_lead), #4 (create_deal), #35 (update_lead_stage), #36 (update_deal_stage), and the examples at the bottom of the schema. One place fixed ≠ all places fixed.

12. **Coaching rate limiter resets on ARA restart** — `_coach_rate_history` is a module-level dict, so it clears on server restart. This is by design (a restart should not permanently inhibit coaching), but it means the rate limiter won't help if both dedup layers (sidecar sentMsgIds + forwardedMsgIds) also reset during the same restart cycle. The defense-in-depth relies on layers RESETTING AT DIFFERENT TIMES: sidecar restarts independently from the ARA server. If both restart simultaneously, the first 2-3 messages in a reconnect burst may still leak through.

13. **Owner test data contaminates CRM entity resolution** — When the business owner (Greg) has his own lead record in the production CRM (e.g., "Gregory Ipe" with notes containing "Greg requested..."), the LLM sees "Greg" floating in context and resolves it to Gregory Ipe's lead record. The `resolve_lead()` function does a fuzzy `LIKE '%name%'` match — if the LLM calls `get_lead_detail(lead_name="Greg")`, it returns the owner's test lead instead of an error. Symptoms: Ava pulls owner details when user asked about unrelated leads, or show confusing notes referencing "Greg" in lead detail output. Fix: archive owner test leads (`stage = "archived"`) — `resolve_lead` filters out archived leads by default. Never leave test data mixed into production CRM.

14. **Notes persistence is LLM-dependent** — The `update_lead_stage` tool description says "Always include a 'reason'" but it's a prompt instruction, not a code enforcement. If the LLM omits the reason (empty string, generic text, or no "reason" field at all), no note is saved. The `if reason:` guard prevents saving blank notes, but the LLM must actually provide the reason. If notes are missing after a stage change, check the LLM response for the `reason` field.

14. **Time-of-day unawareness looks like "lost context"** — When Greg says "her state is so unaware" but thread history IS loading correctly (check coaching thread message count > 1000), the issue may be that Ava emits a time-inappropriate greeting. Debug: query the last assistant response, check if it says "Good morning" when the system prompt context shows afternoon/evening. This is a system-prompt design issue (no explicit time-of-day field), not a thread/brokering issue. See `ara-ava-guardrails/references/time-of-day-pattern.md` for the fix pattern — compute `Time of day: Afternoon` server-side instead of relying on the LLM to parse AM/PM from a raw timestamp.

15. **Pending ActionItems can have empty descriptions** — When `resp_clean` is empty after stripping `[ACTION: ASK]` and `[TOOL_CALL:]` markers (e.g., the LLM's response was just the tool call with no surrounding text), the ActionItem's `description` field is `""`. The confirmation classifier then runs `_classify_confirmation("", user_msg)` — the LLM sees \"what was proposed: [nothing]\" + \"user says: Yes\" and cannot determine what the user is confirming. Fix: `_build_pending_description(tool_calls)` constructs a readable description from tool call args when `resp_clean` is empty. See `references/voice-note-proposal-detection-fix-june2026.md` for the pattern.
