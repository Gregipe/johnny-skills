# Escape Mangling Incident Report

**Date:** Sprint 3, June 20, 2026
**Impact:** Dashboard.js rendered blank — all tabs broken
**Root cause:** `hermes chat -q ... | tee` mangled backslash escapes in JS string literals

## Reproduction

```bash
# This produces mangled output:
hermes --profile johnny chat -q "$(cat /tmp/prompt.txt)" \
  --model deepseek-v4-pro --provider deepseek \
  --toolsets terminal,file,web --quiet \
  2>&1 | tee /tmp/output.txt
```

The `hermes chat -q` subprocess writes clean code, but piping through `tee` (or `>`) introduces double-escaping of backslash-quote sequences.

## What breaks

In JavaScript string literals inside HTML generation:
- Input: `'<th onclick="_sortActionItems(\'due_at\', this)">'`
- After pipe: `'<th onclick=\\"_sortActionItems(\\\\'due_at\\\\', this)\\"'`
- Browser sees: `SyntaxError: Invalid escape in identifier: 'due_at\'`

## Detection
```bash
node -c /opt/ara/static/dashboard.js  # Always run after subprocess-based JS changes
```

## Recovery
1. Revert file to pre-sprint backup: `cp file.js.sprint3.bak file.js`
2. Verify backup is clean: `node -c file.js`
3. Re-apply changes using a Python script that writes directly (no pipe):
```python
with open(PATH, "w") as f:
    f.write(fixed_content)
```
4. Version bump to force browser cache clear: edit `dashboard_template.py`, increment `?v=N`
5. Verify: `node -c file.js && curl -s -o /dev/null -w '%{http_code}' http://localhost:8766/dashboard`

## Lessons
- Never pipe `hermes chat -q` output through `tee` for code that contains backslash escapes
- Always `node -c` after subprocess-based JS changes
- Prefer Python scripts with `write_file` for applying patches to static files
