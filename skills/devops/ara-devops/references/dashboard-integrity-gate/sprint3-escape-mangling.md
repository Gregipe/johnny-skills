# Sprint 3 Escape Mangling — Reproduction Recipe

## What happened
The subprocess `hermes chat -q | tee` pipeline added one shell escaping layer.
Every backslash in the JS was doubled. What should have been `\"` became `\\"`.
The browser threw `Invalid escape in identifier` and stopped all JS.

## Timeline
1. Sprint 3 dispatched via `hermes chat -q "$(cat prompt.txt)" | tee dashboard.js`
2. JS written with double-escaped quotes throughout (~58 occurrences)
3. `node -c` passed — allows escaped chars in strings
4. Browser threw `SyntaxError: Invalid escape in identifier: 'due_at\'` at line 1428
5. All dashboard tabs/buttons stopped working — blank screen
6. Backup taken AFTER corruption — useless for recovery
7. True clean backup found at Jun 15 — but it predated Sprint 2, losing overdue detection
8. Restore corrupted: lost overdue; restore clean: lost history tab and sort

## Detection
- `node -c` does NOT catch this — it allows escaped chars in JS strings
- Browser JS engine DOES catch it — `Invalid escape in identifier`
- `grep '\\\\\"' dashboard.js` finds the mangled pattern
- `dashboard_integrity_test.py` (post-deploy) catches it via curl check

## Prevention
1. NEVER pipe hermes chat -q through a shell pipe to write files
2. ALWAYS use safe_write.py as the write gate
3. ALWAYS run dashboard_integrity_test.py after any dashboard.js change
4. Backup BEFORE write, diff backup against previous version
