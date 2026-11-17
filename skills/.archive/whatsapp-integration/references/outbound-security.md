# Outbound Send Security — Incident and Fix

## The Incident

A WhatsApp message reading *"Test message from Ava. Don't reply, just checking connectivity now."* was sent to a personal contact (9999111372) during WhatsApp integration testing. The contact read it.

**Root cause:** Two unvalidated send pathways:

1. **`/api/whatsapp/send` endpoint** in `server.py` — accepted any phone number with zero validation. No lead check, no admin check, no tenant_id required.

2. **Sidecar `/send` endpoint** — same, no validation. Trusted anything the Python server sent.

The message was not in the system as a lead and was not the owner's number. The exact source path couldn't be traced because the database was rebuilt during debugging, but the safety gap was clear.

## The Fix

Added `_is_allowed_destination()` validation function and applied it to all outbound paths:

### Code Changes

**Server (`server.py`):**

```python
def _is_allowed_destination(phone: str, db, tenant_id: str) -> bool:
    clean = ''.join(c for c in phone if c.isdigit())
    if not clean:
        return False
    # Check leads table
    lead_match = db.query(Lead).filter(
        Lead.tenant_id == tenant_id,
        Lead.phone.like(f"%{clean}%")
    ).first()
    if lead_match:
        return True
    # Check admin/owner phone
    admin = db.query(User).filter(User.role == "admin", User.tenant_id == tenant_id).first()
    if admin and admin.phone:
        admin_clean = ''.join(c for c in admin.phone if c.isdigit())
        if clean == admin_clean:
            return True
    return False
```

**Applied to:**
- `execute_tool('send_whatsapp')` — after `resolve_lead()`, validates lead.phone
- `/api/whatsapp/send` — requires tenant_id, validates number before send
- Sidecar endpoints — logging added but validation stays in server

**Sidecar (`whatsapp-sidecar/index.js`) — logging added:**

All three endpoints (`POST /send`, `POST /send-jid`, `GET /send`) now log:
```
OUTBOUND via /send: to=<dest> text="<preview>"
OUTBOUND SENT via /send: to=<dest> msgId=<id>
OUTBOUND FAILED via /send: to=<dest> error=<msg>
```

## Verification

```
POST /api/whatsapp/send {number: "9999111372", text: "...", tenant_id: "3e736242"}
→ 403: "Phone number is not an allowed destination"

POST /api/whatsapp/send {number: "+919582549236", text: "...", tenant_id: "3e736242"}  
→ 200: {"status": "sent", "msg_id": "..."}
```

## Lessons

1. **Every outbound endpoint needs destination validation** — never trust that the caller has already validated.
2. **Log every outbound send** — who, what, where, success/failure. Post-incident analysis depends on it.
3. **Database resets erase the trail** — if the DB gets rebuilt during debugging, the evidence of what numbers were messaged is gone. Keep sidecar-level logging separate from the DB.
4. **The sidecar is a thin transport** — all business validation belongs in the Python server. Never add destination logic to the sidecar itself.
