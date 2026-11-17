# Advisor Review Examples

Real review output from the technical-advisor profile (Claude Sonnet).

## Sprint 2 Phase 3 — PRD Review
The advisor found 7 issues in a 5-task PRD, expanding scope to 10 tasks.

Key pattern from the review:
- Specific line references ("L6747 tier classifier prompt")
- SQL evidence queries ("SELECT COUNT(*) FROM action_items WHERE execution_state IS NULL")
- Impact statements ("This will cause a crash on the first due_at row")
- Fix directives ("Resequence task 3 before task 2")
- Verdict: CHANGES_REQUESTED with blocking items

## Sprint 2 Phase 7 — QA Gate Review
Post-implementation review caught:
- Copy-paste bug: Created column sort compared `a.created_at` against `a.created_at`
- Dismissed count inflated 19x by pending_confirmation items
- Missing REST PATCH status sync

Pattern: pre-review catches design flaws; post-review catches implementation bugs. Both are necessary.

## Sprint 3 Phase 7 — QA Gate Review
UI-only sprint. Found:
- Created column sort copy-paste bug (b.created_at → a.created_at typo)
- Dead code in history tab (execution_state arms unreachable)
- Confirmed dismissed=0 is consistent post-pending_confirmation exclusion

Verdict: CHANGES_REQUESTED with one real bug. Fixed on the spot.

## Advisor false positive log
- Sprint 2: "undefined 'now' in _build_recent_actions_block" — uses datetime.min, not now. False positive. Lesson: require line references for every finding. "Seems wrong" is not a finding.
