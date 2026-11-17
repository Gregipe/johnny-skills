# Pipeline Injection Over-Generation (June 17, 2026)

## The Problem

The system prompt injects the full pipeline (leads + deals) into every coaching turn. This primes the LLM to take initiative on pipeline items — even when the user only asked for a single, specific action. The LLM treats the pipeline context as a TODO list rather than situational awareness.

## Real Incident

**Date:** June 17, 2026, 9:29 AM IST

**Sequence:**
1. Greg: "send a whatsApp message to Jimmie Tete and tell him that i will send the infosec today itself."
2. Ava proposed TWO tool calls: `create_deal` (Shriram Finance / Ajay Fageria) + `send_whatsapp` (Jimmie Tete)
3. Greg: "Ignore the shriram finance deal for now and just handle the whatsApp to Jimmie please."
4. Classifier returned `reject` → both actions cancelled → WhatsApp never sent.

## Why Shriram Finance?

The pipeline injection at lines 6431-6446 in server.py injects ALL non-archived leads and ALL deals:

```python
leads = db.query(Lead).filter(Lead.tenant_id == tenant_id, Lead.stage != "archived").all()
deals = db.query(Deal).filter(Lead.tenant_id == tenant_id).all()
```

Shriram Finance was a deal at `stage: "new"` with contact `Ajay Fageria`. The LLM saw a fresh deal sitting in the pipeline and decided to propose creating it alongside the requested WhatsApp.

Two messages earlier, Greg had asked "What skills do you have?" and Ava listed "Create and manage leads, deals, and contacts" — further priming the LLM to take pipeline initiative.

## Why This Is Different From Conversation History Poisoning

| Pattern | Source of contamination | Effect |
|---------|------------------------|--------|
| Conversation history poisoning | Ava's own hallucinated past responses | Self-reinforcing — each hallucination primes the next |
| Pipeline injection over-generation | Live DB data (leads/deals) injected every turn | LLM treats awareness as TODO list — proposes unrequested actions |

The first is a feedback loop. The second is a context design issue: the pipeline is injected for situational awareness but the LLM interprets it as a to-do list.

## Mitigations

### Anti-pattern (added to guardrails SKILL.md):
```
Single-action request → multi-action proposal
Never bundle unsolicited pipeline actions with a single-task request.
If Greg asks for one thing, do that one thing.
The pipeline data in your context is for awareness, not a TODO list.
```

### System prompt hardening:
The pipeline injection section should include an explicit instruction:
```
The pipeline data below is for your SITUATIONAL AWARENESS only.
Do NOT propose actions on these items unless Greg explicitly asks about them.
```

### Code-level guard (future):
Before creating a pending ActionItem, compare tool count to user request scope. If the user's message contains exactly one action verb but the LLM proposed >1 tool calls, flag it and re-evaluate.

## Related

- `ara-agent-tools` skill — Multi-tool confirmation gap (companion bug — over-generation + cannot partial-confirm = double failure)
- `ara-ava-guardrails` skill — Anti-Patterns list, Conversation History Poisoning reference
- `ara-agent-chat-debugging` skill — Layer 3 (context injection)
