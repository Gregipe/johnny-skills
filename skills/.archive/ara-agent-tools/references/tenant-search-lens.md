# Tenant Search Lens — Contextual Web Research

Added July 18, 2026. Drives relevant, de-duplicated search results filtered
through the tenant's actual proposition and GTM learnings.

## Problem

Web searches for companies (e.g. "latest news about HDFC Bank") returned
generic noise — credit card lounge changes, MCLR revisions, stock moves —
with zero relevance to the tenant's pitch. The agent had no context about
what signals matter for the tenant's business.

## Solution: `build_tenant_search_lens(tenant_id, db)`

Located in `/opt/ara/server.py`. Reads all proposition + GTM learning skills
from induction and distills them into a compact three-part filter:

```
SIGNALS: VoiceAI/automation deployment, attrition spikes, hiring surges, ...
PROPOSITION: Faster screening. Faster onboarding. Better engagement.
IGNORE: FD rates, consumer banking products, credit card changes, ...
```

### Signal Detection Logic

Keyword-based pattern matching against all proposition + GTM skill values:

| Skill keywords detected | Signal added |
|---|---|
| hiring, recruitment, recruiter, candidate, screening, interview | hiring surges, recruitment drives |
| attrition, retention, drop-off, exit interview | attrition spikes |
| voice ai, conversational ai, ai agent, automation | VoiceAI/automation deployment |
| telecalling, outreach, call center | telecalling operations |
| volume, scale, 10k, 50k, mass hiring, bulk | volume increases, workforce scaling |
| frontline, blue-collar, gig worker, rider, driver | frontline workforce expansion, gig worker onboarding |
| funding, series, investment, growth, expansion | funding events, growth/expansion |
| bfsi, bank, insurance, nbfc, branch | branch network changes |
| logistics, 3pl, delivery, fleet, warehouse | logistics network expansion |
| hiring surges (present) → always cascades to | funding events, growth/expansion |

### Proposition Extraction

Reads `value_prop` and `pitch` skills from the proposition category, picks
the shortest one for compact prompt injection. Falls back to platform/connect
overview skills.

### Ignore List

Hardcoded consumer banking noise that's always irrelevant for B2B tenants:
FD rates, consumer banking products, credit card changes, lounge access,
savings account rates, personal loan offers. Branch openings also suppressed
unless BFSI is a detected signal.

## Injection Points

### 1. Agent Chat System Prompt

In `/api/agent/chat` (around line 5753 of server.py), the search lens is
injected into the context block:

```
SEARCH LENS: {search_lens if search_lens else 'No tenant context — show all relevant news.'}
```

### 2. Tool-Calling Principles (Rule 5 sub-bullet)

```
- **Use the SEARCH LENS.** When searching for news about a company,
  frame your query and filter results through the SEARCH LENS in Context.
  Only surface news that signals a potential entry point.
```

### 3. Search & Research Formatting Section

New section in AGENT_SYSTEM_PROMPT_BASE with explicit template:

```
📰 [Company] — Key Updates

1. **Headline** — 1-2 lines of what happened and why it matters.
   [Source1](url) · [Source2](url)
```

Rules: de-duplicate, lead with most important, compact source links,
no raw dumps, no fetch_url on every result.

## Search Result Formatting Rules

| Rule | Detail |
|---|---|
| De-duplicate | Multiple sources on same story = ONE entry with multiple links |
| Compact attribution | `[Mint](url) · [Bloomberg](url)` — use `·` separator |
| No raw dumps | Never show raw markdown, URLs, or tool output to user |
| No fetch_url spam | web_search already returns snippets; only fetch_url on explicit request |
| Silent filtering | Skip irrelevant results entirely — don't say "I filtered out X" |

## Raw web_search Output Improvement

Both `_search_tavily` and `_search_ddg` now extract domain from URL for
compact attribution: `- Title [domain.com](url)` instead of `- [Title](url)`.

## Example: Hunar.ai → HDFC Bank

Search "latest news about HDFC Bank" without lens:
→ MCLR rate revision, credit card lounge access, Q1 results, stock analysis

Same search with Hunar lens:
→ HDFC Bank cuts 3,300+ jobs via AI automation (perfect entry point)
→ All results about workforce reduction, automation, digital transformation

## Deployment

Function lives in server.py alongside `_get_agent_context`. Server restart
required after changes. Verify with:

```python
from database import init_db
from server import build_tenant_search_lens
db = init_db()
print(build_tenant_search_lens('3e736242', db))
```
