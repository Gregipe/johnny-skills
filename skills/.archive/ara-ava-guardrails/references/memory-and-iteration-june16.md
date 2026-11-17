# Memory System, Reasoning, Error Recovery & Self-Audit — June 16, 2026 (Late Session)

Four new layers added to Ava's intelligence architecture after the Message Classification and System Inspection tools.

## Reasoning Preamble

**Problem:** Ava jumped from classification straight to tool calling without articulating what she was trying to achieve. This caused wrong-tool selection (calling `create_lead` in STRATEGIC mode) and missing-info failures (calling `create_action` without a time).

**Location:** `AGENT_SYSTEM_PROMPT_BASE`, inserted between Message Classification rules and Identity & Context.

**Text:**
```
## Reasoning Preamble (BEFORE touching any tool)
After classifying, state your plan aloud in ONE line before calling tools.

Format: "Got it — [what Greg wants]. I'll [1-2 sentence plan]."
Examples:
- "Got it — Greg wants the check-in pushed to 5 PM. I'll find the action and update its due time."
- "Got it — strategic question about next leads. I'll analyze pipeline gaps first, then suggest targets."
- "Got it — capability question. No tools needed, direct answer."

If your plan involves a tool you DON'T have, say so NOW.
If your plan needs info you DON'T have, ASK before calling tools.
```

## Error Recovery Instincts

**Problem:** When a tool failed, Ava silently moved to the next tool or dumped "Query error: Textual SQL expression..." as her response. She had no error recovery instincts.

**Location:** Rule #7 in Tool-Calling Principles, expanded with 4 recovery paths.

**Text:**
```
7. **Use what the tool returns — then iterate if it fails.**
   On SUCCESS: confirm clearly — state what was done, to whom, and when.
   On ERROR: DIAGNOSE before moving on. Don't silently jump to the next tool.
     • Syntax/format error? Fix your input and retry (up to 2 times).
     • Wrong tool for the task? Switch to the right tool and explain why.
     • Tool doesn't exist for this? Tell Greg: "I can't do X — I don't have a tool for that."
     • Missing required info? Ask Greg: "I need [field] to proceed — what should I use?"
   Never dump raw error text as your response. Never say "Something went wrong."
```

## Confirmation Self-Audit

**Problem:** Confirmations hid critical details. "Create action: Check in with team — shall I create it?" showed no due time. Greg confirmed actions with wrong times because he couldn't see them.

**Also:** All confirmation prompts now show key details:
- `set_reminder`: shows title + time ("for Jun 17 at 9:00 AM")
- `send_whatsapp`: shows lead + message preview
- `send_email`: shows lead + subject + attachment indicator
- `create_action`: shows description + due date/time

**Location:** Execution Intent Protocol, before the marker definitions.

**Text:**
```
## Before Every [ACTION: ASK] — Self-Audit
Before showing Greg a confirmation proposal, pause and run this 3-bullet check:

1. TIME: Is the due date/time exactly what Greg asked for?
2. LEAD: Is this the right lead? If ambiguous, state which one you picked and why.
3. GAPS: Am I missing anything Greg specified?

If any check fails, fix the tool args FIRST, then show the corrected confirmation.
```

## Memory System

**Tools added:**
- `save_memory(key, value)` — writes to `skills` table with `category="memory"`, `source="ava_memory"`
- `search_memory(query)` — ILIKE search on key + value across `skills` table for `category="memory"`

**Injection:** Every `agent_chat` call loads the last 20 memories from the skills table (category="memory") and appends them to the system prompt as:

```
## Your Memories (persisted across sessions)
• greg_prefers_5pm_deadlines: Greg wants check-in actions due at 5 PM unless specified otherwise
```

**Schema:** Uses existing `skills` table — no new table needed. Key columns: id, tenant_id, category, key, value, source, created_at.

## Code-Level Fixes (Same Session)

### `final_response_text` delivery
- **Bug:** `agent_chat` returned `render_results` ("✅ 9 actions completed") instead of LLM's synthesis
- **Fix:** `return {"response": final_response_text or response, ...}` at line 6262

### `query_database` text() wrapper
- **Bug:** Raw SQL strings rejected by SQLAlchemy session
- **Fix:** `from sqlalchemy import text as _sql_text; db.execute(_sql_text(sql))`

### `create_action` date-only default
- **Bug:** Date-only "2026-06-16" defaulted to 9 AM UTC = 2:30 PM IST
- **Fix:** Default to 6 PM IST (12:30 UTC) for close-of-business

### `create_lead` placeholder names
- **Bug:** 18 "TBD — CompanyName" leads created during testing
- **Fix:** Reject names starting with "TBD", "Unknown", "N/A" at tool level

### `_build_pending_description` key params
- **Bug:** Confirmation text hid due time, message content, subject
- **Fix:** All confirmations now show time, message preview, subject, attachment

## Testing Pattern

When testing against the live endpoint (SSH timeouts on long LLM calls):
1. Start curl in background: `curl -s -o /tmp/result.json -w "%{http_code}" -X POST ...`
2. Wait for 200: `sleep 60`
3. Read the file: `cat /tmp/result.json`
4. Files under 100 bytes = error (check server logs)

## Hard Guard — Block Data-Modifying Tools in Analysis Modes (June 16, 2026 — Late Session)

**Problem:** Despite prompt-level anti-patterns saying "Do NOT create leads in STRATEGIC mode," the LLM still called `create_lead` during multi-step observe loop iterations. After 3-4 iterations, the LLM's context got crowded with tool outputs and it lost the classification context. Result: every STRATEGIC analysis created garbage leads.

**Solution: Three-layer code-level defense in `_run_observe_loop()`:**

### Layer 1: Mode Detection from Reasoning Preamble

The first LLM response contains the reasoning preamble (e.g., "Got it — strategic question about next leads. I'll analyze..."). The observe loop extracts classification from this text:

```python
# In _run_observe_loop(), first_pass block:
_text_lower = (text or "").lower()
_analysis_mode = None
if any(w in _text_lower for w in ("strategic", "analyze gap", "suggest target", ...)):
    _analysis_mode = "strategic"
elif any(w in _text_lower for w in ("diagnostic", "why did", ...)):
    _analysis_mode = "diagnostic"
elif any(w in _text_lower for w in ("capability", "can you attach", ...)):
    _analysis_mode = "capability"
```

### Layer 2: Hard Guard at Tool Execution

Before executing each tool, check if it's data-modifying in an analysis mode:

```python
# In tool execution loop (around line 5743):
if _analysis_mode in ("strategic", "capability") and not get_tool_read_only(tn):
    if tn in ("create_lead", "create_deal", "send_whatsapp", "send_email", "trigger_cadence"):
        results.append(ToolResult.fail(tn, "BLOCKED_IN_ANALYSIS",
            f"Cannot {tn} in {_analysis_mode} mode. Analyze and recommend — do not execute."))
        continue
```

### Layer 3: Mode Re-Injection Per Iteration

After tool results are fed back to the LLM, re-inject mode context to prevent drift:

```python
_mode_reminders = {
    "strategic": "Reminder: you are in STRATEGIC mode. Analyze pipeline, identify gaps, suggest targets. Do NOT create leads or deals — just recommend.",
    "diagnostic": "Reminder: you are in DIAGNOSTIC mode. Investigate, present evidence, explain findings. Do NOT execute actions — just diagnose.",
    "capability": "Reminder: you are in CAPABILITY mode. Explain what you can/cannot do. Do NOT call tools to 'check' — answer directly.",
}
if _analysis_mode and _analysis_mode in _mode_reminders:
    loop_messages.append({"role": "user", "content": _mode_reminders[_analysis_mode]})
```

### Layer 4: Failure Diagnosis Prompt

When tools fail, explicitly ask the LLM to diagnose before continuing:

```python
if failed_so_far:
    _fail_names = [f.tool for f in failed_so_far]
    _fail_msg = f"Some tools failed: {', '.join(_fail_names)}. Your move: can you fix the input and retry? Should you try a different approach? If you cannot fix it, tell Greg what went wrong and what you need."
    loop_messages.append({"role": "user", "content": _fail_msg})
```

**Verified:** STRATEGIC query "Analyze my pipeline, suggest targets" → 5 read-only tools, **zero leads created**. The guard blocked `create_lead` at the code level. The prompt-level anti-patterns alone are not sufficient — code-level enforcement is required for multi-step observe loops.

**Commit:** `1d9a81e` — "hard guard blocks data-modifying tools in analysis modes + mode persistence + failure diagnosis"
