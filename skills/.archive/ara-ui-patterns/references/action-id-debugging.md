# Action Item ID Format & State Debugging

## The `action_` Prefix Problem

The ARA codebase has TWO different ID formats for action items depending on which API you query:

| API Endpoint | ID Format | Example |
|-------------|-----------|---------|
| `/api/activities` | `action_{raw_id}` | `action_493719ff` |
| `/api/actions/{id}` | `{raw_id}` | `493719ff` |
| `/api/action-items` (internal) | `{raw_id}` | `493719ff` |
| `/api/leads/{id}/actions` | `{raw_id}` | `493719ff` |

The `/api/activities` endpoint (server.py line 2548) deliberately prefixes IDs to namespace them in the unified feed:
```python
"id": f"action_{a.id}"
```

But individual endpoints (`/api/actions/{id}`, `/api/action-items/{id}`) use raw DB IDs.

### Where it breaks

The Actions page (Tasks tab) renders from `/api/activities`. The `data-aid` attribute gets the prefixed form. When Edit/Mark Done/Delete handlers call `/api/actions/action_493719ff`, the endpoint does `ActionItem.id == "action_493719ff"` which never matches → 404.

### Three render paths use different ID sources

| Render path | Line in dashboard.js | `a.id` source | Has prefix? |
|------------|---------------------|---------------|-------------|
| Actions page table | ~1352 | `/api/activities` | YES |
| Lead detail menu | ~1943 | `/api/leads/{id}/actions` | NO |
| Class-based menu (3rd path) | ~4024 | varies | depends |

### The silent 404 bug

FastAPI returns `{"detail": "Action not found"}` on 404. The frontend check is `if (!a || a.error)` — but there's no `error` key, only `detail`. So the check silently passes, and the modal renders with `undefined` for all fields. The user sees a blank/weird modal instead of an error alert.

### Fix: `_stripActionPrefix()`

The canonical fix is a named utility function that strips the `action_` prefix (restored to dashboard.js v47, June 23 2026):

```javascript
function _stripActionPrefix(id) {
  return (typeof id === "string" && id.startsWith("action_")) ? id.slice(7) : id;
}
```

Call it at the top of every function that hits `/api/actions/{id}`:
- `editActionItem(actionId)` → `actionId = _stripActionPrefix(actionId);`
- `deleteActionItem(actionId)` → `actionId = _stripActionPrefix(actionId);`
- `saveEditedAction(actionId)` — the fetch URL must use the stripped ID
- `resolveActionItem(actionId)` → same pattern

## Execution State Anomaly: `execution_state = "completed"`

During a June 18, 2026 investigation, three manual action items were found with `execution_state = "completed"` and `outcome_state = "resolved"` despite the user not marking them done.

### Invalid value fingerprint

`"completed"` is NOT a valid `execution_state` value anywhere in the codebase. The only values set by code:

| Value | Set by |
|-------|--------|
| `pending` | `create_action` handler, new action creation |
| `awaiting_approval` | Confirmation flow (when Ava proposes an action) |
| `fired` | Confirmation flow (when user confirms) |
| `cancelled` | `_prune_pending_actions`, rejection path |

`"completed"` only appears in `status` comparisons (e.g., `a.status in ('completed', 'resolved')`) — never as a value being set on `execution_state`.

### Investigation methodology

1. **Grep for the value**: `grep -rn '"completed"\|execution_state.*completed' server.py` — found zero SET operations
2. **Git log for the value**: `git log -p -- server.py | grep 'completed'` — only status checks and prompt text
3. **Journalctl for modification evidence**: searched server logs for `update_action` calls with `outcome_state` arg — none found
4. **Trace all code paths that set outcome_state**:
   - `_prune_pending_actions` — only sets `execution_state = "cancelled"` on `awaiting_approval` rows
   - Confirmation flow — only fires for `action_type = "pending_confirmation"`
   - `update_action` tool (Ava) — would appear in agent_chat_messages logs
   - UI "Mark Done" — only sets `status`, not `execution_state` or `outcome_state` (before fix)
5. **Conclusion**: `execution_state = "completed"` is a fingerprint of direct DB manipulation (manual SQL or one-off script). SQLite's lack of row modification timestamps prevents exact time/actor attribution.

### Preventive measures

- Added `execution_state` and `outcome_state` sync to the UI "Mark Done" PATCH endpoint (so all three fields stay consistent)
- Consider adding an `action_items_snapshot` table with pre-modification row copies (designed but not yet implemented)
