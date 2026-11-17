# Trace Before Declaring a Root Cause (June 2026)

Greg's engineering mindset: he pushes back on premature conclusions. When debugging, do NOT jump to "found it" on the first plausible cause. He will ask "ARE YOU sure?" — and he's usually right to be skeptical.

## The Pattern

**Session trigger**: Agent said "Found it — the crash is due_at=string" after seeing the traceback. Greg: "ARE YOU sure this is the issue?" This forced a full code-path trace that revealed three corroborating signals, not just one.

## Correct Debugging Workflow

1. **Trace the FULL code path** end-to-end:
   - LLM output → system prompt → tool schema → handler → DB INSERT → exact line
2. **Find MULTIPLE corroborating signals**:
   - Log entries, DB state, the exact line number and parameters from the traceback
   - Never rely on a single signal
3. **Present the evidence chain**, not just the conclusion:
   - "Here's the tool schema telling the LLM to output YYYY-MM-DD (line 5018). Here's the handler passing it straight to SQLAlchemy (line 3488). Here's the crash at db.commit() with the exact parameter. These three points prove the chain."
4. **If the trace is incomplete, say so** — don't fill gaps with assumptions

## Anti-Pattern

> "The crash says due_at is a string → that's the bug."

This skips: what told the LLM to output a string? Where does the string enter SQLAlchemy? Is this the only path, or are there multiple codepaths with the same issue?

## Correct Pattern

> "Here's the evidence chain: (1) tool schema line 5018: `due_at: "YYYY-MM-DD"` tells the LLM to output strings. (2) handler line 3488: `due_at=args.get("due_at")` passes it directly. (3) crash at db.commit() on line 3491 shows the exact INSERT with `due_at='2026-06-16'`. These three signals prove the root cause. Fix: parse date strings in the handler."
