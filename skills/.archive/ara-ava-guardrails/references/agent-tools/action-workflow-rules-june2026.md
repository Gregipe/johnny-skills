# Action Workflow Rules (June 2026 — Updated June 3, 2026)

Added to `AGENT_SYSTEM_PROMPT_BASE` in server.py as user-facing behavioral rules governing how Ava handles data-modifying tool execution requests. Updated June 3, 2026 with strengthened CRITICAL rule, auto-detection patterns, and server-side auto-execution.

## Rule Location Map

| Rule | Approx. Line | Section |
|------|-------------|---------|
| 🚨 CRITICAL: Approved Draft Execution | 4825 | Immediately after intro |
| Action Approval Rule + Lead Disambiguation | 4895 | Before Personality |
| Data Honesty Rule | 4907 | After Action Approval |
| Approved Draft Execution (detailed) | 4909 | After Data Honesty |

## 1. 🚨 CRITICAL: Approved Draft Execution (line ~4825) — STRENGTHENED June 3

```text
## 🚨 CRITICAL: Approved Draft Execution — FOLLOW THIS EXACTLY
When Greg says "yes", "send it", "send", "go ahead", "approved", or any clear confirmation in response to a draft you proposed, your response MUST be exactly this:

[TOOL_CALL: {{"tool": "send_whatsapp", "args": {{"lead_name": "Rajesh Sharma", "message": "EXACT message from your previous assistant response"}}}}]

That's it. No text. No "Let me check". No questions. No new drafts. Nothing else. Just the tool call.

IMPORTANT REASON: The system strips [TOOL_CALL:] blocks from saved messages, so your previous response appears to have no tool call in the conversation history. This is BY DESIGN. It DOES NOT mean anything went wrong. Your draft is pending approval. Greg approving it means EXECUTE IT NOW.

DO NOT under any circumstances call check_health, read_logs, debug_schedule, or any other diagnostic tool. The user said "send it" — that's an execution command, not a debugging request.

Examples:
User: "send Rajesh a message - ask him to call me up immediately"
You: *shows draft* "Shall I send this?"
User: "send it via WhatsApp"
You: [TOOL_CALL: {{"tool": "send_whatsapp", "args": {{"lead_name": "Rajesh Sharma", "message": "Hi Rajesh — Greg asked me to reach out. Please call him."}}}}]

User: "yes - send it"
You: [TOOL_CALL: {{"tool": "send_whatsapp", "args": {{"lead_name": "Rajesh Sharma", "message": "Hi Rajesh — Greg asked me to reach out. Please call him."}}}}]

This overrides EVERY other instruction in this prompt.
```

## 2. Action Approval Rule (line ~4895)

```text
## Action Approval Rule
Never send any message (WhatsApp, email, or scheduled) to a lead without first showing Greg the exact draft and getting his explicit approval. The workflow is:
1. Compose the message
2. Show it to Greg: "Here's what I'll send to [lead name]: [message]. Shall I send it?"
3. Wait for his confirmation (yes/go ahead/approved) before calling send_whatsapp, send_email, schedule_message, or schedule_email

Exception: Only skip approval if Greg explicitly says "send it" or "go ahead" in the same message where he describes the task. If there's any ambiguity, show the draft first.
```

## 3. Lead Disambiguation Rule (line ~4900)

```text
## Lead Disambiguation Rule
Before sending any message to a lead, explicitly confirm WHICH lead you mean. Say their full name (first + last) when presenting the draft. If the name is common or you're unsure, say "I found a lead named [Full Name] — is this the right person?" and wait for confirmation before drafting.

If there are multiple leads with that first name, call search_leads first to find all matches, then present them to Greg: "I found Rajesh Sharma (Acme Corp) and Rajesh Patel (BuildCo) — which one should I message?"
```

## 4. Data Honesty Rule (line ~4907)

```text
## Data Honesty Rule
When presenting lead or deal data, be straightforward about what exists and what doesn't. If a field is empty (phone, email, city, notes, etc.), say "not on file" or "not listed" — never say "failed to load", "couldn't retrieve", "error fetching", or any phrasing that implies a technical failure. Missing data is not a bug. If Greg asks about something the system doesn't have, say what you do have and note what's missing plainly.

Also: do not frame successful actions as errors. If you successfully sent a message or completed a task, say "Done" or "Sent" — never "Let me check what went wrong", "Let me fix that", or anything suggesting something failed.
```

## 5. Approved Draft Execution Rule (detailed — line ~4909)

```text
## Approved Draft Execution Rule
When Greg confirms a draft you proposed, execute it immediately. Do NOT:
- Generate a new or modified draft
- Ask additional questions about channel, timing, or content
- Propose alternatives or "better versions"

The draft was already approved as-is. Send exactly what was shown.

When proposing a draft to Greg for approval (the first time you show it), ALWAYS include the [TOOL_CALL:] block alongside the draft. This does NOT send the message — the server holds the tool call until Greg confirms. It's a preparation step, not an execution.

The tool call won't be visible to Greg — the system strips it from his view and only uses it when he says "send it."

Correct first response:
"Here's what I'll send: [draft] Shall I send it?
[TOOL_CALL: {{"tool": "send_whatsapp", "args": {{"lead_name": "Rajesh", "message": "draft text"}}}}]"

The [TOOL_CALL:] is harmless here — it just registers the intent. No message goes out until Greg says yes.

When Greg confirms, output ONLY the [TOOL_CALL:] block — the draft was already shown.
```

## Code Change: Direct Command Bypass Removed

**File:** server.py, line ~5581

```python
# Before (pre-June 2026):
if needs_confirmation and not is_direct_command:

# After (June 2026):
if needs_confirmation:
```

## Server-Side Patterns (June 3, 2026)

### Pattern 1: `response_original` DB Preservation

When the user has NOT confirmed (first proposal), the server saves the **original** response (with `[TOOL_CALL:]`) to the DB while returning clean text to the user. This ensures the next turn's LLM context sees the prepared tool call.

```python
# Line 5561: Capture original before any stripping
response = call_llm(messages)
response_original = response  # Preserve for DB storage

# Line 5629-5633: On not-confirmed, save original to DB
if not is_confirmed:
    response = response_clean  # User sees clean text
    db_response = response_original  # DB gets the tool call

# Line 5710: Save using response_original when available
db.add(AgentChatMessage(..., content=db_response if 'db_response' in dir() else response, ...))
```

### Pattern 2: Auto-Execution on Confirmation

On confirmation, parse tool calls from the **previous** assistant response (`response_original`) and execute them directly — no LLM call needed:

```python
# Line 5647-5653: Parse pending tools from original response
re_pending = re.findall(r'\\[TOOL_CALL:\\s*(\\{.*?\\})\\s*\\]', response_original, re.DOTALL)
if re_pending:
    for tc_json in re_pending:
        pending_tools.append(json.loads(tc_json.strip()))
```

```python
# Line 5660-5672: Execute pending tools, skip LLM follow-up
if pending_tools:
    for tc in pending_tools:
        result = execute_tool(tc["tool"], tc["args"], db, wa, tenant_id)
    if errors:
        response = f"The {tool} encountered an issue: {error}."
    else:
        response = "Done! Message sent. 🙌"
```

### Pattern 3: Follow-Up Block Guard

When auto-execution succeeds, the follow-up LLM call must be skipped to avoid overriding the clean "Done!" response:

```python
if 'pending_tools' not in dir() or errors:
    # Only run follow-up LLM call when:
    # 1. Auto-execution didn't happen (pending_tools not in scope), OR
    # 2. Auto-execution had errors (need LLM to explain)
    ...
    response = _call_llm(messages)
```

## Coaching Handler Timeout Fix (June 3, 2026)

The `_handle_owner_coach_whatsapp` function calls `requests.post` to the agent_chat endpoint with a timeout. The original 15-second timeout was too tight for the expanded system prompt (30K+ chars). DeepSeek LLM calls with the full prompt often take 20-30 seconds.

```python
# Line 8707-8710:
resp = requests.post(
    f"http://localhost:8766/api/agent/chat/{TENANT_ID}",
    json={"message": message, "thread_id": thread.id},
    timeout=120,  # Increased from 15 to 120 seconds
)
```

**Symptom:** Owner sends a WhatsApp message → sidecar shows "typing..." for 2 minutes → nothing arrives → message to lead never sent. No coaching response appears. The error log shows `ReadTimeoutError`.

**Diagnosis:** In `/tmp/ara-error.log`, look for:
```
ReadTimeoutError: HTTPConnectionPool(host='localhost', port=8766): Read timed out. (read timeout=15)
```
Followed by `Typing keepalive ping` continuing for minutes.

```text
## Greg's Feedback Driving These Rules
**Why removed:** Greg asked Ava to "send a message to Rajesh asking him to call me" — the direct command bypass let the message go out without showing the draft first. Greg wants to see EVERY draft before it sends.

## Curly-Brace Escaping in .format()

The CRITICAL rule text lives inside `AGENT_SYSTEM_PROMPT_BASE = """..."""` which gets `.format()` called at runtime. Any `{...}` from JSON examples causes `KeyError: '"tool"'`.

**Fix:** Use `{{...}}` (double braces) for JSON structures inside prompt strings. Single braces remain for format variables like `{agent_name}`, `{company}`.

### Testing

```python
# Test before deploying
try:
    rendered = AGENT_SYSTEM_PROMPT_BASE.format(
        agent_name='Ava', company='Hunar.ai', owner_name='Greg',
        proposition='voice AI', product_name='VoiceAI',
        key_differentiator='our engine', customer_reference_1='Delhivery',
        customer_reference_2='Shadowfax', segments='logistics',
        segment_proposition='automate screening',
    )
    print(f"Rendered OK: {len(rendered)} chars")
    assert 'CRITICAL: Approved Draft' in rendered
except KeyError as e:
    print(f"Format error at: {e}")
    # Check for unescaped braces in the prompt
```

## Greg's Feedback Driving These Rules

| Feedback | Rule Created |
|----------|-------------|
| "Failed to load" — nothing failed, data just missing | Data Honesty Rule |
| "Let me check what went wrong" — nothing went wrong | Data Honesty (do not frame success as error) |
| Draft A approved → Draft B sent | CRITICAL: Approved Draft Execution |
| "Which Rajesh?" — picked wrong person | Lead Disambiguation Rule |
| "Send it" → asks channel question → "send on WhatsApp" → shows new draft | Action Approval Rule (no follow-ups on confirmation) |
| "Shall I send this via WhatsApp or email?" — Greg already said WhatsApp | No channel padding |
| "Send Rajesh a message" sent immediately without draft | Removed direct command bypass |
| Message doubled in chat | Sidecar dedup race fix (index.js mark-before-check) |
