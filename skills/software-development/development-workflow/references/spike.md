# Spike — Throwaway Experiments

Use this when the user wants to **feel out an idea** before committing to a real build — validating feasibility, comparing approaches, or surfacing unknowns that no amount of research will answer. Spikes are disposable by design. Throw them away once they've paid their debt.

Load this when the user says things like "let me try this", "I want to see if X works", "spike this out", "before I commit to Y", "quick prototype of Z", "is this even possible?", or "compare A vs B".

## When NOT to use this

- The answer is knowable from docs or reading code — just do research, don't build
- The work is production path — use the `plan` skill instead
- The idea is already validated — jump straight to implementation

## If the user has the full GSD system installed

If `gsd-spike` shows up as a sibling skill (installed via `npx get-shit-done-cc --hermes`), prefer **`gsd-spike`** when the user wants the full GSD workflow: persistent `.planning/spikes/` state, MANIFEST tracking across sessions, Given/When/Then verdict format, and commit patterns that integrate with the rest of GSD. This skill is the lightweight standalone version for users who don't have (or don't want) the full system.

## Core method

1. **Set a time budget** — spikes are disposable. 15-30 minutes max.
2. **Define the question** — what exactly are you validating?
3. **Build the minimum** — just enough to answer the question
4. **Document the verdict** — Does it work? What's the tradeoff?
5. **Throw it away** — don't carry spike code into production

## Spike Output Format

```
## Spike Verdict: [Question]

### Approach Tried
[What you built]

### Findings
[What you learned]

### Recommendation
[Go / No-Go / Need More Info]

### Time Spent
[Minutes]
```

## Integration with other skills

- Use `plan` for production implementation after spike validates the approach
- Use `subagent-driven-development` to delegate spike exploration
- Use `test-driven-development` once moving from spike to production