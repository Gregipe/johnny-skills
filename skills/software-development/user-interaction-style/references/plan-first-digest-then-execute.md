# Plan-First: Digest, Then Execute

## The Pattern

When Greg provides a multi-phase plan (e.g., an advisor prompt with multiple fixes), the expected workflow is:

1. **Read and digest** the full plan before acting
2. **Acknowledge understanding** — "Digested. Ready for..."
3. **Wait for go-ahead** — Greg will give explicit signal to proceed
4. **Execute one fix at a time**, in strict order
5. **Gate each fix** — run gate tests after each fix; do NOT proceed to next fix until gates pass
6. **Never batch** — don't apply multiple fixes together

## Frustration Signals

- **"Do not build anything. Just read this."** — Stop immediately. The plan is for digestion only. Acknowledge and wait.
- **"I will give you four specific fixers for you to apply one after the other."** — Greg will hand out fixes sequentially. Don't jump ahead.
- **"After each fix, run that fix's gate test and confirm it passes before proceeding. Do not batch them. Do not skip a gate."** — Explicit gate discipline. Every fix gets its own verification before the next.

## Contrast With Action-First

This is NOT contradictory with Action-First. The distinction:

- **Plan-First (Digest):** When Greg provides a complex, multi-step plan crafted by an advisor/expert, he has already done the thinking. Your job is to execute faithfully with gates.
- **Action-First:** When Greg gives a simple instruction, execute immediately. Don't over-analyze.

The signal: if Greg provides a structured plan with numbered fixes and gate tests, enter Plan-First mode. If he says "update the due date," enter Action-First mode.

## Gate Discipline

Each gate test must be reproducible and explicit. The advisor's gate format:
- Specific input → specific assertion
- Pass/fail binary
- If gate fails: STOP and report. Do NOT proceed to the next fix.

This ensures each fix can be verified independently. Batched fixes make it impossible to identify which fix broke which behavior.
