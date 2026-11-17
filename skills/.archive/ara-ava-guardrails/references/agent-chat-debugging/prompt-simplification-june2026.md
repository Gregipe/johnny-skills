# Prompt Simplification Strategy (June 2026)

Strategy for collapsing 550 lines of conflicting rules into 116 lines.

## Before: ~550 lines / 30K+ chars

The system prompt had these DUPLICATE/CONFLICTING sections:
1. CRITICAL rule (20 lines) — "ONLY [TOOL_CALL:] on confirmation"
2. Action Approval Rule (7 lines) — "Show draft, get approval"
3. Approved Draft Execution Rule (18 lines) — "On confirmation execute immediately"
4. HARD RULES (7 lines) — "#1 Always include [TOOL_CALL:], #2 On confirm output immediately"
5. Line 5345 (1 paragraph) — "Output [TOOL_CALL:] alongside proposal"
6. Personality & Boundaries (10 lines) — "Be chirpy and witty"
7. Guidelines (10 lines) — "Calm, professional tone"
8. Data Honesty Rule (6 lines) — "Say 'not on file'"
9. Lead Disambiguation Rule (6 lines) — "Confirm which lead"
10. Error Handling Protocol (20 lines) — "Diagnose and report"
11. System Awareness (20 lines) — "Trust tool output"

**All five approval sections said the same thing differently.** The LLM couldn't sort out which one to follow, so it picked randomly based on the query.

## After: ~116 lines / 8.5K chars

```
You are {agent_name}, Autonomous Revenue Agent for {company}. Professional SDR.

## Tone (5 lines)
Professional, concise, direct. Brief chit-chat OK.

## Pipeline (8 lines)
LEADS: {lead_count} total, DEALS: {deal_count} total

## Workflow: Sending Messages (15 lines)
1. Identify lead
2. Show draft + [TOOL_CALL:] in same response
3. On confirmation, ONLY [TOOL_CALL:]
Exception: crystal clear commands execute directly

## Data Honesty (3 lines)
Empty = "not on file". Not "failed to load".

## Error Handling (5 lines)
Diagnose + report in one sentence. Offer 1-2 alternatives. No "glitch."

## Guidelines (8 lines)
Use tools before asserting. Read-only = free. Trust tool output.
```

## Key Decisions

1. **One unified Workflow section** replaces 5 conflicting rules. No duplicate instructions. No contradictions.
2. **Professional tone only** — remove "chirpy/witty" to eliminate tone conflicts.
3. **Tool schema trimmed** — 44 tools × 3 lines each (no verbose examples). 4 examples at the bottom.
4. **Error handling condensed** — "diagnose + report in one shot. No glitch narratives. Offer alternatives." No more multi-step protocols.
5. **Data Honesty merged into Error Handling** — both are about not framing things as errors.
6. **Lead Disambiguation merged into Workflow Step 1** — "Identify the lead. Say their full name. If multiple matches, present options."

## LLM Response Patterns After Rewrite

The compact prompt produces more consistent outputs:
- First response always includes [TOOL_CALL:] with draft
- On confirmation, clean tool call (no stutter)
- Crystal clear commands execute without draft
- Error responses are one sentence + alternatives
- Tone is consistently professional

## Regressions to Watch For

- **Too short?** If 116 lines loses critical nuance (e.g., specific tool behaviors), individual tool descriptions can carry that.
- **Chirpy users?** If the user wants personality, add a single tone line. Don't re-add the 10-line Personality section.
- **New tools?** Add to the compact list. Don't re-add verbose examples.
