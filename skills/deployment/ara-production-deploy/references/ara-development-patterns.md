# ARA Development Patterns

Class-level patterns for modifying Ava's behavior and the ARA dashboard. Covers system prompt engineering, confirmation flow, and frontend/backend development.

## 1. System Prompt Modification

### Safety Rules

The system prompt lives in `AGENT_SYSTEM_PROMPT_BASE` in `server.py` (a triple-quoted `"""..."""` string). Key rules:

1. **`.format()` is active** — This string is processed with Python's `.format()` at runtime. Every `{` and `}` in your content must be doubled (`{{` and `}}`) except for named format variables like `{agent_name}`, `{owner_name}`, etc. See `references/format-string-pitfall.md` for the full crash analysis.

2. **`AGENT_TOOL_SCHEMA` is safe** — It's appended via `+=`, not `.format()`. Single curly braces work fine there.

3. **Prompt sections to know** (in order):
   - **Brand Voice** (early) — Tone, style, personality. Don't add technical instructions here.
   - **Tool-First Policy** (around line 4890) — Where to add "You MUST call X tool" mandates. This is where `web_search`, `search_knowledge_base` mandates live.
   - **Data Honesty** — Anti-hallucination rules. Add "Never invent data" here.
   - **Read-Only Tools section** — Lists tools Ava can call without asking. Add new read-only tools here.
   - **Data-Modifying Tools section** — Lists tools that need confirmation. Add new data-modifying tools here.

4. **Adding a tool mandate**: Add it in the Tool-First Policy section with a clear "You MUST call" instruction. Add an example `[TOOL_CALL: ...]` format. Make sure the example's curly braces are escaped for `.format()`.

### Common Patterns

**Adding web_search mandate:**
```python
# In Tool-First Policy section (after the KB policy paragraph):
You MUST call **web_search** when Greg asks you to search the internet, look up something online, find news, or any similar request. Output [TOOL_CALL: {"tool": "web_search", "args": {"query": "..."}}] and STOP.
```

**Anti-hallucination:**
```python
# In Data Honesty section:
**CRITICAL: Never invent or fabricate search results, company names, or news.** If Greg asks you to search for something and you did not call web_search, do not pretend you found results.
```

**Adding a tool description to AGENT_TOOL_SCHEMA:**
```python
# Just add a line — no escaping needed here since it's appended via +=
**schedule_message** — Schedule WhatsApp later. Args: {"lead_name": "...", "message": "...", "delay_minutes": 30}
```

### Testing Prompt Changes

```bash
# Quick check: does the format call succeed?
python3 -c "with open('/opt/ara/server.py') as f: compile(f.read(), 'server.py', 'exec'); print('SYNTAX OK')"

# Full test: restart and check API
systemctl restart ara-server && sleep 5
curl -s -X POST http://localhost:8766/api/whatsapp/inbound \
  -H 'Content-Type: application/json' \
  -d '{}' -w ' HTTP:%{http_code}'
# → {"status":"skipped",...} HTTP:200 (means no crash)
```

## 2. Confirmation Flow (Intent Detector)

### Architecture

When Ava proposes a data-modifying action (like `update_lead`, `update_lead_stage`, `send_whatsapp`), the system pauses and waits for the user to confirm before executing.

The flow in `agent_chat()` (around line 5370-5440 in server.py):

```
Ava proposes with [TOOL_CALL: {...}] in response
    ↓
System strips the [TOOL_CALL:] from the text shown to user
    ↓
Checks if user's message is a direct command (first word in command_verbs)
    ↓
If not a direct command, checks:
  1. Hardcoded phrase matching (CONFIRM or REJECT lists)
  2. Falls through to LLM intent detector if no match
    ↓
If CONFIRM → execute the tool call from the original response
If REJECT → return Ava's text without executing
```

### The "Fixed?" Bug

When the user asks "Fixed?" after Ava proposes an action, the LLM intent detector sees it as a question (not a confirmation) and returns REJECT. The action is never executed. Ava then says "Yes, it's fixed" on the next turn without including the TOOL_CALL again.

**Fix:** Hardcoded phrase matching before the LLM call:

```python
_confirm_phrases = ("fixed", "done", "all good", "go ahead", "send it", "do it",
                    "yes", "yeah", "yep", "sure", "ok", "okay", "proceed")
_reject_phrases = ("no", "nope", "nah", "dont", "wait", "hold", "stop",
                   "cancel", "never mind")
_msg_clean = user_msg.strip().lower().rstrip("?!.")
if any(_msg_clean.startswith(p) for p in _confirm_phrases):
    is_confirmed = True
elif any(_msg_clean.startswith(p) for p in _reject_phrases):
    is_confirmed = False
else:
    # Fall through to LLM intent detector
```

Also add "fixed" and "done" to `command_verbs` so these are recognized as direct commands on first messages.

### Data-Modifying Tools

The set that needs confirmation is at line ~5375 in server.py:
```python
data_modifying_tools = {
    "update_lead", "update_lead_stage", "update_deal", "update_deal_stage",
    "send_whatsapp", "send_whatsapp_to_owner", "send_email",
    "schedule_message", "schedule_email", "schedule_follow_up",
    "trigger_cadence", "cancel_scheduled", "set_reminder",
    "save_learning", "send_internal_note", "create_action_item",
    "evaluate_qualification", "mark_meeting_booked",
    "escalate_to_human", "log_insight", "upload_document",
    "add_to_watchlist", "resolve_watchlist_item",
    "attach_to_deal", "detach_from_deal", "create_deal",
}
```

If you add a new tool that modifies data, add it here and to the tool schema.

## 3. Frontend Development (Dashboard)

### Architecture

The entire frontend is a **single vanilla JS SPA** at `/opt/ara/static/dashboard.js` (~204KB). CSS is inline in the HTML template in `dashboard_template.py`. No framework — raw DOM manipulation.

### File Locations

| What | Where |
|------|-------|
| HTML + CSS | `dashboard_template.py` — Python string with `<!DOCTYPE html>` |
| JavaScript | `/opt/ara/static/dashboard.js` — all rendering logic |
| Backend API | `server.py` — `@app.get`/`@app.post` routes |

### How to Add a Frontend Feature

1. **Backend first**: Add the API endpoint in `server.py`
2. **Frontend renderer**: Add a render function in `dashboard.js`
3. **Navigation**: Add to sidebar + page switch logic
4. **CSS**: Inline in the `<style>` block of `dashboard_template.py`

### Key Frontend Patterns

**Rendering a page/tab:**
```javascript
else if (page === 'activities') renderActivities();

function renderActivities() {
  var cp = document.getElementById('contentPanel');
  fetch('/api/action-items?limit=50').then(function(r){...}).catch(...);
  cp.innerHTML = '...';
}
```

**Making an API call:**
```javascript
fetch('/api/leads/' + leadId, {
  method: 'PATCH',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({name: newName, notes: newNotes})
}).then(...)
```

### Lead Editing Pattern (toggleEditLead)

The lead detail page has a full inline-edit system at `toggleEditLead()` (~line 2537) and `saveLead()` (~line 2591). To make a field editable:

1. Add `data-field="fieldname"` to the `<span class="value">` inside `#leadDetailCard`
2. `toggleEditLead()` converts `span.value[data-field]` into `<input>` or `<select>`
3. `saveLead()` reads all `.lead-edit-input` elements and PATCHes `/api/leads/{id}`

**Adding the lead name field:**
The name was displayed in the header (`<div class="lead-name-large">`) but NOT inside the card. Added:
```html
<div class="lead-info-row">
  <span class="label">Name:</span>
  <span class="value" data-field="name">...</span>
</div>
```
The edit system auto-picks it up from `data-field="name"`. **Always put editable fields inside `#leadDetailCard`.**

### Chat Input: textarea with Auto-Grow (replacing `<input type="text">`)

The original chat input was `<input type="text">` which is single-line by nature. Long text scrolls horizontally instead of wrapping.

**Fix:** Replace with `<textarea>` that enters Submit on Enter, Shift+Enter for newlines, auto-grows up to 120px:

```html
<!-- Before: -->
<input type="text" placeholder="Coach Ava..." id="chatInput"
       onkeydown="if(event.key==='Enter')sendMsg()">

<!-- After: -->
<textarea placeholder="Coach Ava..." id="chatInput"
          onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendMsg();}"
          oninput="autoGrowChatInput(this)" rows="1"></textarea>
```

**CSS added:**
```css
.chat-input-wrap input, .chat-input-wrap textarea { flex:1; border:none; background:transparent; font-size:13px; font-family:inherit; color:#111; outline:none; }
.chat-input-wrap textarea { resize:none; min-height:20px; max-height:120px; padding:0; line-height:1.5; overflow-y:auto; white-space:pre-wrap; word-wrap:break-word; }
```

**JavaScript auto-grow:**
```javascript
function autoGrowChatInput(el) {
  el.style.height = 'auto';
  el.style.height = el.scrollHeight + 'px';
}
```

Also reset height in `sendMsg()`: `inp.style.height = 'auto';` after clearing the value.

### Text Wrapping Fix (Chat Messages)

For long unbroken strings (URLs, company names) in chat messages:
```css
/* Before: */
.chat-msg { white-space: pre-wrap; }

/* After: */
.chat-msg { white-space: pre-wrap; overflow-wrap: break-word; }
```

The CSS is in `dashboard_template.py` (line ~72), **not** in `dashboard.js`.

### Static File Cache Busting

After editing `dashboard.js`, bump the version string in `dashboard_template.py`:
```html
<script src="/static/dashboard.js?v=N"></script>
```
Increment `N` when you deploy new JS. Browsers cache aggressively.

## 4. Adding Scheduling to an Existing Tool (send_whatsapp_to_owner)

When an existing tool only supports immediate execution and needs scheduling support, follow this pattern:

### Step 1: Add `delay_minutes` parameter in the tool handler

In `server.py`'s `execute_tool()` function, find the tool handler and add:
```python
message = args.get("message", "")
delay_minutes = int(args.get("delay_minutes", 0))  # ← add this
```

### Step 2: Add scheduling branch before the immediate-send path

```python
if delay_minutes > 0:
    scheduled_at = utcnow() + timedelta(minutes=delay_minutes)
    action = ScheduledAction(
        tenant_id=tenant_id,
        lead_id=None,  # ← None for owner-directed messages
        action_type="whatsapp_to_owner",  # ← unique type for this target
        status="pending",
        scheduled_at=scheduled_at,
        payload={"message": message},
        channel="whatsapp",
    )
    db.add(action)
    db.commit()
    return f"📬 Scheduled to you at {eta} ({delay_minutes} min from now)."
```

### Step 3: Add handler in the scheduler's `_execute_action()`

In the legacy format section (around line 7618), add:
```python
elif action.action_type == "whatsapp_to_owner":
    message = payload.get("message", "")
    if message:
        admin = db.query(User).filter(
            User.tenant_id == action.tenant_id,
            User.role == "admin"
        ).first()
        if admin and admin.phone:
            wa.send_message_sync(admin.phone, "Ava: " + message)
```

### Step 4: Update the tool schema in AGENT_TOOL_SCHEMA

Update the tool description to show the optional parameter:
```
**send_whatsapp_to_owner** — Send WhatsApp to Greg (or schedule with delay_minutes).
Args: {"message": "...", "delay_minutes": 30}
```

### Step 5: Verify

1. `compile()` the file — look for indentation errors
2. Restart the server
3. Test: send a message with `delay_minutes=1` — check it appears in `scheduled_actions` table
4. Wait for the scheduler to fire it (runs every 30s)

## 5. Adding a New Tool to Ava

1. Add the tool description to `AGENT_TOOL_SCHEMA` (no escaping needed)
2. Add the handler in `execute_tool()`: `elif tool_name == "my_new_tool":`
3. If data-modifying, add to `data_modifying_tools` set (line ~5375)
4. If read-only, add to the read-only prompt section
5. If it adds new action types that run via the scheduler, add a handler in `_execute_action()`
