# Induction Reset Procedure (June 2026)

Session-specific detail for resetting ARA's induction to a clean slate —
wiping conversation history and induction-sourced skills while preserving
the knowledge base from uploaded documents and conversation learnings.

## When to Use

- User wants to restart induction from the absolute beginning
- System prompt or engine changed significantly and old conversation history
  would contaminate the new flow (e.g., old multi-question responses acting
  as few-shot examples)
- Induction is stuck showing "complete" when the user never actually did it
  (caused by `covered_count > 0` from document-derived skills)

## What Gets Deleted vs Kept

| Data | Source / Type | Action |
|------|---------------|--------|
| Induction skills | `Skill.source = 'induction'` | **DELETE** |
| Document skills | `Skill.source = 'document'` | KEEP |
| Conversation skills | `Skill.source = 'conversation'` | KEEP |
| Induction chat logs | `CoachingLog.feedback_type IN ('induction_chat', 'induction_chat_response')` | **DELETE** |
| Documents | `Document` table | KEEP |
| Tenant state | `induction_completed`, `induction_score` | **RESET** |
| In-memory session | `INDUCTION_SESSIONS[tenant_id]` | **CLEAR** (or restart server) |

## Procedure

### 1. Audit What Exists (Before Deleting)

```python
import database; database.init_db()
db = database.SessionLocal()
from collections import Counter

skills = db.query(Skill).filter(Skill.tenant_id == tenant_id).all()
sources = Counter(s.source for s in skills)
print(f"Total skills: {len(skills)}")
print(f"By source: {dict(sources)}")

chat_logs = db.query(CoachingLog).filter(
    CoachingLog.tenant_id == tenant_id,
    CoachingLog.feedback_type.in_(["induction_chat", "induction_chat_response"])
).count()
print(f"Induction chat logs: {chat_logs}")
db.close()
```

### 2. Execute the Reset

```python
import database; database.init_db()
db = database.SessionLocal()

# 1. Delete induction-sourced skills ONLY
deleted_skills = db.query(Skill).filter(
    Skill.tenant_id == tenant_id,
    Skill.source == "induction"
).delete(synchronize_session=False)
print(f"Deleted {deleted_skills} induction skills")

# 2. Delete induction conversation logs
deleted_logs = db.query(CoachingLog).filter(
    CoachingLog.tenant_id == tenant_id,
    CoachingLog.feedback_type.in_(["induction_chat", "induction_chat_response"])
).delete(synchronize_session=False)
print(f"Deleted {deleted_logs} induction chat logs")

# 3. Reset tenant state
t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
t.induction_completed = False
t.induction_score = 0

db.commit()
db.close()
```

### 3. Clear In-Memory Session

```python
# Option A: if you have access to the server process
INDUCTION_SESSIONS.pop(tenant_id, None)

# Option B: restart the server (simpler, always works)
# ssh root@SERVER "systemctl restart ara-server"
```

### 4. Verify the Fresh Start

```bash
# Hit the induction chat endpoint — should start Module 0 with ONE question
curl -s -X POST http://localhost:8766/api/induction/{tenant_id}/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"hi"}'
```

**Expected response:** Ava acknowledges the knowledge base (if documents exist),
then asks a single question — typically "What's your name?" (Module 0, Q1).

**Red flag:** If Ava says "induction is fully done" or "you've completed all
modules" — the `hist_count == 0` gate is not implemented. See the
"Knowledge-Aware Induction Start (Code Gate)" section in the SKILL.md.

## Key Lesson

Document-derived skills are CONTEXT, not CONVERSATION. A tenant with 200+
skills from uploaded decks and website crawling has zero induction history.
The fresh-start gate must check `hist_count` (actual CoachingLog conversation
records), not `covered_count` (which counts ALL skills including document-sourced).

Using `covered_count == 0` as the gate causes the LLM to see "2/5 modules
covered" and skip induction entirely — the worst possible UX.
