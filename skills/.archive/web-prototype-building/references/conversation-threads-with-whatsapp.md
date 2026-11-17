# Conversation Threads + WhatsApp Logging (ARA Implementation)

Reference for the complete thread-grouping + WhatsApp conversation logging built for the ARA dashboard. Combines ChatThread model, thread-scoped agent history, and WhatsApp inbound/outbound callbacks logging to leads.

## Architecture

```
server.py
├── /threads              → HTML page (ChatGPT-style thread sidebar)
├── /api/threads/{tid}    → CRUD endpoints
├── /api/agent/chat/{tid} → thread-scoped agent chat (accepts thread_id)
└── WhatsApp callbacks    → log to Conversation table via phone matching
```

## Database Schema

```python
# In database.py
class ChatThread(Base):
    __tablename__ = "chat_threads"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())[:8])
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    title = Column(String, nullable=False, default="New Thread")
    thread_type = Column(String, default="general")
    lead_id = Column(String, ForeignKey("leads.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

# Add to AgentChatMessage:
# thread_id = Column(String, ForeignKey("chat_threads.id"), nullable=True, index=True)
```

## WhatsApp Callback Wiring

```python
from whatsapp_manager import wa

def log_to_lead_conversation(phone, message, inbound=True):
    """Thread-safe: creates its own DB session."""
    from database import SessionLocal, Lead, Conversation
    db = SessionLocal()
    try:
        clean = "".join(c for c in phone if c.isdigit())[-10:] if phone else ""
        if not clean:
            return
        lead = db.query(Lead).filter(Lead.phone.contains(clean)).first()
        if not lead:
            lead = Lead(tenant_id=TENANT_ID, name=f"WhatsApp {clean[-4:]}",
                       phone=clean, source="whatsapp_inbound", status="new")
            db.add(lead)
            db.commit()
            db.refresh(lead)
        convo = Conversation(
            tenant_id=TENANT_ID, lead_id=lead.id,
            direction="inbound" if inbound else "outbound",
            message=message, channel="whatsapp"
        )
        db.add(convo)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

wa.on_inbound_message = lambda phone, name, msg: \
    log_to_lead_conversation(phone, msg, inbound=True)
wa.on_outbound_message = lambda phone, msg: \
    log_to_lead_conversation(phone, msg, inbound=False)
```

## Thread-Scoped Agent Chat (server.py)

```python
@app.post("/api/agent/chat/{tenant_id}")
def agent_chat(tenant_id: str, data: dict, db: DBSession = Depends(get_db)):
    t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not t: raise HTTPException(404)

    user_msg = data.get("message", "").strip()
    thread_id = data.get("thread_id")

    # Load history scoped to thread
    query = db.query(AgentChatMessage).filter(
        AgentChatMessage.tenant_id == tenant_id
    )
    if thread_id:
        query = query.filter(AgentChatMessage.thread_id == thread_id)
    else:
        query = query.filter(AgentChatMessage.thread_id == None)
    recent_msgs = query.order_by(AgentChatMessage.created_at.asc()).limit(20).all()

    # Build system prompt with live pipeline data
    leads = db.query(Lead).filter(Lead.tenant_id == tenant_id).all()
    # ... build system prompt ...

    messages = [{"role": "system", "content": system_prompt}]
    for m in recent_msgs:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": user_msg})

    response = call_llm(messages)

    # Save with thread_id
    db.add(AgentChatMessage(tenant_id=tenant_id, role="user",
           content=user_msg, thread_id=thread_id))
    db.add(AgentChatMessage(tenant_id=tenant_id, role="assistant",
           content=response, thread_id=thread_id))
    db.commit()
    return {"response": response}
```

## Frontend (/threads)

- Full-page ChatGPT-style layout: left sidebar (thread list) + right panel (chat window)
- Sidebar shows: title, last message preview (truncated 80 chars), message count, type badge
- Type badges: `general` (default), `coaching` (purple), `lead` (green)
- Click thread → loads message history, enables input
- "New Thread" button → POST /api/threads → opens blank chat
- Send message → POST /api/agent/chat with thread_id
- Delete button on each thread → DELETE /api/threads/{id} (cascade deletes messages)

## Nav Integration

Add "Threads with Ava" link in dashboard sidebar, pointing to `/threads`.
