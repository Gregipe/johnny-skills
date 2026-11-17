# Sprint 3 dashboard.js Corruption Postmortem

**Date:** June 20, 2026  
**Impact:** All dashboard tabs, buttons, and actions stopped working. Blank screen.  
**Root cause:** Shell pipe double-escaping — `hermes chat -q` subprocess piped through `tee` doubled all backslash escape sequences in JS strings.

## Corruption Pattern

The subprocess wrote JS code using regex replacement, but shell piping (`tee`) double-escaped all backslash characters:

```
Correct:   '<th onclick=\"_sortActionItems(\'due_at\', this)\">'
Corrupted: '<th onclick=\\\"_sortActionItems(\\'due_at\\', this)\\\">'
```

In the actual production file, the corruption manifested as `\\"` (0x5c 0x5c 0x22) where `\"` (0x5c 0x22) was intended. Example from L1323:

```
Correct:   ct.innerHTML = '<span style=\"font-size:12px;color:#6E6E73\">' + ...
Corrupted: ct.innerHTML = '<span style=\\\"font-size:12px;color:#6E6E73\\\">' + ...
```

The corrupted source produces a literal backslash before the double-quote in the resulting HTML string: `style=\"font-size:...\"`. Browsers reject this in certain contexts as "Invalid escape in identifier."

## Why 3 Layers of Testing Missed It

| Layer | Result | Why |
|-------|--------|-----|
| `node -c` (syntax check) | PASSED | JS parser allows escaped chars in string literals |
| T1 Drift test (16/16) | PASSED | Server-side, Python, no JS execution |
| T2 Agreement test (3/3) | PASSED | API-level, no browser involved |
| T5 Roundtrip (15/15) | PASSED | REST endpoints only |

None of the 34 tests executed JavaScript or rendered the dashboard in a browser.

## What Would Have Caught It

1. **Byte-level corruption detector** — `check-js-escapes.py` scanning for `\\"` (0x5c 0x5c 0x22) — NOW IMPLEMENTED
2. **Dashboard health test** — curl dashboard, grep for expected content, fail on blank
3. **Headless browser smoke test** — load page, check console for errors
4. **Static file integrity check** — fetch `/static/dashboard.js` after deploy and validate
5. **Pre-commit hook** — block deployment if JS fails escape validation

## Defense Layers Implemented (Post-Sprint 3)

### 1. Pre-commit hook (`/opt/ara/.git/hooks/pre-commit`)
Blocks any commit containing `\\"` in JS files. Runs `check-js-escapes.py` + `node -c` on staged `.js` files.

### 2. JS gate in qa-gate.sh
Step 2 of qa-gate.sh runs `check-js-escapes.py` + `node -c` on all `static/*.js` before mypy and pytest. Any double-escaping or syntax error blocks deploy.

### 3. Static file integrity check in deploy.sh
Step 6 of deploy.sh fetches every `static/*.js` from `localhost:8766` after restart and validates:
- HTTP 200
- Content > 100 bytes (catches blank/truncated)
- No double-escaped quotes in the served file

### 4. Daily static backups
`backup-static.sh` snapshots `static/` with 7-day retention. Runs as part of the daily 3 AM IST cron (in `ara-backup.sh`). Can also be run manually before agent-driven file modifications.

## Key Insight: node -c is Insufficient

`node -c` validates JavaScript syntax but allows constructs that browsers reject. It is a necessary but NOT sufficient gate. The byte-level `check-js-escapes.py` catches the specific corruption that `node -c` misses. This was proven during testing: the pre-commit hook correctly BLOCKED the sprint3 backup file while `node -c` PASSED it.

## Single vs Double Quote Escaping

The checker intentionally only scans for `\\"` (double-escaped double-quotes), not `\\'` (double-escaped single-quotes). In this codebase, `\\'` inside single-quoted JS strings is a legitimate idiom for constructing onclick handlers:

```javascript
'<button onclick="showActionsTab(\\'tasks\\')">'
```

The `\\'` produces `\'` in the HTML output, which browsers treat as an escaped single-quote in the onclick handler's JavaScript context. This is sloppy-mode JS — it would be a SyntaxError in strict mode, but it works and is the established pattern in dashboard.js.

`\\"` however has no legitimate use case in this codebase and is always corruption.

## Fix Commits (June 20, 2026)

| Commit | Description |
|--------|-------------|
| `5c08be8` | Fix L1323 double-escaped quotes in dashboard.js |
| `4de9f4a` | Bump cache buster v36→v37 |
| `4239fff` | Add `check-js-escapes.py` checker script |
| `4bb8221` | Add JS gate to qa-gate.sh |
| `6e7e034` | Add static file integrity check to deploy.sh |
| `7e0c5bc` | Add backup-static.sh + wire into daily cron |
