## Iteration 5: The Question-With-Intent Blind Spot (June 10, 2026)

**Problem:** The enforcer had `not _is_question` in its condition. A voice note `"🎤 Hey Eva, could you set a reminder..."` was correctly classified as a question (`is_q=True`). The enforcer skipped entirely — LLM said "Done. I've set up a daily morning briefing..." with NO tool call. No re-call happened.

**Root cause:** `_is_question` was a blanket skip. It treated "could you set a reminder?" the same as "what's the weather?" — both skip the enforcer. But "could you set a reminder?" has data intent ("set", "reminder") and needs a tool call.

**Fix (June 10):** Changed from `not _is_question` to `not (_is_question and not _has_intent)`:

```python
# OLD — questions always skip
if _has_intent and not _has_data_tool and not _is_question:

# NEW — questions skip ONLY if they don't have data intent
if _has_intent and not _has_data_tool and not (_is_question and not _has_intent):
```

Since `_has_intent` is already True (outer condition), `(_is_question and not _has_intent)` is always `False`. Effectively: **enforcer fires on ALL messages with data intent and no data tool call, regardless of question status.**

**Trade-off:** "Can you update Sahib's email?" now triggers the enforcer (~3-5s re-call). Previously it skipped. This is correct behavior — questions with data intent require tool calls.

## Iteration 6: The `_has_tool`→`_has_data_tool` Rename Crash (June 10, 2026)

**Problem:** The variable rename from `_has_tool` to `_has_data_tool` was applied in the `if` branch (the enforcer check and re-call check) but NOT in the `else` branch (the SKIPPED log line). The `else` block still referenced `{_has_tool}` which no longer existed → `NameError` on every non-enforcer path.

**Impact:** All non-enforcer paths crashed silently (questions, simple queries, chit-chat). Voice notes failed for 30+ minutes until the stale reference was fixed. The interim message was sent but the response never followed.

**Fix:** `sed -i 's/has_tool={_has_tool}/has_data_tool={_has_data_tool}/' /opt/ara/server.py`

**Permanent protocol:** After any variable rename in server.py, grep for ALL occurrences of the old name in the function. Always check `else`/`except`/`finally` branches — they're visually separate from the main logic and are the most commonly missed locations.

## Python 3.12 Scoping Crash (June 10, 2026)

**Problem:** The `set_cron` tool handler called `ScheduledAction(...)` and the `execute_tool` function had `from database import ScheduledAction` at line ~4724 (used by a different tool handler). Python 3.12's compiler sees ANY `from X import Y` in a function and makes `Y` a local variable across the ENTIRE function. When `set_cron` at line ~4625 referenced `ScheduledAction` before the import at line ~4724, it threw: `cannot access local variable 'ScheduledAction' where it is not associated with a value`.

**Fix:** Added `from database import ScheduledAction` at line ~4624, immediately before the `try` block in `set_cron` where `ScheduledAction(...)` was first used. This initializes the local variable before it's consumed.

**Lesson:** Python 3.12 has stricter `try`/`except` scoping than Python 3.11. If a function references `Name` that also appears in a `from X import Name` anywhere else in the same function, the first usage must come AFTER an import. The visual proximity of the import to its usage matters less than the compiler's function-level analysis.

**Diagnostic pattern for silent tool failures:** If a tool call appears to start executing (log shows "executing") but no DB record is created and no error is returned to the LLM, suspect Python 3.12 scoping:
1. Does the function have a late `from X import Y` that shadows the module-level `Y`?
2. Is the first use of `Y` BEFORE that import?
3. Error: `cannot access local variable 'Y' where it is not associated with a value`
