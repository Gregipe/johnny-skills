# Sprint 2 Sparring — Key Advisor Findings

The advisor reshaped the PRD from 5 tasks to 10. Here are the sparring outcomes that changed the plan.

## Finding 1: query_actions NULL trap (Critical)
**Advisor:** "query_actions uses status != 'cancelled' — same NULL trap as get_action_items"
**Johnny:** "Checked production DB — zero NULL execution_state rows. But the trap is armed."
**Consensus:** Fix the filter now (not wait for data). Add to scope.

## Finding 2: query_actions formatter crash (Critical)
**Advisor:** "Formatter calls strftime on date objects without conversion. Crashes on any due_at row."
**Johnny:** "Not seeing this in production — but all open items have due dates. Will crash on first call."
**Consensus:** Fix the strftime before the filter (blocking crash). Resequenced to Task 2 (before filter).

## Finding 3: Tier classifier routes "got it done" to smalltalk (Critical)
**Advisor:** "got it is a smalltalk example → got it done matches → no tools → update_action never called"
**Johnny:** "Verified in tier prompt at L6747. This is the confirmed root cause of the 8:06 PM failure."
**Consensus:** Add "done", "got it done", "all done" to command examples. Add tie-break rule.

## Finding 4: update_action status sync on reopen (Important)
**Advisor:** "Resolved items reappear in context on next turn — status isn't synced on reopen"
**Johnny:** "Fixed the REST endpoint in Sprint 1. Tool handler wasn't covered."
**Consensus:** Expand Task 6 to sync status on ALL transitions (resolve, cancel, reopen).

## Finding 7: _build_recent_actions_block still on legacy status
**Advisor:** "Block uses status != 'resolved' — still reading legacy field"
**Johnny:** "Grep confirmed. Added as Task 10. This was the surface neither of us checked in Sprint 1."
**Consensus:** Migrate block to outcome_state. Add docstring note.
