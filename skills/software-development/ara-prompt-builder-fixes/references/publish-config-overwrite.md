# Publish Endpoint Config Overwrite Bug (June 2026)

## Symptom

After publishing the cold cadence template, the page renders correctly but on next open:
- Final tab shows empty / placeholder
- Individual tab fields are populated (from promptParts)
- Hard refresh fixes it

**DB check reveals:** The cold template's config had been **replaced** with just `{"promptParts": {...}}` — missing `systemPrompt`, `id`, `title`, `desc`, `objective`, `rules`, `steps`, `conditions`, `stopConditions`, `brandVoice`, and all other metadata.

## Root Cause

**`/api/cadence/publish` endpoint** (`server.py` ~line 2090) was doing:

```python
if existing:
    existing.config = template          # ❌ REPLACES entire config dict
```

This caused TWO separate data-loss bugs, depending on which caller triggered it:

### Bug 1: Prompt Builder Publish (June 2026 v1 fix — specific fields)

The prompt builder sends `template: { promptParts: parts, systemPrompt: compiled }` — only 2 keys. `existing.config = template` strips everything else. The v1 fix saved only these 2 specific fields:

```python
merged = dict(existing.config or {})
merged["promptParts"] = template.get("promptParts", ...)
if template.get("systemPrompt"):
    merged["systemPrompt"] = template["systemPrompt"]
existing.config = merged
```

**Problem:** This only handles the prompt builder's partial template. It breaks when the same endpoint is called from the main Outreach Central page.

### Bug 2: Main Page Publish (June 2026 v2 fix — full merge loop)

The main page's `publishCadence()` function (`cadence_template.py` line 1598) sends:
```javascript
body: JSON.stringify({ template_id: t.id, template: t })  
// t = getTemplate() — the FULL template object with steps, conditions, etc.
```

The v1 fix only saved `promptParts`, `systemPrompt`, and `title` — all other keys from `t` (`steps`, `conditions`, `stopConditions`, `brandVoice`, `objective`, `rules`, etc.) were **silently dropped**. The user's step configuration (WhatsApp 10×/1h, Email 1×/1h, Call removed) disappeared on publish.

## Fix (v2 — Full Merge Loop)

Changed publish endpoint to merge ALL template fields into existing config:

```python
if existing:
    merged = dict(existing.config or {})
    for k, v in template.items():
        if v is not None and v != '':
            merged[k] = v
    existing.config = merged
    existing.updated_at = utcnow()
```

This handles both callers correctly:
- **Main page** sends full template → all keys (steps, conditions, etc.) are merged in
- **Prompt builder** sends partial template → only promptParts/systemPrompt are merged in, everything else preserved

## Verify publish-global

`publish-global` already uses merge:
```python
cfg = dict(existing.config)
cfg["promptParts"] = prompt_parts
cfg["systemPrompt"] = compiled_prompt
existing.config = cfg
```

Starts with existing config then updates specific fields. Safe.

## Damage Recovery

After cold template was corrupted (only `promptParts` key remained), restore from inbound's structure:

```python
inbound = db.query(CadenceConfig).filter(... template_id='inbound').first()
fixed = {k: v for k, v in inbound.config.items()
         if k not in ('promptParts', 'systemPrompt', 'previous_systemPrompt')}
fixed['promptParts'] = cold.config['promptParts']
fixed['systemPrompt'] = inbound.config['systemPrompt']
```

After restoration, regenerate prompts for all templates via `POST /api/cadence/generate-prompt` with the correct tenant_id.

Also check that the `publish-global` cross-contamination didn't overwrite inbound/nurture's prompts with cold's stale data. If so, regenerate.

## Lesson

Every endpoint that writes to `CadenceConfig.config` must **merge** — never replace. This JSON blob contains both user content AND infrastructure fields. The `for k, v in template.items()` pattern is the robust approach because it adapts to whatever the caller sends without hardcoding field names.

Two callers hit the same endpoint with different payloads — both must work.

## Detection

After publish, compare key counts across all 3 templates. If cold has fewer keys than inbound/nurture, the publish endpoint is stripping data. Also verify step values persisted by checking the DB directly:
```python
c = json.loads(cur.execute("SELECT config FROM cadence_configs WHERE ...").fetchone()[0])
for s in c.get('steps', []):
    print(s['channel'], s.get('repeat_count'), 'x', s.get('interval_hours'), 'h')
```
