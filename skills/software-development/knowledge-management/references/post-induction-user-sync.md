# Post-Induction User Sync (June 2026)

When induction completes (`induction_completed = True`), the server now syncs admin email and name from induction skills to the `users` table.

## The Problem

Module 0 (Account Setup) asks for the admin's name and email. These are saved as skills (category=`account`). But the `users` table still had the hardcoded placeholder `admin@tenant.com`. After induction, email notifications went to the wrong address because the induction data never propagated to the users table.

## The Fix

At induction completion (line 3325 in server.py), read the `account` category skills and sync to the admin user:

```python
if skills_state['covered_count'] >= skills_state['total_modules']:
    t.induction_completed = True
    # Sync owner email + name from induction skills to users table
    admin = db.query(User).filter(User.tenant_id == tenant_id, User.role == 'admin').first()
    if admin:
        email_skill = db.query(Skill).filter(
            Skill.tenant_id == tenant_id, Skill.category == 'account',
            Skill.key.ilike('%email%')
        ).first()
        name_skill = db.query(Skill).filter(
            Skill.tenant_id == tenant_id, Skill.category == 'account',
            Skill.key.ilike('%name%')
        ).first()
        if email_skill and email_skill.value and '@' in email_skill.value:
            admin.email = email_skill.value.strip()
        if name_skill and name_skill.value:
            admin.name = name_skill.value.strip()

db.commit()
```

## Verification

After induction completes, check:
```sql
SELECT name, email FROM users WHERE role = 'admin';
```

Should show the values provided during induction, not the placeholder `admin@tenant.com`.
