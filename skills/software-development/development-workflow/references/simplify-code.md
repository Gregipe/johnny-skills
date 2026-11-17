# Simplify Code — Parallel Review & Cleanup

Review your recent code changes with three focused reviewers running in parallel, aggregate their findings, and apply the fixes worth applying.

**Core principle:** Three narrow reviewers beat one broad reviewer. Each one deeply searches the codebase for a single class of problem — reuse, quality, efficiency — without diluting its attention across all three. They run concurrently, so you pay the latency of one review, not three.

## When to Use

Trigger this skill when the user says any of:

- "simplify" / "simplify my changes" / "simplify these changes"
- "review my code" / "review my recent changes" / "clean up my changes"
- "/simplify" (if they're carrying the Claude Code habit over)

## The Three Reviewers

### 1. Reuse Reviewer

Searches for:
- Duplicated code patterns
- Opportunities for function extraction
- Repeated logic that could be shared
- Magic numbers that should be constants

### 2. Quality Reviewer

Searches for:
- Unclear variable/function names
- Missing docstrings or comments
- Complex conditionals that could be simplified
- Functions that are too long

### 3. Efficiency Reviewer

Searches for:
- Unnecessary loops or redundant operations
- O(n²) patterns that could be O(n)
- Repeated API calls that could be batched
- Inefficient data structures

## Workflow

1. Run all three reviewers in parallel via delegate_task
2. Aggregate findings into a single report
3. Apply fixes worth applying (prioritize high-impact)
4. Verify tests still pass after changes

## Integration with Other Skills

- Use `test-driven-development` before making changes to ensure test coverage
- Use `systematic-debugging` if issues are discovered during review
- Use `requesting-code-review` for formal pre-commit review