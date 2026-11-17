# Tool Failure Patterns — June 16, 2026

## 1. create_action: date-only due_at defaults to wrong timezone

**Symptom:** Actions created with due times in the past, or wrong time of day. "Push check-in to 5 PM" results in 2:30 PM due time.

**Root cause:** `create_action` tool (server.py ~line 3535) had:
```python
if len(_due_raw) <= 10:  # date-only, default 9 AM
    _due = _due.replace(hour=9, minute=0, second=0)
```
9 AM UTC = 2:30 PM IST. When the LLM passes date-only ("2026-06-16"), the action defaults to mid-afternoon IST — often already in the past when created.

**Fix:** Changed default from 9 AM UTC to 12:30 UTC (6 PM IST — close of business):
```python
if len(_due_raw) <= 10:  # date-only — default to close of business (6 PM IST = 12:30 UTC)
    _due = _due.replace(hour=12, minute=30, second=0)
```

**Lesson:** Time defaults in UTC must account for the tenant's timezone. IST is UTC+5:30 — 9 AM UTC is never a good default for IST users. Always default to end-of-business-day in the tenant's timezone.

## 2. create_lead: placeholder names ("TBD") accepted silently

**Symptom:** 18 leads created with name "TBD — CompanyName" during STRATEGIC query testing. The LLM recommended target companies, then called `create_lead` with placeholder names for every recommendation.

**Root cause:** No validation on lead names. The STRATEGIC classification tells the LLM "suggest targets, don't create deals" but `create_lead` wasn't blocked. The anti-patterns table said "DO NOT call create_deal as first move" but didn't cover `create_lead` as follow-up.

**Fix:** Tool-level rejection at `create_lead` (server.py ~line 4154):
```python
if name.strip().upper().startswith("TBD") or name.strip() in ("Unknown", "N/A", "TBD", "???"):
    return "Error: 'name' appears to be a placeholder. Use the actual person's name, 
            or if unknown, use the company name followed by '(contact)' — e.g. 'Delhivery (contact)'."
```

**Lesson:** Prompt-level guardrails (anti-patterns table, classification rules) are not sufficient. Critical data-quality gates must be at the tool level. If the LLM ignores a prompt instruction, the tool still rejects bad data.

## 3. query_database: raw SQL rejected by SQLAlchemy session

**Symptom:** Every `query_database` call returned: "Textual SQL expression 'SELECT * FROM...' should be explicitly declared as text('SELECT * FROM...')"

**Root cause:** `db.execute(sql)` passes raw string to SQLAlchemy session. SQLAlchemy ORM sessions require `text()` wrapper for raw SQL:
```python
# Before (broken)
result_proxy = db.execute(sql)

# After (fixed)
from sqlalchemy import text as _sql_text
result_proxy = db.execute(_sql_text(sql))
```

**Lesson:** When building a diagnostic tool that accepts LLM-generated SQL, test with the actual ORM session, not a raw sqlite3 connection. The `_validate_sql_query` function was tested against sqlite3 directly (which accepts raw strings) but the production path uses SQLAlchemy ORM (which doesn't).

## 4. create_lead storm from STRATEGIC testing

**Symptom:** Running STRATEGIC test queries ("Analyze my pipeline and suggest targets") caused Ava to create 18 leads named "TBD — CompanyName" across 4 test batches. Live DB polluted.

**Root cause:** The STRATEGIC mode correctly gathered data and analyzed gaps, but then the LLM called `create_lead` for every recommendation as a follow-up action. The anti-patterns table blocked `create_deal` but not `create_lead`.

**Lesson:** When testing STRATEGIC/DIAGNOSTIC queries against a live endpoint, always include "Do NOT create leads. Do NOT create deals." in the test message. Even better: test in a staging environment or clean up immediately after.

**Cleanup:** Deleted 18 TBD leads from DB. Added tool-level guard (pattern #2 above).

## 5. search_conversation_history: ToolResult.fail() called with wrong signature

**Symptom:** Ava called `search_conversation_history` to answer "did the message go through?" — returned: `ToolResult.fail() missing 1 required positional argument: 'message'`. Crashed silently, Ava fell back to hallucination.

**Root cause:** Two `ToolResult.fail()` calls in the handler (lines 5224, 5243) passed only 2 args `(tool, message)` but the signature requires 3: `(tool, code, message)`.
```python
# BROKEN — missing 'code' argument
return ToolResult.fail("search_conversation_history", "No query provided...")
return ToolResult.fail("search_conversation_history", f"Search failed: {e}")

# FIXED
return ToolResult.fail("search_conversation_history", "MISSING_ARG", "No query provided...")
return ToolResult.fail("search_conversation_history", "SEARCH_FAILED", f"Search failed: {e}")
```

**Lesson:** Every other tool in the codebase uses the 3-arg `ToolResult.fail(tool, code, message)` pattern. When adding a new tool, copy the pattern from an existing tool rather than writing from scratch. The error taxonomy (`ERROR_CODES` dict in `tool_results.py`) defines the valid codes — use one of those, not a freeform string.
