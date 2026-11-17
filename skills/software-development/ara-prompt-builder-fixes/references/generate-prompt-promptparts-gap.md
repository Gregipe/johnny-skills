# Generate-Prompt PromptParts Regeneration Gap

## The Bug

`POST /api/cadence/generate-prompt` (server.py ~line 3145) was doing:

```python
existing.config["promptParts"] = existing.config.get("promptParts", {})
```

This kept **existing (stale) promptParts** unchanged — only `systemPrompt` was updated with the newly generated sections. The prompt builder tabs continued showing old/truncated section content because they read from `promptParts`.

## How It Happened

1. `publish-global` (called from main page's old `publishCadence()`) overwrote all templates' `promptParts` with cold's stale data
2. When `generate-prompt` ran later, it generated a fresh 14,935-char `systemPrompt` but line 3145 kept the contaminated `promptParts`
3. The prompt builder's Final tab showed the correct prompt (from `systemPrompt`), but individual tabs showed truncated content (from `promptParts`)

## The Fix

**Option A (in-script, used in practice):** Run a standalone script that parses the `systemPrompt` (split by `---`) and maps each section to the correct `promptParts` field:

```python
import sqlite3, json

conn = sqlite3.connect('ara.db')
cur = conn.cursor()

for tid in ['cold', 'inbound', 'nurture']:
    c = json.loads(cur.execute("...").fetchone()[0])
    sp = c.get('systemPrompt', '')
    sections = sp.split('---')
    
    pp = {}
    if len(sections) > 1:
        pp['brandPersonality'] = {
            'phrases': sections[1].strip(),
            'personality': sections[1].strip()[:200],
            'tone': 'sophisticated', 'style': 'witty', 'vocabulary': 'direct', 'nonos': []
        }
    if len(sections) > 2:
        pp['sectorSpecific'] = {'valueProps': sections[2].strip(), ...}
    if len(sections) > 3:
        pp['security'] = {'injectionPrevention': sections[3].strip(), ...}
    if len(sections) > 4:
        pp['channelSpecific'] = {
            'whatsapp': {'structure': sections[4].strip(), ...},
            'email': {'body': sections[5].strip(), ...},
            'call': {'intro': sections[6].strip(), ...}
        }
    
    c['promptParts'] = pp
    cur.execute("UPDATE cadence_configs SET config=? WHERE tenant_id=? AND template_id=?", 
                (json.dumps(c), tid_id, tid))
conn.commit()
```

**Option B (preferred — in endpoint):** Add a `_build_prompt_parts_from_sections()` helper in `server.py` that runs inside `generate_system_prompt()` to regenerate promptParts from the freshly built sections before saving. This was attempted with a patch but not completed in this session.

The section-to-promptParts mapping:
| Index | Section | promptParts field |
|-------|---------|-------------------|
| 0 | Objective | (no field — only in systemPrompt) |
| 1 | Brand Voice | brandPersonality.phrases |
| 2 | Sector Context | sectorSpecific.valueProps |
| 3 | Security & Guardrails | security.injectionPrevention |
| 4 | WhatsApp | channelSpecific.whatsapp.structure |
| 5 | Email | channelSpecific.email.body |
| 6 | Call | channelSpecific.call.intro |
| 7+ | (other) | (fallback from systemPrompt in compilePbPrompt) |

## Prevention

Every time `systemPrompt` is regenerated, `promptParts` must also be rebuilt. The `compilePbPrompt()` function has a fallback that reads from `t.systemPrompt` for sections without textareas, but the primary 6 textareas (Brand, Sector, Security, WhatsApp, Email, Call) depend on `promptParts` being current.

## Related

- `compilePbPrompt()` fallback (skill: lazy-loaded tabs section)
- `fix_promptparts.py` (script in session history)
- `POST /api/cadence/generate-prompt` endpoint (server.py ~line 3144)
