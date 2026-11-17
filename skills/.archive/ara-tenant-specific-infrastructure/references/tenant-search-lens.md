# Tenant Search Lens — Full Implementation

Built July 18, 2026. Greg's requirement: when Ava searches for news about a
target company, results must be filtered through the tenant's proposition.
Generic noise (stock prices, credit cards, FD rates) has zero relevance to
a pitch about voice AI for frontline hiring.

## The Function

`build_tenant_search_lens(tenant_id, db)` lives in `server.py` (before
`_get_agent_context`). Returns "" if no induction skills exist.

```python
def build_tenant_search_lens(tenant_id, db):
    """Distill proposition + GTM learnings into a compact search relevance filter."""
    from database import Skill

    skills = db.query(Skill).filter(
        Skill.tenant_id == tenant_id,
        Skill.category.in_(["proposition", "gtm_learnings"]),
    ).all()

    if not skills:
        return ""

    all_text = " ".join(s.value.lower() for s in skills)

    # Signal detection from keyword clusters
    signals = set()

    if any(w in all_text for w in ["hiring", "recruitment", "recruiter", "candidate", "screening", "interview"]):
        signals.add("hiring surges")
        signals.add("recruitment drives")

    if any(w in all_text for w in ["attrition", "retention", "drop-off", "re-hiring", "exit interview"]):
        signals.add("attrition spikes")

    if any(w in all_text for w in ["voice ai", "voiceai", "conversational ai", "ai agent", "ai hr", "automation", "automated"]):
        signals.add("VoiceAI/automation deployment")

    if any(w in all_text for w in ["telecalling", "outreach", "call center", "outbound call", "screening call"]):
        signals.add("telecalling operations")

    if any(w in all_text for w in ["volume", "scale", "10k", "50k", "high volume", "mass hiring", "bulk"]):
        signals.add("volume increases")
        signals.add("workforce scaling")

    if any(w in all_text for w in ["frontline", "blue-collar", "gig worker", "delivery partner", "rider", "driver", "field force"]):
        signals.add("frontline workforce expansion")
        signals.add("gig worker onboarding")

    if any(w in all_text for w in ["funding", "series", "investment", "growth", "expansion", "new market"]):
        signals.add("funding events")
        signals.add("growth/expansion")

    # If hiring is a signal, growth/funding always are too (causal link)
    if "hiring surges" in signals:
        signals.add("funding events")
        signals.add("growth/expansion")

    if any(w in all_text for w in ["digital", "transformation", "modernization", "tech stack", "technology"]):
        signals.add("digital transformation")

    if any(w in all_text for w in ["bfsi", "bank", "insurance", "nbfc", "branch", "financial"]):
        signals.add("branch network changes")

    if any(w in all_text for w in ["logistics", "3pl", "delivery", "fleet", "warehouse"]):
        signals.add("logistics network expansion")

    # Proposition summary — pick shortest value_prop for compact injection
    prop_skills = [s for s in skills if s.category == "proposition"]
    value_props = []
    for s in prop_skills:
        if "value_prop" in s.key.lower() or "pitch" in s.key.lower():
            value_props.append(s.value[:200])

    if not value_props:
        for s in prop_skills:
            if any(w in s.key.lower() for w in ["platform", "connect", "overview", "ai_hr"]):
                value_props.append(s.value[:200])
        value_props = value_props[:2]

    if value_props:
        value_props.sort(key=len)
        prop_summary = value_props[0][:300]
    else:
        prop_summary = (
            next((s.value[:200] for s in prop_skills if "platform" in s.key.lower()), "")
            or next((s.value[:200] for s in prop_skills), "")
        )

    # Ignore list: consumer banking noise (always for B2B tenants)
    ignore = set()
    ignore.add("consumer banking products")
    ignore.add("credit card changes")
    ignore.add("lounge access")
    ignore.add("savings account rates")
    ignore.add("FD rates")
    ignore.add("personal loan offers")

    if "branch network changes" not in signals:
        ignore.add("branch openings")

    lines = []
    if signals:
        lines.append(f"SIGNALS: {', '.join(sorted(signals))}.")
    if prop_summary:
        lines.append(f"PROPOSITION: {prop_summary}")
    if ignore:
        lines.append(f"IGNORE: {', '.join(sorted(ignore))}.")

    return "\n".join(lines)
```

## Injection: Agent Chat System Prompt

In the agent chat endpoint (~line 5669 of server.py), right after
`skills_context` is computed:

```python
# Build tenant search relevance lens for contextual research
search_lens = build_tenant_search_lens(tenant_id, db)
```

Then in the pipeline context string (~line 5753):

```python
system_prompt += f"""
...
INDUCTION: {skills_context}
SEARCH LENS: {search_lens if search_lens else 'No tenant context — show all relevant news.'}
DOCUMENTS: {doc_context}
...
"""
```

## Injection: Tool-Calling Principles

In `AGENT_SYSTEM_PROMPT_BASE`, under rule 5 (web search), a sub-bullet:

```
5. **Web search is mandatory for web requests.** ...
   - **Use the SEARCH LENS.** When searching for news about a company
     (especially for outbound research), frame your query and filter
     results through the SEARCH LENS in Context. Only surface news that
     signals a potential entry point — a trigger event, pain point, or
     growth signal relevant to your proposition. Dismiss generic consumer
     news, stock moves, and product launches that don't create an opening.
```

## Example Output (Hunar.ai Tenant)

```
SIGNALS: VoiceAI/automation deployment, attrition spikes, branch network
changes, digital transformation, frontline workforce expansion, funding
events, gig worker onboarding, growth/expansion, hiring surges, logistics
network expansion, recruitment drives, telecalling operations, volume
increases, workforce scaling.

PROPOSITION: Faster screening. Faster onboarding. Better engagement.

IGNORE: FD rates, consumer banking products, credit card changes, lounge
access, personal loan offers, savings account rates.
```

## Behavior Per Tenant

- **Hunar.ai (HR tech for frontline):** Signals = hiring, attrition, voice AI, telecalling, volume. Ignore = consumer banking.
- **Empty induction:** Returns "" → prompt shows fallback "No tenant context — show all relevant news."
- **New tenant (different industry):** Signals are derived from THEIR proposition keywords. A cybersecurity tenant would get different signals (breach, CISO changes, compliance mandates).

## Design Decisions

- **No injection at web_search tool level.** The LLM constructs the query based on the lens in its system prompt. Prepending tenant context to every query would break generic lookups ("AI voice trends").
- **Proposition picks shortest value_prop.** Multiple value props exist per tenant (per segment). The shortest one fits best in the compact prompt format.
- **Keyword-based, not LLM-based.** Deterministic keyword matching is fast, free, and consistent. LLM summarization would add latency and cost per session.
- **Causal linking (hiring → growth).** If a tenant cares about hiring, they inherently care about growth events too — even if "growth" isn't explicitly in the induction data.
