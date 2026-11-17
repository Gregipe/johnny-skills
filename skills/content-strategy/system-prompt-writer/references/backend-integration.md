# Backend Integration — Auto Prompt Generation

## Endpoint

`POST /api/cadence/generate-prompt`

Called by Ava at induction completion to auto-generate the full 13-section system prompt.

### Request

```json
{ "tenant_id": "3e736242" }
```

### Response

```json
{
  "status": "ok",
  "tenant_id": "3e736242",
  "tenant_name": "Hunar.ai",
  "sections": 13,
  "section_titles": ["Objective", "Brand Voice", "Sector Context", ...],
  "prompt": "## Objective\n\nHunar.ai's outbound...",
  "prompt_length": 14935,
  "updated": ["cold", "inbound", "nurture"],
  "note": "Hard refresh (Cmd+Shift+R) the cadence page to see the new prompt"
}
```

- `section_titles` — Array of section heading names, used by the induction chat to display the structure
- `prompt` — The full compiled prompt text (for immediate display, no need to query DB again)

## What It Generates

### Inherited Sections (from `prompt_templates.json`)

10 sections that are the same for EVERY tenant:

| Section | Source | Customizable? |
|---------|--------|---------------|
| Brand Voice | Canonical style anchor | NEVER — same for all |
| Security & Guardrails | Canonical injection defense | Tags only |
| WhatsApp | Channel anatomy + sequence rules | Examples only |
| Email | Channel anatomy + sequence rules | Examples only |
| Call | Channel anatomy + tone rules | Examples only |
| Lead Context Awareness | Canonical adaptation rules | Never |
| FOMO & Curiosity | Canonical strategic tension | Never |
| Message Structure | Canonical CTA rules | Never |
| Sequence Evolution | Canonical touch progression | Never |
| Communication Rules | Canonical do/don't | Never |

### Per-Tenant Sections (from induction data)

3 sections built dynamically:

| Section | Data Source | Fields |
|---------|-------------|--------|
| Objective | Tenant name + industry | target_roles, ICP, tenant_name |
| Sector Context | Induction docs | capabilities, positioning, themes |
| Industry Contextualization | Tenant config segments | pain points per segment |

## prompt_templates.json Format

Stored at `/ara/prompt_templates.json`. Loaded at server startup:

```python
import json, pathlib
path = pathlib.Path(__file__).parent / "prompt_templates.json"
if path.exists():
    with open(path) as f:
        SYSTEM_PROMPT_SECTIONS_INHERITED = json.load(f)
```

Each key is the section heading (e.g. "Brand Voice"), value is the full markdown text.
Kept as JSON to avoid Python triple-quote escaping issues.

## localStorage Cache Issue

**This is the #1 source of "why isn't my prompt updating?" confusion.**

The cadence FE caches template data in `localStorage['ara_cadence_data']`. When the backend saves a new systemPrompt to the DB, the browser's localStorage still has the OLD data. The page continues serving the old prompt until:

1. User does a **hard refresh** (`Cmd+Shift+R`) — bypasses all cache
2. OR JavaScript clears it programmatically:
   ```javascript
   localStorage.removeItem('ara_cadence_data');
   ```

The `fetchFromServer()` async call in `cadence_template.py` (line 1157-1208) does eventually update the in-memory `TEMPLATES` object, but `compilePbPrompt()` may run before it completes.

**Fix in the induction flow:** After saving the prompt, also write the fresh data to localStorage:

```javascript
fetch('/api/cadence/config').then(r=>r.json())
  .then(d=>{localStorage.setItem('ara_cadence_data', JSON.stringify(d))})
```

Then tell the user to hard refresh.

## Where This Lives

| Component | File | Lines |
|-----------|------|-------|
| Route handler | `server.py` | `@app.post("/api/cadence/generate-prompt")` |
| Inherited sections | `prompt_templates.json` | Full JSON file |
| Induction auto-trigger | `server.py` | `POST /api/induction/{id}/chat` (after LLM response, ~line 3300) |
| Frontend compiler | `prompt_builder_template.py` | `compilePbPrompt()` (~line 970) |
