# ARA Bug Patterns (June 2026)

> Companion to `ara-qa-checklist` — specific recurring bug patterns with reproduction steps and fix strategies.

## Pattern 1: Set Completeness Audit (data_modifying_tools, etc.)

**Symptom:** A comprehensive set of tool/error names in the codebase is missing an element, causing a silent bypass of a safety check.

**Live example:** `data_modifying_tools` had every data-modifying tool except `create_lead`. Voice notes bypassed the confirmation gate and created leads without asking.

**Root cause:** Sets are maintained manually. When a new tool is added or an existing one is modified, the set is updated in the tool definition but not in the companion set. The refactor (changing the set from scattered conditionals to a clean list) made it look intentional — nobody noticed `create_lead` was missing because it's the most obvious member.

**Fix strategy:**
1. Write a regression test that diffs the set against the source of truth (all tool names in `execute_tool`)
2. Run the diff after ANY change to the set or tool definitions
3. See `ara-qa-checklist` → "Set Completeness Regression Test" for the test pattern

## Pattern 2: Regex Strip Failure with Nested JSON

**Symptom:** User sees raw `[TOOL_CALL: {"tool": "...", "args": {...}}]` in the response instead of cleaned text.

**Root cause:** The regex `r'\[TOOL_CALL:\s*\{.*?\}\s*\]'` uses non-greedy `{.*?}` which matches the **inner** `}` in nested JSON. For `{"tool": "x", "args": {"query": "y"}}`, it matches up to the inner `}` after `"y"`, leaving the outer `}` and `]` unclaimed → the full regex fails → nothing is stripped.

**Fix:** Replace with `r'\[TOOL_CALL:[^\]]*\]'` — match from `[TOOL_CALL:` to the nearest `]`. JSON tool calls never contain literal `]`.

## Pattern 3: Tool Description Silent Knowledge Gap

**Symptom:** Ava (the LLM) gives an incorrect answer about tool behavior that contradicts what the code actually does.

**Root cause:** The system prompt tool description doesn't mention the behavior. The LLM answers from general knowledge instead of from the code.

**Example:** `create_lead` has built-in `DUPLICATE_PHONE` detection, but the tool description just said "Create new lead." Greg asked "what happens if I create a duplicate phone?" → Ava answered "the system doesn't deduplicate" based on general CRM knowledge.

**Fix:** Every tool description in `AGENT_TOOL_SCHEMA` must mention:
- Error codes the tool can return
- Automatic checks (duplicate detection, validation)
- Special behavior (persistence, side effects)

## Pattern 4: DB Contention on Tight Read-Write Cycles

**Symptom:** Read tools (`get_lead_detail`, `get_summary`) fail intermittently with "database read failed" or SQLite locked errors during demos.

**Root cause:** SQLite in WAL mode allows concurrent reads during writes, but a read that starts during a write's commit phase can timeout. Voice note flows (transcribe → create lead → read lead detail) are particularly vulnerable.

**Fix:** Every `execute_tool()` call in the agent loop is wrapped with 3-attempt retry. The `agent_chat` `db.commit()` also has retry. Individual read-heavy tools (`get_lead_detail`) have their own retry.

The `_db_retry` decorator in `database.py` can be applied to any DB function:
```python
from database import _db_retry

@_db_retry(max_attempts=3, delay=0.1)
def my_db_operation():
    ...
```

## Pattern 5: LLM Prefers create_action_item Over add_skill

**Symptom:** User says "save that as a skill" → Ava creates an action item instead.

**Root cause:** The `add_skill` tool description said "(No confirmation needed)" which made it sound like background auto-logging. Ava chose `create_action_item` because "action item" sounds more user-facing.

**Fix:** Update the tool description to clearly say "USE THIS when Greg says 'save that as a skill'" — make it for user-facing requests, not internal use.
