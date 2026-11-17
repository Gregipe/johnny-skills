#!/usr/bin/env python3
"""Daily WhatsApp morning brief — production ARA data gatherer.

Run ON the prod server (root@46.224.132.99), NOT localhost. Transfer via
base64-over-ssh (sqlite3 CLI is NOT installed on Ubuntu):

    base64 < daily-brief-gather.py | ssh root@46.224.132.99 \
        'base64 -d > /tmp/gather.py && python3 /tmp/gather.py'

Defensive by design: probes PRAGMA table_info and SELECTs only columns that
exist, because the ARA schema has drifted from past hardcoded guesses
(action_items has no lead_id/lead_name; learning_notifications uses
notif_type not type; skills uses key/value not summary).
"""
import sqlite3, json, datetime
from collections import Counter

DB = '/opt/ara/ara.db'
TENANT = '3e736242'

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
c = conn.cursor()
now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
now_s = now.strftime('%Y-%m-%d %H:%M:%S')
out = {}

def cols(t):
    c.execute(f"PRAGMA table_info({t})")
    return [r['name'] for r in c.fetchall()]

def sel(table, want):
    have = cols(table)
    return [w for w in want if w in have]

for t in ['action_items', 'scheduled_actions', 'learning_notifications',
          'conversations', 'skills', 'ava_insights']:
    out[f'{t}_cols'] = cols(t)

# --- Overdue (human, actionable) ---
ai_sel = sel('action_items', ['id', 'title', 'lead_name', 'owner', 'due_at',
                              'outcome_state', 'execution_state'])
c.execute(f"SELECT {', '.join(ai_sel)} FROM action_items "
          f"WHERE tenant_id=? AND due_at IS NOT NULL AND due_at < ? "
          f"ORDER BY due_at ASC", (TENANT, now_s))
raw = [dict(r) for r in c.fetchall()]
out['overdue_raw_count'] = len(raw)
out['overdue_owner_counts'] = dict(Counter(str(r.get('owner')) for r in raw))
out['overdue_outcome_counts'] = dict(Counter(str(r.get('outcome_state')) for r in raw))

resolved = {'resolved', 'done', 'completed', 'closed', 'won', 'lost',
            'cancelled', 'canceled', 'dismissed'}
filtered = [r for r in raw
            if (r.get('owner') or '').strip().lower() == 'human'
            and not (r.get('title') or '').startswith('Reminder:')
            and '[REGRESSION]' not in (r.get('title') or '')
            and (r.get('outcome_state') or '').strip().lower() not in resolved]
out['overdue_filtered_count'] = len(filtered)
out['overdue_filtered'] = [{'title': r.get('title'), 'due': r.get('due_at'),
                            'lead': r.get('lead_name')} for r in filtered[:10]]

# --- Today's scheduled actions (IST window in UTC) ---
start = (now - datetime.timedelta(days=1)).replace(hour=18, minute=30, second=0, microsecond=0)
end = now.replace(hour=18, minute=30, second=0, microsecond=0)
sa_sel = sel('scheduled_actions', ['id', 'channel', 'payload', 'scheduled_at',
                                   'status', 'executed_at'])
c.execute(f"SELECT {', '.join(sa_sel)} FROM scheduled_actions "
          f"WHERE scheduled_at >= ? AND scheduled_at < ? ORDER BY scheduled_at ASC",
          (start.strftime('%Y-%m-%d %H:%M:%S'), end.strftime('%Y-%m-%d %H:%M:%S')))
out['today_items'] = [dict(r) for r in c.fetchall()]
out['today_count'] = len(out['today_items'])
c.execute("SELECT MAX(scheduled_at) FROM scheduled_actions")
out['sched_latest'] = c.fetchone()[0]

# --- Learnings last 24h ---
since = (now - datetime.timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
for tbl in ['skills', 'ava_insights']:
    tcols = cols(tbl)
    ts = 'created_at' if 'created_at' in tcols else (tcols[0] if tcols else None)
    if not ts:
        out[f'{tbl}_err'] = 'no columns'
        continue
    c.execute(f"SELECT COUNT(*) FROM {tbl} WHERE {ts} >= ?", (since,))
    out[f'{tbl}_24h'] = c.fetchone()[0]
    c.execute(f"SELECT MAX({ts}) FROM {tbl}")
    out[f'{tbl}_latest'] = c.fetchone()[0]

# --- Conversations last 24h ---
cv = cols('conversations')
ts = 'created_at' if 'created_at' in cv else ('started_at' if 'started_at' in cv else None)
if ts:
    c.execute(f"SELECT COUNT(*) FROM conversations WHERE {ts} >= ?", (since,))
    out['conversations_24h'] = c.fetchone()[0]
    c.execute(f"SELECT MAX({ts}) FROM conversations")
    out['conversations_latest'] = c.fetchone()[0]

# --- Reminder-noise flag ---
c.execute("SELECT COUNT(*) FROM learning_notifications WHERE notif_type='action_reminder'")
out['reminder_total'] = c.fetchone()[0]
if 'acknowledged' in cols('learning_notifications'):
    c.execute("SELECT COUNT(*) FROM learning_notifications "
              "WHERE notif_type='action_reminder' AND acknowledged=0")
    out['reminder_unacked'] = c.fetchone()[0]

print(json.dumps(out, default=str, indent=1))
