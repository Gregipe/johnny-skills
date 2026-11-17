---
name: development-methodology
description: Core software development methodologies — systematic debugging (4-phase root cause analysis) and test-driven development (RED-GREEN-REFACTOR cycle). Covers investigation protocols, TDD workflow, and integration patterns.
---

# Development Methodology

This skill covers the two foundational development practices that ensure high-quality, maintainable code: systematic debugging and test-driven development.

## Systematic Debugging

> **Content absorbed from `systematic-debugging`.**

### The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

If you haven't completed Phase 1, you cannot propose fixes.

### The Four Phases

#### Phase 1: Root Cause Investigation

**BEFORE attempting ANY fix:**

1. **Read Error Messages Carefully** — Don't skip past errors or warnings
2. **Reproduce Consistently** — Can you trigger it reliably?
3. **Check Recent Changes** — What changed that could cause this?
4. **Trace Data Flow** — Where does the bad value originate?

**Key techniques:**
- Reason backward from stack trace, not forward from changes
- Use `search_files` to find error strings in codebase
- Check env vars / API keys / credentials first for auth issues

#### Phase 2: Pattern Analysis

- Find working examples in the same codebase
- Compare against references
- Identify differences

#### Phase 3: Hypothesis and Testing

- Form single hypothesis: "I think X is the root cause because Y"
- Test minimally — one variable at a time
- Verify before continuing

#### Phase 4: Implementation

- Create failing test case first
- Implement single fix
- Verify fix works

**Rule of Three:** If 3+ fixes failed, question the architecture.

### Investigation Tools

- `search_files` — Find error strings, trace function calls
- `read_file` — Read source code with line numbers
- `terminal` — Run tests, check git history
- `web_search`/`web_extract` — Research error messages, library docs

### Debugging Patterns

See `references/` for session-specific details:
- `references/llm-api-truncation-detection.md` — LLM response truncation
- `references/server-rendered-js-debugging.md` — Client-side JS in server-rendered pages
- `references/silent-scheduler-failure.md` — Scheduler crashes
- `references/parallel-code-paths.md` — Multi-entry-point analysis
- `references/sqlite-unexplainable-state.md` — DB state investigation

## Test-Driven Development

> **Content absorbed from `test-driven-development`.**

### The Iron Law

```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

Write code before the test? Delete it. Start over.

### Red-Green-Refactor Cycle

#### RED — Write Failing Test

Write one minimal test showing what should happen:
- Clear descriptive name
- One behavior per test
- Real code, not mocks (unless truly unavoidable)

#### GREEN — Minimal Code

Write the simplest code to pass the test:
- Nothing more
- Hardcode return values OK in GREEN
- Skip edge cases — fix in REFACTOR

#### REFACTOR — Clean Up

- Remove duplication
- Improve names
- Extract helpers

Keep tests green throughout.

### Why Order Matters

Tests written after code pass immediately. Passing immediately proves nothing:
- Might test the wrong thing
- Might test implementation, not behavior
- Might miss edge cases

Test-first forces you to see the test fail, proving it actually tests something.

### ARA-Specific Patterns

See `references/testing-fastapi-sqlalchemy.md` for:
- Local import patching
- Background thread handling
- E2E smoke test template
- DB fixture patterns

## Integration with Hermes

### With delegate_task

```python
delegate_task(
    goal="Implement [feature] using strict TDD",
    context="Follow test-driven-development skill: RED → GREEN → REFACTOR"
)
```

### With Bug Fixes

Bug found? Write failing test reproducing it. Follow TDD cycle. The test proves the fix and prevents regression.

## Common Rationalizations to Avoid

| Excuse | Reality |
|--------|---------|
| "Too simple to test" | Simple code breaks. Test takes 30 seconds. |
| "I'll test after" | Tests passing immediately prove nothing. |
| "Already manually tested" | Ad-hoc ≠ systematic. No record, can't re-run. |
| "TDD will slow me down" | TDD faster than debugging. |

## Red Flags

- Code before test
- Test passes immediately on first run
- Can't explain why test failed
- Rationalizing "just this once"

**All mean: Delete code. Start over with TDD.**
