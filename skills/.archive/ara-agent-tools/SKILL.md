---
name: ara-agent-tools
title: "ARA Agent Tools — JSON Tool Calling for Ava"
description: "Add structured JSON tool-calling capabilities to Ava's agent chat endpoint. Covers the tool dispatcher pattern, [TOOL_CALL: {json}] format, [ACTION: NOW]/[ACTION: ASK] execution-intent architecture, ToolResult structured response layer with render_results(), DEPENDS_MAP for dependency skips, regex parsing, system prompt schema design, working hours constraints, frontend suggestions integration, voice note confirmation policy, and pitfall avoidance."
category: "software-development"
triggers:
  - "Adding a new tool/action Ava can perform"
  - "Adding tenant-contextualized web search via search lens (see references/tenant-search-lens.md)"
  - "Extending Ava's ability to call APIs, update leads/deals, send messages"
  - "Migrating from text-marker [TOOL_CALL:] parsing to native function calling"
  - "Building or debugging the observe loop (call_llm_with_tools + tool result feedback)"
  - "Adding or updating a tool in build_tools_schema() — must sync with execute_tool()"
  - "Running the schema coverage assertion test after tool changes"
  - "Implementing the execution-intent architecture ([ACTION: NOW] / [ACTION: ASK] protocol)"
  - "Building the structured ToolResult-based response renderer"
  - "Debugging Ava claiming she 'doesn't have visibility' or 'doesn't know' info that's stored in the DB"
  - "Injecting owner/tenant context into the agent system prompt"
  - "Adding user-facing action workflow rules — approval, draft execution, lead disambiguation"
  - "Ava generating a new draft instead of executing the approved one on confirmation"
  - "Ava asking channel/timing follow-up questions after Greg already confirmed"
  - "Ava framing missing optional data (phone, email) as 'failed to load' or platform errors"
  - "Ava sending a message to the wrong lead when multiple share a first name"
  - "Debugging observe loop: MAX_TOOL_STEPS hit, tool results not fed back, claim/no-call false positive"
  - "LLM calling check_health/read_logs on confirmation because tool calls were stripped from history"
  - "LLM conflating 'move to new stage' with 'send a WhatsApp' — tool conflict detection"
  - "Canned response fabricating 'Message sent' when only stage was updated"
  - "Over-generating outreach tools from context pollution in coaching thread"
  - "Adding interim WhatsApp/voice message to combat dead air during slow processing"
  - "Debugging voice pipeline silent failures"
  - "Setting up dynamic morning briefing with __morning_briefing__ special message"
  - "Scheduler cron reschedule causing infinite loop on invalid frequency"
files:
  - references/regex-patterns.md
  - references/suggestions-frontend-integration.md
  - references/scheduled-action-delegation-pattern.md
  - references/suggestion-chips-pattern.md
  - references/action-agent-7-layer-expansion.md
  - references/system-awareness-design.md
  - references/tool-conflict-middleware-june2026.md
  - references/agent-context-injection.md
  - references/action-tools-reference.md
  - references/llm-intent-confirmation-may2026.md
  - references/data-visibility-audit-may2026.md
  - references/tool-execution-response-layer.md
  - references/code-advisor-tool-execution-response-spec.md
  - references/observe-loop-advisor-fixes-june2026.md
  - references/sql-null-comparison.md
  - references/sed-line-insertion.md
  - references/partial-confirmation.md
---

## Tool-Based Architecture Philosophy

**Core principle: The only non-deterministic part of the system is Ava's natural-language response. Everything else — every data read, write, or transformation — must go through a deterministic tool call.**

### The 95/5 Rule

- **95% of user requests** should be handled by Ava's existing toolset immediately, with no iteration. The observe loop ensures this by catching responses that describe changes instead of executing them, and letting the model retry with corrected args.
- **~5% of requests** (long-tail, novel capabilities) will find no matching tool. These should trigger the metacognition layer — Ava logs the gap via `log_capability_request`, offers a workaround, and the gap becomes a build signal.
- **If significantly more than 5% of requests enter the iterative/metacognition path**, the toolset is incomplete — that's the verticalization signal. Build the missing tools.

### Layered Defense (Execution Integrity — June 2026 Architecture)

```
User request
  → Build messages + TOOLS_SCHEMA (native API parameter)
  → [OBSERVE LOOP] — bounded 4-step loop:
      → call_llm_with_tools(messages, TOOLS_SCHEMA) — native function calling
      → [CLAIM/NO-CALL CHECK] — catches "I've updated X" without tool call, re-prompts
      → [INTENT GATE] — parse [ACTION: NOW] / [ACTION: ASK] marker
      → Execute tools deterministically
      → Feed structured ToolResult back as role:"tool" message
      → Loop continues: model sees results, may retry/chain
  → Render final response from ToolResult objects
```

Only the first step involves the LLM. Everything in between is deterministic code. The enforcer, phantom-update corrector, and phantom-lookup corrector from the old architecture were **deleted** (June 2026) — the observe loop's claim/no-call detection handles all three cases with one rule.

## Native Function Calling (June 2026 — Replaces Text-Marker Parsing)

**What changed:** The agent loop now uses native OpenAI-compatible function calling via the `tools` API parameter instead of parsing `[TOOL_CALL: {...}]` text markers from the LLM response.

### The Old Architecture (Pre-June 2026)

```python
# Text-marker parsing — 60 lines of balanced-brace matching
response = call_llm(messages)  # LLM outputs raw text
tool_calls = _parse_tool_calls(response)  # Extract [TOOL_CALL: {...}] from text
```

- System prompt taught LLM to output `[TOOL_CALL: {"tool": "name", "args": {...}}]` as text
- 60-line `_parse_tool_calls()` function with balanced-brace matching
- Brittle: JSON formatting errors, missing brackets, nested-brace breakage
- 200-char marker search limit silently dropped long tool calls
- Prompt bloat: every tool definition lived in the system prompt text

### The New Architecture (June 2026)

```python
# Native function calling — API returns structured JSON
from induction_engine import call_llm_with_tools

out = call_llm_with_tools(messages, TOOLS_SCHEMA, model="deepseek-v4-pro")
tool_calls = out["tool_calls"]    # [{"id": "...", "name": "...", "args": {...}}]
text = out["text"]                 # LLM's natural language response
raw = out["raw_tool_calls"]        # Provider-shape for appending to messages
```

- Schemas live in the `tools` API parameter (never in the prompt text)
- `build_tools_schema()` generates OpenAI-format JSON schema for all 50 tools
- Coverage test diffs schema keys against `execute_tool()` branches on every PR
- `tool_choice="auto"` so the model can answer simple questions without tools
- Lower temperature (0.2) for the tool-deciding turn
- Malformed JSON args captured as `{"_raw": "<string>"}` — loop feeds back to model

### Key Components

**`call_llm_with_tools(messages, tools, model, temperature)`**
— `induction_engine.py`. Sends `tools` parameter to DeepSeek API (OpenAI-compatible). Returns dict: `{text, tool_calls[{id,name,args}], raw_tool_calls, raw, error}`. Error-safe: returns `{"error": str}` on provider failure. Existing `call_llm()` is untouched for non-agentic callers (insight extraction, cadence gen, stage detection).

**`build_tools_schema()`**
— `server.py`. Returns OpenAI-format JSON schema list, one entry per `tool_name ==` branch in `execute_tool()`. Each entry: `{type:"function", function:{name, description, parameters}}` with `additionalProperties: true` for flexible arg passing.

**`get_tool_read_only(name)`**
— `server.py`. Returns `True` if the tool is read-only (auto-execute, no confirmation needed). Used by the intent gate to distinguish writes from reads.

### The Observe Loop

Replaces the single-call-then-parse flow with a bounded feedback loop:

```python
MAX_TOOL_STEPS = 4
while steps < MAX_TOOL_STEPS:
    out = call_llm_with_tools(loop_messages, TOOLS_SCHEMA)
    
    # Claim/no-call check (replaces enforcer + phantom correctors)
    if not tool_calls and _claims_action_without_call(text):
        re_prompt: "You described an action but issued no tool call..."
        continue
    
    if not tool_calls:
        final_text = text  # model answered directly
        break
    
    # Intent gate — resolved once on first pass
    if requires_confirmation(tool_calls, text) and not confirmed:
        store_pending(...)
        break
    
    # Execute tools + feed results back
    results = [execute_tool(tc.name, tc.args, ...) for tc in tool_calls]
    loop_messages.append({"role": "assistant", "content": text, "tool_calls": raw})
    for tc, r in zip(tool_calls, results):
        loop_messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(r)})
```

**What was deleted (no longer needed):**
- `_parse_tool_calls()` — replaced by native `tool_calls` in API response
- The `_data_keywords` pre-execution enforcer block — replaced by observe loop's claim/no-call check
- The phantom-update corrector (`update_claim_re` + re-prompt cascade)
- The phantom-lookup corrector (`_lookup_claim_re` + re-prompt)
- `AGENT_TOOL_SCHEMA` constant — replaced by `build_tools_schema()` + `tools` API parameter
- Model routing keywords — agent loop defaults to Pro

**Kept as fallback:** `_parse_tool_calls(response)` still runs inside the observe loop when `call_llm_with_tools` returns empty `tool_calls` but the text contains `[TOOL_CALL:]` markers. This covers model swaps or API regression. Tracked for deletion in `docs/deletion_ticket_parse_tool_calls.md`.

### Migration Path (Build Order)

See `references/native-function-calling-build-spec.md` for the full seven-part build spec that was executed June 13, 2026. Parts 6 → 1 → 3 → 2 → 5 → 4 → 7.

**Status:** All 7 parts complete and deployed. 22 tests pass across 3 test suites.

## Metacognition Layer (Capability Gap Logging)

When Ava cannot fulfill a request (no matching tool, or all attempts fail), she follows this flow from the system prompt:

1. **Interim message:** "Let me check what I can do..." (signals user processing is happening)
2. **Identify the gap:** Determine exactly what capability is missing
3. **Log the gap:** Call `log_capability_request` with user_request, missing_capability, attempted_tool, workaround
4. **Offer workaround:** Find the closest thing she CAN do with existing tools
5. **Ask:** Present the workaround and ask if the user wants it

Creates an ActionItem with `action_type="capability_request"`. Johnny queries these to prioritize build decisions from real demand.

## Pre-Execution Enforcer (HISTORICAL — Replaced by Observe Loop June 2026)

> **⚠️ This section describes the old architecture that was removed in June 2026.**
> The enforcer, phantom-update corrector, and phantom-lookup corrector were all replaced
> by the observe loop's claim/no-call check. See the "Native Function Calling" section
> above for the current architecture. This section is kept for historical reference only.

**Purpose:** Catches LLM responses that describe or acknowledge a data change WITHOUT including a [TOOL_CALL:] block — before the response is saved or sent. Runs immediately after Stage 1 LLM call, before tool call parsing.

Checks `user_msg` for data-modifying keywords (update, change, create, send, set, schedule, remind, etc). If keywords found but no `[TOOL_CALL:]` in response, re-calls the LLM with specific instructions.

**Key insight:** Complements the post-processing check (which catches phantom updates after execution). The enforcer catches them before any execution — the response isn't even saved to DB until after this gate passes.

### Question Detection (Critical — Prevents False Triggers)

The enforcer must NOT fire on questions about capabilities ("Can you set cron jobs?", "Do you have X?"). Three-layer detection:

1. **Question mark check** — `"?" in _msg_lower` catches most questions
2. **Start-with check** — `_msg_clean.startswith(("can", "could", "would", "do", "does", "is", "are", "will", "what", "how", "should", "may"))` catches leading question words
3. **Substring check** — `any(" " + w + " " in " " + _msg_clean[:60] + " " for w in _question_words)` catches questions embedded after names/greetings like "🎤 hey eva, could you..."

**Voice note emoji stripping:** Voice transcripts arrive prefixed with `🎤`. The `_msg_clean` must strip emoji characters before checking startswith:
```python
_msg_clean = _msg_lower.strip().lstrip("🎤👍💬💭️✨🌟").strip()
_is_question = "?" in _msg_lower or _msg_clean.startswith(_question_words) or any(
    " " + w + " " in " " + _msg_clean[:60] + " " for w in _question_words
)
```

**Without this:** "🎤 hey eva, could you set a reminder..." passes keyword check (`"set"`) but fails startswith (`"hey"` not `"could"`) — enforcer fires and wastes 30s+ on a re-call. With the substring check, `" could "` IS found in the first 60 chars.

### Interim Message (Combat Dead Air)

When the enforcer fires (identifying a genuinely slow path), send an immediate interim message so the user sees progress:

```python
if _has_intent and not _has_tool and not _is_question:
    try:
        _interim = "Ava is thinking..."
        wa.send_to_jid(COACHING_GROUP_JID, _interim)
    except Exception:
        pass
```

**Using `COACHING_GROUP_JID`** — Greg's personal WhatsApp JID defined at module level in server.py. The interim message is a permanent text message (not a transient typing indicator) so the user sees it even if WhatsApp's typing indicator times out (~20-30s).

### Data-Tool-Only Check (NOT Any [TOOL_CALL:])

The enforcer must NOT be satisfied by diagnostic tools (read_logs, check_health, fetch_url) when the user asked for a data-modifying action. The LLM may investigate instead of executing — respond with "Let me check the logs" while calling read_logs, which satisfies a naive [TOOL_CALL:] check.

**Fix (deployed 99d7676):** Check for data-modifying tool names specifically, not just any [TOOL_CALL:] pattern:

```python
_data_tools = ["set_cron", "set_reminder", "create_lead", "update_lead", "create_deal",
               "update_deal", "send_whatsapp", "send_email", "update_lead_stage", ...]
_has_data_tool = any('"tool": "' + t + '"' in response for t in _data_tools)

if _has_intent and not _has_data_tool and not _is_question:
    # Enforcer fires — LLM didn't call a real data tool
```

**Without this:** LLM responds with "[TOOL_CALL: read_logs]" → enforcer sees [TOOL_CALL:] → skips → logs are read but the user's request is never executed.

The same check applies in the re-call path — if the re-call STILL calls read_logs instead of a data tool, log and proceed (don't loop infinitely).

### Hallucination Contagion — Cleaning Conversation History

**Problem (June 2026):** When the LLM generates a hallucinated "tool failed" response, that response becomes part of the conversation history. On subsequent turns, the LLM reads its OWN hallucination and repeats it: "Yes, the cron tool hit a system error again."

16 duplicate voice notes + 7 hallucinated "cron tool failed" responses accumulated over 3 days. Each new turn reinforced the belief.

**Fix — two-layer:**

1. **DB cleanup** — Delete hallucinated assistant messages from the conversation history:
```sql
DELETE FROM agent_chat_messages
WHERE role='assistant'
  AND (content LIKE '%hit a system error%'
    OR content LIKE '%couldn''t save%'
    OR content LIKE '%read_logs%');
```

2. **Prompt rule** — Add to system prompt:
```
## Forgetting Past Tool Failures
If your previous response about a tool said it "failed", "hit an error", 
or "couldn't save" — IGNORE that. The tool IS working now. Do not mention 
past failures. Do not offer workarounds. Just call the tool again with the 
correct arguments and report the actual result.
```

**Warning signs:**
- LLM repeats the same error message across multiple turns without any change in system state
- LLM says "the tool hit an error" but the server logs show no actual tool error
- User is sending the same request repeatedly getting different hallucinated variants of the same failure

### Re-call Prompt (Specific Instruct, Not Generic)

The enforcer re-call prompt must tell the LLM WHICH tools to use, not just "call something":

```python
_enforcer_prompt = (
    "Your previous response did NOT include a [TOOL_CALL:] block for the action the user requested.\\n"
    "The user asked you to: " + user_msg + "\\n\\n"
    "Pick the right tool and call it NOW with the correct arguments.\\n"
    "Available tools: set_cron, set_reminder, schedule_message, schedule_email, "
    "create_lead, create_deal, update_lead, send_whatsapp, send_email, "
    "trigger_cadence, create_action_item, save_learning, log_insight, log_capability_request.\\n"
    'Example: [TOOL_CALL: {\\"tool\\": \\"set_cron\\", \\"args\\": {\\"title\\": \\"Morning Briefing\\", \\"frequency\\": \\"daily\\", \\"time\\": \\"06:30\\"}}]\\n'
    "Output ONLY your natural language response with the [TOOL_CALL:] block included."
)
```

**Why:** The old generic prompt (`"You MUST include a tool call"`) caused the LLM to respond with "Let me check the logs and offer a fix" — metacognition-style noise instead of actually calling the tool. The specific prompt lists the available tools and gives an example matching the user's intent.

### Re-check After Re-call

After the enforcer re-call, re-evaluate `_has_tool` on the new response. If it STILL has no tool call, log a warning and proceed (do NOT loop):

```python
try:
    response = call_llm(messages, model=_chat_model)
    _has_tool = "[TOOL_CALL:" in response
    if not _has_tool:
        logging.getLogger("ara").warning(
            f"Pre-execution enforcer: re-call still has no tool call."
        )
except Exception:
    logging.getLogger("ara").error("Pre-execution enforcer re-call failed")
```

**Why:** Before this fix, the enforcer re-called the LLM and replaced `response`, but never checked if the new response had a tool call. The code fell through to tool parsing with a tool-less response — Ava said "Yes I can" but never actually called set_cron.

**Single attempt only** — never loops more than once. The 95% rule says if the first re-call doesn't produce a tool call, the toolset may be incomplete (or the user's request is genuinely a question/statement). Log the gap and proceed.

See `references/enforcer-improvements-june2026.md` for the full evolution of the enforcer across multiple sessions.

## Model Routing (Flash vs Pro) — DELETED June 2026

**This feature was removed on June 13, 2026.** The keyword-based router (`_model_routing_keywords` in server.py) was deleted. Rationale from the technical advisor: "wrong route toward Pro costs $0.02-0.05, wrong route toward Flash costs a silently dropped action which correctors then spend two extra Pro calls to claw back anyway."

**Current behavior:** The agent loop always uses `deepseek-v4-pro` (set via `_chat_model`). `deepseek-v4-flash` is still used explicitly at server.py line ~1589 for non-agentic subtasks (JSON extraction, insight analysis) where no tool-calling contract is needed.

If a cost-saving route optimizer is needed in the future, use model-level queuing/scheduling (e.g., route non-urgent requests to Flash during off-peak) rather than keyword-based routing — keyword lists always have blind spots that cause silent failures.

## Architecture Overview

Ava's tool calling uses an **execution-intent pattern**:

```
LLM generates response → declares intent via [ACTION: NOW] / [ACTION: ASK]
  → Code OBEYS the declaration (no second-guessing)
  → [ACTION: NOW] → execute tool calls immediately
  → [ACTION: ASK] → store as pending, return proposal, wait for user
  → User responds → check pending (confirm/reject) or re-enters normal flow
```

**Execution intent protocol (system prompt):**
- `[ACTION: NOW]` — Execute immediately. Use when: user gave a direct command, responded to your question with the requested info, explicitly confirmed a previous proposal, or asked for a correction.
- `[ACTION: ASK]` — Show proposal and ask for confirmation. Use when: you are proposing an action (not a direct command), voice notes (STT garbles names), or actions with significant side effects.
- No marker → assumes `[ACTION: ASK]` for data-modifying tools.

The response is built from structured `ToolResult` objects via `render_results()` — single LLM call per action, no synthesis re-call. See `references/tool-execution-response-layer.md`.

**Voice notes:** ALL data-modifying voice actions always require confirmation (STT garbles names/phones/emails). The voice note check at the execution gate overrides any `[ACTION: NOW]` marker.

## Tool Format

Ava outputs tools as inline JSON inside `[TOOL_CALL: ...]` brackets:

```
[TOOL_CALL: {"tool": "update_lead", "args": {"lead_name": "Gregory Ipe", "fields": {"stage": "qualified"}}}]
```

Multiple tool calls in one response are supported — they execute in order.

## Implementation Steps

### 1. Build the tool dispatcher

Create a Python function `execute_tool(tool_name, args, db, wa, tenant_id)` that:
- Acts as a single dispatch table via `if/elif` (or a dict lookup)
- Each tool handler is responsible for its own DB operations, commit, and result string
- Returns a string describing the outcome (success or error)
- Uses helper functions for fuzzy entity resolution:

```python
def resolve_lead(name_hint, db):
    lead = db.query(Lead).filter(Lead.name.ilike(f"%{name_hint}%")).first()
    if not lead:
        raise ValueError(f"Lead '{name_hint}' not found")
    return lead

def resolve_deal(name_hint, db):
    deal = db.query(Deal).filter(Deal.org_name.ilike(f"%{name_hint}%")).first()
    if not deal:
        raise ValueError(f"Deal '{name_hint}' not found")
    return deal
```

### 2. Write the system prompt

The system prompt is split into two layers: a **behavioral base prompt** (AGENT_SYSTEM_PROMPT_BASE, the `.format()`-able template) and a **pipeline context block** (appended as a separate f-string after `.format()`). The tool schema is NEVER in the prompt text — it lives in the `tools` API parameter via `build_tools_schema()`.

#### Placeholder Conventions (June 2026+)

| Placeholder | Source | Example Value |
|-------------|--------|--------------|
| `{agent_name}` | `ctx["agent_name"]` | `"Ava"` |
| `{user_name}` | `ctx["owner_name"]` | `"Greg"` (same as owner_name in single-owner mode) |
| `{owner_name}` | `ctx["owner_name"]` | `"Greg"` |
| `{company}` | `ctx["company"]` | `"Hunar.ai"` |
| `{current_datetime}` | `now_ist.strftime(...)` | `"Saturday, June 13, 2026 at 11:42 AM"` |
| `{timezone}` | `"IST"` | `"IST"` |

The `user_name` vs `owner_name` distinction exists for multi-rep coaching: `{user_name}` is the person Ava is chatting with, `{owner_name}` is the admin who owns settings/induction. In single-owner mode they're identical.

#### Format Call Template

```python
now_ist = datetime.now(IST)
system_prompt = AGENT_SYSTEM_PROMPT_BASE.format(
    agent_name=ctx["agent_name"],
    user_name=ctx["owner_name"],
    owner_name=ctx["owner_name"],
    company=ctx["company"],
    current_datetime=now_ist.strftime('%A, %B %d, %Y at %I:%M %p'),
    timezone="IST",
)
```

#### Pipeline Injection (After .format())

Pipeline data is NEVER embedded in the base prompt. Append it after `.format()`:

```python
system_prompt += f"\n\n## Pipeline\nLEADS ({len(leads)} total):\n{lead_details}\n\nDEALS ({len(deals)} total):\n{deal_details}\n\nINDUCTION: {skills_context}\nDOCUMENTS: {doc_context}\nINTEGRATIONS: {whatsapp_status}\n..."
```

This keeps the base prompt stable across tenants and DB states.

### Historical Architecture References

#### Pre-June 2026 Architecture (Text-Marker Parsing)

**This section describes the pre-June 2026 two-part format. The current architecture (June 2026+) uses a single behavioral prompt — see "Native Function Calling" section above.**

The old system prompt was split into two parts to avoid `.format()` conflicts with JSON curly braces:

```python
AGENT_SYSTEM_PROMPT_BASE = """You are Ava... {company}... {lead_count}..."""
AGENT_TOOL_SCHEMA = """AVAILABLE TOOLS — ... [TOOL_CALL: {...}] ..."""

# At call site:
system_prompt = AGENT_SYSTEM_PROMPT_BASE.format(...)
system_prompt += AGENT_TOOL_SCHEMA
```

**Current architecture (June 2026):** `AGENT_TOOL_SCHEMA` was deleted from the prompt-append path (Part 4). The tool schema now lives in the `tools` API parameter via `build_tools_schema()` — never in the prompt text. The system prompt is purely behavioral: it teaches *how* to use tools, not what tools exist.

Key changes in the new behavioral prompt:
- Removed `[TOOL_CALL: {...}]` format teaching (native API handles format)
- Removed tool inventory list (replaced by `build_tools_schema()`)
- Removed threat framing ("Violation = false information")
- Added "After a tool runs" section (structured feedback from observe loop)
- Added "Read vs. write" intent protocol with `[ACTION: NOW]` / `[ACTION: ASK]`
- Kept: identity, pipeline context, post-engagement, system awareness, forgetting past failures

Include in the tool schema:
- Tool reference table (name, description, args schema, available fields)
- 5-7 concrete examples covering common use cases
- Note about backward compatibility with old `[SEARCH:]`, `[WHATSAPP:]` formats

### 3. Parse tool calls from LLM response

Replace the old if/elif regex chain with a unified parser:

```python
import re
import json

# Parse new [TOOL_CALL: ...] JSON format
tool_calls = []
tc_matches = re.findall(r'\[TOOL_CALL:\s*(\{.*?\})\s*\]', response, re.DOTALL)
for tc_json in tc_matches:
    try:
        tc = json.loads(tc_json.strip())
        tool_calls.append((tc.get("tool"), tc.get("args", {})))
    except (json.JSONDecodeError, TypeError):
        pass

# Also parse old-style patterns and translate
search_match = re.search(r'\[SEARCH:\s*(.*?)\]', response)
# ... etc
if search_match:
    tool_calls.append(("web_search", {"query": search_match.group(1).strip()}))
```

## ToolResult Response Layer (June 2026 — replaces Step 4 "re-call")

The response-building from tool execution now uses structured `ToolResult` objects and a pure-function renderer:

```python
for _tc in _tools_to_run:
    _r = execute_tool(tn, args, db, wa, tenant_id)
    _tr = from_legacy_string(tn, _r) if not isinstance(_r, ToolResult) else _r
    _results.append(_tr)

_results = apply_dependency_skips(_results, _tools_to_run)
response = render_results(_results, channel=_channel)
```

**No re-call LLM call.** The renderer builds the response deterministically from structured fields (ok, verb, entity, summary, error, suggestions). Channel-aware: WhatsApp gets `- ` bullets and 900-char cap. Error taxonomy with recovery templates covers ~90% of failure modes without an LLM call.

**No-hallucination guarantee:** The LLM never touches the output text. LLM generates the request (tool call with data) -> tool executes against the real DB -> structured `ToolResult` objects -> `render_results()` (pure Python, 0 LLM calls) -> user text. The `response` string is a deterministic function of `tool_results`. They cannot disagree.

### API Response Contract (June 2026)

Every agent_chat response now includes:
```json
{
  "response": "✅ Created lead Jimmie Tete: phone 0123456789 | company Bajaj",
  "thread_id": "abc123",
  "tool_results": [
    {
      "tool": "create_lead",
      "ok": true,
      "verb": "Created lead",
      "entity": "Jimmie Tete",
      "entity_id": "4a43e37a",
      "summary": "phone: 0123456789 | company: Bajaj",
      "suggestions": [{"kind": "create_deal", "prompt": "...", "args": {...}}],
      "error": null
    }
  ]
}
```
When no tools executed, `tool_results` is `null`. The rendered `response` and the structured `tool_results` come from the same source and are guaranteed to agree.

### Migration Status

**All 33 tools now return native `ToolResult`.** The `from_legacy_string()` adapter is effectively unused — it only passes through for read-only diagnostic tools (get_*, search_*, list_*) that still return string formatted results. Every mutation tool returns `ToolResult.success()` or `ToolResult.fail()` with proper error codes, recovery text, and structured details.

The adapter is retained as a safety net for future tools that aren't immediately migrated, but any new mutation tool should return native `ToolResult` from day one.

### UNKNOWN Error Diagnosis (Part 3)

For the rare case where a tool returns `"UNKNOWN"` error code (taxonomy miss), `render_results.py` includes a `diagnose_unknown_error()` function. It searches the results for `UNKNOWN`-coded errors and appends a diagnostic message to the response:

```python
if any(not r.ok and r.error and r.error.code == "UNKNOWN" for r in _results):
    _dx = diagnose_unknown_error(_results, user_msg)
    if _dx:
        response = _dx
```

The current implementation is template-based (`"Something unexpected happened with {tool}: {msg}. Want me to try a different approach?"`). The ideal would be a single cheap LLM call (deepseek-v4-flash, max 150 tokens, 8s timeout) but requires API key access from the subprocess context. Template fallback is sufficient since `UNKNOWN` errors are rare.

See `references/tool-execution-response-layer.md` for the full spec: ToolResult dataclass, error taxonomy, renderer rules, DEPENDS_MAP, and legacy adapter.

## Confirmation Gate (for data-modifying tools)

Add a confirmation layer BEFORE step 4. When tools are data-modifying, the server asks for user confirmation instead of executing immediately.

> **Single-action guard & partial confirmation (June 17, 2026):** See `references/single-action-guard.md` for the `_guard_single_action` (prevents LLM from bundling unsolicited extra tools) and `_split_partial_rejection` (handles "ignore X, do Y" in multi-tool proposals). Both deployed to server.py.

#### Tool Classification

Define which tools modify data:

```python
_DATA_MODIFYING_TOOLS = {
    "update_lead", "create_lead", "attach_to_deal", "detach_from_deal",
    "create_deal", "update_deal",
    "send_whatsapp", "send_whatsapp_to_owner", "send_email", "send_internal_note",
    "save_learning", "set_reminder",
    "create_action_item", "update_lead_stage", "update_deal_stage", "schedule_follow_up",
    "escalate_to_human", "log_insight",
    "schedule_message", "schedule_email", "cancel_scheduled",
    "trigger_cadence", "evaluate_qualification", "mark_meeting_booked",
}

def _is_data_modifying(tool_name):
    return tool_name in _DATA_MODIFYING_TOOLS

## Autonomous Tool Exception

Some tools modify data but need no confirmation because they're purely enrichment. Currently `add_skill` saves learnings silently. To add an exception: omit from `_DATA_MODIFYING_TOOLS` and list under read-only in the system prompt. Rule of thumb: enrichment/observation = autonomous; stage changes, escalations, outbound messages = always confirm.

**⚠️ Multi-tool confirmation gap:** `_classify_confirmation` is all-or-nothing. "Ignore X, just do Y" with multi-tool proposals → `reject` kills everything. See `references/multi-tool-confirmation-gap.md`.

## Adding a New Tool (Checklist)

1. **Handler** — Add `elif tool_name == 'my_tool':` block in
   `execute_tool()` function. Return a descriptive result string.
2. **System prompt definition** — Add a numbered entry to the tool
   schema in `AGENT_TOOL_SCHEMA` with name, description, args format,
   valid values, and usage notes.
3. **Verify enum values against DB** — Before writing the schema definition,
   check the actual DB model or existing API handlers for the correct valid values.
   Tool schema stage lists (e.g. `new/reached_out/engaged/qualified/...`)
   frequently drift from the DB model. A stale stage value causes the LLM
   to call tools with invalid arguments that silently fail or do the wrong thing.
   Cross-reference: `grep 'Column.*Enum\|valid_stages\|valid_.*=' database.py`.
4. **Examples** — Add a concrete `[TOOL_CALL: {...}]` example below
   the definitions.
5. **Confirmation gate** — Add to `data_modifying_tools` set if the
   tool modifies state. Omit if autonomous (see exception above).
6. **Read-only list** — Add to the `IMPORTANT: Read-only tools (...)` line
   in the system prompt if the tool is read-only (and also the
   `Read-only tools (...)` line in System Awareness).
7. **Confirmation prompt text** — Update the `IMPORTANT: Before
   executing any action that CHANGES data (...)` line to include
   your new tool name. If read-only, add to the companion list in
   the same line instead.
8. **Wire the tool in two places** — Both `agent_chat()` and
   `send_scheduled_step()`/`_execute_action()` must have access to
   the same `execute_tool()` dispatcher. The handler lives in one
   place; both call paths use it.
9. **Numbering** — Assign the next sequential number. Check the last
   numbered entry in `AGENT_TOOL_SCHEMA` to find the next number.
10. **Final sweep** — After all changes, verify:
    - The tool name appears in `data_modifying_tools` (if data-modifying)
    - The tool name appears in the `IMPORTANT:` confirmation line
    - The tool has at least one `[TOOL_CALL:]` example in the examples section
    - The tool definition lists all required args
    - The tool number matches its position in the sequence
11. **Run gatekeeping tests** — Two tests MUST pass after any tool addition:
    - `test_schema_coverage::test_all_tools_have_schema` — asserts every `elif tool_name ==` branch in `execute_tool()` has a matching `TOOL_SCHEMAS` entry AND vice versa. Missing either = FAIL.
    - `test_shadow_imports::test_execute_tool_local_imports_must_be_aliased` — asserts local `from database import ActionItem` imports use aliases (`as _AI`) if `ActionItem` was already imported at module level. Unaliased = FAIL.
    - Also update `test_build_tools_schema_returns_list` count (`assert len(schema) == N`) to match the new total tool count.

### Tool Patterns

#### Read-Only Diagnostic & Data Tool Pattern (e.g., check_health, query_leads)

Some tools aggregate and return live system data without modifying state. These are read-only by nature:
- `check_health` — probes WhatsApp (wa.status_sync()), Gmail (IntegrationConfig DB query), Tavily (resolve_api_key()), sidecar (HTTP to :8767/health). Returns a status summary with emoji indicators.
- `query_leads` — filters leads by segment/stage/source/industry/city, optionally groups by a field and returns counts with percentage bars. Supports two modes: filtered list or grouped breakdown.

**Implementation pattern:**
```python
elif tool_name == "check_health":
    results = {}
    try:
        wa_status = wa.status_sync()
        results["whatsapp"] = "connected" if wa_status.get("authenticated") else "disconnected"
    except Exception as e:
        results["whatsapp"] = f"error: {e}"
    # ... more services ...
    return "### Health\n" + "\n".join(f"{icon} **{s.title()}**: {v}" for s, v in results.items())
```

**When to use this pattern:**
- Probing multiple independent services and returning a unified status (`check_health`)
- Aggregating DB data with optional grouping, filtering, or math (`query_leads`, `list_documents`)
- Any tool that queries state without changing it — these NEVER go in `data_modifying_tools`

**Checklist for adding a read-only diagnostic tool:**
1. Handler returns a formatted string — no DB commits, no side effects
2. Add to `AGENT_TOOL_SCHEMA` with note "READ-ONLY — no confirmation needed"
3. Add to the system prompt's read-only tools list (the long IMPORTANT line)
4. Add examples showing both modes (list + grouped)
5. Do NOT add to `data_modifying_tools` set — it's read-only

#### Notification Ref-Checking Pattern (June 2026)

Some tools return notifications that reference underlying DB records (ScheduledAction, ActionItem) that may have been completed or resolved since the notification was created. Always cross-reference:

```python
# In the notification list endpoint, post-filter results:
actionable_types = {"escalation", "action_failed", "action_item", "call_reminder"}
filtered = []
for n in notifs:
    # Check if the underlying ref is still active
    if n.ref_type == "scheduled_action" and n.ref_id:
        sa = db.query(ScheduledAction).filter(ScheduledAction.id == n.ref_id).first()
        if sa and sa.status in ("completed", "cancelled"):
            continue  # skip — action already done
    # Skip info-only types  
    if n.notif_type not in actionable_types:
        continue
    filtered.append(n)
return [format_notification(n) for n in filtered]
```

**When to use:** Any endpoint that returns notifications, activity feed, or items referencing external records. Three filters to apply:
1. **Staleness filter** — exclude records older than a threshold (e.g., `action_failed` > 24h)
2. **Ref-status filter** — exclude notifications whose underlying record is completed/cancelled
3. **Type filter** — exclude info-only types (synthesis_ready, system_notices) from actionable counts

**The bell icon rule:** Users want the count to represent "things I need to do" — not "things that happened." Cross-reference all three filters against the actual data before returning counts.

#### DB-Fetched Destination Pattern (e.g., send_whatsapp_to_owner)

Some tools send to an implicit destination that must be fetched from the database rather than passed as a parameter. The canonical example is `send_whatsapp_to_owner`: the owner's phone number is stored in the DB (via Settings tab), not passed by the user.

**How it works:**
```python
elif tool_name == "send_whatsapp_to_owner":
    lead_name = args.get("lead_name")
    message = args["message"]
    # Fetch owner's phone from the DB rather than requiring it as args
    user = db.query(User).filter(User.tenant_id == tenant_id).first()
    if not user or not user.phone:
        return "Error: Owner phone not configured in Settings"
    result = send_whatsapp_message(user.phone, message, wa, tenant_id)
    if result.get("status") == "sent":
        return f"✅ Message sent to owner ({user.phone[-4:]})"
    return f"Error: {result.get('error', 'Send failed')}"
```

**When to use this pattern:**
- Sending to the owner/admin (their contact info is always in the DB)
- Sending to a system-defined destination (default notification channel, primary email)
- Any case where the destination is known from context and shouldn't be re-typed

**When NOT to use:**
- Sending to leads (phone/email passed per-message, always different)
- Sending to external recipients the system doesn't know about

**Checklist for adding a DB-fetched destination tool:**
1. Add to `_DATA_MODIFYING_TOOLS` set (it modifies state — sends a message)
2. Add handler in `execute_tool()` that queries the DB for the destination
3. Add to `AGENT_TOOL_SCHEMA` with args that DON'T include the destination field
4. In the schema description, explain that the tool sends to the owner automatically
5. Test end-to-end — verify the DB query returns the right value and the message sends

```
Read-only tools (web_search, fetch_url, search_leads, search_deals) execute immediately — no confirmation needed.

## Data Visibility Audit (Systematic Gap Analysis)

Before adding a new tool or injecting new data into Ava's context, run a **data visibility audit** to answer "what else doesn't she see?" This prevents the discover → patch → discover → patch cycle.

### When to run this

- Greg asks "what else does she not see?" after a fix
- Before adding any new context field to the system prompt
- When Ava claims she "doesn't have visibility" into something stored in the DB
- When adding a new Settings tab field that should be accessible to Ava

### The Methodology

1. **Map all DB tables** — `inspector.get_table_names()` against the DB, list every column
2. **Map what Ava already sees:**
   - System prompt context (time, owner phone, induction status, email status, action item count, leads list, skills, documents)
   - Tools available (`get_system_map`, `get_cadence_config`, `get_action_items`, `search_leads`, `search_deals`, `read_logs`, `debug_schedule`, etc.)
   - Per-message injected data (WhatsApp connection status, watchlist items)
3. **Cross-reference** — for each DB table/column not surfaced, ask:
   - "Would Greg ever ask about this?" → if yes, it's a gap
   - "Would Ava ever need this to do her job autonomously?" → if yes, it's a gap
   - "Is this data dynamic enough that a tool is better than hardcoded prompt text?" → if yes, use a tool
4. **Classify gaps by impact:**
   - **High** — directly answerable questions Greg would naturally ask (owner phone, induction status, email connectivity)
   - **Medium** — queryable data supporting deeper work (action items, segment configs, pending scheduled actions)
   - **Low** — internal metrics, audit trails, historical data rarely queried
5. **Choose delivery mechanism:**
   - **System prompt context** — tiny, always-relevant data (phone number, induction status, connectivity status)
   - **Read-only tool** — list-structured data queried on demand (action items, segments, pending scheduled actions, insights)
   - **Augment existing tool** — data that belongs with related info (add `tenant_info` to `get_system_map`)

### Real Example (May 2026 — Greg's WhatsApp Number)

| Step | Action |
|------|--------|
| 1. Gap found | Greg stored his number via Settings tab, Ava couldn't see it |
| 2. Trace path | `_get_agent_context()` returned `{agent_name, owner_name, company}` — no `phone` |
| 3. Fix | Added `owner_phone` to return dict, injected into system prompt context section |
| 4. Wider audit | Checked induction status, email integration, action items, tenant segments — all gaps |
| 5. Apply pattern | Induction + email → context. Action items → tool. Segments → augment `get_system_map` |

### Pitfalls

- **Stale server masks the fix** — After changing `_get_agent_context()` or system prompt building, verify the **correct** server process was restarted. A stale server on a different port serves old responses. Check: `lsof -i :8766` for PID, then `ps -p <pid> -o lstart=` vs file mtime. See `references/ava-pitfalls-2026-06-16.md` for more recent pitfalls.
- **Context fields compound token usage** — Every field added to the system prompt consumes context window. Use tools for queryable data, context for always-on data.
- **DB has it ≠ agent can access it** — Never assume data stored in the DB is visible to the LLM agent. The agent only knows what's in its system prompt and tools. Always trace the full path: DB → prompt building code → LLM call.
- **One gap fix often reveals more** — When fixing a data visibility gap, run the full audit. Greg will ask "what else?" and you want to answer with a complete inventory, not iterate one-by-one.
- **Confirmation flow bugs compound silently** — When confirmation proposals create ActionItem rows, check: (a) PENDING_TTL is long enough for voice-to-text round-trips (600s), (b) voice_note check runs AFTER pre_confirmed so it always wins, (c) title comes from `_build_pending_description()` not LLM conversational text, (d) `status=resolved` is set on both accept AND reject paths. See `references/confirmation-flow-bugs-june2026.md`.
- **New reference files** — `references/system-inspection-tools-june2026.md` (4 new tools), `references/email-attachment-support-june2026.md` (attachment dispatch), `references/scoped-prompt-improvements-june2026.md` (prompt changes scoped, not yet built).

## Tool Alias Pattern

When a tool has multiple names for discoverability, add an alias handler in `execute_tool()` that delegates:

```python
elif tool_name == "send_whatsapp_instantly":
    return execute_tool("send_whatsapp", args, db, wa, tenant_id)
```

The alias appears in `AGENT_TOOL_SCHEMA` with a note "Same as tool #N. Included for discoverability." Only the canonical name goes in `_DATA_MODIFYING_TOOLS`.

## Time Injection (IST at Dispatch Time)

Inject current IST time at LLM dispatch time, not at system prompt save time. Static time goes stale.

Include an explicit `Time of day` label (Morning/Afternoon/Evening/Night) so the LLM doesn't have to infer it from AM/PM. LLMs are unreliable at extracting time periods from raw timestamps — they frequently say "Good morning" at 3 PM IST without this label.

```python
IST = timezone(timedelta(hours=5, minutes=30))
now_ist = datetime.now(IST)
# Determine time-of-day label for greeting awareness
_hour = now_ist.hour
if 5 <= _hour < 12: _tod = "Morning"
elif 12 <= _hour < 17: _tod = "Afternoon"
elif 17 <= _hour < 21: _tod = "Evening"
else: _tod = "Night"

system_prompt += f"\n\n## Context\nCurrent time: {now_ist.strftime('%A, %B %d, %Y at %I:%M %p IST')} (UTC+5:30) — Time of day: {_tod}\nOwner WhatsApp: {ctx['owner_phone']}\n..."
```

Also update the Tone section to explicitly reference the Time of day field:
```
- Greet {owner_name} by name using the appropriate Time of day from the Context
  section (Morning / Afternoon / Evening / Night). E.g. "Good morning, Greg" in
  the morning, "Good afternoon, Greg" in the afternoon, etc.
```

### Why This Matters — Real Bug (June 2026)

Ava said "Good morning, Greg" at **3:33 PM IST** because she was given "03:33 PM IST" in the context but didn't extract "Afternoon" from the AM/PM notation. The fix explicitly labels the time period so the greeting is always accurate.

## 7-Layer Action Agent Expansion

See `references/action-agent-7-layer-expansion.md` for the full architecture — expanding Ava from 13 tools to ~30 tools across 7 layers (Time, Schedule, CRM, Communication, Knowledge, Personal Assistant, Memory). Includes tool listings, implementation patterns, and the complete data-modifying tools list.

#### Confirmation Flow (Parse-and-Recheck — No Thread Metadata)

The implemented approach avoids thread metadata entirely. It re-parses the LLM's response in the same turn and checks the user's current message for confirmation intent:

#### LLM-Based Intent Detection (Primary Method — May 2026)

The original keyword-based confirmation list was brittle — it required maintaining a comprehensive set of confirmation words, didn't understand context, and failed on non-English confirmations like "kar de" (Hindi), "haan", or "ho jaye".

**The fix:** Replace the hardcoded keyword gate with an LLM-based intent detection call. When the user's message is not a direct command, the server calls back to the LLM with a specific confirmation prompt:

```python
# LLM-based intent detection replaces the CONFIRMATION_WORDS set
if not is_direct_command:
    confirmation_prompt = (
        "Determine if the user is confirming or rejecting a proposed action. "
        "Understand tone, slang, shorthand, Hinglish, Hindi, and any language. "
        "Respond with exactly one word: CONFIRM or REJECT."
    )
    confirmation_msgs = [
        {"role": "system", "content": confirmation_prompt},
        {"role": "user", "content": (
            f"Ava proposed the following action to Greg:\n"
            f"---\n{llm_response_text}\n---\n\n"
            f"Greg replied: '{user_msg}'\n\n"
            f"Is Greg confirming or rejecting this action? "
            f"Respond: CONFIRM or REJECT"
        )}
    ]
    confirmation_result = call_llm(confirmation_msgs)
    is_confirmed = "CONFIRM" in confirmation_result
```

**Key design decisions:**
- **Direct command bypass was REMOVED (June 2026)** — The old `is_direct_command` check at line 5576-5581 (server.py) let verb-first commands ("send a message to...", "create a deal...") skip the LLM confirmation gate. Greg explicitly asked for this to be removed after Ava fired a message without showing the draft first. **Current behavior: ALL data-modifying tool calls require confirmation, even verb-first commands.** The condition is now just `if needs_confirmation:` without the `and not is_direct_command` clause. The `is_direct_command` variable still exists in the code but is unused in the gate.
- The LLM sees the full context — The prompt includes both what Ava proposed and what Greg said, so it judges intent with full conversational understanding — not a single word in isolation.
- **Language-agnostic** — The LLM understands Hindi, Hinglish, code-switching, shorthand, and any language. No keyword list maintenance needed.
- **Single word output** — Constrained to "CONFIRM" or "REJECT" for deterministic parsing.

**Evolution from keyword-based approach:**
1. **Initial:** Hardcoded `CONFIRMATION_WORDS = {"yes", "ye", "yeah", ...}` with `startswith()` matching → brittle, missed "ok", "k", failed on non-English
2. **Expanded:** Added "ok", "okay", "k" → still language-bound, failed on "kar de", "haan"
3. **LLM-based (current):** Call back to the LLM with full context → handles any language, tone, slang

The keyword-based approach is retained as a **fallback** — if the LLM call fails (timeout, API error), the server falls back to keyword matching. The keyword set is used only when the LLM is unavailable.

### Flow Diagram (End-to-End — June 2026)

```
1. User: "send Rajesh a message - ask him to call me up immediately"
2. LLM response:
   → Shows draft: "Hi Rajesh — Greg asked me to reach out. Please call him."
   → Asks: "Shall I send it via WhatsApp?"
   → Includes [TOOL_CALL: {"tool": "send_whatsapp", "args": {"lead_name": "Rajesh Sharma", "message": "..."}}]
3. Server detects tool calls AND they're data-modifying (needs_confirmation=True).
   → Calls LLM for intent detection (CONFIRM/REJECT).
   → Greg's message is a NEW instruction → REJECT → Return draft text without executing.
   → (Tool calls are stripped from the saved assistant message.)
4. User: "send it via WhatsApp"
5. LLM response — CRITICAL rule triggers:
   → [TOOL_CALL: {"tool": "send_whatsapp", "args": {"lead_name": "Rajesh Sharma", "message": "EXACT same draft"}}]
   → NO new text, NO new draft, NO questions
6. Server detects tools + needs_confirmation=True.
   → Calls LLM for intent detection: "send it via WhatsApp" → CONFIRM
   → Executes send_whatsapp tool
   → Re-calls LLM with results for synthesis
```

#### Direct Command Detection — REMOVED (June 2026)

**Previous behavior:** Messages starting with imperative verbs (send, create, update) bypassed the confirmation gate. Greg explicitly asked for this to be removed after Ava fired a message without showing the draft first.

**Current behavior:** ALL data-modifying tool calls require confirmation, even verb-first commands. The `is_direct_command` variable still exists in the code (server.py line ~5579) but is never checked in the confirmation gate.

The `command_verbs` set and `is_direct_command` logic remain in the code but serve no active function. They could be removed in a cleanup pass but keeping them doesn't cause harm (they're just unused).

**What this means for the confirmation logic:**
```python
# Current (June 2026):
if needs_confirmation:  # Removed: `and not is_direct_command`
    # Check intent via LLM
    # CONFIRM → execute tools
    # REJECT → return proposal without executing

# Historical (pre-June 2026):
if needs_confirmation and not is_direct_command:
    # Direct commands like "send a message to Rajesh" skipped confirmation
```

See `references/action-workflow-rules-june2026.md` for the full rationale and Greg's feedback that drove this change.

The check runs alongside the confirmation word check:

```python
command_verbs = {"stop", "cancel", "send", "start", "trigger", "restart",
                 "pause", "resume", "create", "update", "delete", "remove",
                 "add", "schedule", "mark"}
first_word = msg_lower.split()[0] if msg_lower.split() else ""
is_direct_command = first_word in command_verbs

is_confirmed = is_direct_command or any(
    ...
)
```

The original [TOOL_CALL:] blocks stay in the assistant message so they can be re-parsed on the next turn. No pending state needed.

#### Implementation in agent_chat()

```python
# After parsing tool_calls from the LLM response:

data_modifying_tools = {"update_lead", "attach_to_deal", ...}
tool_names = {t[0] for t in tool_calls}
needs_confirmation = bool(tool_names & data_modifying_tools)

# Check if the user's current message is a confirmation or a direct command
msg_lower = user_msg.lower().strip()

# Direct command detection: imperative verbs grant implicit permission
command_verbs = {"stop", "cancel", "send", "start", "trigger", "restart",
                 "pause", "resume", "create", "update", "delete", "remove",
                 "add", "schedule", "mark"}
first_word = msg_lower.split()[0] if msg_lower.split() else ""
is_direct_command = first_word in command_verbs

# Also match confirmation words (yes, ok, do it, etc.)
is_confirmed = is_direct_command or any(
    msg_lower == w or msg_lower.startswith(w)
    or msg_lower.startswith(w + ",") or msg_lower.startswith(w + ".")
    for w in CONFIRMATION_WORDS
)

if needs_confirmation and not is_confirmed:
    # Clean markers from response, ask "Shall I proceed?"
    response_clean = re.sub(
        r'\[TOOL_CALL:\s*\{.*?\}\s*\]', '', response, flags=re.DOTALL
    )
    response_clean = re.sub(
        r'\[(SEARCH|FETCH_URL|CADENCE_TRIGGER):\s*.*?\]', '', response_clean
    )
    response_clean = response_clean.strip()
    confirmation_text = response_clean or "I can help with that."
    if not confirmation_text.endswith("?"):
        confirmation_text += " Shall I proceed?"
    response = confirmation_text
else:
    # Confirmed (or read-only tools) — execute all and re-call LLM
    results = []
    for tool_name, args in tool_calls:
        result = execute_tool(tool_name, args, db, wa, tenant_id)
        results.append(f"Tool '{tool_name}': {result}")

    result_summary = "\\n".join(results)
    follow_up = (
        f"All requested actions completed:\\n{result_summary}\\n\\n"
        f"DO NOT repeat what you already said — the user saw it. "
        f"Respond naturally. Do NOT output [TOOL_CALL:] blocks."
    )
    messages.append({"role": "user", "content": follow_up})
    response = call_llm(messages)
```

**Tradeoff:** The original [TOOL_CALL:] blocks persist in chat history. They're stripped from the saved message via `response_clean`.

### 3.5 Scheduling Tools (Time-Offset Pattern)

Three tools let Ava schedule future actions using the existing `ScheduledAction` DB model:

```python
# schedule_message — WhatsApp at a future time
elif tool_name == "schedule_message":
    lead = resolve_lead(args["lead_name"], db)
    delay = args.get("delay_minutes", 30)
    now = utcnow()
    msg = db.query(CadenceMessage).filter(
        CadenceMessage.tenant_id == tenant_id,
        CadenceMessage.lead_id == lead.id,
    ).order_by(CadenceMessage.created_at.desc()).first()
    send_at = now + timedelta(minutes=delay)
    action = ScheduledAction(
        tenant_id=tenant_id, lead_id=lead.id,
        action_type="whatsapp",
        payload={"message": args["message"], "sequence_name": msg.sequence_name if msg else None},
        execute_after=send_at, status="pending"
    )
    db.add(action); db.commit()
    return f"⏳ Scheduled WhatsApp for {lead.name} in {delay} min"

# schedule_email — same pattern, action_type="email", payload includes subject + body
# cancel_scheduled — marks ScheduledAction.status="cancelled" where status="pending"
```

The scheduler daemon polls every 30 seconds — no cron expressions needed. Use `delay_minutes` as the offset from current time, never absolute timestamps.

### 3.6 Personal Assistant Tools

```python
# set_reminder — creates ActionItem for Greg
# get_summary — aggregates lead/deal/conversation stats
```

### 3.7 Knowledge Tools

```python
# search_knowledge_base — SQLAlchemy ilike search across Skill.key/Skill.value
# save_learning — inserts new Skill row with category validation
```

#### Confirmation Words Must Be Comprehensive (Historical / Fallback Only)

**This section is historical context.** The primary confirmation method now uses LLM-based intent detection (see section above). The keyword list below is only used as a fallback when `call_llm()` fails (timeout, API error) — it should still be maintained for that edge case.

The original confirmation word list was missing `"ok"`, `"okay"`, and `"k"` in the initial implementation. This caused a silent failure — Greg said "ok", the code didn't match, Ava looped asking "Shall I proceed?" but Greg was told "Done!". The DB was never updated.

**Required word list:**

```python
CONFIRMATION_WORDS = {
    "yes", "ye", "yeah", "sure", "confirm", "proceed",
    "do it", "go ahead", "please do", "go for it",
    "that's right", "correct", "ok", "okay", "k",
}
```

Matching uses `startswith()` so "yes please", "ok sounds good", "go ahead and do it" all trigger. Also covers punctuation variants (period, comma).

**Anti-patterns:**
- Exact-match only ("ok" won't match "ok do it")
- Missing common abbreviations like "k" or "ok"
- Not having a fallback default when is_confirmed is False — leads to infinite confirmation loop

#### System Prompt Instructions

Add to the tool schema section of the system prompt:

```
CRITICAL — CONFIRMATION RULE:
Before using ANY data-modifying tool (update_lead, attach_to_deal, create_deal,
send_whatsapp, trigger_cadence, etc.), you MUST:
1. Propose what you want to do (explain the action and its effects)
2. Ask "Shall I proceed?" at the end
3. Include the [TOOL_CALL: {json}] block in your response so it can execute
   when the user confirms

Read-only tools (web_search, fetch_url, search_leads, search_deals) can be
executed immediately without asking.
```

#### Alternative: Thread Metadata Approach

For contexts where storing pending state across turns is beneficial (e.g. the LLM response is large and re-parsing is expensive), use the thread-metadata pattern in `references/confirmation-thread-metadata.md`.

### 6. Working Hours Constraints (Optional)

When tools fire at scheduled times (auto-emails, cadence messages), respect working hours:

```
WhatsApp/SMS → fire anytime (low intrusion)
Email/Call   → only 9AM-6PM weekdays (respect recipient's business hours)
Replies      → bypass all constraints (the lead engaged first, so it's urgent)
```

Implementation is channel- and trigger-context-specific — apply in the tool handler or scheduler, not in the core re-call loop.

### 7. Security: Prompt Injection Hardening

When building agent tools that accept external input (lead messages, user text), the system prompt must be hardened against prompt injection.

**Core principle:** Never interpolate user-controlled text into instruction sentences. Always place it in a clearly labeled data section with visible delimiters.

**The fix applied** (full details in `references/action-agent-7-layer-expansion.md#security-hardening`):

- ❌ **Dangerous** — `- {lead_message} is the latest message` (inline injection — lead's text becomes part of the instruction)
- ✅ **Safe** — `## The lead's latest message:\n<lead_message>\n{lead_message}\n</lead_message>` (labeled data with delimiters)
- **Defense in depth:** Also send the lead's message as a separate `{"role": "user", "content": message}` — the LLM sees it both ways

**Also check:** `lead_name` injection. If a lead's name (from CRM) contains "ignore all instructions", it can become active text in the prompt. Use labeled sections for lead metadata too.

### 8. Contextual Suggestions (Optional)

When tools fire at scheduled times (auto-emails, cadence messages), respect working hours:

```
WhatsApp/SMS → fire anytime (low intrusion)
Email/Call   → only 9AM-6PM weekdays (respect recipient's business hours)
Replies      → bypass all constraints (the lead engaged first, so it's urgent)
```

Implementation is channel- and trigger-context-specific — apply in the tool handler or scheduler, not in the core re-call loop.

### 8. Contextual Suggestions (Optional)

Add a `GET /api/agent/suggestions/{tenant_id}` endpoint that returns 5-8 clickable suggestion chips based on pipeline state. These are shown on new chat load and cleared when the conversation starts.

```python
@app.get("/api/agent/suggestions/{tenant_id}")
def agent_suggestions(tenant_id: str, db: DBSession = Depends(get_db)):
    """Return contextual suggestions for the chat panel based on pipeline state."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        return {"suggestions": []}
    suggestions = []

    # Lead-specific: suggest next-stage promotion for each lead in pipeline
    leads = db.query(Lead).filter(
        Lead.tenant_id == tenant_id,
        Lead.stage.in_(["new", "reachout", "qualified", "meeting_booked"])
    ).limit(3).all()
    for lead in leads:
        next_stage = _next_stage(lead.stage)
        if next_stage:
            suggestions.append({
                "text": f"Move {lead.name} to {next_stage.title()}",
                "tool": "update_lead",
            })
        suggestions.append({
            "text": f"What's happening with {lead.name}?",
            "tool": "search_leads",
        })

    # Deal-based
    deals = db.query(Deal).filter(Deal.tenant_id == tenant_id).limit(3).all()
    for deal in deals:
        suggestions.append({
            "text": f"What's the latest on {deal.org_name}?",
            "tool": "search_deals",
        })

    # General suggestions
    suggestions.extend([
        {"text": "Show me all my leads", "tool": "search_leads"},
        {"text": "Search the latest news about Voice AI", "tool": "web_search"},
    ])

    return {"suggestions": suggestions[:8]}
```

The frontend fetches this on page load / new chat and renders clickable chips (see Pitfall 7 below for frontend integration tips):

```javascript
function fetchSuggestions() {
  fetch('/api/agent/suggestions/' + TENANT)
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!data.suggestions || data.suggestions.length === 0) return;
      renderSuggestions(data.suggestions);
    });
}

// Hide suggestions on first user message
function clearSuggestions() {
  var el = document.getElementById('suggestionChips');
  if (el) el.style.display = 'none';
}
```

### 9. English-Only Language Enforcement (DeepSeek Mandarin Problem) — REMOVED from prompt June 2026

**The English-only enforcement was removed from `AGENT_SYSTEM_PROMPT_BASE` during the June 2026 prompt trim.** Previously it was the first sentence: "You ALWAYS respond in English, regardless of the language the user writes in."

**If DeepSeek starts switching to Mandarin again**, add it back as the first line. DeepSeek models have a known tendency to switch to Mandarin based on lead names or Indian city names in context. The position matters: LLMs give higher weight to instructions at the start.

**Two prompts that historically needed this:**
1. `AGENT_SYSTEM_PROMPT_BASE` (agent_chat / dashboard chat with Greg)
2. `AVA_AUTO_SYSTEM_PROMPT` (WhatsApp auto-responder to leads)

**Context length warning:** Do NOT append this as a trailing caveat. It must be early in the prompt to override the language-detection signals from lead data.

`_GLOBAL_THROTTLE` list, `json.loads(f.read())`)


**Cross-reference:** `references/build-desc-fallback-count-july2026.md`

## Troubleshooting

#### The Engagement States

| State | Condition | Tone |
|-------|-----------|------|
| `outbound` | `first_reply_at` is `None` — lead has never replied | Standard SDR outreach |
| `first_reply` | Lead just replied for the first time | Deferential — acknowledge their response, don't push hard |
| `follow_up` | Lead has replied before (2+ inbound messages), last contact within 7 days | Direct and efficient — they know you already |
| `repeat_contact` | Lead came back after 7+ days gap | Warm re-engagement — reference the gap naturally |

#### DB Fields Required

On the `Lead` model:
```python
last_contacted_at = Column(DateTime, nullable=True)  # Updated on every inbound reply
first_reply_at = Column(DateTime, nullable=True)      # Set once on first inbound reply
```

Both fields are set atomically in the inbound message handler:
```python
now_dt = utcnow()
lead.last_contacted_at = now_dt
if not lead.first_reply_at:
    lead.first_reply_at = now_dt
```

#### The Detector Function

```python
def _engagement_stage(lead):
    if not lead.first_reply_at:
        return "outbound"
    if not lead.last_contacted_at or lead.last_contacted_at == lead.first_reply_at:
        return "first_reply"
    days_since = (utcnow() - lead.last_contacted_at).days if lead.last_contacted_at else 7
    return "repeat_contact" if days_since > 7 else "follow_up"
```

#### Dual Injection Points

The engagement stage must be injected into TWO system prompts:

**1. `AGENT_SYSTEM_PROMPT_BASE` (agent_chat / dashboard chat):**

Included in the per-lead detail line and explained in the prompt body:

```
LEADS (N total):
- Lead Name | Company | Source | Stage: engaged | Engagement: first_reply | Email: ...
- Lead Name | Company | Source | Stage: new | Engagement: outbound | Email: ...

Each lead has an Engagement signal: outbound / first_reply / follow_up / repeat_contact.
Adjust your tone:
- first_reply: Be more deferential — acknowledge, don't push
- follow_up: Direct and efficient — they know you already
- repeat_contact: Warm re-engagement — reference the gap naturally
- outbound: Standard SDR outreach
```

**2. `AVA_AUTO_SYSTEM_PROMPT` (WhatsApp auto-response):**

```python
engagement = _engagement_stage(lead)
prompt = AVA_AUTO_SYSTEM_PROMPT.format(
    lead_engagement=engagement,
    ...
)
```

With the prompt showing:
```
Engagement: {lead_engagement} — first_reply: deferential, follow_up: direct, repeat_contact: warm re-engagement
```

#### Why Two Injection Points

- The `agent_chat()` prompt is for Greg (the human operator) asking Ava about leads — the engagement signal helps Ava give context-appropriate answers
- The `AVA_AUTO_SYSTEM_PROMPT` is for leads directly messaging on WhatsApp — the engagement signal changes how Ava presents herself to the lead (first contact vs. established conversation)

#### Pitfalls

- **Engagement is per-lead, not per-thread.** A lead could have multiple conversation threads — the engagement state reflects their overall lifecycle, not the current thread.
- **`first_reply_at` is write-once.** Once set, it never changes. This is by design — it tracks "when did this lead first engage with us."
- **`last_contacted_at` updates on EVERY inbound reply** (WhatsApp, SMS, email, call). Keep it in the inbound handler, not in isolated API endpoints.
- **Outbound sends don't change engagement state.** Only inbound replies do.
- **Stage transitions are independent.** Moving a lead from "engaged" to "qualified" for business reasons doesn't reset engagement state.
- **The `startswith()` match on confirmation words is important** — a user saying "ok" is different from "ok do it" but both should work. See the Confirmation Gate section above.

#### Pitfalls

### 8. ToolResult.from_string doesn't exist — use from_legacy_string

**Symptom:** `AttributeError: type object 'ToolResult' has no attribute 'from_string'` at runtime.

**Root cause:** The `ToolResult` class in `tool_results.py` has `from_legacy_string()` and `from_string_with_check()` — but NOT `from_string()`. This is a common guess because all three sound interchangeable.

**Fix:**
```python
# WRONG
tr = ToolResult.from_string(tool_name, result_string)

# CORRECT
from tool_results import from_legacy_string
tr = from_legacy_string(tool_name, result_string)
```

**Verification:** Search for `ToolResult.from_string` across the codebase. The correct pattern uses the module-level function `from_legacy_string()`, never the class method.

### 9. Resolve Lead with Archived Leads — include_archived=True

**Symptom:** Calling `trigger_cadence` on an archived lead returns `"AmbiguousLeadError: Lead 'X' not found"` instead of the expected `"Lead X is archived"` message.

**Root cause:** `resolve_lead(name_hint, db)` defaults to `include_archived=False`, which filters out archived leads via SQL `WHERE stage != 'archived'`. If the lead IS archived, it returns no matches and raises `AmbiguousLeadError` — before the caller ever gets to check the stage.

```python
def resolve_lead(name_hint, db, include_archived=False):
    query = db.query(Lead).filter(Lead.name.ilike(f"%{name_hint}%"))
    if not include_archived:
        query = query.filter(Lead.stage != "archived")
```

**Fix:** When the caller NEEDS to check/report on archived leads (e.g., trigger_cadence rejects them, update_lead_field needs to modify them), pass `include_archived=True`:

```python
lead = resolve_lead(lead_name, db, include_archived=True)
if lead.stage == "archived":
    return ToolResult.fail("trigger_cadence", "INVALID_VALUE",
        f"{lead.name} is archived",
        recovery="Reactivate the lead first.")
```

**Tools affected:** Any tool that needs to find a lead regardless of stage — trigger_cadence, update_lead_field, and any diagnostic that reports on archived records. The default `include_archived=False` is correct for outreach/pipeline tools where archived leads should be invisible.

### 10. Route Decorator Attaches to NEXT Function, Not the Line Above

**Symptom:** FastAPI route `@app.post(...)` returns 422 or routing errors.

**Pitfalls reference:** See `references/python-source-encoding-pitfalls.md` for three source-level traps: smart quotes in string literals, doubled triple-quotes from text replacement slicing, and `f"""` strings with nested braces on Python 3.14.

**Root cause:** The decorator binds to the *next function defined* after it, not the function visually below it. If you have:

```python
@app.post("/api/agent/chat/{tenant_id}")

def _run_observe_loop(messages, tools_schema, db, wa, tenant_id, user_msg, channel):
    ...

def agent_chat(tenant_id: str, data: dict, db: DBSession = Depends(get_db)):
    ...
```

The decorator binds to `_run_observe_loop` (a helper with no valid FastAPI signature), and `agent_chat` is registered to **no route at all**. The endpoint is effectively dead.

**Fix:** Ensure the decorator sits IMMEDIATELY above the correct function (no blank lines between decorator and `def`):

```python
def _run_observe_loop(messages, tools_schema, db, wa, tenant_id, user_msg, channel):
    ...

@app.post("/api/agent/chat/{tenant_id}")
def agent_chat(tenant_id: str, data: dict, db: DBSession = Depends(get_db)):
    ...
```

**Verification:** After fixing, call the endpoint with `curl` and verify a successful response. Check that `_run_observe_loop.signature` isn't being matched as the route handler.

### 11. Helper Function Variable Scope — Unpacking Return Dict

**Symptom:** The logging block or DB storage section references variables like `db_response`, `_results`, `_tools_to_run`, `_intent` that throw `NameError` or silently fall through to defaults.

**Root cause:** When extracting an inner function's return into agent_chat, the old single-pass variable names persist in the logging and storage sections. The helper function returns a dict (e.g., `_loop_out = _run_observe_loop(...)`), but the code below still uses the old local variable names from the pre-refactor days.

**Fix pattern — always unpack the return dict explicitly and update ALL downstream references:**

```python
_loop_out = _run_observe_loop(messages, ...)
_all_calls = _loop_out.get("all_calls", [])
_all_results = _loop_out.get("all_results", [])
_response_original = _loop_out["db_response"]
_obs_intent = _loop_out.get("intent")
_obs_executed = _loop_out.get("executed", False)
_pending_key = _loop_out.get("pending_key")
_claim_nudge_fired = _loop_out.get("claim_nudge_fired", False)

# Then throughout the rest of agent_chat, use _all_calls, _all_results, etc.
# NEVER reference db_response, _results, _tools_to_run, _intent, _is_confirmed
# — those belong to the old single-pass architecture.
```

**Verification:** After extraction, search for every reference to the old variable names in the caller. `grep -n "_results\|_tools_to_run\|_intent\|_is_confirmed\|db_response" server.py` should return 0 hits (except the function definition itself).

### 12. Pending-Action Resume — The "send it" Problem

**Symptom:** User says "send it" to confirm a proposed action, but the agent starts a fresh observe loop with no memory of the pending tool call. The `_pending_actions` dict gets written but never read.

**Root cause:** The observe loop stores pending tool calls on `[ACTION: ASK]`, but the next user message ("send it", "go ahead") triggers a new `agent_chat` call with no explicit check for confirmation of a prior proposal.

**Fix — add a confirmation-resume block at the top of agent_chat BEFORE message building:**

```python
# ── Check for pending-action confirmation ──
_confirm_words = {"yes", "send it", "send", "go ahead", "do it", "confirm", "proceed", "yeah", "sure", "ok"}
_lower_msg = user_msg.strip().lower()
_is_confirm = _lower_msg in _confirm_words or any(_lower_msg.startswith(w) for w in ["send it", "yes"])
if _is_confirm and _pending_actions:
    _recent_pending = None
    _recent_ts = 0
    for _k, _v in _pending_actions.items():
        if _k.endswith("_" + tenant_id) and _v.get("timestamp", 0) > _recent_ts:
            _recent_pending = _v
            _recent_ts = _v["timestamp"]
    if _recent_pending:
        # Execute the pending tool calls directly
        _pending_calls = _recent_pending.get("tool_calls", [])
        _pending_results = [execute_tool(pc["tool"], pc["args"], db, wa, tenant_id) for pc in _pending_calls]
        _resp_text = render_results(_pending_results, channel="whatsapp")
        # Clean up pending actions for this tenant
        for _k in list(_pending_actions.keys()):
            if _k.endswith("_" + tenant_id): del _pending_actions[_k]
        # Store to DB directly
        db.add(AgentChatMessage(tenant_id=tenant_id, role="user", content=user_msg, thread_id=thread_id))
        db.add(AgentChatMessage(tenant_id=tenant_id, role="assistant", content=_resp_text, thread_id=thread_id))
        db.commit()
        return {"response": _resp_text, "thread_id": thread_id}
```

This bypasses the LLM entirely for the confirmation turn — the tool calls have already been approved, so just execute and render.

**Symptom:** After tool execution succeeds, the user sees "Done! Message sent to Rajesh Sharma" even when no message was sent (e.g., only an `update_lead_stage` was executed). The canned template says "sent" for every tool that has a `lead_name` argument.

**Incident (June 4, 2026):** Greg sent "Hey Ava - can you move Rajesh Sharma to New stage." The LLM generated BOTH `[TOOL_CALL: update_lead_stage]` AND `[TOOL_CALL: send_whatsapp]`. Both executed. The response was: `"Done! Message sent to Rajesh Sharma. 🙌"` — misleading because it implied only a message was sent, not the stage change.

Even worse: if the LLM had ONLY generated `update_lead_stage`, the canned response would STILL say "Message sent to Rajesh Sharma" — a complete fabrication.

**Status: FIXED (June 4, 2026).** Both canned response locations (lines 5346 and 5372 in server.py) now build responses from actual tool execution results. See the "Fix applied" note in the "Unused Tool Calls from Context Pollution" pitfall above.

**Root cause:** Lines 5316 and 5339 in server.py:
```python
lead_name = next((args.get("lead_name") for _, args in tool_calls if "lead_name" in args), "")
if lead_name:
    response = f"Done! Message sent to {lead_name}. 🙌"
```
The code assumes the first tool call with a `lead_name` arg was a send operation. It doesn't check what tool was actually called. `update_lead_stage` also has a `lead_name` arg, so it triggers the same template.

**Fix:** Build the response from actual tool results instead of using a hardcoded template:

```python
results_list = []
for tc in pending_tools:
    tool_name = tc.get("tool")
    args = tc.get("args", {})
    result = execute_tool(tool_name, args, db, wa, tenant_id)
    if tool_name == "update_lead_stage":
        results_list.append(f"{args.get('lead_name')} → stage {args.get('stage')}")
    elif tool_name == "send_whatsapp":
        results_list.append(f"Message sent to {args.get('lead_name')}")
    elif tool_name == "update_deal_stage":
        results_list.append(f"Deal {args.get('deal_name')} → {args.get('stage')}")
    else:
        results_list.append(result)
response = f"Done! {' + '.join(results_list)}. 🙌"
```

### 1. `.format()` variable conflicts with JSON
**Symptom**: `KeyError: '"tool"'` when the server starts or handles a request.
**Fix**: Split the system prompt into a format-able base string and a raw tool schema string. Concatenate AFTER formatting.

### Unused Tool Calls from Context Pollution
  
The LLM may generate tool calls the user NEVER asked for, driven by context bias from the conversation thread. This is NOT a regex parsing or execution bug — it's a context quality issue.

**Incident (June 4, 2026):** Greg said "move Rajesh Sharma to New stage." The coaching thread had ~1200 messages, almost all about Ava proposing WhatsApp to Rajesh. The LLM responded with BOTH `update_lead_stage` AND `send_whatsapp` tool calls — the second was a context-hallucinated action. Both executed, and Greg got an unsolicited outreach message + a misleading "Done! Message sent" response.

**Diagnosis:** Check the coaching thread message count. If >100 and the majority are about one action type (e.g., "send WhatsApp to Rajesh"), the LLM will over-generate that tool call even when Greg asks for something unrelated.

**Fix options (in order of preference):**

1. **Prompt-level scoping** — Add to the tool description a line like: "IMPORTANT: Stage changes and outreach are separate actions. If the user asks to change a stage, ONLY call update_lead_stage."
2. **Thread hygiene** — Cap the coaching thread context to last ~20 meaningful turns. Archive old messages or summarize them into a compressed context line.
3. **Code-level guard (IMPLEMENTED June 2026)** — Added `_validate_tool_calls()` middleware that strips conflicting outreach tools when the user only asked for a stage update. Defines mutually exclusive tool groups in `_CONFLICT_MAP`. This runs BEFORE `execute_tool()` and logs warnings when conflicts are detected. See the "Three-layer defense" fix note above.

**Verification:** After applying a fix, send "move X to Y stage" — check that only `update_lead_stage` appears in the tool calls. No `send_whatsapp`, no `trigger_cadence`.

Also see `ara-agent-chat-debugging` skill for the full Bug: Tool Call Over-Generation section.

**Fix applied (June 4, 2026) — Three-layer defense:**

1. **Prompt layer** — Added a "## Tool Selection (HARD RULE)" section with explicit negative examples. Each tool description now includes "NEVER combine with X" or "DO NOT call this when user says Y."
2. **Middleware layer** — Added `_validate_tool_calls()` in `agent_chat()` that runs BEFORE execution. Defines `_CONFLICT_MAP` specifying mutually exclusive tool groups (e.g., `update_lead_stage` cannot appear with `send_whatsapp`). If conflicts are detected, outreach tools are stripped and a warning is logged — the legitimate update tools still execute.
3. **Response layer** — Replaced the hardcoded `"Done! Message sent to {lead_name}"` template with a result-aware builder that reads the actual tool execution output.

See `references/tool-conflict-middleware-june2026.md` for the full code and research rationale.

**Cross-reference (June 15, 2026):** `references/claim-nudge-confirmation-june15-2026.md` — claim/no-call nudge, `_build_pending_description()`, structured confirmation summaries, conversation history poisoning.

### 2. Regex doesn't match nested JSON
**Symptom**: Tool calls are silently dropped (no match found), raw `[TOOL_CALL: ...]` text appears in the final response.
**Fix (June 2026)**: The old regex `r'\[TOOL_CALL:\s*\{.*?\}\s*\]'` matches the **inner** `}` first
in nested JSON like `{"tool": "x", "args": {"query": "y"}}` — the remaining `}]` doesn't
match `\s*\]`, so the ENTIRE match fails and nothing is stripped.

Use `r'\[TOOL_CALL:[^\]]*\]'` — match from `[TOOL_CALL:` to the nearest `]`. JSON tool calls
never contain literal `]` in their args, so this is safe with both nested and flat formats.

**Double-strip:** Both `_strip_markers()` (line ~3004) and `response_clean` (line ~5071) 
have this regex. Fix both. Also check `_auto_re.sub(r'\[TOOL_CALL:.*?\]', ...)` at 
line ~8357 — that one uses `.*?\]` which works because it goes to the nearest `]`.

### 3. Empty response_clean after cleaning
**Symptom**: If the LLM outputs ONLY a tool call with no surrounding text, `response_clean` becomes empty string. The re-call messages will have "Let me handle that..." as the assistant message, which can confuse the LLM.
**Mitigation**: The current fallback works; the tool results are rich enough for the LLM to respond from.

### 4. Tool modifies DB but re-call LLM returns poor response
**Symptom**: DB changes are persisted but Ava's final response is incoherent or just repeats the tool call.
**Mitigation**: Ensure the re-call context clearly says "Tool has been executed" and the results are included.

### 5. API return value contract mismatch — sidecar/service returns different keys than handler checks
**Symptom**: Tool executes successfully (message sent, DB updated) but handler reports "failed" to the user. The tool result string says "Error: ..." even though the operation worked.
**Root cause**: The underlying service API returns success under a different key than the handler checks. Example: WhatsApp Baileys sidecar returns `{"status": "sent"}` on success and `{"error": "..."}` on failure, but the handler checked `wa_result.get("success")` — always `None`, so every send reported as failure.
**Fix**: Always verify the actual return value contract of the underlying service BEFORE writing the handler:

```python
# BAD: Guess the return key
result = wa.send_message(...)
if result.get("success"):  # Wrong! Sidecar returns {"status": "sent"}
    return "Message sent"

# GOOD: Check the contract first
# Print result to logs first: print(f"WhatsApp sidecar returned: {result}")
# Then handle both success and error keys
if result.get("status") == "sent":
    return "Message sent successfully"
elif result.get("error"):
    return f"Failed: {result['error']}"
```

**Prevention checklist for new tools wrapping external services:**
1. Call the service with a test input and print/log the raw return value
2. Identify the success key (`"status": "sent"`, `"ok": true`, `"id": "<non-null>"`, etc.)
3. Use that key in the handler — never guess
4. Handle both success and error paths explicitly
5. Test the tool end-to-end before adding to the system prompt

## Error Handling Protocol (Agentic Response Pattern)

### Email Signature Pattern

See `references/email-signature-pattern.md` for the email signature format rule: first email signs with full name+title+company, replies sign with just first name. This is injected into the channel prompt body section and used by the email generation tool.

When a tool call fails (e.g. cadence trigger, WhatsApp send, email send), Ava must NOT dump raw error text to the user. Instead, follow this agentic pattern.

### Diagnostic Tools (May 2026)

Two new read-only diagnostic tools help Ava investigate errors internally before reporting to the user:

**`read_logs` (tool #31):** Returns the last N server log lines from an in-memory ring buffer. Filter by level: `{"lines": 50, "level": "ERROR"}`. Use when tools return unexpected errors — the traceback is often in the logs. NEVER share raw log output with the user.

**`debug_schedule` (tool #32):** Dry-runs the cadence scheduling logic for any lead WITHOUT making changes. Returns: lead stage, cadence_type, template published status, step summary, pending action count, and any blocking issues. Use when trigger_cadence fails or Greg asks why a lead isn't receiving outreach.

**Both tools are READ-ONLY — no confirmation needed.** Call them freely to diagnose before talking to the user.

### The Pattern

```
```

## Deployment Dependency: `fix_tests.py`

After every deploy that SCPs `server.py` to production, the test suite will fail with 3 errors unless you run `venv/bin/python fix_tests.py` on the server. This script:
1. Re-adds the 3 action tool schemas (`create_action`, `query_actions`, `update_action`) to `TOOL_SCHEMAS`
2. Fixes SQLAlchemy import aliasing in the 3 tool handlers (`from database import ActionItem` → `from database import ActionItem as _AI`)
3. Updates `test_schema_coverage.py` asset from 50 to 53

**Pitfall:** SCP overwrites the server file with the local copy, which may not have these fixes. Run `fix_tests.py` AFTER every SCP deploy, BEFORE running pytest.

```bash
scp server.py root@46.224.132.99:/opt/ara/server.py && \
ssh root@46.224.132.99 'cd /opt/ara && venv/bin/python fix_tests.py && systemctl restart ara-server'
``` New Tools (Schema Coverage + Shadow Imports)

After adding a tool to both `execute_tool()` and `TOOL_SCHEMAS`, run the guard tests:

```bash
cd /opt/ara && /opt/ara/venv/bin/python -m pytest tests/test_schema_coverage.py tests/test_shadow_imports.py -v
```

**Schema coverage failure:** The test parses `execute_tool()` for `elif tool_name == "xxx"` patterns and cross-references against `TOOL_SCHEMAS`. If the count assertion (`assert len(schema) == N`) fails, update N in the test. Always add schemas alphabetically within the dict.

**Shadow import failure:** The test checks that `from database import SomeModel` inside `execute_tool()` is always aliased (`as _Alias`). This prevents the local import from shadowing a reference used earlier in the function. Fix: add `as _Alias` to the import line and update all local references to use `_Alias`.

**SCP overwrite trap:** When the schema fix script runs on the server, a subsequent `scp` from local will overwrite the fix unless the local copy is synced first. Pattern: always run `fix_tests.py` on the server AFTER every `scp` deploy.

```
User: "Start cold cadence for Gregory"
Ava internally: calls read_logs(level="ERROR") + debug_schedule(lead_name="Gregory")
Ava internally: sees "Lead stage is 'engaged' — past the cadence window"
Ava to user:    "Gregory is in the 'engaged' stage, so the automated cadence 
                 won't fire — it only runs for leads in 'new' or 'reached_out'. 
                 I can reset his stage and retry, or send him a manual WhatsApp 
                 right now. Which works better?"

BAD (no diagnose): "Looks like the system hit an internal error when trying to 
                    trigger the automated cadence for Gregory. That's on the 
                    backend."

ALSO BAD (raw data dump): "The trigger_cadence tool returned: Lead stage is 
                           'engaged' — past the cadence window."

GOOD (diagnose + plain English): "Gregory is in 'engaged' stage — means the 
                                   cadence won't auto-fire. I can reset his 
                                   stage, or send a manual message now."
```

### Protocol (5 steps)

**Step 0 — Diagnose internally first:** Before telling the user anything, call `read_logs(level="ERROR")` and/or `debug_schedule(lead_name="...")` to find the root cause. These tools are for YOUR eyes only — never share their raw output with the user.

**Step 1 — Understand the WHY:** Read the logs and debug output. Identify the exact reason: missing config? wrong stage? server crash? template not published?

**Step 2 — Tell the user in plain English:** One sentence on what happened. No technical details, no error codes, no "the system encountered an issue."

**Step 3 — Offer 1-2 concrete options:** Things you can do RIGHT NOW with your tools. Manual message? Change stage? Publish template? Give specific actions.

**Step 4 — Keep it short:** One paragraph max. No raw tool output, no tracebacks, no backend explanations.

**Implementation: Resolution-Oriented Tool Messages**

Tool error messages should include a `Resolution:` hint so Ava can immediately offer an action, not just describe the failure:

```
BAD:  "Could not trigger cadence for Gregory: no cadence_type"
GOOD: "Could not trigger cadence for Gregory: no cadence type assigned. 
       Resolution: Assign a cadence type first (cold/inbound/nurture) 
       via update_lead, then retry."
```

### Implementation: Follow-Up Instruction

In the agent_chat re-call loop, when tools return errors, the follow_up message must explicitly invoke the Error Handling Protocol:

```python
follow_up = (
    f"Some actions encountered errors:\n{result_summary}\n\n"
    f"The user needs a clear, action-oriented response. "
    f"FOLLOW THE ERROR HANDLING PROTOCOL: diagnose why it failed, "
    f"propose a fix you can do, and offer 1-2 alternatives you can do right now. "
    f"Do NOT output any [TOOL_CALL:] blocks — the tools have already run. "
    f"Be concise. One paragraph max."
)
```

### Ava's System Prompt Section

The Error Handling Protocol must appear in Ava's system prompt as a distinct section (not buried in guidelines):

```
## ⚡ Error Handling Protocol

When a tool returns an error, follow these steps IN ORDER:

**Step 0 — Diagnose internally first:** Before telling the user anything, 
call `read_logs(level="ERROR")` and/or `debug_schedule(lead_name="...")` 
to find the root cause. These tools are for YOUR eyes only — never share 
their raw output with the user.

**Step 1 — Understand the WHY:** Read the error, the logs, and the debug 
output. Identify the exact reason.

**Step 2 — Tell the user in plain English:** One sentence on what happened 
(no technical details, no error codes, no "the system encountered an issue").

**Step 3 — Offer 1-2 concrete options:** Things you can do RIGHT NOW with 
your tools.

**Keep it short:** One paragraph, max. No raw tool output, no tracebacks.

Bad: "The trigger_cadence tool returned: Lead stage is 'engaged' — past the 
       cadence window."
Good: "Gregory is in 'engaged' stage, which means the automated cadence won't 
       fire because he's already in an active conversation. I can send him a 
       manual WhatsApp or email right now, or reset his stage to restart the 
       cadence. Which would you prefer?"
```

### Pitfalls

- **Don't make the error abstract** — "the system encountered an issue" is worse than useless. It gives the user nothing to act on. Always include the specific what and the specific fix.
- **Don't offer options you can't execute** — if you say "I can send a WhatsApp message right now," make sure WhatsApp is connected and the lead has a phone number.
- **Don't skip asking** — always end with a question (e.g., "What works best?"). If the user has to figure out what to say next, it's not agentic.
- **Single paragraph, not a list** — the user should be able to read the entire response in one glance on mobile.
- **Never share raw tool output** — the diagnostic tools are for Ava's eyes only. The user should see plain English, never `read_logs` output or `debug_schedule` JSON.
- **Tool descriptions are behavioral primer** — Any use-case suggestion in a tool description WILL be treated as an instruction by the LLM. The `set_cron` description said "Use for daily summaries" and the LLM hallucinated crons ~6 times. Document use cases in skills, not in AGENT_TOOL_SCHEMA. After any tool desc change, purge contaminated assistant messages from the coaching thread. See `ara-ava-guardrails` references/tool-description-priming-june15.md.
- **ScheduledAction gap** — `set_reminder` and `create_action_item` must create a `ScheduledAction(action_type="whatsapp_to_owner")` when `due_at`/`delay_minutes` is set. Without it, the scheduler has nothing to deliver and no WhatsApp notification fires. The `create_action` API endpoint (UI path) already does this; the tool-call path must too. See `ara-ava-guardrails` references/scheduled-action-notification-gap-june15.md.

## ⚡ Always Use Tools Before Asserting State (Critical)

**Ava must never claim anything about system state without calling a tool to verify it first.** If Greg asks "is there anything pending?" or "cancel all outbound for Gregory", Ava must call the relevant tool — she must not guess, assume, or fabricate.

Bad: "There are no pending actions for Gregory." (Ava guessed — she didn't check.)
Good: "Let me check..." → [TOOL_CALL: {"tool": "cancel_scheduled", "args": {"lead_name": "Gregory Ipe"}}] → "Cancelled 18 pending actions for Gregory."

### Why This Exists (Session Context)

This session proved the problem: Greg asked "stop all outbound to Gregory Ipe" and Ava responded "There are no pending messages for Gregory Ipe" without calling cancel_scheduled or any tool. The lead had 18 pending actions. Ava fabricated the "nothing pending" claim because her training prioritized confident-sounding responses over tool-based verification.

### Implementation: System Prompt Rule

Add this as a distinct section in AGENT_SYSTEM_PROMPT_BASE (after the English-only rule, before the tool schema):

```
## 🛑 Always Use Tools Before Asserting State

Never describe, confirm, or deny lead/deal state (pending actions, stage, conversations,
cadences, settings) unless you have JUST called a tool to verify it. If Greg asks you
about or to act on ANY lead, call the tool first. Do not assume what exists.
```

Also reinforce in the re-call follow_up when tools are executed successfully:

```python
follow_up = (
    f"All requested actions completed:\n{result_summary}\n\n"
    f"Summarize what was done. Do NOT output [TOOL_CALL:] blocks. "
    f"Be precise about what actually changed — check the results above."
)
```

### Pitfalls

- **Don't let Ava elaborate on what she THINKS exists** — if she hasn't called a tool, anything she says about state is speculative
- **This rule applies to ALL state claims**, not just actions — also stage, cadence_type, lead source, conversations, scheduling
- **The re-call follow_up must reinforce this** — when tools were executed, the follow_up should say "check the results" not just "summarize what you did"
- **This is different from the Error Handling Protocol** — that governs how Ava communicates AFTER a tool fails. This rule prevents Ava from fabricating state before any tool runs

## User-Facing Action Workflow Rules (June 2026)

This section covers the behavioral rules in Ava's system prompt that govern how she handles user requests involving data-modifying actions (sending messages, updating leads, etc.). These sit on TOP of the tool infrastructure — they shape how Ava interacts with Greg through the tool execution lifecycle.

See `references/action-workflow-rules-june2026.md` for the exact prompt text added to server.py.

### The Approval Workflow (4 Steps)

```
1. Greg says: "send Rajesh a message - ask him to call me up immediately"
2. Ava: Shows draft + asks "Shall I send it?"
3. Greg: "send it via WhatsApp"
4. Ava: [TOOL_CALL: send_whatsapp with EXACT approved message] — NO new text
```

**Rules embedded in the system prompt:**

1. **Action Approval Rule** (line ~4895): Never send any message without showing the exact draft and getting explicit approval. Workflow: compose → show → wait for confirmation → execute.

2. **Lead Disambiguation Rule** (line ~4900): Before drafting, confirm WHICH lead. Say full name. If multiple matches, call search_leads and present options.

3. **CRITICAL: Approved Draft Execution** (line ~4825, placed FIRST in the prompt): When Greg confirms, output ONLY the [TOOL_CALL:] block. Do NOT generate new text, drafts, questions, or alternatives. The draft was already approved.

4. **Data Honesty Rule** (line ~4907): "not on file" instead of "failed to load". Don't frame successful actions as errors.

### The CRITICAL Rule (Why It Exists)

**Problem:** When the server strips [TOOL_CALL:] blocks from assistant messages before saving to the DB (to avoid duplicate rendering), the LLM sees its previous response as just "Shall I send this?" — without the tool call. When Greg then says "send it", the LLM thinks "no tool call was executed last time, something went wrong" and falls into the Error Handling Protocol (calling check_health, read_logs) instead of executing the send.

**Fix:** The CRITICAL rule at the TOP of the system prompt explicitly tells the LLM:
- On confirmation, output ONLY [TOOL_CALL:]
- The missing tool call in history is NOT an error — it was intentionally stripped
- Do NOT run diagnostics on confirmation
- This rule TRUMPS all other instructions

**Curly-brace escaping:** The CRITICAL rule text lives inside `AGENT_SYSTEM_PROMPT_BASE` which is a Python `"""..."""` string that gets `.format()` called on it. Any `{...}` in JSON tool call examples will be interpreted as format placeholders and cause `KeyError: '"tool"'`. Fix: use `{{...}}` (double braces) around JSON examples. The format variables like `{agent_name}`, `{company}` remain single-braced.

```python
# CORRECT in the prompt string — double braces for JSON, single for format vars
CRITICAL: ...
Correct:
[TOOL_CALL: {{"tool": "send_whatsapp", "args": {{"lead_name": "Rajesh Sharma", "message": "Hi Rajesh — call me."}}}}]
```

### "Via WhatsApp" / Extra Detail Problem

When Greg adds "via WhatsApp" or "as an email" in his confirmation (e.g., "send it via WhatsApp"), the LLM treats the extra detail as a request for a new draft. Fix: the CRITICAL rule now explicitly says: "treat extra details as channel hints for the EXISTING draft, NOT as a request for a new draft. Use the exact message text from your previous assistant message."

### Direct Command Bypass — REMOVED (June 2026)

The old code had a `is_direct_command` check (line ~5576-5579) that let verb-first messages ("send a message to...", "create a deal...") skip the LLM confirmation gate. Greg explicitly asked for this to be removed after Ava fired a message without showing the draft first.

**Current behavior (server.py line ~5615):**
```python
# Before: if needs_confirmation and not is_direct_command:
if needs_confirmation:  # ALL data-modifying tools require confirmation now
```

The `is_direct_command` variable still exists in the code but is never checked. The `command_verbs` set is also unused in the gate.

### Common Pitfalls

- **LLM calls check_health/read_logs on confirmation** — Fix: CRITICAL rule explains tool call stripping (see above)
- **Draft B replaces Draft A after approval** — Fix: CRITICAL rule: "output ONLY the [TOOL_CALL:] block. Do NOT generate any new text."
- **Channel padding** — Ava asks "WhatsApp or email?" after Greg already said WhatsApp. Fix: "Do NOT ask follow-up questions on confirmation."
- **"Let me check what went wrong" framing** — Fix: Data Honesty Rule. If no error occurred, don't check for one.
- **Grabbing the wrong Rajesh** — Fix: Lead Disambiguation Rule. Confirm which lead before drafting.
- **CRITICAL rule `{tool}` format error** — Always double-brace JSON examples in prompt strings that use `.format()`. Test with a quick `.format()` call before deploying.
- **Stale server still serving old prompt** — After adding prompt rules, verify the correct server PID was restarted. `lsof -i :8766` then `ps -p <pid> -o lstart=` to check start time matches your restart.

## Backward Compatibility

Old command formats (`[SEARCH: query]`, `[WHATSAPP: number | msg]`, `[CADENCE_TRIGGER: name]`, `[FETCH_URL: url]`) are translated into equivalent tool calls by the parser. This ensures:
- Existing conversation threads with old-format responses still render correctly
- Users who type these manually still get results
- New sessions use the unified format
