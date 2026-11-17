# Database Model Pitfalls (WhatsApp/Cadence related)

## Lead.source doesn't exist

The `Lead` model has `lead_source` and `campaign_source` but NOT `source`.
Line 209 in `database.py` has `source = Column(...)` but it's on the **Skill** class, not Lead.

**Fix in code:** Use `lead.lead_source` instead of `lead.source`

Location in `server.py`:
```python
# Line 1695 — in _generate_step_message()
Source: {lead.lead_source or 'Not specified'}   # was: lead.source
```

## Missing DB columns

If SQLAlchemy has a column in the model but the table doesn't have it, add it:
```sql
ALTER TABLE leads ADD COLUMN source VARCHAR DEFAULT 'auto';
```
(But double-check the column is on the right class first!)

## Stale __pycache__

When editing models, always clear:
```bash
rm -rf __pycache__/
```
Python may use stale `.pyc` files even when `.py` source changes.

## ActionItem schema: Python model vs actual SQLite columns

The `database.py` `ActionItem` model defines columns that may not exist in the running `ara.db` if migrations haven't run yet. **The server.py lifespan startup (lines ~95-135) handles migrations automatically on restart.** When you hit "no such column" errors on `/api/action-items`, restart the ARA server — the lifespan function inspects existing columns and adds missing ones.

### Columns handled by automatic migration (as of July 2026)

These are added by the lifespan startup if missing:

| Column | Migration SQL |
|---|---|
| `deal_id` | `ALTER TABLE action_items ADD COLUMN deal_id VARCHAR` |
| `owner` | `ALTER TABLE action_items ADD COLUMN owner VARCHAR DEFAULT 'ava'` |
| `requires_confirmation` | `ALTER TABLE action_items ADD COLUMN requires_confirmation BOOLEAN DEFAULT 0` |
| `outcome_state` | `ALTER TABLE action_items ADD COLUMN outcome_state VARCHAR` |
| `channel` | `ALTER TABLE action_items ADD COLUMN channel VARCHAR DEFAULT 'none'` |
| `due_at` | `ALTER TABLE action_items ADD COLUMN due_at DATETIME` |
| `due_type` | `ALTER TABLE action_items ADD COLUMN due_type VARCHAR DEFAULT 'soft'` |
| `scheduled_action_id` | `ALTER TABLE action_items ADD COLUMN scheduled_action_id VARCHAR` |

### Legacy state (pre-July 2026 — before migrations were added)

Before the lifespan migrations, the actual `ara.db` had only these columns: `id`, `tenant_id`, `action_type`, `title`, `description`, `ref_type`, `ref_id`, `status`, `created_at`, `resolved_at`, `pending_tool_calls`, `execution_state`. Cron queries targeting missing columns (like `due_at`, `owner`) would cause 500 errors.

### Post-migration cron queries

After migration, all model columns exist. Use the model columns directly:

```sql
-- Open items with due dates (due_at now exists)
SELECT id, title, description, action_type, status, due_at, created_at
FROM action_items
WHERE tenant_id = '3e736242'
  AND status = 'open'
ORDER BY COALESCE(due_at, created_at) ASC;

-- Overdue items (due_at is now valid)
SELECT id, title, status, due_at
FROM action_items
WHERE tenant_id = '3e736242'
  AND status = 'open'
  AND due_at IS NOT NULL
  AND due_at < datetime('now');
```
