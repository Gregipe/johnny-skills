# ARA Document-to-Skills Implementation (May 2026)

## Session History

Built document → skills extraction for the ARA system, initially for the induction chat, then expanded to the main agent chat. Also built a Skills Dashboard with source provenance tracking.

## Key Files

| File | Purpose |
|------|---------|
| `server.py` | POST /api/induction/{tenant_id}/upload endpoint |
| `document_skills.py` | `extract_skills_from_document()` — LLM extraction logic |
| `induction_template.py` | Induction chat UI with 📎 button |
| `dashboard_template.py` | Main chat UI with 📎 button, Skills Dashboard CSS, detail overlay |
| `static/dashboard.js` | `renderLearnings()` rewrite with source badges, filters, search, detail panel |
| `database.py` | Skill model with `source` column |
| `induction_engine.py` | Sets `source="induction"` on induction-created skills |
| `extract_conversation_learnings.py` | Sets `source="conversation"` on conversation-created skills |

## The Extraction Prompt

The LLM prompt used in `document_skills.py` asks for one JSON object per line:

```
For each distinct piece of knowledge, output exactly one line of valid JSON:
{"category": "<category>", "key": "<short_snake_case_key>", "value": "<complete_sentence_value>"}

Categories:
- proposition: Value propositions, segment-specific claims, feature descriptions
- gtm_learnings: GTM strategies, channel insights, competitive intel
- guardrail: Pricing tiers, policy rules, prohibited actions, compliance info
- segment_signal: Segment-specific behavioral or preference signals
- messaging_win: Proven messaging patterns with response rates
- objection_pattern: Common objections and effective responses
- timing_pattern: Timing/preference patterns for outreach
```

## Source Tracking Migration

The `source` column was added to the `skills` table via raw SQLite:

```sql
ALTER TABLE skills ADD COLUMN source VARCHAR DEFAULT 'induction';
```

Backfill for existing entries (117 skills at migration time):
- `proposition`, `gtm_learnings`, `inbound`, `guardrail` categories → `induction`
- `objection_pattern`, `messaging_win`, `segment_signal`, `timing_pattern` → `conversation`
- Skills with document-specific key patterns → `document`

## Frontend: Full Source Filter Tabs

The Skills tab in the Learnings page now has source filter tabs plus a search bar that re-renders the skills list in-place without fetching from the server again (uses the cached `skills` array from the initial load).

## June 2026: Induction Prompt Sharpening

The induction chat prompt in `induction_engine.py` was sharpened to force knowledge-first questioning:

- **Module 0 (Account Setup)** added as the first module — captures admin name, email, WhatsApp, industry, language, personality, team structure BEFORE business discussion
- **Skip basics rule**: If pre-loaded skills exist from document/website crawl, Ava MUST start by summarizing what she knows, then probe deeper. Never ask "what do you do?" if the knowledge base already answers it
- **Module 1 with knowledge**: Scans pre-loaded proposition skills. If 10+ exist, goes directly to probing: "I see your segments are X, Y, Z — which has highest margin?" If <5 exist, falls back to discovery
- **First-uncovered-module tracking**: `next_idx` now finds the first uncovered module, not skip by `covered_count` (which counted non-consecutive completions)
- The induction chat URL: `http://46.224.132.99:8080/induction/chat/{tenant_id}` (port 8080 via Caddy proxy with basic auth)
- Simulator: `/tmp/induction_v2.html` — 32-industry dropdown, knowledge-aware questions, 5-module flow

## June 2026: Chunked Extraction & Anti-Hallucination

- **Chunked extraction** deployed in `document_skills.py`: documents split into 6K-char windows, each chunk labeled `filename (part N/M)`, LLM called per chunk, skills deduplicated by key (first occurrence wins)
- **Anti-hallucination 3-layer defense** implemented in `document_skills.py`:
  1. Prompt: "Do NOT invent, extrapolate, or guess. Leave empty rather than fabricate."
  2. Temperature = 0 (not 0.1)
  3. Verification gate: grep extracted skill value keywords against raw `text_content`, discard if zero matches
- **Root cause of hunar.ai pricing hallucination**: the extraction prompt's FORMAT EXAMPLE contained fake pricing tiers. The LLM copied the format example when the actual website had no pricing data. Fix: removed concrete examples from the prompt.

## June 2026: Notification & Voice Note Pipeline

- **Action reminder notifications** now always use the `action.title` as the message body, never `action.description`. Descriptions often contain raw voice note transcriptions that are incomprehensible out of context.
- **Quiet-hours gate**: `_check_action_notifications()` skips reminders between 10 PM and 7 AM IST to prevent midnight spam.
- **Voice note pipeline**: Greg sends WhatsApp voice notes → Ava transcribes → action items created with title = Ava's interpretation, description = raw transcription. WhatsApp sidecar doesn't store incoming messages in DB (`inbox_messages` has OUTBOUND only). Voice transcriptions only survive in `action_item.description`.
- **Backfill gap**: 11 pending action items had `due_at` set but `scheduled_action_id = NULL` — no WhatsApp reminders created. These were from the `channel: call` path (pre-June-2026 code didn't create ScheduledActions). Backfilled Jun 23 with immediate-fire for past-due items.

## What I'd Do Differently

1. **Add source column from the start** — It's a one-line migration but touches 5 files. Much cleaner to have it from day one.
2. **Skill card detail panel as a shared component** — The detail overlay is in `dashboard_template.py` as static HTML, not dynamically generated. Fine for now, but a shared render function would be cleaner for reuse.
3. **Store incoming WhatsApp messages in DB** — The sidecar only stores outbound messages. Voice note transcriptions vanish into `action_item.description`. Without inbound storage, debugging what Greg actually said requires forensic reconstruction from action item descriptions.
4. **Lead actions tab URL was wrong for months** — `loadActionsForLead()` called `/api/actions/{leadId}` but the endpoint is `/api/leads/{leadId}/actions`. The tab silently showed "No actions" — no error, no alert, just blank. Fixed v43.
