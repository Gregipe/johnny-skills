# ActionItems Notification System

## Architecture

```
Ava (LLM) calls evaluate_qualification / mark_meeting_booked
    ↓
execute_tool() in server.py creates ActionItem row + optionally advances stage
    ↓
REST API serves ActionItems to dashboard
    ↓
dashboard.js renderActions() displays with filter + resolve buttons
    ↓
Greg clicks "✓ Done" → PATCH /api/action-items/{id} → status = resolved
```

## API Endpoints

### GET /api/action-items
- Default: returns only `open` items
- `?status=all` — returns everything
- `?status=resolved` — resolved only
- `?status=dismissed` — dismissed only
- Fields: id, action_type, title, description, ref_type, ref_id, status, created_at, resolved_at, lead_name

### GET /api/action-items/stats
- Returns: `{"open": N, "resolved": N, "dismissed": N}`
- Polled every 15s for the sidebar badge

### PATCH /api/action-items/{id}
- Body: `{"status": "resolved"}` or `{"status": "dismissed"}`
- Sets `resolved_at` timestamp

## Action Types and Their Icons

| action_type | Icon | Created by |
|-------------|------|------------|
| stage_change | 🔄 | evaluate_qualification, _check_and_create_action_items |
| review_qualification | ❓ | evaluate_qualification (low confidence) |
| meeting_request | 📅 | mark_meeting_booked |
| suggest_deal | 💼 | _check_and_create_action_items (Ava chat) |
| escalate | 🚨 | _check_and_create_action_items (Ava chat) |
| review_reengagement | 🔄 | _handle_inbound_whatsapp (lost lead) |
| review_lead | 👤 | _check_and_create_action_items |

## Dashboard Integration

- `renderActions()` in `static/dashboard.js` — fetches from /api/action-items, renders cards with blue left border
- `filterActionItems(filter)` — re-fetches with status param, re-renders
- `resolveActionItem(id)` — PATCH to resolve, re-renders on success
- Lead name resolution: fetches `/api/leads/{ref_id}` for each unique lead ref
- Badge: `updateActionBadge(count)` sets badge text + visibility

## CSS Classes

- `.action-item-card` — card with blue left border (3px #2563eb)
- `.ai-icon`, `.ai-body`, `.ai-title`, `.ai-desc`, `.ai-meta`, `.ai-actions`
- `.btn-sm` — small button (4px 10px padding, 11px font)
- `.action-filters .af-pill` — filter pill buttons

## Design Decisions

1. **Separate endpoints from ScheduledActions.** ActionItems and ScheduledActions are semantically different (human tasks vs system actions) and must never share an endpoint.
2. **No auto-resolve.** Only Greg can mark items as resolved/dismissed. The system creates, the human closes.
3. **Lead name resolved client-side.** The API returns `lead_name: ""` — the JS fetches lead names per ref_id. This avoids N+1 on the server and keeps the API lean.
4. **Status defaults to open.** All ActionItems start with `status="open"`. The DB default handles this.
