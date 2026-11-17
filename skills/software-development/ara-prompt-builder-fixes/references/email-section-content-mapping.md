# Email Section: Content Mapping & Architecture

## Where Email Content Lives

The email section exists in THREE locations, each serving a different purpose:

| Location | Format | Size | Source of Truth? | Purpose |
|----------|--------|------|-----------------|---------|
| `prompt_templates.json["Email"]` | Full section: subject lines + body + sequencing | **8,631 chars** | ✅ **Primary source** | `generate-prompt` reads from here to build systemPrompt |
| DB `promptParts.channelSpecific.email.body` | Body + sequencing ONLY (NO subject lines) | **6,973 chars** | ✅ Prompt builder Body tab | Populates `pe_emailBody` textarea on open |
| DB `promptParts.channelSpecific.email.subject` | Subject line prompt only | **1,656 chars** | ✅ Prompt builder Subject Lines tab | Populates `pe_emailSubject` textarea on open |
| DB `config.systemPrompt` Email section | Part of **21,166-char** full prompt | 8,631+ chars | ✅ LLM reads from here | Used by preview endpoint and message generation |

## Email Section Structure (June 2026 — after user's rewrite)

```
## Email
Channel characteristics...                                    ← fixed intro (inherited)

### Subject Lines                                              ← 1,656 chars
Full subject line generation prompt (user's prompt)
5 categories: Curiosity, Company Specific, Industry Trigger, Executive-to-Executive, Quirky

### Body & Sequence Rules                                      ← ~5,800 chars
You are a world-class enterprise SDR writing cold outbound emails.
Objective: generate curiosity, establish credibility, start a conversation.

---
EMAIL 1 — Establish Relevance (sharp operational challenge, solution, proof block)
EMAIL 2 — Reinforce Credibility (keep short, measurable outcomes)
EMAIL 3 — Lead with Proof (mini case study: Customer → Problem → Approach → Results)
EMAIL 4 — Pattern Interrupt (humour, self-awareness, humanity)
EMAIL 5 — Breakup Email (gentle loss aversion, response options)
---

### Cross-Channel Continuity                                   ← inherited
WhatsApp should not repeat email's recent angle
```

**⚠️ The `---` separator issue:** The EMAIL 1-5 sections use `---` as visual dividers. When `generate-prompt` splits the system prompt by `---`, these create false section boundaries. All content IS present, just fragmented across ~9 sections instead of 1. No functional impact on LLM output.

## Inputs Available to the LLM

The email body prompt specifies these inputs for message generation:
- Company Name: {company_name}
- Prospect Name: {prospect_name}
- Title: {title}
- Industry: {industry}
- Product Name: {product_name}
- Customer References: {customer_references}
- Case Studies: {case_studies}
- Calendar Link: {calendar_link}
- Case Study Link: {case_study_link}
- Company Research: {company_research}
- Industry Research: {industry_research}
- Proof Metrics: {proof_metrics}

## Update Flow (How to Change Email Content)

When the user provides new email content (subject lines, body templates, signature):

### Step 1: Update prompt_templates.json
```python
# Read the current file
import json
with open('/Users/greg/ara/prompt_templates.json') as f:
    templates = json.load(f)

# Edit the Email section
email = templates["Email"]
# ... make edits ...

# Write back
with open('/Users/greg/ara/prompt_templates.json', 'w') as f:
    json.dump(templates, f, indent=2, ensure_ascii=False)
```

### Step 2: Restart server
The server reads `prompt_templates.json` at startup. A restart is required to pick up changes.

### Step 3: Regenerate system prompt
```bash
curl -s -X POST http://localhost:8766/api/cadence/generate-prompt \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"3e736242"}'
```
This rebuilds `systemPrompt` from the updated templates.
### Step 4: Update promptParts in DB

`generate-prompt` does NOT update `promptParts` — so the prompt builder tabs still show old content. Update promptParts separately.

**Critical separation rule:** `prompt_templates.json["Email"]` contains BOTH subject lines (for the system prompt, used by the LLM) AND body/sequencing. But `promptParts.email.body` should contain ONLY the body + sequencing content — the subject lines are stored separately in `promptParts.email.subject` and displayed in their own tab.

When syncing after a template update:

```python
import sqlite3, json

conn = sqlite3.connect('/Users/greg/ara/ara.db')
cur = conn.cursor()

with open('/Users/greg/ara/prompt_templates.json') as f:
    templates = json.load(f)

new_email = templates["Email"]
# Extract just the body/sequencing part (after ### Body & Sequence Rules)
body_marker = "### Body \u0026 Sequence Rules"
subject_end = new_email.find(body_marker)
if subject_end > 0:
    body_only = new_email[subject_end:].strip()
else:
    body_only = new_email  # fallback: use entire section

for tid in ['cold', 'inbound', 'nurture']:
    # ... update promptParts.email.body = body_only
    # ... keep promptParts.email.subject as-is (it already has subject content)
```

### Step 5: Hard refresh the browser
`Cmd+Shift+R` to clear localStorage cache and load fresh data.

## Subject Line Prompt (Current Content)

The subject line prompt was written by Greg and stored June 2026. It instructs the LLM to generate 10 subject line options across 5 categories:
- Curiosity (examples: "One thing I didn't expect", "Curious, {first_name}")
- Company Specific (examples: "Question about {company_name}")
- Industry Trigger (examples: "The hiring market is changing")
- Executive-to-Executive (examples: "Wanted your take")
- Quirky (examples: "This wasn't on my bingo card")

Rules: Max 6 words, avoid "meeting/demo/solution/platform/AI/sales/pitch/opportunity", no exclamation marks, natural personalization only.

## How compilePbPrompt Handles Email

In `prompt_builder_template.py`'s `compilePbPrompt()`:

1. Reads `pe_emailSubject` DOM textarea → prepends as "## Email — Subject Lines" section
2. Reads `pe_emailBody` DOM textarea → uses as email body section
3. If DOM fields are empty (lazy-loaded tab not visited), falls back to `promptParts.channelSpecific.email.subject` / `.body`
4. If both DOM and promptParts are empty, falls back to extracting from `t.systemPrompt` by heading match

The Final tab output uses `---` separators between sections. Subject lines come BEFORE the body in the concatenated output.
