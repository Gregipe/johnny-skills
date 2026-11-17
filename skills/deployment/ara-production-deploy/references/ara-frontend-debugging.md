# ARA Frontend Debugging: "Error loading X" Pattern

## The Pattern

When a dashboard page shows "Error loading leads", "Error loading lead", "Error loading deal", etc. — the render function's `catch` block swallowed the real error. The generic message tells you nothing.

## Debugging Workflow

### 1. Find the render function's catch block

Search `dashboard.js` for the exact error string:
```bash
grep -n "Error loading lead" /opt/ara/static/dashboard.js
```

### 2. Inject `console.error` into the catch block

Replace the generic error with one that logs the actual exception:
```javascript
// Before:
} catch(e) { cp.innerHTML = '<div class="page-title">Error loading lead</div>'; }

// After:
} catch(e) { console.error("showLeadDetail error:", e); cp.innerHTML = '<div class="page-title">Error loading lead</div>'; }
```

### 3. Bump the cache buster

Edit `dashboard_template.py`:
```bash
sed -i 's/dashboard.js?v=N/dashboard.js?v=N+1/' /opt/ara/dashboard_template.py
```

### 4. Restart server and hard-refresh browser

```bash
systemctl kill ara-server; sleep 2; systemctl start ara-server
# Browser: Cmd+Shift+R
```

### 5. Reproduce and check browser console

Open DevTools → Console (Cmd+Option+J). Look for the `console.error` output.
Common error types and their fixes:

## Common Frontend Error Causes

### Template variable not substituted
**Symptom:** `RangeError: invalid time zone: {{TENANT_TIMEZONE}}` or similar raw `{{VAR}}` string.
**Root cause:** Variable added to `dashboard_template.py` but not substituted in the dashboard endpoint (`server.py:1968`).
**Fix:** Add `.replace("{{VAR}}", value)` to the endpoint chain.

### Null field accessed in render
**Symptom:** `TypeError: Cannot read properties of null (reading 'charAt')` or similar.
**Root cause:** API response missing a field that the JS expects, or field is `null` when JS expects a string.
**Fix:** Add null guard: `(c.channel || '').charAt(0)` or add the field to the backend API response.

### Stale cache
**Symptom:** Error on one machine/browser but not another. Or error persists after code fix.
**Root cause:** Browser caching old `dashboard.js`.
**Fix:** Bump `?v=` version in `dashboard_template.py`.

## Interactive Agent Chat Frontend Debugging

When the agent chat panel shows errors or blank messages:
- Check `chatMessages` array in the response — the backend may be sending malformed JSON
- Look for `[TOOL_CALL:*]` markers that weren't stripped by the backend before sending to frontend
- Check for unescaped HTML in messages breaking innerHTML rendering
