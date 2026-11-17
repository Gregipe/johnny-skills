# Cadence Template Restoration Procedure

When a cadence template is wiped (steps, conditions, brandVoice, or systemPrompt lost), use this recovery procedure.

## Symptoms

- Cadence steps show as empty in the UI
- Ava reports "cold cadence hasn't been set up" despite the user having configured 8 WhatsApp + 12 email steps
- `sqlite3 ara.db "SELECT json_extract(config, '$.steps') FROM cadence_configs WHERE template_id='cold';"` returns `null` or `[]`
- The systemPrompt field is empty: `SELECT length(coalesce(json_extract(config, '$.systemPrompt'), '')) FROM cadence_configs;`

## Common Causes

1. **Publish button with incomplete localStorage data** — The main Publish Cadence button POSTs `{template_id, template}` which REPLACES the entire config JSON in the DB. If the browser's localStorage had partial data (e.g., `steps` was absent from the saved payload because of a DOM bug), the DB gets wiped.
2. **Prompt Builder's `template_id='global'` bug** — Save & Close attempts to publish with `template_id: 'global'` which the backend rejects (only accepts `cold/inbound/nurture`). The prompt stays in localStorage but the DB never gets `systemPrompt`. Fixed by `/api/cadence/publish-global` endpoint.
3. **Test/development wipe** — Direct edits to the DB or API calls that replace the config JSON without preserving existing fields.

## Recovery Procedure

### Step 1: Assess the damage

```bash
cd /Users/greg/ara
sqlite3 ara.db "
SELECT template_id,
  json_extract(config, '$.steps') IS NOT NULL AS has_steps,
  length(coalesce(json_extract(config, '$.systemPrompt'), '')) AS sysprompt_len,
  json_extract(config, '$.title') AS title
FROM cadence_configs;
"
```

### Step 2: Reconstruct steps

If steps are missing, you need to reconstruct them with the correct schema. Each step needs:

```json
{
  "channel": "whatsapp|email|call",
  "delay_hours": 0,
  "repeat_count": 1,
  "interval_hours": 0,
  "desc": "Rich NL prompt describing the message purpose, tone, angle, CTA"
}
```

**Timing fields:**
| Field | Description |
|-------|-------------|
| `delay_hours` | First fire offset from lead creation (hours) |
| `repeat_count` | How many times to send (default 1) |
| `interval_hours` | Gap between repeats (default 0) |

**Cold template default (8 WhatsApp + 12 email at 1-hour intervals, no delay):**

```json
[
  {"channel": "whatsapp", "delay_hours": 0, "repeat_count": 8, "interval_hours": 1, "desc": "Cold WhatsApp sequence. Reference the screening bottleneck — how voice AI makes volume screening the hidden bottleneck. Lead with a compliment about their growth. Warm, direct, 2-3 lines. CTA: '2 minutes to see if it fits?'"},
  {"channel": "email", "delay_hours": 0, "repeat_count": 12, "interval_hours": 1, "desc": "Cold email sequence x12. Reference screening bottleneck, 3-4 paragraphs. Subject should be short and evoke curiosity. Professional sign-off with calendar link."}
]
```

*Note: The `desc` fields above are minimal. For better results, replace with richer instructions that reference the system prompt's content.*

### Step 3: Reconstruct conditions

Conditions control when email/call steps fire (WhatsApp is NOT subject to working hours):

```json
{
  "workingHours": true,
  "weekdays": true,
  "saturday": false,
  "sunday": false
}
```

**Resolution order:**
1. If `saturday`/`sunday` explicitly set → use that value
2. If NOT set → fall back to `weekdays` (true=block weekends, false/absent=allow all)

### Step 4: Reconstruct full config

Use Python to write the complete config to the DB:

```python
import json, sqlite3
db = sqlite3.connect('ara.db')

config = {
    "title": "Cold Outreach",
    "steps": [...],  # From step 2
    "conditions": {...},  # From step 3
    "stopConditions": [],
    "brandVoice": {
        "tone": "consultative",
        "style": "direct",
        "language": "english",
        "formality": 3,
        "nonos": [],
        "phrases": "",
        "personality": ""
    },
    "systemPrompt": "",  # Populated by Prompt Builder
    "promptParts": {}     # Populated by Prompt Builder
}

db.execute(
    "UPDATE cadence_configs SET config = ? WHERE template_id = ?",
    (json.dumps(config), "cold")
)
db.commit()
```

### Step 5: Push the system prompt

If the system prompt was saved in the Prompt Builder UI before the wipe, it's still in `localStorage`. Open the browser to `/cadence`, select the Cold template, click "✎ Open Builder", verify the prompt parts are intact, and click "Save & Close" to publish to the server.

If the prompt is lost entirely, you'll need to rebuild it from:
- Brand voice settings (`brandVoice`)
- Sector context (Hunar.ai value props, case studies)
- Security guardrails (English-only, injection protection)
- Channel guides (WhatsApp short/punchy, email subject+body, call talking points)

See `references/prompt-builder-vs-cadence-boundaries.md` for the content-vs-behavior design boundary.

### Step 6: Verify

```bash
sqlite3 ara.db "
SELECT template_id,
  json_extract(config, '$.steps') IS NOT NULL AS has_steps,
  json_extract(config, '$.conditions') IS NOT NULL AS has_conditions,
  length(coalesce(json_extract(config, '$.systemPrompt'), '')) AS sysprompt_len
FROM cadence_configs;
"
```

Expected: `has_steps=1`, `has_conditions=1`, `sysprompt_len > 0` for all templates.

### Step 7: Propagate to all templates

After restoring one template, fan out the Prompt Builder data to all three:

```python
# Get the prompt from the restored template
row = db.execute("""
  SELECT json_extract(config, '$.systemPrompt'),
         json_extract(config, '$.promptParts')
  FROM cadence_configs WHERE template_id='cold'
""").fetchone()
sysprompt = row[0]
parts = json.loads(row[1]) if row[1] else {}

# Use the publish-global endpoint (avoids template_id='global' rejection)
import requests
r = requests.post('http://localhost:8766/api/cadence/publish-global', json={
    'promptParts': parts,
    'compiled_prompt': sysprompt
})
print(r.json())  # Expected: {'status': 'ok', 'updated': ['cold', 'inbound', 'nurture']}
```

## Prevention

The `publish-global` fan-out in `publishCadence()` (added June 2026) prevents future wipe scenarios: publishing a single template's steps now also re-publishes the global prompt to all three templates in the same click.
