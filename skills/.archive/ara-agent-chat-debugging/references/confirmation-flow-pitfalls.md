# Confirmation Flow Pitfalls

Three common failure modes in the voice-note → proposal → confirm → execute pipeline.

## 1. Date String in DateTime Column (2026-06-15)

**Symptom**: User says "Yes" to a voice note proposal, but the action never gets created. Server returns 500.

**Root cause**: The `create_action` tool schema tells the LLM to output `due_at: "YYYY-MM-DD"`. The handler at `server.py:3488` passes this directly to `ActionItem(due_at=args.get("due_at"))`. SQLite's DateTime column rejects the plain string:

```
TypeError: SQLite DateTime type only accepts Python datetime and date objects as input.
[SQL: INSERT INTO action_items (...) VALUES (..., '2026-06-16', ...)]
```

**Cascade**: The `db.commit()` failure rolls back the session. The confirmation flow then hits `PendingRollbackError` on its own commit. The pending action expires (120s TTL). All subsequent user messages see no pending action → Ava responds with "Good morning" with zero context.

**Fix**: Parse date strings before the INSERT. `create_action_item` already does this correctly:

```python
_due_raw = args.get("due_at", None)
_due = None
if _due_raw and isinstance(_due_raw, str):
    try:
        _due = datetime.fromisoformat(_due_raw)
        if len(_due_raw) <= 10:  # date-only
            _due = _due.replace(hour=9, minute=0, second=0)
    except (ValueError, TypeError):
        _due = None
elif _due_raw:
    _due = _due_raw
```

**Detection**: Check `journalctl -u ara-server | grep "TypeError.*DateTime"` or look for `PendingRollbackError` in agent_chat.

## 2. Route Collision: GET /api/actions/{id} (2026-06-15)

**Symptom**: Frontend ⋮ menu on actions doesn't work. Clicking "Edit" does nothing. No visible error in browser console.

**Root cause**: Two `GET /api/actions/{id}` routes exist:
- Line 2552: `GET /api/actions/{lead_id}` — returns actions FOR a lead
- Line 6973: `GET /api/actions/{action_id}` — returns a ScheduledAction

FastAPI uses first-match. `fetch('/api/actions/aa001774')` hits the lead endpoint, which queries `ActionItem.ref_id == "aa001774"` → empty result → frontend gets nothing → modal never opens.

**Detection**: `curl http://localhost:8766/api/actions/<action_id>` returns `{"actions": []}` instead of an action object.

**Fix**: Rename the lead endpoint to `GET /api/leads/{lead_id}/actions` and add a proper ActionItem GET endpoint for `GET /api/actions/{action_id}`.

## 3. WhatsApp Sidecar Dedup Never Persisted (2026-06-15)

**Symptom**: After a sidecar crash+reconnect, WhatsApp replays the last message. Ava responds again as if it's new. Multiple "good morning" messages from a single "hi Ava".

**Root cause**: `saveDedup()` was called OUTSIDE the `trackForwarded()` function body at module load time (once). The `forwardedMsgIds` Set lived only in memory. Every sidecar crash wiped it.

```javascript
// WRONG — runs once at startup
function trackForwarded(id) {
  forwardedMsgIds.add(id);
}                                  // function ends here
  saveDedup();                     // never called again
```

**Fix**: Move `saveDedup()` inside both `trackForwarded()` and `trackForwardedContent()`:

```javascript
function trackForwarded(id) {
  forwardedMsgIds.add(id);
  saveDedup();                     // persists on every forward
}
```

**Detection**: Check `cat /opt/ara/whatsapp-sidecar/dedup_state.json` — if always `{"ids":[],"hashes":[]}`, the fix isn't working.

## 4. Missing action_type on Tool-Created ActionItems (2026-06-15)

**Symptom**: User says "Yes" to a voice note proposal, server returns 500. Previous attempts may have already fixed the `due_at` string issue — this is a *different* crash at the same point.

**Root cause**: The `create_action` tool handler creates an ActionItem without setting `action_type`. The column has a NOT NULL constraint:

```
sqlite3.IntegrityError: NOT NULL constraint failed: action_items.action_type
[SQL: INSERT INTO action_items (...) VALUES (...)]
```

**Cascade**: Same as pitfall #1 — `db.commit()` rolls back session → confirmation flow hits `PendingRollbackError` → pending action expires → context lost.

**Fix**: Set `action_type="manual"` in the `create_action` handler. Other handlers use `"review_lead"`, `"note"`, `"stage_change"` — check existing patterns.

**Detection**: `journalctl -u ara-server | grep "NOT NULL constraint failed: action_items.action_type"`

## 5. Backup Restore Wipes Prior Fixes (2026-06-15)

**Symptom**: A fix was deployed and working, but later it's broken again. The fix code is no longer in the file.

**Root cause**: When making risky changes (e.g., adding logging that might break syntax), a backup of `server.py` is taken before the changes. If the changes break things and the backup is restored, ALL intermediate fixes between the backup timestamp and the restore are lost.

**Example**: The `due_at` parsing fix and route rename were deployed at 16:00. Logging changes broke syntax at 16:02. Restored from backup taken at 16:00:22 — which was taken *before* the `due_at` fix was applied.

**Prevention**: 
1. Take backups BEFORE each fix, not just before risky changes
2. Verify all previously-deployed fixes are present after a restore
3. Commit and push after EACH successful fix so git history has every change

## 6. PENDING_TTL Expiry → Orphaned "Yes" → LLM Hallucination (2026-06-15, updated 2026-06-29)

**Symptom**: User says "Yes" to a proposal, but Ava responds with raw tool names as text: `save_memory; save_memory; save_memory`. Or responds with something completely unrelated — e.g., proposing a Daily Pipeline Summary cron job instead of saving the requested memories.

**Root cause — two layers**:

**Layer 1 — TTL expiry** (HISTORICAL, FIXED 2026-06-29): PENDING_TTL was 600 seconds (10 min). User took longer to respond. By the time "Yes" arrived:
1. `_prune_pending_actions` cancelled the expired pending action
2. `_live_pending_for_tenant` returned NONE
3. The confirmation gate was skipped — "Yes" fell through to regular LLM processing
4. The LLM saw the word "yes" in isolation and hallucinated whatever it was "about to do"

**Layer 2 — `_build_pending_description` missing tool cases** (FIXED 2026-06-29): When the LLM re-proposed the action, `_build_pending_description` had no case for `save_memory`. The generic fallback couldn't parse `save_memory` args (`key`/`value` didn't match the filter list), so it output bare tool names.

**Fix applied (2026-06-29)**:
1. **PENDING_TTL changed from 600s to 86400s (24h)** — for garbage collection only. `_live_pending_for_tenant` no longer filters by TTL — pending actions persist until explicitly resolved or pruned by 24h GC.
2. **Clarification gate added** — when user seems to be confirming but no live pending exists, Ava responds: "I don't have any pending action waiting for your confirmation. What would you like me to do?" instead of falling through to LLM.
3. **Missing tool cases added** — `save_memory`, `send_whatsapp_to_owner`, `send_whatsapp_instantly` added to `_build_pending_description`. Generic fallback now includes `key`/`value` in arg filter.

## 7. SQL NULL Comparison Silently Excludes Rows (2026-06-15)

**Symptom**: API endpoint returns 0 results when rows clearly exist in the DB. Filter was added to exclude resolved actions but ended up excluding everything.

**Root cause**: In SQL, `column != "value"` returns NULL (not True) when `column IS NULL`. WHERE treats NULL as false, so rows with NULL in that column are silently excluded:

```python
# ❌ BROKEN — excludes rows where outcome_state IS NULL
q = q.filter(ActionItem.outcome_state != "resolved")

# ✅ CORRECT — use or_() for NULL-safe comparison
from sqlalchemy import or_
q = q.filter(or_(ActionItem.outcome_state != "resolved", ActionItem.outcome_state == None))
```

**Detection**: Compare DB query results with API results:
```bash
# DB has rows
python3 -c "import sqlite3; ...execute('SELECT ... WHERE ...').fetchall()"
# API returns empty
curl http://localhost:8766/api/actions | python3 -m json.tool  # → {"actions": [], "total": 0}
```

**Fix**: Either use `or_()` for NULL-safe comparison, or skip the NULL-sensitive filter entirely if the frontend already has its own filtering (e.g., tab-based filtering for Pending/History).

## 8. _build_recent_actions_block Returns Resolved Actions (2026-06-15)

**Symptom**: Ava reports "Here's what's on your plate today" and lists 4 actions, but Greg only has 2 pending. The other 2 were already marked Done.

**Root cause**: `_build_recent_actions_block()` (line 5471) queries ALL ActionItem rows with NO filter on status, execution_state, or outcome_state:

```python
rows = db.query(_ARAI).filter(_ARAI.tenant_id == tenant_id).order_by(...).limit(30).all()
```

It returns cancelled, resolved, fired, AND pending actions. The sort gives priority to recently-resolved ones (by `coalesce(resolved_at, created_at)`), so they appear FIRST in the list.

**Also**: The pending actions count at line 5785 was wrong:
```python
pending_actions = db.query(_AI).filter(_AI.status == "pending").count()
```
The `status` column uses `"open"` not `"pending"` — always returned 0.

**Fix**:
```python
# In _build_recent_actions_block:
rows = db.query(_ARAI).filter(
    _ARAI.tenant_id == tenant_id,
    _ARAI.execution_state != "cancelled",
    _ARAI.status != "resolved",
).order_by(...).limit(30).all()

# In pending count:
pending_actions = db.query(_AI).filter(
    _AI.tenant_id == tenant_id,
    _AI.execution_state.notin_(["cancelled", "fired"]),
    _AI.status != "resolved",
).count()
```

## 9. status=resolved on Pending Actions — Two-Axis State Confusion (2026-06-15)

**Symptom**: Two active pending actions (`execution_state=pending`, `outcome_state=None`) have `status=resolved`. The API filter bumps against them. The `_build_recent_actions_block` excludes them (so Ava never mentions them).

**Root cause**: The `ActionItem` model has two state axes:
- `execution_state` / `outcome_state` — the action lifecycle (pending → fired → resolved)
- `status` — a separate column with values `"open"`, `"resolved"`, `"dismissed"`

These get out of sync. When `resolveActionItem` in the frontend PATCHes `outcome_state=resolved`, the handler sets `status=resolved`. But if the user later manually changes `execution_state` back to `pending` (without reverting `status`), the axes diverge.

**Fix**: 
```sql
-- Correct stale rows in DB
UPDATE action_items SET status='open' 
WHERE status='resolved' AND execution_state='pending' AND outcome_state IS NULL;
```

**Prevention**: The PATCH endpoint should sync `status` when `execution_state` or `outcome_state` changes:
```python
# In update_action PATCH handler:
if data.get("execution_state") in ("pending", "open"):
    action.status = "open"
elif data.get("outcome_state") == "resolved":
    action.status = "resolved"
```

## 10. render_results Swallows LLM Synthesis (2026-06-16)

**Symptom**: STRATEGIC queries return "✅ 9 actions completed" instead of pipeline analysis. DIAGNOSTIC queries return the same instead of findings.

**Root cause**: `agent_chat` returned `_loop_out["response"]` which is `render_results(all_results)` — the tool confirmation text. The observe loop correctly captured `_loop_out["final_text"]` (the LLM's actual synthesis) but `agent_chat` never used it.

**Fix**: Line 6262: `return {"response": final_response_text or response, ...}` — use LLM synthesis when available, fall back to tool confirmations when not.

**Detection**: Response is under 50 chars and starts with "✅ N action(s) completed" instead of having actual analysis content.

## 11. create_action Date-Only Defaults to Wrong Timezone (2026-06-16)

**Symptom**: Actions created with due time 2:30 PM IST but Greg asked for 5 PM. Date-only "2026-06-16" defaulted to 9 AM UTC = 2:30 PM IST.

**Root cause**: `len(_due_raw) <= 10` triggered for date-only strings, defaulting to `hour=9, minute=0, second=0` in UTC.

**Fix**: Default to 6 PM IST (12:30 UTC) for date-only input. Also: all confirmation prompts now show the due time.

## 12. create_lead Accepts Placeholder Names (2026-06-16)

**Symptom**: 18 "TBD — CompanyName" leads created during STRATEGIC query testing.

**Root cause**: Prompt-level anti-patterns ("don't create leads in STRATEGIC mode") aren't sufficient. LLM still calls `create_lead` for every recommendation.

**Fix**: Tool-level validation rejects names starting with "TBD", "Unknown", "N/A", "???". Error message guides LLM to use "CompanyName (contact)" format.

## 14. Duplicate Confirmation Messages (resp_clean + pending_desc concatenation) (2026-06-16)

**Symptom**: Ava shows the same proposal text twice:
```
💰 Create deal: Shriram Finance — shall I create it?
💰 Create deal: Shriram Finance — shall I create it?
```

**Root cause**: In the confirmation pending path (line 5793), `resp_clean` (LLM's conversational text) and `_build_pending_description(data_tools)` (system-generated tool summary) were concatenated with `\n\n`. When the LLM includes the proposal in its text ("Create deal: Shriram Finance — shall I create it?") AND `_build_pending_description` generates the same text, it appears twice.

**Fix**: Use LLM text (`resp_clean`) if present; only fall back to `pending_desc` when LLM text is empty:
```python
if resp_clean:
    pending_text = resp_clean
elif pending_desc and pending_desc != "Pending confirmation":
    pending_text = pending_desc
else:
    pending_text = "I can help with that."
```

## 15. Stale Pending Siblings Cause Re-Proposal of Completed Actions (2026-06-16)

**Symptom**: Greg confirms a deal creation, it executes. Minutes later he asks about a different deal. Ava proposes creating the FIRST deal AGAIN alongside the new one.

**Root cause**: The duplicate-confirmation bug (#14) created TWO pending ActionItems for the same response (e.g., one for create_deal + one for attach_to_deal). When Greg confirmed, only the matched one executed. The sibling sat in `awaiting_approval`. On the next message, `_live_pending_for_tenant` found the stale sibling, and the LLM confused it with the current request — reproposing already-completed actions.

**Fix**: When a confirmation executes, cancel ALL other `awaiting_approval` pendings for the tenant:
```python
# In the confirm-execute path (after marking _live as fired):
_others = db.query(ActionItem).filter(
    ActionItem.tenant_id == tenant_id,
    ActionItem.execution_state == "awaiting_approval",
    ActionItem.id != _live.id,
).all()
for _o in _others:
    _o.execution_state = "cancelled"
    _o.status = "resolved"
```

## 16. Failure Diagnosis Doesn't Include Actual Error Details (2026-06-16)

**Symptom**: A tool fails 3 times with the same error. Ava never tells Greg what went wrong — just "I couldn't finish all of that." Greg has to ask Johnny to diagnose.

**Root cause**: The diagnosis prompt injected after tool failures was generic: *"Some tools failed: update_action. Your move: can you fix the input and retry?"* — no actual error message. The LLM couldn't parse the SQLAlchemy traceback to know *what* to fix.

**Fix**: Include actual error details in the diagnosis prompt + escalate same-tool repeated failures:
```python
err_msg = (f.error.message if f.error and f.error.message else "unknown error")[:200]
_fail_msg = f"Tool failures: {tool_name}: {err_msg}. "

# Escalate repeated same-tool failures
if same_tool_failed >= 2:
    _fail_msg += "STOP retrying. Tell Greg exactly what you need."
else:
    _fail_msg += "Your move: fix input and retry once, or ask Greg."
```

**Detection**: Look for "I couldn't finish all of that" in responses following multiple same-tool failures with empty error summaries.

## 17. LLM Describes Actions Without Corresponding Tool Calls (2026-06-16)

**Symptom**: Ava's confirmation text says "Create deal: Shriram Finance + attach Ajay Fageria as contact — shall I proceed?" but only `create_deal` was in the tool calls. The attachment never executes because there's no `attach_to_deal` tool call.

**Root cause**: The LLM writes conversational text describing multiple actions but generates tool calls for only some of them. The text-actions aren't backed by real tool calls — they're fabrications.

**Fix**: Added self-audit rule #4 in the system prompt:
```
4. TOOLS MATCH TEXT: Every action you describe in your proposal
   MUST have a matching tool call. Never mention an action in your
   text that isn't backed by a real tool call. If you describe two
   actions, you need two tool calls.
```

**Detection**: Check `pending_tool_calls` JSON in the DB. If the count of described actions in the confirmation text exceeds the tool call count, this pitfall applies.

## 18. Structural Cross-Check Disabled on First Pass (2026-06-16)

**Symptom**: Pitfall #17's self-audit rule was deployed but the structural cross-check (system scans text for action keywords, verifies matching tool calls exist) still wasn't catching mismatches. LLM text said "Create PayTM deal + attach Vinay Bhoj" but only `create_deal` was in the tool calls.

**Root cause**: The cross-check condition was `if _missing and not first_pass:`. The `not first_pass` prevented the check from running on the initial LLM generation — exactly when it's most needed. The observe loop only runs the check on re-prompts (after the LLM has been told to fix something), but the first pass is where the mismatch originates.

```python
# ❌ BROKEN — only checks on re-prompt, not first generation
if _missing and not first_pass:
    prompt = f"Your response mentions actions without tool calls: ..."

# ✅ FIXED — checks every pass including the first
if _missing:
    prompt = f"Your response mentions actions without tool calls: ..."
```

**Detection**: Check if `_missing` list is non-empty but the re-prompt never fires. Compare tool calls in `_loop_out["tool_calls"]` against described actions in `_loop_out["response"]`.

## 19. Global Pending Pool Causes Cross-Thread Contamination (2026-06-16)

**Symptom**: Running multiple test threads against the same tenant produces bizarre confirmation results. A "yes" in `thread_id=A` confirms a pending proposal from `thread_id=B`. Messages with new thread IDs get classified as confirmations of stale pendings instead of fresh requests.

**Root cause**: `_live_pending_for_tenant(db, tenant_id)` queries ALL pending confirmations for the tenant, regardless of `thread_id`. The confirmation flow is tenant-scoped, not thread-scoped:

```python
# Returns the MOST RECENT awaiting_approval across ALL threads
_live = db.query(ActionItem).filter(
    ActionItem.tenant_id == tenant_id,
    ActionItem.execution_state == "awaiting_approval",
).order_by(ActionItem.created_at.desc()).first()
```

When a previous test thread left an unconfirmed pending, EVERY subsequent message on ANY thread matched against it. The LLM classifier saw "yes" or even unrelated text and matched it as a confirmation.

**Detection**: 
```bash
# Check for stale awaiting_approval pendings across all threads
python3 -c "
import sqlite3; db=sqlite3.connect('/opt/ara/ara.db')
rows = db.execute('''
    SELECT id, description, created_at FROM action_items 
    WHERE tenant_id='3e736242' AND execution_state='awaiting_approval'
    ORDER BY created_at DESC
''').fetchall()
for r in rows: print(f'{r[0][:8]} | {r[2][:19]} | {r[1][:80]}')
"
```

**Fix**: Always cancel stale test pendings before running new tests. In production, the sibling cancellation (pitfall #15) prevents accumulation, but during testing with rapidly-changing thread IDs and multiple unconfirmed proposals, manual cleanup is needed.

**Prevention**: Consider adding `thread_id` to the ActionItem model and scoping `_live_pending_for_tenant` to the current thread. This would isolate confirmation flows per conversation.

## 20. attach_to_deal Doesn't Set Deal's Primary Contact (2026-06-16)

**Symptom**: User says "Create PayTM deal + attach Vinay Bhoj as primary contact." Both tools execute successfully. But the PayTM deal's `contact_name`, `contact_email`, and `contact_phone` are all empty. Vinay is attached (Lead.deal_id = PayTM) but the deal doesn't reflect him as primary contact.

**Root cause**: `attach_to_deal` only sets `Lead.deal_id` (linking the lead to the deal). It does NOT set `Deal.lead_id` (primary contact) or sync contact details.

**Fix**: Auto-set the deal's primary contact when attaching a lead to a deal that has none:
```python
lead.deal_id = deal.id
if not deal.lead_id:
    deal.lead_id = lead.id
    deal.contact_name = lead.name
    deal.contact_email = lead.email
    deal.contact_phone = lead.phone
    deal.contact_designation = getattr(lead, 'designation', None)
primary_tag = " (primary contact)" if deal.lead_id == lead.id else ""
```

**Detection**: Query deals with attachments but no primary contact:
```sql
SELECT d.org_name, d.lead_id, d.contact_name, l.name as lead_name
FROM deals d JOIN leads l ON l.deal_id = d.id
WHERE d.lead_id IS NULL OR d.contact_name = '';
```

## 21. Confirmation Context Loss from Accumulated Loop Messages (2026-06-17)

**Symptom**: User says "yes please" to a proposal, but Ava re-lists all overdue items instead of executing the one pending action. "yes" maps correctly to "confirm" in `_classify_confirmation` but the execution path re-enters the full observe loop with pipeline context, causing the model to re-evaluate against the whole pipeline.

**Root cause**: The confirmation path must be a SHORT-CIRCUIT — executing stored `pending_tool_calls` directly and returning without re-entering the observe loop. If it falls through, the model re-evaluates against the full pipeline context and produces a different response.

**Fix**: Verify the confirm path at the top of `agent_chat()` (lines ~6336-6420) executes `pending_tool_calls` directly and returns with `return {"response": ..., ...}`. Never fall through to the observe loop after a confirm.

**Detection**: Check CONFIRM-FLOW logs: if `CONFIRM-FLOW executing` appears but the response contains "here are the three" or "which one", the confirm executed but the response text is wrong (rendering issue). If no `CONFIRM-FLOW executing` appears for "yes please", the classifier returned "unrelated" (proposal description too vague).

## 22. Command Auto-Execution After Deleting Regex Guards (2026-06-17)

**Symptom**: After Fix 2 (deleting regex guards), regular text commands auto-execute without creating pending confirmations. "yes please" falls through to the observe loop as a fresh message because no pending action exists.

**Root cause**: Without the `_analysis_mode` guard forcing confirmations for certain cases, `_parse_execution_intent` defaults to "now" when no `[ACTION: ASK]` marker is present. The LLM includes `[ACTION: NOW]` or nothing → `confirmed = True` → tool executes immediately.

**Mitigation**: Voice notes ALWAYS force confirmation (`if voice_note and is_data_modifying: intent = "ask"`). For text commands, accept the tradeoff — faster execution with the prose-after-result invariant ensuring no false claims.

**Detection**: Check if `CONFIRM-FLOW created-pending` never appears for text commands. If all commands auto-execute without pendings, this pitfall applies.

## 23. Described-but-Uncalled Write in Multi-Step Commands (2026-06-17)

**Symptom**: "update X and send Y a WhatsApp" — the update fires but the send is described in prose ("Here's the WhatsApp I'll send...") without a `send_whatsapp` tool call. The observe loop treats empty tool_calls as done. The send silently vanishes.

**Root cause**: Text and tool_calls are decoupled surfaces from the same LLM response. The model composes a narrative describing the send but doesn't include it in tool_calls. The observe loop's empty-tool_calls branch breaks unconditionally.

**Fix**: Four-case exit branch replaces unconditional break (commit 4814e60):
1. Text doesn't describe a write → break (unchanged)
2. Text asserts a write as done with no tool call → one retry nudge → continue
3. Text is a proposal ("shall I?") → break (confirm flow handles it)
4. Retry exhausted → downgrade to honest language, break

Case 2 must run BEFORE case 3 — text like "✅ Updated. What do you want me to send?" triggers the retry before the proposal break.

**Debugging**: Add EXIT-DBG logging at the empty-tool_calls branch:
```python
logger.info(f"EXIT-CHECK: tool_calls=empty, text_preview={text[:80]}")
logger.info(f"EXIT-DBG: describes_write={_describes_write} text_preview={text[:60]}")
logger.info(f"EXIT-DBG: checking proposal, ends_with_q={text.rstrip().endswith('?')}")
logger.info(f"EXIT-DBG: checking assertion (retry_used={retry_used})")
```
Then check: `journalctl -u ara-server --since '30s ago' | grep 'EXIT-'`

## 24. Confirmation Classifier Misses Implicit Confirmation Phrases (June 2026)

**Symptom**: User says "Did you send it yet?" or "and??" after Ava proposes sending a WhatsApp. Classifier returns "unrelated" instead of "confirm". Ava creates a new tool call (which fails if sidecar is down) instead of executing the pending one. User gets stuck in a confirmation loop.

**Root cause**: The classifier prompt at line ~375 lists explicit confirmation phrases but doesn't cover implicit expectations:

```
"done?", "is it done?", "update?", "any update?", "what happened?", "did you do it?"
```

Missing: "Did you send it yet?", "and?", "??" (impatient expectation), "still waiting...", "hello?" (any follow-up after a proposal that implies the user expected execution).

When these fall through as "unrelated", the message re-enters the observe loop as a fresh request. The LLM creates a NEW tool call, which if the sidecar is down, returns an error — but the user sees silence because the error only appears in tool results, not in the assistant response.

**Fix**: Add missing phrases to the classifier:
```
"did you send it?", "and?", "??", "still waiting", "hello?"
```

**Better fix**: Owner communication tools (send_whatsapp_to_owner, notify_owner) should ALWAYS use [ACTION: NOW] — no confirmation gate at all. These tools only send to Greg's own device, so there's no risk of wrong recipient. Updated the system prompt (rule #4 in AGENT_SYSTEM_PROMPT) to say: "Tools that send communication TO THE OWNER ALWAYS use [ACTION: NOW]. When the user says 'send me', 'drop me', 'ping me', or asks for a message/notification for themselves — execute immediately."

## 25. Coaching Context Contamination from Loading Oldest Messages (June 2026)

**Symptom**: Ava hallucinates names from weeks-old conversations. User asks about pending actions, Ava responds with "Which one — Dinesh Nagar lead, the Ramgopal catchup, or both?" — neither name is in the current conversation.

**Root cause**: Line 7001 in server.py — the coaching context query loads the 50 OLDEST messages instead of the 50 most recent:

```python
# ❌ BROKEN — loads oldest 50 messages
recent_msgs = msg_query.order_by(AgentChatMessage.created_at.asc()).limit(50).all()
```

The first 50 messages in the table are from May-June — 3+ weeks old. They contain names and topics that have no relevance to the current conversation, but the LLM picks them up and hallucinates from them.

**Fix**:
```python
# ✅ Load 50 MOST RECENT messages, reverse to chronological order
recent_msgs = list(reversed(msg_query.order_by(AgentChatMessage.created_at.desc()).limit(50).all()))
```

**Detection**: Check the date range of messages in the context window:
```python
msgs = db.execute('SELECT created_at FROM agent_chat_messages ORDER BY created_at ASC LIMIT 50').fetchall()
print(f'Oldest in window: {msgs[0][0]}, Newest: {msgs[-1][0]}')
```
If the newest is more than 2 days old, the context window is stale.

---

## 26. `_build_pending_description` Missing Tool Cases → Raw Tool Names (2026-06-29)

**Symptom**: Confirmation prompts show raw tool names: `save_memory; save_memory; save_memory` or `send_whatsapp_to_owner; send_whatsapp_instantly` instead of human-readable descriptions like "💾 Save: Pricing tiers — shall I save it?"

**Root cause**: `_build_pending_description` (line 6707) has explicit formatters for ~15 tools (`send_whatsapp`, `create_lead`, `set_reminder`, etc.) but falls through to a generic fallback for unrecognized tools. The fallback tries to extract meaningful arg values but only checks keys in `("title", "name", "lead_name", "message", "description", "org_name")`. Tools using different arg keys (e.g., `save_memory` uses `key`/`value`, `send_whatsapp_to_owner` uses `message`/`body`) produce empty descriptions → bare tool names.

**Missing tool cases**:
- `save_memory` — args: `key`, `value`
- `send_whatsapp_to_owner` — args: `message`, `body`, `subject`
- `send_whatsapp_instantly` — args: `lead_name`, `message`

**Fix**: Add cases for all three missing tools:
```python
elif name == "save_memory":
    key = args.get("key", "")
    val = args.get("value", "")[:60]
    key_display = key.replace("greg_", "").replace("_", " ").title()
    parts.append(f"💾 Save: {key_display} — shall I save it?")
elif name == "send_whatsapp_to_owner":
    msg = args.get("message", "") or args.get("body", "")
    preview = f" — \"{msg[:60]}{'…' if len(msg) > 60 else ''}\"" if msg else ""
    parts.append(f"📱 Send to you{preview} — shall I send it?")
elif name == "send_whatsapp_instantly":
    lead = args.get("lead_name", "")
    msg = args.get("message", "")[:60]
    preview = f" — \"{msg}{'…' if len(msg) == 60 else ''}\"" if msg else ""
    parts.append(f"⚡ Send instantly to {lead}{preview} — shall I send it?")
```

**Detection**: If a pending action title or description is a single word or semicolon-separated tool names, `_build_pending_description` is missing a case.

## 27. WhatsApp Sidecar False-Positive During Session Corruption (2026-06-29)

**Symptom**: Ava claims "✅ Messaged WhatsApp message sent to Arun Naik..." with confirmed msgIds, but messages never delivered. The sidecar was in a corrupted session state (Bad MAC errors, decryption failures) but reported `connected: true` and returned `{ ok: true }` for sends.

**Root cause — two layers**:

**Layer 1 — Sidecar**: `connectionState` is set to `'connected'` only on `connection === 'open'` event (line 550 in index.js). Session corruption (Bad MAC, decryption failures, 401 device_removed) does NOT trigger a connection state change — `connectionState` stays `'connected'`. `sock.sendMessage()` returns a message ID even when the underlying session cannot deliver. The sidecar returns `{ ok: true }` to the server.

**Layer 2 — Server**: `execute_tool('send_whatsapp', ...)` trusts the sidecar's response unconditionally (line ~4140):
```python
if wa_result.get("status") == "sent":
    return ToolResult.success(tool="send_whatsapp", summary=f"WhatsApp sent to lead '{lead_name}'")
```
No post-send health check or delivery verification. The `ToolResult` claims success → `render_results` formats as "✅ Messaged..."

**Real example (June 29, 2026)**:
```
09:58:13 — Tools executed: send_whatsapp × 2 (Arun Naik + Sai Bharat)
09:58:15 — Sidecar returned { ok: true } with msgIds
09:58:17 — Sidecar received WhatsApp 401 "device_removed" — session killed
09:58:17 — Auth cleared, sidecar restarted
→ Messages had msgIds but were never delivered (session dead on send)
→ Ava claimed "✅ Messaged..." based on ToolResult from before the kick
```

**Detection**:
```bash
# Check sidecar for Bad MAC / session errors around send time
journalctl -u ara-whatsapp-sidecar --since "2026-06-29 09:58:00" --until "2026-06-29 10:00:00" | grep -i "bad mac\|decrypt\|error\|logged out\|device_removed"

# Verify deliverability: sidecar status shows 'connected' but has decrypt_error_count > 0
curl -s http://localhost:8767/status | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'connected={d.get(\"connected\")}, decrypt_errors={d.get(\"decrypt_error_count\",0)}')"
```

**Fix applied (2026-06-29)**:
1. **Confirmation flow post-execution health check** (Fix #3): After confirmation flow executes `send_whatsapp` tools, pings sidecar `/status`. If disconnected or unhealthy, appends warning ToolResult: "WhatsApp sidecar is not connected. Messages may not have been delivered."
2. **Permanent fix direction**: Health check should be in `send_message_sync()` (the single choke point for ALL WhatsApp sends), not just the confirmation flow. This covers `[ACTION: NOW]` sends, auto-respond, notifications, and cadences. See build plan references/build-plan-2026-06-29.md for full implementation.
3. **Sidecar `/status` should report `healthy` field** — factoring `decryptErrorCount` > 10 as zombie detection, not just socket `connectionState`. See build plan for sidecar changes.

## 28. Echo/Forwarded Messages Poisoning Confirmation Classifier (2026-06-29)

**Symptom**: User forwards Ava's own messages back into the chat (prefixed "✨ Ava : …") as context. The confirmation classifier sees phrases like "Not yet — let me finish that now" and classifies them as "reject" (matching "Not yet" as a negative). The pending action gets cancelled by an echo.

**Real example**:
```
10:27:58 — Pending bd9b5bb5: attach Devashish to Instamart deal
10:36:50 — Greg forwards "✨ Ava : Not yet — let me finish that now."
→ CONFIRM-FLOW verdict: reject for pending id=bd9b5bb5
→ Pending cancelled. Step 3 never executes.
```

**Root cause**: No echo detection exists. Every user message passes through `_classify_confirmation` regardless of whether it's genuinely from the user or a forwarded copy of Ava's output. The classifier sees "Not yet" as a negative/rejection.

**Fix** (from build plan, pending implementation):
1. Add `_is_echo_message()` — checks for known forwarded-message prefixes (`✨ Ava :`, `Ava:`, `Forwarded:`, `Fwd:`) and content match against recent assistant messages.
2. Gate at the top of the confirmation block: if echo detected, skip the confirmation classifier. The echo passes through as context to the LLM but never confirms or rejects a pending action.

**Detection**: `journalctl -u ara-server | grep "CONFIRM-FLOW verdict: reject"` — check if the associated user message starts with an echo prefix.

## 29. Clarification Gate Too Strict — Misses Variant Confirmations (2026-06-29)

**Symptom**: No pending action exists, and user says "yes - run all three" or "do all of them" or "run everything". The clarification gate (added in Fix #2) should respond "I don't have any pending action…" but instead the message falls through to the LLM, which creates a fresh (potentially incomplete) proposal.

**Root cause**: The clarification gate uses exact-set matching:
```python
_bare_confirms = {"yes", "yes please", "yeah", ...}
if _bare in _bare_confirms or (_bare.startswith("yes") and len(_bare) <= 7):
```
`"yes - run all three"` (18 chars) fails the length check. `"do all of them"`, `"run everything"`, `"go ahead with all three"` don't match the set at all.

**Fix** (from build plan, pending implementation): Replace exact-set match with regex patterns:
- `^yes\b` — catches all yes-variants regardless of what follows
- `^(do|run|send|approve|execute|go ahead with|fire)\s+(all|everything|them|it all|all of (them|it)|all \w+)\b` — catches "do all", "run everything", "send them all"
- `^(go on|continue)\b` — continuation prompts
- Keep status-check patterns: `done?`, `is it done?`, `did you do it?`, `any update?`

**Detection**: Look for variant confirmations in `agent_chat_messages` that were NOT followed by a clarification response but instead triggered fresh LLM proposals.

## 30. LLM Drops Entities on Re-Proposal (2026-06-29)

**Symptom**: Original proposal says "Attach both Devashish AND Sai Bharat to the Instamart deal." User sends an unrelated message, causing the LLM to re-propose. The re-proposal only mentions Devashish — Sai Bharat is silently dropped.

**Real example**:
```
Original: "Step 3/3: Attach both Devashish and Sai Bharat to the deal"
Re-proposal: "Step 3: Attaching Devashish Sarin to the Instamart deal"
→ Sai Bharat dropped
```

**Root cause**: The LLM has no explicit memory of the original proposal's entity list. When re-generating, its attention may drift and drop entities.

**Fix** (from build plan, pending implementation):
1. **Entity injection guard**: When a live pending exists and the message is "unrelated", inject the pending's entity list into the user message: "⚠️ IMPORTANT: You currently have a pending proposal that references these entities: Devashish Sarin, Sai Bharat. If your response touches the same action, do NOT drop any of these entities."
2. **Strengthen system prompt rule #4**: "If the user said 'attach X AND Y', you need two attach_to_deal calls — one for each."
3. **Defense-in-depth**: Combined with step-count mismatch detection (pitfall #17/#23), any entity dropping would also trigger the step-count mismatch.

**Detection**: Compare entities in original proposal text vs re-proposal. Check `pending_tool_calls` JSON — if original had 2 attach calls but re-proposal has 1, this pitfall applies.

## 32. _BUILD_DESC_FALLBACK_COUNT Not Initialized → 500 on /api/voice/stage (2026-07-12)

**Symptom**: Ava loops trying to call a tool (e.g., `update_action`) — keeps retrying with different parameter formats but never succeeds. Server returns 500 on `POST /api/voice/stage`. User sees "I couldn't finish all of that" after the step limit.

**Root cause**: `_build_pending_description()` (line 6901) has explicit `elif` cases for ~15 tools in `VOICE_WRITE_TOOLS`. Tools without an explicit case fall through to the generic `else` branch (line 7009) which references `_BUILD_DESC_FALLBACK_COUNT`:

```python
# server.py:7010-7011
_BUILD_DESC_FALLBACK_COUNT[name] = _BUILD_DESC_FALLBACK_COUNT.get(name, 0) + 1
if _BUILD_DESC_FALLBACK_COUNT[name] == 3:
```

**`_BUILD_DESC_FALLBACK_COUNT` is NEVER initialized.** It's only referenced on these two lines — no `_BUILD_DESC_FALLBACK_COUNT = {}` exists anywhere in the codebase. This causes:

```
NameError: name '_BUILD_DESC_FALLBACK_COUNT' is not defined
→ 500 Internal Server Error on POST /api/voice/stage
→ LLM sees tool call fail → retries with different params → same 500 → loop
```

**Why `update_action` triggers it**: `update_action` is in `VOICE_WRITE_TOOLS` (line 6390) but has NO explicit case in `_build_pending_description`. Every `update_action` call goes through staging → falls to generic else → crashes.

**Affected tools**: Any tool in `VOICE_WRITE_TOOLS` that lacks an explicit `elif` case in `_build_pending_description`. Check with:

```bash
# Cross-reference VOICE_WRITE_TOOLS vs _build_pending_description cases
ssh root@46.224.132.99 "python3 << 'EOF'
with open('/opt/ara/server.py') as f:
    c = f.read()
# Extract VOICE_WRITE_TOOLS list
import re, ast
# Find tools with explicit cases in _build_pending_description
cases = set(re.findall(r'elif name == \"(\w+)\"', c[c.find('def _build_pending_description'):c.find('def _guard_single_action')]))
# Find tools in VOICE_WRITE_TOOLS
vwt_start = c.find('VOICE_WRITE_TOOLS = [')
vwt_end = c.find(']', vwt_start)
vwt = set(re.findall(r'"(\w+)"', c[vwt_start:vwt_end]))
missing = vwt - cases - {'send_attachment','schedule_follow_up','schedule_message','schedule_email','mark_meeting_booked','evaluate_qualification','log_insight','save_learning','add_to_watchlist','resolve_watchlist_item','import_leads_from_text','upload_document','detach_from_deal'}
print('Tools in VOICE_WRITE_TOOLS without explicit _build_pending_description cases:')
for t in sorted(missing):
    print(f'  {t}')
EOF"
```

**Fix**:
1. **Add `_BUILD_DESC_FALLBACK_COUNT = {}`** at module level (near line 320, by `_cf_log`).
2. **Add an explicit case for `update_action`** in `_build_pending_description` so it doesn't hit the fallback at all.

**Detection**: `journalctl -u ara-server | grep "NameError.*_BUILD_DESC_FALLBACK_COUNT"` — if present, this pitfall applies. Also check for 500 on `/api/voice/stage` correlating with a specific tool name in `CONFIRM-FLOW` logs.

**Symptom**: Fix #3 added WhatsApp sidecar health check, but ONLY in the confirmation flow execution path. `[ACTION: NOW]` sends, auto-respond messages, notifications, and cadence sends are all still vulnerable to the false-positive "sent" bug (pitfall #27).

**Root cause**: The health check is at the wrong level — in the confirm-execute loop instead of in `send_message_sync()`, the single choke point for ALL WhatsApp sends. Every send path calls `send_message_sync()` and trusts its response unconditionally.

**Send paths that bypass the health check**:
- `[ACTION: NOW]` sends (direct `execute_tool` without confirmation)
- Auto-respond messages (WhatsApp webhook processing)
- Notification sends (sidecar watchdog, system alerts)
- Cadence sends (scheduled pipeline messages)

**Fix** (from build plan, pending implementation):
1. **Move health check into `send_message_sync()`** — after `/send` returns ok, ping `/status` and check `healthy` field. If unhealthy, return `{status: "sent", warning: "…"}`.
2. **Add `healthy` field to sidecar `/status`** — factor `decryptErrorCount > 10` as zombie detection (`healthy: false` even when `connected: true`).
3. **Handle warning in `execute_tool`** — check for `warning` key and surface as degraded ToolResult.
4. **Simplify confirmation-flow check** — now redundant since `send_message_sync` handles it.

**Detection**: Check if a `send_whatsapp` ToolResult claims success but sidecar had `decrypt_error_count > 0` at send time. If warning key is missing, the health check didn't execute for that path.
