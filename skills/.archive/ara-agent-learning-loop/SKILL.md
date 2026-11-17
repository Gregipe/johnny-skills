---
name: ara-agent-learning-loop
category: software-development
description: Build a self-improving AI agent loop in ARA — extract learnings from every customer interaction and feed them back into the agent's knowledge base so it improves from Lead 1 → Lead 100. Covers the learning flywheel architecture, two-tier storage, channel-agnostic analysis, multi-language handling, background threading, and DUAL-INJECTION of skills into BOTH the coaching chat AND scheduled message generation paths.
---

# ARA Agent Learning Loop (Flywheel Architecture)

Build a self-improving AI agent that gets better with every conversation. The core loop:

```
Ava replies → Lead responds → ANALYSIS extracts learnings
                                  ↓
                          Updates Skills (active knowledge)
                          + Saves AvaInsight (journal)
                                  ↓
                          Next Lead → Skills injected into prompt
                          → Ava is smarter than last time
```

## Core Philosophy (Greg's Karpathy Reference)

Greg explicitly referenced Andrej Karpathy's "auto research" paradigm — the system must improve from Lead 1 → Lead 40 → Lead 100 through self-learning. This is NOT about passive data collection. It's a learning flywheel:

1. **Action** — Ava sends a message
2. **Observe** — Lead responds (or doesn't)
3. **Extract** — Analyze the exchange for lessons
4. **Update** — Write lessons to Ava's active knowledge base
5. **Apply** — Next interaction is informed by everything learned before

## Architecture

### Three Tiers of Knowledge

**Tier 1: Skills (`Skill` table)** — WHAT AVA KNOWS (active, read on every interaction)

- Categories: `objection_pattern`, `messaging_win`, `segment_signal`, `timing_pattern`, plus existing induction categories (`proposition`, `gtm_learnings`, `inbound`, `guardrail`)
- `source` column: tracks origin — `induction`, `document`, or `conversation`. Displayed as color-coded badges in the Skills Dashboard. Added via `ALTER TABLE skills ADD COLUMN source VARCHAR DEFAULT 'induction'`.
- Injected into Ava's system prompt via `load_skills_for_prompt()`
- Skills are **upserted** (not duplicated) — same `category`+`key` updates existing row
- This is the flywheel — every new skill makes the next response better

**Tier 2: AvaInsight (`ava_insights` table)** — THE JOURNAL (for dashboards later)

- One row per atomic insight extracted from a conversation
- Types: `sentiment`, `intent`, `objection`, `topic`, `segment_signal`, `decision_maker`, `language`, `comms_style`, `engagement`, `timing`
- `key`: normalized English label regardless of source language (pricing, interested-but-hesitant, founder, hinglish)
- `confidence`: 0.0-1.0
- Links back to `lead_id` + `conversation_id`

**Tier 3: Experience Metrics (computed)** — THE STORY

- How many leads handled? How many skills learned? Response rate trend?
- Computed from Skills + AvaInsight + Conversation data
- See `/api/insights/stats` and `/api/insights/learnings`

### Key Design Decisions

| Decision | Why |
|----------|-----|
| **Channel-agnostic** | Analysis function takes a `Conversation` object, works for WhatsApp, email, voice with zero changes |
| **Multi-language** | Analysis prompt explicitly handles Hinglish, Hindi, English, mixed — `language` insight captures what was detected |
| **Background thread** | Analysis fires on a `threading.Thread` (daemon) so it never blocks the WhatsApp response flow |
| **Don't touch Conversation model** | Analysis data lives purely in AvaInsight + Skill tables. No modifications to existing records |
| **Skill deduplication (upsert)** | `db.query(Skill).filter(category, key).first()` — if exists, update value; if not, create new |
| **Graceful failure** | Every LLM call wrapped in try/except. Analysis fails silently — WhatsApp reply is unaffected |

## Prerequisites

- ARA server running at `http://localhost:8766`
- `database.py` has `AvaInsight` model (see `references/ava-learning-loop-implementation.md` for schema)
- `Skill` model already exists with `category`, `key`, `value`, `updated_at` fields
- `Conversation` model exists for logging inbound/outbound messages

## Implementation Workflow

### Phase 1: Design & Research (This Is The Karpathy Step)

Before building a learning feature, Greg expects you to:

1. **Ask what the user actually wants** — "What does 'learning' mean here?" "What should improve?"
2. **Research the paradigm** — If Greg references a specific concept (Karpathy's auto research, data flywheels, etc.), find and understand it before proposing architecture. Use `web_search` / `browser_navigate` / `skill_view` as appropriate. (Note: SSL issues may prevent web search from some networks — if so, synthesize from what you know and present it honestly.)
3. **Rethink the approach** — Propose architecture, get feedback, iterate. Don't go straight to code.
4. **Impact analysis** — Trace the full execution flow (see Phase 2 below). What components touch what? Which threads? What fails gracefully? Present this before building.
5. **Only build after explicit approval** — Greg will say "yes" or "makes sense" before you write code.

### Phase 2: Impact Analysis (Mandatory Before Code)

Trace the full execution path of the system BEFORE writing any code. Document:

- **Threading model**: Which thread runs what? (WhatsApp keepalive loop, thread pool executor, background daemon threads)
- **DB session management**: Who opens/closes sessions? Are they shared or independent?
- **API costs**: How many additional LLM calls does the analysis add? What size?
- **Failure modes**: What happens when analysis LLM fails? When DB is locked? When network is down?
- **Latency impact**: Does the analysis block the message response flow?

Example analysis from the Layer 1 implementation:

```
WhatsApp keepalive (async loop)
  └→ run_in_executor(thread_pool) → _handle_inbound_whatsapp()
       ├─ Open DB, find lead, log inbound
       ├─ Load Skills → build prompt → call DeepSeek → send reply → log outbound
       └─ Fire background thread → analyze_conversation()
              ├─ Own DB session (independent)
              ├─ Call DeepSeek (small prompt, ~500 tokens)
              ├─ Parse JSON → save AvaInsight rows
              ├─ Upsert Skill rows
              └─ Close DB → thread exits
```

### Phase 3: Build the Analysis Function

The `analyze_conversation()` function is the core. It:

1. **Builds an analysis prompt** with:
   - Lead context (name, company, stage, channel)
   - The lead's message
   - Ava's response
   - Previous conversation summary
   - JSON schema defining what to extract

2. **Calls the LLM** (`call_llm` from `induction_engine.py`, temperature 0.3 for consistency)

3. **Parses the JSON response** (handles ````json` code blocks)

4. **Creates AvaInsight rows** for every structured insight

5. **Upserts Skills** — checks for existing skill matching `category`+`key`, updates or creates

6. **Handles escalations** — creates `ActionItem` if `should_escalate` is true

#### JSON Schema for the Analysis Response

The LLM response must contain a JSON object with this structure (values are pipe-separated options):

```json
{
  "insights": [
    {"insight_type": "sentiment", "key": "interested|interested-but-hesitant|neutral|disengaged|negative", "value": "...", "confidence": 0.5},
    {"insight_type": "intent", "key": "high|medium|low|unknown", "value": "..."},
    {"insight_type": "objection", "key": "pricing|timing|competitor|not-priority|features|implementation|trust|none", "value": "...", "confidence": 0.5},
    {"insight_type": "segment_signal", "key": "founder|ops-head|hr|decision-maker|influencer|unknown", "value": "..."},
    {"insight_type": "decision_maker", "key": "yes|no|unclear", "value": "..."},
    {"insight_type": "language", "key": "english|hinglish|hindi|mixed", "value": "..."},
    {"insight_type": "comms_style", "key": "formal|casual|terse|detailed|technical", "value": "..."},
    {"insight_type": "engagement", "key": "engaged|non-committal|disengaged", "value": "..."},
    {"insight_type": "asked_questions", "key": "about_product|about_pricing|about_implementation|about_company|none", "value": "..."}
  ],
  "skills_to_update": [
    {"category": "objection_pattern|messaging_win|segment_signal|timing_pattern|proposition|gtm_learnings|guardrail", "key": "short_descriptive_key_no_spaces", "value": "Specific, actionable lesson for future conversations."}
  ],
  "should_escalate": false,
  "escalation_reason": ""
}
```

### Phase 4: Wire Skills into ALL Generation Paths (Dual Injection)

**CRITICAL: Skills must be injected into TWO separate generation paths, not just one.**

#### Path A: Coaching Chat (`agent_chat` / dashboard)

The chat system prompt already has `{skills_context}` via `AGENT_SYSTEM_PROMPT_BASE`:
```
INDUCTION KNOWLEDGE (what has been learned about {company}):
{skills_context}
```

Loaded at line ~4198 in `agent_chat()`:
```python
skills_context = "\n".join([
    f"- [{s.category}] {s.key}: {s.value[:200]}"
    for s in skills
]) if skills else "No induction knowledge yet."
```

#### Path B: Scheduled Message Generation (`_generate_step_message`)

**This path was MISSING and was discovered as a bug in May 2026.** The `_generate_step_message()` function (line ~2480 in server.py) builds its OWN system prompt from the template's compiled `systemPrompt` + `brandVoice` + `channel_guide`. It NEVER queried the `Skill` table. Result: when Ava sent scheduled cadence messages (emails, WhatsApp at fire time), she had ZERO knowledge of the tenant's induction data.

**The fix evolved in two phases:**

**Phase 1 (May 2026 — initial fix):** Inline skill query in `_execute_action()`. Queried all skills, grouped by category, built context string inline. Worked but duplicated the same logic across code paths.

**Phase 2 (May 2026 — centralized refactor):** All skill loading now goes through the single `load_skills_for_prompt(tenant_id, db, lead=lead)` function. This function:
- Reads skills from DB filtered by tenant
- **Filters by lead segment** — only shows skills relevant to this lead's segment (e.g., QSR skills for a Swiggy lead, logistics skills for an Acme lead)
- Groups by category for readability
- Marks the filter header: `[SKILLS FILTERED FOR <SEGMENT> LEAD]`

Called from BOTH generation paths:
```python
# Path A (agent chat)
skills_context = load_skills_for_prompt(TENANT_ID, db, lead=lead)

# Path B (scheduled message generation — _execute_action)
skills_context = load_skills_for_prompt(TENANT_ID, db, lead=lead)
```

The old inline code was removed — everything uses the centralized function now.

#### Segment-Aware Filtering

Segment definitions live in **tenant config** (`tenant.config["segments"]`), not hardcoded in code. Each tenant defines:
```json
{
  "segments": {
    "logistics": {
      "keywords": ["logistics", "delivery", "fleet", "warehouse"],
      "company_patterns": ["bluedart", "delhivery", "acme"],
      "description": "Logistics companies"
    },
    "qsr": {
      "keywords": ["qsr", "restaurant", "food delivery"],
      "company_patterns": ["swiggy", "zomato", "domino"],
      "description": "Quick service restaurants"
    }
  }
}
```

The `load_skills_for_prompt()` function reads segment keywords from the tenant's config and filters skills accordingly:
- General skills (no segment keyword) → shown to ALL segments
- Segment-specific skills → shown only to matching leads
- Skills mentioning OTHER segments → hidden from this lead

See also: `ara-tenant-specific-infrastructure` skill for the full tenant-configurable architecture pattern.

#### Why Dual Injection Matters

- Path A (chat) skills are visible when Greg talks to Ava: "what should I say to a BFSI lead?"
- Path B (message gen) skills are visible when Ava generates actual outbound: writing the email itself
- Without Path B, Ava composes generic emails even though she "knows" the tenant's business in the chat context
- The `_generate_step_message` function signature change needs BOTH Path A saved + Path B passed:
  ```python
  def _generate_step_message(step, lead, config, step_index, total_steps,
      repeat_idx=0, total_repeats=1, conv_summary="", skills_context=""):
  ```
- The `skills_context.strip()` guard ensures the old behavior is preserved if no caller passes skills

#### Verification

Check that skills are flowing into both paths:
- **Path A:** Send a chat message to Ava about a specific segment — she should reference induction data
- **Path B:** Generate a preview email via the preview endpoint or trigger a scheduled action — the output should reference segment-specific propositions, not generic copy

### Phase 5: Wire the Analysis Hook

After the outbound conversation is logged (Ava sent her reply and it was recorded):

```python
# Fire learning analysis on background thread
import threading as _ta
_t = _ta.Thread(
    target=analyze_conversation,
    args=(lead, inbound_conv, outbound_conv, tenant_id, init_db()),
    daemon=True
)
_t.start()
```

### Phase 6: API Endpoints for Data Access

| Endpoint | Purpose |
|----------|---------|
| `GET /api/insights` | Raw insight journal (paginated, filterable by type/lead) |
| `GET /api/insights/stats` | Aggregated: objections by frequency, sentiment distribution, total skills |
| `GET /api/insights/learnings` | Human-readable: what Ava knows, grouped by category, with experience tier |

### Phase 8: Coaching Capture (May 2026 — Built)

When Greg corrects Ava in chat, the feedback must be saved to skills **instantly** — not batched. This is the highest-signal learning because Greg explicitly tells Ava what to do differently.

#### Implementation

**File:** `coaching_capture.py`

**Detection in `agent_chat` endpoint:** After Ava responds, a background thread runs `check_and_capture(tenant_id, user_msg, response)`:

1. **Quick heuristic check** — Does Greg's message contain trigger phrases? `"next time"`, `"you should have"`, `"instead of"`, `"try this"`, `"remember"`, `"say this when"`, `"do this when"`
2. **If triggered → LLM extraction** — Small prompt (300 tokens) extracts structured fields:
   ```json
   {"is_coaching": true, "category": "objection|tone|messaging|process|compliance", "what_to_do": "full instruction", "context": "when BFSI lead asks about compliance", "segment": "bfsi", "channel": "all"}
   ```
3. **Save to skills table** — `INSERT OR REPLACE` with:
   - `category`: `coaching_<extracted_category>` (e.g. `coaching_objection`)
   - `key`: `coaching_<category>_<normalized_context>` (e.g. `coaching_objection_when_a_bfsi_lead_asks_about_compliance`)
   - `value`: Structured text with Context, Segment, Channel, Instruction fields

**Trigger phrases** (expandable list):
```
next time, you should have, instead of, try this, remember, 
say this when, do this when, next time around, never do this
```

**Rules:**
- Runs in background thread (daemon) — never blocks the chat response
- Uses `uuid.uuid4()` for the skills.id field (VARCHAR NOT NULL in schema)
- Opens its own `sqlite3.connect("ara.db")` — does not use the FastAPI DB session
- Heuristic first → LLM only if triggered → saves only if `is_coaching` is true
- Skips both heuristic and LLM if the user message is very short (<30 chars)

**Testing:** Send a message like "Next time a lead says pricing is too high, say: I hear you. Show them ROI from Blue Dart." → Ava acknowledges it → within seconds, `coaching_objection` skill appears in `SELECT * FROM skills WHERE category LIKE 'coaching%'`.

### Phase 9: Conversation Learning Cron (May 2026 — Built)

Daily extraction of patterns from Ava's conversations. Runs at 6AM IST.

#### Implementation

**File:** `extract_conversation_learnings.py`

**Script approach:** Cron runs the python script directly (via cronjob `script` field, not LLM prompt):

1. Scans conversations from the last 24 hours from `conversations` table + `agent_chat_messages`
2. Groups by lead and channel
3. Calls LLM with aggregated conversation data to extract:
   - **Objection patterns** → `objection_*` skills (e.g. `objection_pricing`, `objection_technical_quality`)
   - **Messaging wins** → `messaging_win_*` skills (e.g. `messaging_win_initial_outreach`)
   - **Engagement patterns** → `timing_pattern_*` skills (e.g. `follow_up_inbound_sequence`, `lead_conversion_funnel`)
   - **Segment signals** → `segment_signal_*` skills (e.g. `segment_bfsi_regional_language`)
4. Writes/updates skills via direct sqlite3 connection
5. Patterns are **aggregate** — not per-conversation. One extraction call per 24h batch.

**Cron schedule:** `0 7 * * *` (7AM IST daily, runs via no_agent script job with wrapper at `~/.hermes/profiles/johnny/scripts/daily_conversation_learning.sh`)

**Tenant isolation:** The script loads `TENANT_ID = "3e736242"` at the top and passes it to all `_upsert_skill()` calls. On a multi-tenant system, this would iterate over all active tenants.<br/><br/>**Source tagging:** Skills created by this script get `source='conversation'` (set in the raw SQL INSERT, matching the Skill model's `source` column).<br/><br/>**API key loading:** The script calls `load_dotenv("/Users/greg/.hermes/.env")` BEFORE importing `call_llm` from `induction_engine`, because `DEEPSEEK_API_KEY` is read at module load time.

**DB tables used:**
- `conversations` — outbound messages with direction, channel, content, sentiment
- `chat_threads` + `agent_chat_messages` — full conversation threads with role (agent/user)
- `skills` — where extracted learnings are upserted

### Phase 10: Learning Flow Into Prefill

The learning loop is closed when prefill templates read from skills:

```
Coaching capture (instant) ─┐
                            ├──→ Skills table → Prefill templates → Prompt Builder
Conversation cron (daily) ──┘    (Path B, instant)
                                      ↑
Document upload (chat) ──────────────┤
Induction docs ───────────────────────┘
```

No explicit "regenerate" needed — the prefill reads fresh from DB on every open.

### Phase 11: Document → Skill Extraction (May 2026)

Users can upload documents (PDF, DOCX, PPTX, TXT) directly in the chat and Ava automatically extracts structured skills from them. Two upload paths:

**Path A — Induction Chat** (`/induction/chat/{tenant_id}`): During onboarding, user drags pricing sheets, case studies, competitor analysis into the chat. Ava parses them, extracts skills, and responds conversationally about what she learned.

**Path B — Main Agent Chat** (dashboard): During day-to-day work, a manager drops a document (e.g. "new pricing from leadership"), and Ava extracts it into the same Skills table so all future messages benefit.

**Implementation (`document_skills.py`):**

```python
EXTRACT_SKILLS_PROMPT = \"\"\"You are a business analyst extracting structured knowledge from a sales document.

DOCUMENT: %s
CONTENT: %s

Extract ALL specific, actionable pieces of information... Categorize into:
- proposition: target segments, value props, pain points, use cases
- gtm_learnings: channels, failures, objection handling, success examples
- inbound: lead sources, volume, follow-up processes
- guardrail: pricing, discount authority, competitor positioning, communication rules
- messaging_win: specific messaging patterns that worked
- objection_pattern: common objections and how they were handled
- segment_signal: signals about specific segments/customers
- timing_pattern: timing-related patterns for outreach

Return JSON array of {"category", "key", "value"} objects.
\"\"\"

def extract_skills_from_document(doc, tenant_id, db):
    prompt = EXTRACT_SKILLS_PROMPT % (doc.filename, doc.text_content[:6000])
    resp = call_llm([{"role": "user", "content": prompt}], temperature=0.1)
    # Parse JSON array, upsert skills by category+key
    for s in skills_data:
        existing = db.query(Skill).filter(Skill.tenant_id == tenant_id, Skill.key == key).first()
        if existing: existing.value = val; existing.updated_at = datetime.now()
        else: db.add(Skill(tenant_id=tenant_id, category=cat, key=key, value=val))
    db.commit()
```

**Backend endpoint** (`POST /api/induction/{tenant_id}/upload`):
- Accepts multipart file upload
- Calls `parse_document()` (supports PDF via PyMuPDF, DOCX via python-docx, PPTX via python-pptx, TXT)
- Saves to `Document` table + raw file to uploads dir
- Calls `extract_skills_from_document()` to create skills
- Generates Ava's conversational response: *"I extracted 17 skills from your pricing sheet — 7 guardrails, 8 propositions, and 2 segment signals."*
- Runs contradiction check against existing documents

**Frontend — induction chat:** 📎 button next to textarea → hidden file input → `uploadFile()` JS → POSTs to upload endpoint → displays Ava's response

**Frontend — main agent chat (dashboard):** Same 📎 button in `.chat-input-wrap` → `uploadChatFile()` JS → same endpoint → displays as a chat message

**Supported formats:** PDF, DOCX, PPTX, TXT — up to 10MB

### Phase 12: Skills Dashboard — Making Learning Visible (May 2026 — LIVE)

After every input source (induction, documents, conversations, coaching) feeds into the Skills table, the user needs to **see what Ava knows**. Without visibility, the learning loop is a black box — Ava says "14 skills extracted" but the user can't verify, appreciate, or correct them.

**The Skills Dashboard is a browseable knowledge base, not an analytics page.** It answers: "What does Ava actually know about my business?"

**Layout:**
- Sidebar nav item under Learning section (🧠 Skills)
- Header with stats: Total Skills (91), New Today (14), Sources (4)
- **Source tabs** to filter: All | 💬 Induction | 📄 Documents | 🔄 Conversations
- **Search bar** (filter by key, value, or category)
- Skills grouped by category with icons + counts
- **Source badges** on each card: 🟩 Induction (green label), 🟦 Document (blue label), 🟨 Conversation (yellow label)
- **Detail panel** — clicking any skill opens a slide-over from the right showing: category, key, value, source, timestamp, and related skills from the same category

**Skill groups (8 categories):**

| Category | Icon | Example skill | Source |
|----------|------|--------------|--------|
| Proposition & Positioning | 📌 | logistics_segment: "For Blue Dart, reduce hiring TAT by 2/3rds" | Induction + Document |
| GTM Learnings | 🎯 | bfsi_channel_cold_email: "Cold email works for BFSI compliance officers" | Induction + Document |
| Inbound Setup | 📥 | lead_volume_range: "~100 leads/month from Google + LinkedIn" | Induction |
| Policy & Guardrails | 🛡️ | tiered_pricing_model: "<=10000 min: ₹4/min" | Induction |
| Objection Patterns | ⚠️ | rate_pricing_objection: "Lead pushed back on per-minute pricing. Ava used value-per-placement." | Conversation |
| Messaging Wins | ✨ | hinglish_greeting_40pct: "Opening with Hinglish greeting increased reply rate by 40%" | Conversation |
| Segment Signals | 📡 | logistics_hinglish_preference: "Logistics leads 3x prefer Hinglish" | Conversation |
| Timing Patterns | 🕐 | in_person_high_value: "Leads open to in-person meetings are high engagement" | Conversation |

**Each skill card shows:** key name (underscores → spaces), full value text, source badge (🟦 Document / 🟩 Induction / 🟨 Conversation), timestamp, blue left-border on new items

**Clicking a card** opens a detail panel with: category, full key, full value, source, timestamp, and related skills.

**Types of learnings both visible:**

1. **From human manager** — Induction chat + document upload. Green/blue badges. Pricing tiers, segments, guardrails.
2. **Self learnings** — Conversation extraction. Yellow badges. Objection patterns, messaging wins, segment signals. Appear automatically as Ava talks to leads.

**Why this matters:** Without the dashboard, the user trusts blindly that Ava learned something. With it, they can browse, verify, correct (via coaching), and appreciate the growing knowledge. It closes the trust loop.

### Three Update Cadences

| Source | Update cadence | DB source value | How |
|--------|---------------|-----------------|-----|
| Induction docs | On upload | `induction` | Written to skills table directly via induction chat |
| Documents in chat | Instant — on upload | `document` | `document_skills.py` extracts via LLM, saves to skills table |
| Conversations | Daily 7AM | `conversation` | `extract_conversation_learnings.py` scans last 24h via no_agent cron |
| Coaching | Instant (chat) | `coaching_*` category | `coaching_capture.py` detects trigger phrases + LLM extraction |

After the backend (model + API + analysis hook) is live, build the frontend layer in `dashboard_template.py`. The UI has three components, all built in a single JS-in-Python-string file:

1. **Sidebar restructure** — Adds a `LEARNING` section below `INTELLIGENCE` in the sidebar nav. Three items:
   - `Knowledge Base` (📖) — links to `/knowledge`
   - `Induction` (🎯) — links to `/induction`
   - `Learnings` (🧠) — new, renders `renderLearnings()` in the center panel
   
   Also rename the old `Knowledge` nav item to `Knowledge Base` for clarity. Order: Knowledge Base → Induction → Learnings.

2. **Learnings page** — `renderLearnings()` with three tabs:
   - **Insights tab** (`lTabInsights`): Objection bar chart (horizontal bars, CSS-only), sentiment distribution pie-style (grouped circles), communication language breakdown, decision maker signals
   - **Skills tab** (`lTabSkills`): What Ava knows — grouped by category from `/api/insights/learnings`. Each category as a collapsible card. Latest entry highlighted.
   - **Activity Feed tab** (`lTabFeed`): Reverse-chronological timeline from `/api/insights`. Each entry shows insight_type badge + key + value + timestamp.
   
   Tabs rendered via `switchLearnTab(tab)` JS function with `l-tab` / `l-tab-active` CSS classes.

3. **Experience card** — Always visible at the top of the Learnings page. Shows the tier name and progress bar:
   - **Early** (0-5 conversations) — 🔬
   - **Learning** (5-50) — 📚
   - **Experienced** (50-200) — 🧠
   - **Master** (200+) — ⚡
   
   Computed from `/api/insights/stats` `total_insights` count. Progress bar fills toward next tier bound. Falls back to `early` if no data.

4. **Dashboard widget** — `renderLearningsWidget()` renders a 4-row mini card shown below the main dashboard stats grid. Shows the 4 most recent skills from `/api/insights/learnings`. Each row: colored insight_type badge + truncated key + value snippet. Click \`→ View all learnings\` to navigate to the full Learnings page.

**UI patterns specific to the Learnings page:**
- Chart bars are pure CSS (no chart library) — `l-chart-bar` divs with inline `width: X%` styles
- Tab content is a single `div#lTabContent` that gets replaced on tab switch
- The `l-tabs` container is a flex row with `gap: 0`, tabs styled as buttons with bottom-border active state
- Collapsible skill sections: `exp-card` with clickable `.exp-card-hdr` toggling `.exp-card-body` via `style.display`
- All data fetched on render via two API calls: `/api/insights/stats` and `/api/insights/learnings`

**Critical CSS classes defined in dashboard_template.py's `<style>` block:**
```css
.learnm-widget   — the dashboard widget container (border, radius, padding)
.exp-card         — skill category card (rounded, bordered, shadow on hover)
.exp-card-hdr     — clickable header with category name + count
.exp-card-body    — collapsible body with skill items
.l-tabs           — tab bar container (flex, no gap)
.l-tab            — tab button (padding, bottom-border transparent)
.l-tab-active     — active tab (bottom-border #2563eb, color #333)
.l-chart-bar      — horizontal bar (height 18px, border-radius, background gradient)
.l-chart-label    — bar label (insight_type key name)
.l-feed-item      — activity feed row (border-left + padding for timeline effect)
.l-badge          — colored insight_type badge (inline, rounded, colored background)
```

**Fetch flow:** `renderLearnings()` → `fetchStats()` → fetch both `/api/insights/stats` and `/api/insights/learnings` (Promise.all) → render tabs + experience card. Widget fetches only `/api/insights/learnings` and renders the top 4.

### Phase 13: Tenant-Specific Segments Infrastructure (May 2026)

**Key principle from Greg: All segment/industry logic must be tenant-configurable, not hardcoded.** No Hunar-specific company names, no hardcoded keyword lists, no assumptions about what segments a tenant serves. Every tenant defines their own segments during induction.

#### Segment Config Storage

Segments live in `tenant.config["segments"]` as a JSON dict, not hardcoded in Python:

```json
{
  "segments": {
    "logistics": {
      "keywords": ["logistics", "delivery", "fleet", "warehouse"],
      "company_patterns": ["delhivery", "dhl", "fedex"],
      "description": "Logistics and supply chain companies"
    },
    "bfsi": {
      "keywords": ["bfsi", "bank", "finance", "insurance", "compliance"],
      "company_patterns": ["bajaj", "kotak", "hdfc"],
      "description": "Banking and financial services"
    }
  }
}
```

> The examples above are Hunar-specific to illustrate the format. For a new tenant (e.g., a US staffing company), they define their own segments — healthcare, tech, etc. — during induction. **Never hardcode company names from one tenant into the codebase.**

#### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/tenants/{tenant_id}/segments` | Read segment config |
| `PUT` | `/api/tenants/{tenant_id}/segments` | Update all segments (full replace) |
| `POST` | `/api/tenants/{tenant_id}/segments/reassign` | Re-run auto-assignment for all leads |

#### Lead Auto-Assignment

`auto_assign_segment(lead, db)` is called on lead creation and reads from tenant config:

```python
def auto_assign_segment(lead, db):
    from database import Tenant
    if not lead or not lead.company:
        return
    current_segment = lead.segment or ""
    if current_segment:
        return  # Already has a segment
    tenant = db.query(Tenant).filter(Tenant.id == lead.tenant_id).first()
    if not tenant:
        return
    segments_config = (tenant.config or {}).get("segments", {})
    if not segments_config:
        return
    company_lower = lead.company.lower()
    for seg_name, seg_data in segments_config.items():
        for pattern in seg_data.get("company_patterns", []):
            if pattern.lower() in company_lower:
                lead.segment = seg_name
                return
```

**Trigger points:** `create_lead()` endpoint (called after cadence assignment), and `POST /api/tenants/{tenant_id}/segments/reassign` (iterates all leads).

#### Skill Filtering from Tenant Config

`load_skills_for_prompt()` reads segment definitions from tenant config, not hardcoded Python:

```python
tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
segments_config = (tenant.config or {}).get("segments", {}) if tenant else {}
segment_keywords = {}
for seg_name, seg_data in segments_config.items():
    seg_keywords = seg_data.get("keywords", []) + seg_data.get("company_patterns", [])
    segment_keywords[seg_name] = seg_keywords
    all_segment_keywords.extend(seg_keywords)
```

Filtering: general skills (no segment keyword) → shown to ALL; segment-specific skills → matching leads only; skills mentioning other segments → hidden.

#### Design Rule for All New Features

Before building any ARA feature, ask: **"Is this Hunar-specific or should it work for any tenant?"** If any tenant, the config/storage/API must be keyed by `tenant_id` and behavior must derive from `tenant.config`.

#### Pitfall: SQLAlchemy Column Truthiness

A SQLAlchemy `Column` object is **always truthy in Python** regardless of value:
```python
# BROKEN — lead.segment is a Column, always truthy
if lead.segment: return  # Never triggers even when value is ""

# FIXED — access the actual value
current = lead.segment or ""
if current: return
```

Same applies to any `if column_name:` guard — always use `column_name or ""` to get the runtime value.

#### Pitfall: `replace_all` on Similar Code Blocks

`patch` tool's `replace_all=true` is dangerous when the same pattern appears in multiple functions with different variable names (`l.cadence_type` vs `lead.cadence_type`). Audit ALL matched locations after a `replace_all`. Better: use unique context strings for individual matches.

## Agent Chat Skills Injection (Corrected June 2026)

**Critical pitfall discovered: Path A (agent_chat) was NOT injecting all skills.** The code at `agent_chat()` line ~6413 was filtering `Skill.category == "memory"` — meaning only skills explicitly saved as `category='memory'` were injected into Ava's context. All other categories (coaching_general, objection_pattern, messaging_win, segment_signal, timing_pattern, guardrail, proposition, gtm_learnings, etc.) were invisible to the agent.

**Fix applied June 2026:** Changed injection to pull ALL skills (up to 50, ordered by created_at desc) and grouped by category:
- Memories (`category='memory'`) get dedicated "## Your Memories" section
- All other skills grouped as "## Your Skills / Knowledge: {category}" with up to 10 per category

The fix enables true dual-injection — skills from induction, documents, conversations, and coaching are now visible in BOTH:
- Path A: agent_chat (dashboard/WhatsApp)
- Path B: scheduled message generation (cadence emails/WhatsApp)

**Related pitfall: Wrong memory tools in prompt.** The system prompt's "Learning the User" section directed Ava to use `save_learning` / `add_skill` / `search_knowledge_base`. These stored to the skills table with non-"memory" categories — which were NEVER injected into agent_chat context. The prompt now uses `save_memory` / `search_memory` (category='memory', always injected).

**Proactive memory trigger added:** The Reasoning Preamble now includes a MEMORY CHECK step — before stating her plan, if the message references a person/company/deal, Ava calls `search_memory()` to check what she already knows from past sessions.

**Response formatting rules added:** A new "Response Formatting (HARD RULE)" section in the system prompt enforces:
- Bold section headers (`*Header Name*` for WhatsApp)
- Action items always show description + lead name + due date
- Sections: 🔴 OVERDUE / ⏳ PENDING / ✅ ACCOMPLISHED / 📚 TODAY'S LEARNINGS
- Multi-step plans formatted as "Step 1/3: ..." with bold headers

## Pitfalls

- **ActionItem.ref_type (NOT lead_id)**: ActionItem has no `lead_id` column — use `ref_type == "lead"` + `ref_id` for lead name resolution. See `references/actionitem-ref-type-pitfall.md`.
- **Skills not injected into agent_chat**: Verify `agent_chat()` line ~6413 and the `system_prompt` builder. Check that the DB query is NOT filtering to `category == "memory"` and is instead pulling all skills. When adding new prompt infrastructure, always check BOTH injection paths (agent_chat AND scheduled message generation).
- **Prompt points to wrong tools**: If the system prompt tells the LLM to use `save_learning`/`add_skill`/`search_knowledge_base`, check whether skills from those tools actually reach the LLM's context. The `save_memory`/`search_memory` tools store to `category='memory'` which was the only category guaranteed to be injected. After the June 2026 fix, all categories are injected, but memory tools remain the intended path for agent learning.
- **`f"""` with triple quotes inside**: An `f"""` string that contains `"""` (triple quotes) as literal text will close the f-string prematurely. Use `---` delimiters or single quotes instead. `py_compile` catches this at compile time.
- **Thread pool saturation**: The inbound handler (`_handle_inbound_whatsapp`) already holds a thread pool thread for 2-5s (lead lookup + LLM call + WhatsApp send). Adding analysis inline makes it 3-6s. Always fire analysis on a **dedicated background thread**, not on the thread pool.
- **SQLite concurrent writes**: If analysis thread and main handler hit the DB simultaneously, SQLite may return "database is locked." At low volume (handful of leads), this is negligible. At scale, consider a task queue or WAL mode.
- **Skill key normalization**: `key` must not contain spaces — use underscores. Keep it concise and descriptive (e.g., `pricing_objection_retail`, `roi_framing_manufacturing`).
- **Empty conversation history**: The first interaction with a new lead has no prior conversation. The analysis should still extract insights (sentiment, intent, language) but won't have timing/sentiment_shift data.
- **JSON parsing from LLM**: The LLM may wrap JSON in ````json ... ```` blocks or return extra text. Always strip these before parsing: check for ````json`, then ````, then try raw.
- **No hardcoded slack**: Don't make the analysis prompt a constant string — it needs dynamic data (lead context, messages, history). Use `f"""` or `.format()` but beware of the triple-quote trap above.
- **Analysis should NOT modify the Conversation model**: Keep analysis data in AvaInsight + Skill tables. The Conversation record is the source of truth for the raw exchange - don't overwrite it with extracted interpretations.
- **SQL column/value mismatch in raw INSERT**: When adding columns to the skills table (like `source`), update both the INSERT columns list AND the VALUES placeholders count. Ensure column count matches placeholder count.
- **env loading order for standalone scripts**: When a standalone script using `induction_engine.call_llm()` runs as a cron job, `load_dotenv("/path/to/.env")` MUST be called BEFORE importing `call_llm`. The `induction_engine.py` reads `DEEPSEEK_API_KEY = os.environ.get(...)` at module load time — if `.env` hasn't been loaded yet, the key is empty. Reorder: `load_dotenv(...)` first, then `from induction_engine import call_llm`.

## See Also

- `references/ara-learning-loop-implementation.md` — Backend implementation reference (May 2026)
- `references/dashboard-learning-ui.md` — Dashboard UI implementation (sidebar, Learnings page, widget)
- `ara-crm-feature-build` — CRM pipeline features (separate concern)
- The `AVA_AUTO_SYSTEM_PROMPT` in `server.py` — has the `{skills_context}` slot
- The `Skill` and `AvaInsight` models in `database.py`
