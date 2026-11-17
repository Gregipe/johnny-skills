---
name: development-workflow
description: Development methodology skills — spikes, code cleanup, and peer review workflows
---

# Development Workflow

This skill covers three essential development practices: exploratory spikes, code simplification, and peer review. Load the appropriate section based on the task.

## Spikes — Throwaway Experiments

Use when the user wants to **feel out an idea** before committing to a real build — validating feasibility, comparing approaches, or surfacing unknowns.

**Trigger phrases:** "let me try this", "I want to see if X works", "spike this out", "before I commit to Y", "quick prototype of Z", "is this even possible?", "compare A vs B"

**When NOT to use:**
- The answer is knowable from docs or reading code — just do research
- The work is production path — use the `plan` skill instead
- The idea is already validated — jump straight to implementation

### Core Method

1. **Set a time budget** — spikes are disposable. 15-30 minutes max.
2. **Define the question** — what exactly are you validating?
3. **Build the minimum** — just enough to answer the question
4. **Document the verdict** — Does it work? What's the tradeoff?
5. **Throw it away** — don't carry spike code into production

### Spike Output Format

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

---

## Simplify Code — Parallel Review & Cleanup

Use when the user wants to clean up recent changes with multiple focused reviewers running in parallel.

**Trigger phrases:** "simplify", "simplify my changes", "review my code", "review my recent changes", "/simplify"

### Core Method

Three narrow reviewers beat one broad reviewer. Each deeply searches for a single class of problem:

1. **Reuse Reviewer** — finds duplicated code, opportunities for abstraction
2. **Quality Reviewer** — finds anti-patterns, unclear naming, missing docs
3. **Efficiency Reviewer** — finds unnecessary loops, redundant operations, O(n²) patterns

Run all three in parallel via delegate_task, aggregate findings, apply fixes worth applying.

---

## Code Review — Pre-Commit Checklist

Use before any code is committed to ensure quality and security gates pass.

**Trigger phrases:** "review this", "can you look at", "pre-commit review"

### Pre-Commit Checklist

- [ ] Security scan passed (no secrets, no injection vulnerabilities)
- [ ] Quality gates passed (lint, type check, tests)
- [ ] Auto-fix applied (formatter, import organizer)
- [ ] Changes are focused (one feature/fix per commit)
- [ ] Commit message describes the "why", not just the "what"

### Review Focus Areas

1. **Correctness** — does it do what it's supposed to?
2. **Edge cases** — what happens with null, empty, huge inputs?
3. **Security** — any injection, exposure, or auth gaps?
4. **Performance** — any obvious O(n²) or unnecessary calls?
5. **Maintainability** — is the code understandable?

---

## Next.js Local Dev — Build/Dev Server Conflict

**Never run `next build` while `next dev` is serving the same project directory.** The build rewrites `.next` chunks that the running dev server holds open; the next route hit 500s with `MODULE_NOT_FOUND './NNN.js'` (chunk ids are arbitrary). The page also serves stale HTML.

- After any `next build`, ALWAYS restart `next dev` (kill + start fresh).
- New API routes/files added mid-dev normally hot-reload — a route 404/500 that previously worked means the module graph was corrupted, restart dev before debugging the code.
- Started with `NODE_ENV=production` in the shell, dev serves a broken stale bundle — always launch dev with explicit `NODE_ENV=development PORT=NNNN`.

## Related Skills

- `test-driven-development` — RED-GREEN-REFACTOR TDD cycle
- `systematic-debugging` — root cause analysis before fixing
- `plan` — production implementation planning
- `subagent-driven-development` — delegating to subagents
