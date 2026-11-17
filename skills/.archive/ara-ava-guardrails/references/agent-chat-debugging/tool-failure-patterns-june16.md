# Tool Failure Patterns — June 16, 2026

Session uncovering five distinct failure patterns in Ava's tool execution. Each is a silent failure — no crash, no error to the user, but wrong behavior.

## Pattern 1: Tool Handler Returns None (query_leads)

**Symptom:** "❌ Tool returned no result" showing in observe loop output. All other tools work.

**Root cause:** The `query_leads` handler (server.py ~line 3702) built a SQLAlchemy query but NEVER executed or returned. It fell through to the next `elif` block (`query_actions`). The handler had filter logic but was left incomplete.

**Fix — added execution + return:**
```python
leads = query.order_by(Lead.updated_at.desc()).limit(25).all()
if not leads:
    return "No leads match the filters."
lines = [f"• {l.name} ({l.company}) — {l.stage or 'new'}" for l in leads]
return "\n".join(lines)
```

Also added `group_by` support (stage, company, lead_source) with SQLAlchemy GROUP BY + COUNT.

**Backstop fix in `from_legacy_string` (tool_results.py):**
```python
if raw is None:
    return ToolResult.fail(tool, "NULL_RESULT", "Tool returned no result",
                           recovery="Something went wrong. Try again or try a different approach.")
```

**Detection:** When observe loop shows "Done X of Y" with exactly one failed tool and no DB errors in logs, suspect a handler returning None. Grep the handler to verify it has a `return` statement after its query logic.

**Prevention:** Every `elif tool_name == "..."` block MUST end with a `return`. Use `grep -A50 "elif tool_name == 'NAME'" server.py` to verify after adding any new tool.

## Pattern 2: SQLite Write Lock in Multi-Tool Observe Loop

**Symptom:** `OperationalError: database is locked` — some tools fail when the LLM calls 6+ tools in one observe loop iteration.

**Root cause:** SQLite supports only ONE writer at a time. When the observe loop runs multiple tools sequentially, each calls `db.add()` + `db.commit()`. If one tool's handler adds but doesn't commit (or the commit hasn't flushed yet), the next tool blocks on the write lock.

**Fix — dual approach:**

1. **After each successful tool:** Call `db.commit()` to flush any pending writes:
```python
r = execute_tool(tn, args, db, wa, tenant_id)
try:
    db.commit()
except Exception:
    pass  # No pending transaction is fine
```

2. **On exception:** Rollback any failed transaction that holds the lock:
```python
except Exception as e_raw:
    try:
        db.rollback()
    except Exception:
        pass
```

3. **In `execute_tool` exception handler:** Also rollback:
```python
except Exception as e:
    try:
        db.rollback()
    except Exception:
        pass
    return f"Error executing {tool_name}: {str(e)}"
```

4. **Increased retry delay:** 0.15s → 0.5s between attempts.

**Detection:** `sqlite3.OperationalError: database is locked` in journalctl. WAL mode is already enabled (`PRAGMA journal_mode=WAL`).

**Prevention:** Every tool handler should call `db.commit()` before returning. The observe loop's commit is a safety net, not a replacement for handler discipline.

## Pattern 3: Confirmation Items Use LLM Text as Action Titles

**Symptom:** `get_action_items` returns items with titles like "You're right — here's the actual proposal with the tool call…" or "Fair call — let me fix that." — these are fragments of LLM conversational text, not action descriptions.

**Root cause:** The confirmation flow (`_create_pending_action_item`, server.py ~line 5485):
```python
title=(resp_clean[:60] + ("…" if len(resp_clean) > 60 else ""))
```
`resp_clean` is the LLM's conversational response text — the friendly wrapping around the proposal. It should be `_build_pending_description(data_tools)` — the structured tool description.

**Fix:** 
```python
_built_desc = _build_pending_description(data_tools)
_pending_row = _AIStore(
    title=(_built_desc[:60] + ("…" if len(_built_desc) > 60 else "")) or "Pending confirmation",
    description=_built_desc,
    ...
)
```

**Related — confirmation items never get status=resolved:**
After execution, only `execution_state = "fired"` was set. `status` stayed `"open"`. Fixed by adding `_live.status = "resolved"` + `_live.outcome_state = "resolved"` in the confirmation-execute path AND the confirmation-reject path.

**Related — get_action_items includes confirmation-queue items:**
Fixed by adding `q = q.filter(_AI.action_type != "pending_confirmation")` in the `get_action_items` handler.

**Cleanup:** One junk row (`e893dc69`) had `execution_state=fired, status=open, action_type=pending_confirmation`. Manually set `status=resolved` via DB update.

## Pattern 4: Voice Note Override Clobbered by pre_confirmed Check

**Symptom:** Voice notes auto-execute even though the prompt says `[VOICE NOTE — do NOT use [ACTION: NOW]]`.

**Root cause:** Ordering bug in the observe loop intent gate:
```python
# Line 5269 — voice note safeguard
if voice_note and is_data_modifying:
    intent = "ask"

# Line 5272 — pre_confirmed OVERRIDES it
if pre_confirmed:
    confirmed = True
    intent = "now"  # ← clobbers voic