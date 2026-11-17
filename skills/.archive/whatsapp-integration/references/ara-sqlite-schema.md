# ARA SQLite Schema — Quick Reference

DB path: `/Users/greg/ara/ara.db` (live, 1.5MB+)
Stale path to ignore: `/Users/greg/ara.db` (empty 0-byte file)

## Tables

```
action_items            conversations           platform_config
agent_chat_messages     deal_events             scheduled_actions
agents                  deals                   skill_evidence
ava_insights            documents               skills
ava_watchlist           integration_config      tenants
cadence_configs         leads                   users
chat_threads            learning_notifications
coaching_logs           mentionable_items
```

## Working Queries (tested July 17, 2026)

### Action Items
```sql
-- Status breakdown
SELECT COUNT(*) as count, status FROM action_items GROUP BY status;

-- Pending/overdue
SELECT id, title, description, status, created_at 
FROM action_items WHERE status != 'resolved' 
ORDER BY created_at DESC LIMIT 10;
```

### Deals (no tenant_id column — all belong to tenant 3e736242)
```sql
-- Stage breakdown
SELECT COUNT(*) as count, stage FROM deals GROUP BY stage;

-- Active deals (columns: id, org_name, stage, expected_value, contact_name, contact_phone, industry_segment, created_at, stage_entered_at)
SELECT id, org_name, stage, expected_value, contact_name, contact_phone, industry_segment, created_at, stage_entered_at 
FROM deals WHERE stage != 'won' AND stage != 'lost' 
ORDER BY created_at DESC;
```

### Learning Notifications (no tenant_id column)
```sql
-- Unacknowledged
SELECT notif_type, acknowledged, created_at 
FROM learning_notifications WHERE acknowledged = 0 
ORDER BY created_at DESC LIMIT 10;

-- By type
SELECT notif_type, COUNT(*) FROM learning_notifications 
WHERE acknowledged = 0 GROUP BY notif_type;
```

### Scheduled Actions
```sql
-- Status breakdown
SELECT COUNT(*) as total, status FROM scheduled_actions GROUP BY status;

-- Pending
SELECT id, action_type, status, scheduled_at, lead_id, retry_count 
FROM scheduled_actions WHERE status = 'pending' 
ORDER BY scheduled_at ASC LIMIT 10;
```

### Owner Phone
```sql
SELECT phone FROM users WHERE tenant_id='3e736242' AND role='admin';
-- Confirmed: 919582549236 (Greg)
```

### Ava Insights (Last 24h)
```sql
SELECT insight_type, key, value, created_at 
FROM ava_insights 
WHERE created_at >= datetime('now','-1 day') 
ORDER BY created_at DESC LIMIT 10;
```

## Known Schema Quirks

- **No `tenant_id` column** on `action_items`, `deals`, `learning_notifications`, or `scheduled_actions` — all data belongs to tenant 3e736242 implicitly
- **`deals` table** has `org_name` (not `name`), `expected_value` (not `value`)
- **`action_items`** schema: id, title, description, status, created_at (no `action_type`, no `execution_state`, no `tenant_id`)
- **`scheduled_actions`** uses `status` values: 'pending', 'completed', 'cancelled', 'failed' (not 'fired', 'queued', etc.)
- **`/api/action-items`** endpoint maps to this table but returns 500 intermittently — API schema ≠ DB schema (the API has more fields)
