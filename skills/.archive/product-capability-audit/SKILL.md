---
name: product-capability-audit
description: "Audit a codebase to identify current capabilities, compare against ideal/world-class state, and generate a prioritized roadmap. Covers the surface-mapping → capability classification → gap analysis → roadmap generation pipeline."
version: 1.0.0
author: Johnny
license: MIT
metadata:
  hermes:
    tags: [audit, roadmap, strategy, product-planning, gap-analysis, prioritization]
    related_skills: [writing-plans, subagent-driven-development, plan]
---

# Product Capability Audit & Roadmap Generation

## Overview

Audit a product/agent codebase to determine what it can do today, identify what's missing for world-class status in its domain, and produce a prioritized build roadmap. The output is a structured analysis the user can make decisions from — not a data dump.

**Core principle:** Classify before gap. Don't name gaps until you've mapped and categorized what exists. Structure drives insight.

## When to Use

- User asks "what else should we build?"
- User asks "make X world-class" or "how does X compare to [competitor]?"
- User says "think through what's missing" about a product
- Before a major investment decision (hire, raise, pivot)
- User asks for a "roadmap" or "strategic direction"

**Do NOT use for:**
- Simple feature requests ("add a delete button")
- Bug-fixing sessions
- Implementation planning (use `writing-plans`)
- Throwaway experiments (use `spike`)

## The Audit Pipeline

### Phase 1: Surface Mapping

Map the codebase surface to identify ALL current capabilities. Be exhaustive — the gaps you miss are gaps that will surface as embarrassment later.

**1a — API Routes**
Search for all HTTP endpoint definitions:

```bash
grep -n '@app\.(get|post|put|delete)' server.py
```

Classify each endpoint into a functional domain (leads, deals, cadence, coaching, learning, system, integrations, etc.).

**1b — Tool/Function Dispatchers**
Find the tool execution engine. In ARA this is `execute_tool()` in server.py. Map every tool the agent can call:

```python
# Search patterns
search_files("tool_name", path="server.py", file_glob="*.py")
```

List each tool with its: name, args, return value, side effects, access control.

**1c — System Prompts & Agent Instructions**
Find ALL system prompt definitions. In ARA:
- `AGENT_SYSTEM_PROMPT_BASE` — the coaching/agent chat persona
- `AGENT_TOOL_SCHEMA` — the tool reference the agent sees
- Any per-cadence or per-channel prompts
- Guardrails, personality sections, security instructions

**1d — Database Models**
Map all DB tables/models to understand what data exists. This reveals capabilities that may not have explicit API endpoints (e.g., if a table exists but has no API, that's a half-built capability).

**1e — Integration Points**
Identify external integrations: WhatsApp, email, calendar, LinkedIn, CRMs, voice/calling. Note which are fully wired vs partially built.

**1f — Scheduled/Background Processes**
Check for cron jobs, background threads, scheduled actions. These are often hidden capabilities.

### Phase 2: Capability Classification

Group everything found in Phase 1 into functional domains. Use the categories most relevant to the product's domain. For an SDR/Revenue Agent, the categories are:

| Domain | What goes here |
|--------|---------------|
| **Lead Management** | CRUD, search, import, dedup, assignment |
| **Outreach Channels** | WhatsApp, Email, LinkedIn, Call, SMS |
| **Cadence/Sequencing** | Templates, scheduling, triggers, multi-channel |
| **Pipeline Intelligence** | Summaries, activity logs, deal tracking |
| **Qualification & Scoring** | ICP matching, lead scoring, stage automation |
| **Coaching & Learning** | Human coaching, insight extraction, knowledge base |
| **Integrations** | CRM sync, calendar, external APIs |
| **System/Admin** | Config, settings, debugging, tenant management |

For each capability, note:
- **Status:** Working / Partial / Missing
- **Quality:** Production-grade / MVP / Prototype
- **Integration depth:** Standalone / Connected / Multi-channel aware

### Phase 3: Gap Analysis

Compare current state against the "world-class ideal" for this domain. For each gap:

1. **Name the gap** — descriptive but specific ("Meeting Scheduling" not "Calendar")
2. **Rate impact:**
   - **Core** — Without this, the product cannot deliver its primary value proposition
   - **Growth** — This unlocks a new segment, use case, or revenue model
   - **Quality** — This makes existing capabilities production-grade
   - **Defense** — This prevents users from churning to competitors
3. **Assess differentiation** — Is this a table-stakes feature or a moat? For SDR agents:
   - Table stakes: multi-channel outreach, cadence, qualification
   - Moat: voice calling, role-play coaching, adaptive sequencing
4. **Note dependencies** — What else needs to be built first?

**Cross-reference with user's stated goals.** If the user said their goal is to start a company in India, prioritize features relevant to the Indian market (WhatsApp > LinkedIn, voice > email).

### Phase 4: Prioritized Roadmap

Produce a ranked build order. Each recommendation should say:

```
### [Priority N]: [Feature Name] (Impact Tier)

**Why:** One-sentence value proposition

**Current state:** What exists today (even if nothing)

**What to build:** 2-3 sentence description of the feature

**Why this priority:** The reasoning — why this before the next item

**Differentiation check:** Table stakes vs moat vs competitive parity

**Dependencies:** [list]
```

**Tier priority heuristic:**
1. **Fix broken core** — Anything that breaks the primary value proposition
2. **Core SDR functions** — Meeting scheduling, LinkedIn outreach, voice calling
3. **Smart automation** — Adaptive cadences, intent classification, multi-channel sequencing
4. **Coaching & intelligence** — Role-play, analytics, deal coaching
5. **Infrastructure & polish** — CRM sync, competitive intel, transcription

**Ordering rules:**
- Fix broken things first (even if boring)
- Build moats before table stakes (you can't compete on parity)
- Build what the user explicitly asked for before inferred needs
- If two features have equal impact, build the one with fewer dependencies

## Output Format

Present the analysis in this structure:

```
## Current Capabilities (Quick Audit)

[Domain]: [capability], [capability], ... — [1-sentence assessment]
[Domain]: [capability], [capability], ... — [1-sentence assessment]

## Gaps

### Tier 1 — [Category Name] (Highest Impact)

### 💎 [Feature Name]
[3-4 sentence description]

### 🥇 [Feature Name]
[description]

### Tier 2 — [Category Name]

...etc...

## Build Order

| Priority | Feature | Why | Tier |
|----------|---------|-----|------|
| 1 | [Name] | [one-liner] | [Core/Moat/Growth] |
| 2 | [Name] | [one-liner] | [Core/Moat/Growth] |

**If I had to pick one to start tomorrow — [single recommendation].**
```

## Reference Documents

When available, save session-specific audit detail as a `references/<product-name>-audit-<date>.md` file under this skill. This gives future sessions the concrete analysis without cluttering the skill itself.

The reference should include:
- Full list of API endpoints found (dense, not prose)
- Full list of tools/functions with args
- Full system prompt text (if relevant)
- The specific competitive/world-class benchmarks used
- Any user reactions or corrections during the presentation

## Pitfalls

- **Don't present raw data as analysis.** A list of 100 API endpoints is a data dump. Group them, classify them, assess them.
- **Don't skip the strengths.** Greg knows what's working. A fair audit includes "this is solid" alongside "this is missing."
- **Don't over-research the codebase.** Read the key files (API routes, tool dispatcher, system prompts) — you don't need to trace every helper function. 30 minutes of reading is better than 3 hours.
- **Don't present without a build order.** A list of gaps without prioritization is just complaining. The user wants to know what to do next.
- **Don't be vague about features.** "Better analytics" is not a recommendation. "Pipeline velocity dashboard with conversion rates by stage, channel, and rep" is.
- **Don't treat this as a design doc.** This is a decision-support document. No architecture diagrams, no wireframes, no code.
- **Don't forget the user's context.** Greg's goals (LinkedIn 5K→100K, start company in India, stay close to family) should influence prioritization. Recommend features that serve these goals, even if they're not the most technically impressive.
