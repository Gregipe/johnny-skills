# Confirmation Flow Architecture — Verified Facts (June 29, 2026)

Session: auditing a 6-issue build plan against production `server.py` (12,690 lines),
`whatsapp-sidecar/index.js` (1,139 lines), `whatsapp_sidecar_client.py` (186 lines).
All line numbers verified against prod at `root@46.224.132.99:/opt/ara/`.

These are durable architectural facts, not session-specific narrative. Future
confirmation-flow changes should re-verify line numbers (they drift) but the
structure below is stable unless a refactor explicitly restructures it.

---

## 1. Single confirmation gate (agent_chat only)

`agent_chat` (line 6964) is the ONLY function with confirmation logic. The
WhatsApp coaching path (`_handle_owner_coach_whatsapp`, line 11522) prunes stale
rows then POSTs to `agent_chat` via HTTP:

```python
resp = requests.post(
    f"http://localhost:8766/api/agent/chat/{TENANT_ID}",
    json={"message": message, "thread_id": thread.id, "channel": "whatsapp"},
    timeout=120,
)
```

So echo detection, clarification gate, `_classify_confirmation`, entity injection —
all only need to be added in `agent_chat`. They automatically cover the WhatsApp path.

## 2. `user_msg` persistence hazard

`user_msg` is persisted to the DB at line ~7420:
```python
db.add(AgentChatMessage(tenant_id=tenant_id, role="user", content=user_msg, thread_id=thread_id))
```

ANY modification to `user_msg` before this line corrupts the conversation record.
If you need to inject context for the LLM (entity guards, system reminders), use a
SEPARATE variable (`_user_msg_for_llm`) and pass that to the observe loop's
`messages.append({"role": "user", "content": ...})` at line ~7362. Never mutate
`user_msg` itself.

## 3. `_live` variable lifecycle in agent_chat

`_live` is assigned inside the `if not data.get("pre_confirmed", False):` block
(line ~7008). It is referenced LATER at the clarification gate (line ~7142):
```python
if _live is None:
    # clarification gate
```

If you restructure the confirmation block with an `if/else` (e.g., echo detection
that skips classification), the branch that skips MUST still assign `_live = None`
— otherwise the clarification gate raises `NameError: name '_live' is not defined`.

## 4. TOOL_SCHEMAS location and the nonexistent module trap

`TOOL_SCHEMAS` is a module-level dict defined directly in `server.py` at line 6175.
There is NO `build_tools_schema.py` module — `build_tools_schema()` is a function
at line 6242 that builds the OpenAI-format schema FROM the dict.

If you need to reference `TOOL_SCHEMAS` inside any function in `server.py`, it's
already in scope. Do NOT write `from build_tools_schema import TOOL_SCHEMAS` —
this module does not exist and will crash with `ImportError` on first use.

## 5. WhatsApp send-path topology (3 client methods, 20+ call sites)

`whatsapp_sidecar_client.py` (BaileysWA class) has THREE send methods:

| Method | Line | What it does | Call sites in server.py |
|--------|------|-------------|------------------------|
| `send_message_sync(phone, text)` | 136 | Send to phone number | 4137 (execute_tool send_whatsapp), 728/917 (queue), 9588/9632/9648 (scheduler), 11255 (auto-respond), 11729 (notify) |
| `send_to_jid(jid, text)` | 144 | Send to JID (groups, coaching) | 11509 (coaching group), 11664 (coaching response), 11792+ (eval agent, voice pipeline — 15+ sites) |
| `send_document(phone, file_path, ...)` | 70 | Send file/PDF | 4264 (send_attachment tool) |

`send_to_owner(text)` (line 62) delegates to `send_message_sync` — covered.

**Critical for health-check work:** A health check placed ONLY in
`send_message_sync` misses ALL `send_to_jid` calls (coaching responses, voice-note
replies, eval agent) and `send_document` calls. These are the paths where silent
failure is most damaging. Any universal send-path fix must cover all three methods,
or route them through a shared `_post_send_health_check()` helper.

## 6. Sidecar `/status` endpoint — `connected` vs `healthy`

The sidecar's `/status` endpoint (index.js line 976) returns `connected: true`
whenever `connectionState === 'connected'` — even when the session is
cryptographically dead (Bad MAC, decrypt failures on every message).

`decryptErrorCount` (line 266) tracks undecryptable messages. A zombie connection
has `connected: true` but `decryptErrorCount > 10`.

**As of June 29, 2026:** The `/status` endpoint does NOT yet have a `healthy` field.
The confirmation-flow health check (Fix #3, server.py line 7036) only checks
`_sc_data.get("connected")` — it does NOT factor in decrypt errors. A `healthy`
field was proposed in the build plan but is NOT yet deployed.

## 7. `_build_pending_description` — anatomy and pitfalls

### Current fallback code (~line 6996, July 2026)

The generic `else` branch extracts meaningful args from a wider set than earlier
versions AND derives a short label from the tool's TOOL_SCHEMAS description:

```python
else:
    key_args = {k: v for k, v in args.items()
                if k in ("title", "name", "lead_name", "message", "description",
                         "org_name", "key", "value", "summary", "subject", "stage", "body", "text")}
    schema_info = TOOL_SCHEMAS.get(name, {})
    schema_desc = schema_info.get("description", "")
    short_label = ""
    if schema_desc:
        short_label = re.sub(r'^[-\s]+', '', schema_desc.split('.')[0])[:60]
    # ... builds description from short_label + key_args ...
    _BUILD_DESC_FALLBACK_COUNT[name] = _BUILD_DESC_FALLBACK_COUNT.get(name, 0) + 1
    if _BUILD_DESC_FALLBACK_COUNT[name] == 3:
        _cf_log.warning("CONFIRM-FLOW build-desc-fallback: tool=%s used 3 times ..." % name)
```

### Pitfall: `_BUILD_DESC_FALLBACK_COUNT` must be initialized

The audit counter `_BUILD_DESC_FALLBACK_COUNT` is used at line 7010 but is **not**
auto-initialized. It must be defined as a module-level dict **before** any staging
call. If missing, the fallback branch throws `NameError` → `/api/voice/stage` returns
500 for any VOICE_WRITE_TOOLS tool lacking an explicit `elif` case.

**Fix:** `_BUILD_DESC_FALLBACK_COUNT = {}` (placed near `_cf_log` init at ~line 322).

### Pitfall: every VOICE_WRITE_TOOLS entry needs an explicit case

When adding a new tool to `VOICE_WRITE_TOOLS`, also add an `elif name == "..."`
case to `_build_pending_description`. Without it, the tool falls to the generic
`else` branch. That's survivable IF `_BUILD_DESC_FALLBACK_COUNT` is initialized,
but the description quality is poor (generic "Update an action. Can change...").
An explicit case gives the user a readable confirmation like
"✏️ Update action: 091d69f6 to Jul 13 at 05:30 AM — shall I update?"

As of July 2026, explicit cases exist for: set_reminder, set_cron, create_lead,
update_lead, send_whatsapp, send_email, update_lead_stage, update_deal_stage,
create_deal, attach_to_deal, trigger_cadence, escalate_to_human, cancel_scheduled,
create_action/create_action_item, save_memory, send_whatsapp_to_owner,
send_whatsapp_instantly, update_action. Any other VOICE_WRITE_TOOLS entry
(update_deal, schedule_follow_up, schedule_message, schedule_email, etc.)
still hits the fallback.

## 8. Observe loop step limit and retry hazards

`MAX_TOOL_STEPS = 10` (line 6336). Any `continue` inside the loop that fires on a
persistent condition (e.g., step-count mismatch retry) will consume all 10
iterations without producing a proposal. Always add a retry counter (`_retried =
False`, allow max 1 retry) for any loop-internal correction mechanism.

## 9. Clarification gate — current state

The clarification gate (line ~7142) uses an exact-match set + `startswith("yes")
and len <= 7`. It does NOT use regex. Variant confirmations like "yes - run all
three" (18 chars) bypass it. Any regex replacement must be careful: `^yes\b` alone
is too aggressive — it matches "yes what's the weather?" and blocks legitimate
questions. Add a length constraint (`.{0,15}$`) or require the trailing text to be
affirmative language.
