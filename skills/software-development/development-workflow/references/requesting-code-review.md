# Pre-Commit Code Review Checklist

Use this skill before any code is committed to ensure quality and security gates pass.

## When to Use

Trigger when user says:
- "review this" / "can you look at this"
- "pre-commit review"
- "before I push"

## Pre-Commit Checklist

### Security
- [ ] No secrets, API keys, or credentials in code
- [ ] No injection vulnerabilities (SQL, command, XSS)
- [ ] Proper input validation on all user inputs
- [ ] Authentication/authorization checks in place

### Quality Gates
- [ ] Lint passed (flake8, eslint, etc.)
- [ ] Type check passed (mypy, TypeScript, etc.)
- [ ] Tests passed (unit + integration)
- [ ] Auto-format applied (black, prettier, etc.)

### Code Quality
- [ ] Changes are focused (one feature/fix per commit)
- [ ] Commit message describes the "why", not just the "what"
- [ ] No debug code or print statements left behind
- [ ] Error handling is appropriate (not too broad, not too narrow)

### Review Focus Areas

1. **Correctness** — does it do what it's supposed to?
2. **Edge cases** — what happens with null, empty, huge inputs?
3. **Security** — any injection, exposure, or auth gaps?
4. **Performance** — any obvious O(n²) or unnecessary calls?
5. **Maintainability** — is the code understandable?

## Integration with Other Skills

- Use `test-driven-development` to ensure tests exist before review
- Use `simplify-code` for parallel 3-agent cleanup before formal review
- Use `systematic-debugging` to investigate any issues found