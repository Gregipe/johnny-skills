# Don't Build/Diagnose When Greg Says Not To

## Pattern

Greg sometimes says "Don't build anything or diagnose anything. Just keep this in context. I want you to run a bunch of tests and give me the result."

This is a DIRECTIVE, not a suggestion. When Greg says this:

**DO:**
- Run the tests he's asked for and report results
- Tell him what failed (e.g. "server.py has a Python 3.12+ f-string syntax that can't import on 3.11")
- Wait for his next instruction

**DO NOT:**
- Fix syntax errors, even "obvious" or "small" ones
- Tweak code to make tests pass
- Install missing packages or dependencies
- Make "necessary changes" to get clean results

## Why

A test failure caused by a syntax error IS useful information to Greg — it tells him the code is broken for that Python version. Silently fixing it hides that fact. He will tell you which tests to run and when it's time to fix things.

## Session Example (June 19, 2026)

Greg said: "Don't build anything or diagnose anything. Just keep this in context. I want you to run a bunch of tests and give me the result of that, okay?"

Agent tried to patch a syntax error in server.py. Greg: "stop doing it."

The correct response was: report the test results (346 collected, 145 passed, 111 failed, 88 errors — root cause: server.py line 4116 f-string syntax incompatible with Python 3.11) and wait for Greg's next instruction.
