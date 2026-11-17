# Arun Matthew Contamination — June 15, 2026

## Pattern

A lead name ("Arun Matthew") became the dominant signal in the coaching thread due to
self-reinforcing LLM hallucination loops. Each failed confirmation mentioning the name
added another mention, which made the NEXT ambiguous query match more strongly.

## Timeline

| Date | Count | Context |
|---|---|---|
| Jun 8-9 | 8 | Legitimate — lead creation, meeting booking, stage changes |
| Jun 11-13 | 3 | Pipeline summaries (factual mentions in lead listings) |
| Jun 14 | 4 | **Contamination** — "set it in" → "Arun Matthew?" hallucination loops |
| Jun 15 | 1 | **Contamination** — "create an action for this" → "Arun Matthew's phone" |

**Total: 18 mentions. 5 contaminated (Jun 14-15), 13 legitimate.**

## Symptoms

- "Create an action for this against me for Rajesh Sharma" → LLM: "I'm not clear — we were just talking about adding Arun Matthew's phone and company later"
- Immediate preceding context was about Rajesh, not Arun Matthew
- LLM defaulted to the stronger signal (18 Arun Matthew mentions) over the weaker signal (1 recent Rajesh mention)

## Fix

1. **Purged 5 contamination messages** from coaching thread (Jun 14-15 hallucination loops)
2. **Bumped context window** from 20→50 messages (commit 6156890) to prevent topic scroll-out
3. **Created lead-context memory spec** (`docs/lead-context-memory-spec.md`) for Phase 2: lead-scoped context injection

## Prevention

- **Do NOT add names to the coaching thread context that aren't direct user requests.** The "set it in → Arun Matthew" pattern arose because the LLM, asked to clarify ambiguous input, guessed the most-mentioned name instead of asking the user.
- **Context window size and contamination are inversely related.** Larger windows help topic retention but also amplify contamination. The right fix is lead-scoped injection (Phase 2 spec), not unbounded window growth.
- **Delete hallucinated responses from the DB** when they create self-reinforcing patterns. The coaching thread is the LLM's memory — garbage in, garbage out.
