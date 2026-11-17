# Email Attachment — Disk Fallback & Induction Sync

## Attachment Fallback for Legacy Documents

The email scheduler (`_execute_action`, action_type="email") looks for attachments on disk at:
```
/opt/ara/uploads/{doc_id}_{filename}
```

If the file doesn't exist on disk (legacy documents uploaded before UPLOAD_DIR was configured), it now falls back to creating a temp file from `doc.text_content`:

```python
if doc and os.path.exists(filepath):
    # Normal path — read binary from disk
    with open(filepath, "rb") as f:
        attachments = [(doc.filename, f.read())]
elif doc and doc.text_content:
    # Fallback — create temp file from stored text
    import tempfile
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    tmp.write(doc.text_content[:100000])
    tmp.close()
    with open(tmp.name, 'rb') as f:
        attachments = [(doc.filename, f.read())]
    os.unlink(tmp.name)
```

This means emails will always have an attachment, even for documents uploaded before the file-save-on-upload was implemented.

## Induction → Users Email Sync

When induction completes (all 5 modules covered), the system syncs the admin's email from induction skills to the users table:

```python
if skills_state['covered_count'] >= skills_state['total_modules']:
    t.induction_completed = True
    # Sync owner email from induction skills
    email_skill = db.query(Skill).filter(
        Skill.tenant_id == tenant_id, Skill.category == 'account',
        Skill.key.ilike('%email%')
    ).first()
    if email_skill and '@' in email_skill.value:
        admin.email = email_skill.value.strip()
```

Module 0 (Account Setup) already asks for the admin's email. This sync ensures it flows from skills → users table.

## Attachment Diagnosis

To check if an email was sent with attachment:
```sql
SELECT payload, status FROM scheduled_actions 
WHERE action_type='email' ORDER BY created_at DESC LIMIT 5;
```
Look for `"attachment": "filename.pdf"` in the payload. If present but the email arrived without it, check the disk path.
