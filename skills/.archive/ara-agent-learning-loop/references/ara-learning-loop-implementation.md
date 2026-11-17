# ARA Agent Learning Loop — Implementation Reference (May 2026)

## Database Model

```python
class AvaInsight(Base):
    """Per-conversation learnings extracted by Ava — journal of what was learned."""
    __tablename__ = "ava_insights"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())[:8])
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=True)
    insight_type = Column(String, nullable=False)
    key = Column(String, nullable=False)   # normalized English label
    value = Column(Text)                   # free-text detail
    confidence = Column(Float, default=0.5)
    source = Column(String, default="auto")  # auto, manual
    created_at = Column(DateTime, default=utcnow)
```

## Key Functions in server.py

### `load_skills_for_prompt(tenant_id, db, lead=None)`

Called before every Ava response. Queries all skills, groups by category, returns formatted string.

**Signature:** `(tenant_id, db_session, lead=None) -> str`

- Returns a string with grouped skill categories: "Objection Pattern:\n  - pricing_retail: Leads from retail...\n\nMessaging Win:\n  - roi_framing: ..."
- Returns "Ava is still learning — no past conversation lessons yet." if no skills exist
- Skills ordered by `updated_at DESC` so newest lessons appear first

### `analyze_conversation(lead, inbound_conv, outbound_conv, tenant_id, db)`

Fired on background thread after Ava sends response. Extracts learnings and saves to both tables.

**Signature:** `(Lead, Conversation (inbound), Conversation (outbound), tenant_id, db_session) -> None`

**Execution:** Runs entirely in try/except. Any failure is logged and silently ignored — never impacts the message flow.

**Analysis prompt structure:**
1. Lead context block (name, company, stage, channel)
2. The lead's message (between `---` delimiters)
3. Ava's response (between `---` delimiters)
4. Previous context summary
5. JSON schema showing all extractable fields with pipe-separated values

**LLM config:** `call_llm(messages, temperature=0.3)` — low temperature for consistency.

**Post-processing:**
- Strips \`\`\`json ... \`\`\` code blocks from response
- Parses JSON
- Saves each insight as AvaInsight row
- For each skill_to_update: checks if skill exists (same category+key) → updates or creates
- If should_escalate: creates ActionItem with type="escalate" and ref_type="lead"

### Skills Injection in Ava's Prompt

The prompt template has a `{skills_context}` placeholder added after the Lead Context section and before Previous Conversation:

```
## What Ava Has Learned From Past Conversations
{skills_context}
```

The `.format()` call in `_handle_inbound_whatsapp` was updated to include:
```python
skills_context = load_skills_for_prompt(tenant_id, db, lead=lead)
prompt = AVA_AUTO_SYSTEM_PROMPT.format(
    ...,
    skills_context=skills_context,
    ...
)
```

## API Endpoints

### `GET /api/insights`
Returns raw AvaInsight records. Supports:
- `limit` (default 50)
- `offset` (default 0)
- `insight_type` (filter by type)
- `lead_id` (filter by lead)

### `GET /api/insights/stats`
Aggregated stats:
- `by_type`: count of records per insight_type
- `top_objections`: objection keys ranked by frequency (excludes "none")
- `sentiment_distribution`: sentiment keys with counts
- `total_skills`: count of Skill rows for this tenant
- `total_insights`: count of AvaInsight rows

### `GET /api/insights/learnings`
Human-readable learning summary:
- `categories`: skills grouped by category with key, value (truncated 200 chars), learned_at
- `total`: total skill count
- `tier`: "early" (<5), "learning" (5-20), "experienced" (>20)

## Background Thread Pattern

```python
import threading as _ta
_t = _ta.Thread(
    target=analyze_conversation,
    args=(lead, conv, outbound, tenant_id, init_db()),
    daemon=True
)
_t.start()
```

Key: `init_db()` is called in the main thread (as argument construction) so the DB session is created before the thread starts. This avoids import issues inside the thread.

## Execution Flow (Trace)

```
WhatsApp keepalive loop (async, dedicated event loop thread)
  └→ Detects unread chat → extracts phone + message
      └→ run_in_executor(None, on_inbound_message, phone, name, msg)
          └→ _handle_inbound_whatsapp(phone, name, message) [THREAD POOL]
              ├─ init_db() → db session
              ├─ Find lead by phone
              ├─ Log inbound Conversation
              ├─ If lead assigned to Ava:
              │   ├─ Load recent conversations
              │   ├─ load_skills_for_prompt() → skills context string
              │   ├─ Build prompt with skills_context
              │   ├─ call_llm() → Ava reply           ← main latency: 1-3s
              │   ├─ wa.send_message_sync()            ← dispatches to WA loop
              │   ├─ Log outbound Conversation
              │   └─ Thread(target=analyze_conversation).start()  ← fires background
              └─ db.close()
```

## Design Principles (From Greg)

1. **Real-time learning** — analysis fires immediately, not batch/nightly
2. **Channel-agnostic** — same function for WhatsApp, email, voice
3. **Multi-language** — analysis handles Hinglish, Hindi, English mixed
4. **Don't modify user communications** — analysis data lives separately from Conversation records
5. **Accumulate, improve** — Ava should be measurably better at Lead 40 than Lead 1
6. **The Karpathy flywheel** — action → observe → extract → update → next action is better

## What Not To Do

- ❌ Don't run analysis inline on the thread pool — fire a background thread
- ❌ Don't modify the Conversation model with analysis output
- ❌ Don't skip skill deduplication — always upsert by category+key
- ❌ Don't use `f"""..."""` with literal `"""` inside — use `---` delimiters instead
- ❌ Don't hardcode the analysis prompt as a module-level constant — it needs dynamic data
- ❌ Don't let analysis failures bubble up — catch everything and log
