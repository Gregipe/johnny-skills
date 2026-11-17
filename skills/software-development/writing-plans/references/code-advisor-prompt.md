# Code Advisor Prompt Template

When facing a complex design decision with meaningful trade-offs (cost, latency, UX, maintainability), write a structured prompt to get expert advice before implementing.

## When to use

- Architectural decisions with >2 viable approaches
- Trade-offs between cost, latency, complexity, and user experience
- Before building a subsystem that's expensive to refactor later
- Any design question where "it depends" is the honest answer

## Prompt structure

Write a markdown document with these sections:

### Context: [System Name]

2-3 paragraphs describing:
- What the system is and who uses it
- The specific flow/component being designed
- How it works today (current approach with code snippets)

### The Problem

- What's wrong with the current approach
- Why the previous approach was rejected (e.g., "too slow," "too expensive")
- What capability was lost in the simplification

### Current Approach (single call, the one needing review)

` ```python`
Focused code snippet showing the current approach — NOT the full implementation, just the key logic block
` ``` `

### Constraints & Context

List in bullet points under subheadings:

**Performance**
- Real-world latency targets (e.g., voice notes already ~3-5s, every 100ms counts)
- Budget constraints (e.g., ~$0.02-0.05 per extra LLM call, 100+ convos/day)
- User expectations (e.g., WhatsApp sub-5s)

**User experience**
- Error message quality expectations
- Multi-step action coherence
- Special cases (voice note garbling, etc.)

**How the system sees things**
- Persistence model (what's stored, what's not)
- What the LLM sees on next turn
- What's lost vs what's recoverable

**Input/output format**
- Examples of raw inputs and expected outputs
- Mixed-format characteristics

### Design Question

> **One-line summary of the core question**

**Option A: [Name]**
- 3-4 bullet pros/cons each
- Keep it honest — every option has trade-offs

**Option B: [Name]**
- Same format

**Option C: [Name]**
- Same format

**Option D: [Name]** (when applicable)
- Sometimes the "do nothing" or "do it differently" option

**Other factors to consider** (at the bottom, not in the question flow)
- Common patterns or edge cases
- Future extensibility concerns
- Open questions you'd like answered

### What we need from you

Numbered questions:
1. Recommendation (or hybrid)
2. Key code structure
3. Any patterns/libraries?
4. MVP vs ideal long-term approach

## Example

See the original session that generated this template: `~/.hermes/profiles/johnny/prompts/code_advisor.md` contains the full prompt used for the ARA ToolResult design question.

## Tips

- Be specific in code snippets — general descriptions invite general answers
- List the pros/cons honestly for each option, including your own bias
- Include performance numbers where possible (latency, cost per call)
- State the current approach's specific failings, not just "it's bad"
- The "How the system sees things" section catches the most common blind spots
