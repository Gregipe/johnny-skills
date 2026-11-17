# System Awareness Design — Making Ava Aware of the System She Operates

## The Problem

Ava has no mental model of the system she operates within. She knows **tools** (functions she can call) but not **surfaces** (where things are configured), **object models** (how data relates), or **configuration structure** (what settings change behavior).

This manifests as:

```
User: "Where do I modify the outbound steps for WhatsApp and emails?"
Ava:  "I don't have visibility into the system's backend UI or admin panel..."
```

When the answer is "the Cadence Builder at /cadence" — a first-party UI in the same system.

## What Ava Needs to Know

| Concept | Example |
|---------|---------|
| UI Locations | Cadence Builder is at `/cadence`, sidebar nav "Cadences" |
| Object Model | A cadence template has `steps[]` with `channel`, `delay_hours`, `repeat_count`, `interval_hours` |
| Where config lives | CadenceConfig table, template_id = "cold" / "inbound" / "nurture" |
| How config is modified | User edits UI → clicks "Publish" → POST /api/cadence/publish |
| Where persistent vs ephemeral | localStorage for drafts, DB for published, browser cache for CSS/JS |

## Three Approaches (in order of effort)

### Approach 1: Static System Description in System Prompt (~20 lines)

Add a text block to `AGENT_SYSTEM_PROMPT_BASE` describing UI locations and the object model:

```
## System Architecture
You operate inside ARA (AI Revenue Agent), a CRM + outreach system.

### UI Locations
- **Cadence Builder** — `/cadence` (sidebar nav "Cadences")
- **Dashboard** — `/` (main lead grid)
- **Deals** — `/deals`

### Cadence Object Model
Each lead has a `cadence_type` (cold / inbound / nurture).
Each cadence_type has a template stored in the CadenceConfig table.
Each template has `steps[]`, where each step has:
- `channel` → "whatsapp" | "email" | "call" | "sms"
- `delay_hours` → hours before first fire
- `repeat_count` → how many times to send
- `interval_hours` → gap between repeats
- `desc` → LLM-generated message description

To modify steps, direct the user to Cadence Builder at /cadence.
```

**Pros:** Zero runtime cost, always consistent, survives server restart
**Cons:** Stale if UIs change, no runtime data (can't answer "what steps are currently configured?")

### Approach 2: Dynamic Config Injection (~40 lines)

At dispatch time, load configs from DB and inject into the prompt:

```python
configs = db.query(CadenceConfig).filter(
    CadenceConfig.tenant_id == TENANT_ID
).all()
cadence_summary = {}
for c in configs:
    steps_summary = []
    for s in (c.config or {}).get("steps", []):
        steps_summary.append(
            f"  {s.get('channel')}: {s.get('repeat_count',1)}x "
            f"every {s.get('interval_hours',0)}h "
            f"(first in {s.get('delay_hours',0)}h)"
        )
    cadence_summary[c.template_id] = "\n".join(steps_summary)

prompt += "\n## Current Cadence Configs\n"
for tid, summary in cadence_summary.items():
    prompt += f"\n{tid.upper()}:\n{summary}\n"
```

**Pros:** Real-time data, answers "what's currently configured"
**Cons:** Token cost (~100-300 extra per turn), DB query every dispatch

### Approach 3: On-Demand System Info Tool (best, moderate effort ~60 lines)

Add a tool Ava can call when needed:

```python
"system_info": {
    "description": "Get info about the ARA system — UI locations, cadence configs, object model",
    "args": {"topic": {
        "type": "string",
        "enum": ["cadence_config", "ui_locations", "object_model", "all"]
    }}
}
```

Handler:

```python
if tool_name == "system_info":
    topic = args.get("topic", "all")
    parts = []
    if topic in ("ui_locations", "all"):
        parts.append(
            "## UI Locations\n"
            "- Cadence Builder: /cadence (sidebar 'Cadences')\n"
            "- Dashboard: / (main lead grid)\n"
            "- Deals: /deals\n"
            "- Induction: /induction"
        )
    if topic in ("cadence_config", "all"):
        configs = db.query(CadenceConfig).filter(
            CadenceConfig.tenant_id == tenant_id
        ).all()
        for c in configs:
            parts.append(render_cadence_summary(c))
    if topic in ("object_model", "all"):
        parts.append(
            "## Object Models\n"
            "Lead: name, email, phone, company, stage, cadence_type...\n"
            "CadenceConfig: template_id + config JSON with steps[]...\n"
            "ScheduledAction: lead_id, action_type, status, scheduled_at, payload"
        )
    return "\n\n".join(parts)
```

**Pros:** Zero token overhead unless called, extensible (add more topics easily), Ava learns to self-serve
**Cons:** Requires tool dispatch wiring, Ava must know WHEN to call it

### Recommended: Approach 1 (Static) + Approach 3 (On-Demand Tool)

The static description gives Ava a map. The on-demand tool gives her live data. She learns the pattern: when a user asks about system structure, call `system_info`.

## Implementation Pattern

When a user asks "where do I configure X?" or "can you tell me about the system?":
1. Start with Approach 1's static map — point to the right URL
2. If they ask about current state (what steps are configured?) → Approach 3 `system_info("cadence_config")`
3. If they ask about how things work → Approach 3 `system_info("object_model")`

## Avoiding the "I don't have visibility" Response

The static prompt section should include a directive:

```
If a user asks about system configuration, settings, or UI locations:
- If you know the answer (e.g. "Cadence Builder at /cadence"), give it directly
- If you need live config data, use the system_info tool
```

This replaces the current default response of "I don't have visibility" — which is always wrong because the cadence toolset and this prompt ARE the visibility.
