# Inbound Email Poller — Stage Transition Checklist

Test that the full pipeline works end-to-end:

## Prerequisites
- Gmail OAuth integration is connected (`/api/integrations` shows `connected: true`)
- Lead exists with `stage = "reached_out"` or `"new"` and a valid email
- Lead has an associated deal (for deal sync verification)

## Steps

1. **Send an email to the lead** from the connected Gmail account
2. **Reply as the lead** — from the lead's email, reply to Ava's message
3. **Wait 60s** — the scheduler polls every 60s
4. **Verify lead stage:**
   ```bash
   sqlite3 /Users/greg/ara/ara.db "SELECT name, stage, lead_source FROM leads WHERE email='lead@example.com';"
   # Expected: stage='engaged', lead_source='email'
   ```
5. **Verify deal synced:**
   ```bash
   sqlite3 /Users/greg/ara/ara.db "SELECT d.org_name, d.stage FROM deals d JOIN leads l ON l.deal_id = d.id WHERE l.email='lead@example.com';"
   # Expected: stage='engaged' (moved forward from reached_out)
   ```
6. **Verify conversation logged:**
   ```bash
   sqlite3 /Users/greg/ara/ara.db "SELECT channel, direction, substr(content,1,100) FROM conversations WHERE lead_id=(SELECT id FROM leads WHERE email='lead@example.com') ORDER BY created_at DESC LIMIT 1;"
   # Expected: channel='email', direction='inbound', content=pricing inquiry text
   ```
7. **Verify email marked as read** — check the connected Gmail inbox; the reply should no longer be unread
8. **Verify pending cadence actions cancelled:**
   ```bash
   sqlite3 /Users/greg/ara/ara.db "SELECT id, action_type, status FROM scheduled_actions WHERE lead_id=(SELECT id FROM leads WHERE email='lead@example.com') AND status IN ('pending','firing');"
   # Expected: no rows returned
   ```
