# Debug Timing Notes

## Validate endpoint takes ~20-30s via browser
The `/api/cadence/validate` endpoint makes an LLM call (~20-30s with full prompt data). This means:

- **browser_console tool** has a 30s timeout — test with minimal `promptParts` (e.g. `{brandPersonality:{tone:"warm"}}`) if you need a quick response
- **curl** from terminal works fine — just set `--max-time 30`
- The page shows "⏳ Compiling prompt..." during the wait — this is expected behavior, not a hang
- If "⏳ Compiling prompt..." stays indefinitely (>60s), check:
  1. Is the server process alive? `curl -s http://localhost:8766/`
  2. Is the LLM provider responding? Check `call_llm` in `induction_engine.py`
  3. Is a previous recursive call stuck? Kill and restart server

## Recursive loop diagnostic
If multiple overlapping validate calls are suspected:
```bash
grep 'api/cadence/validate' /tmp/ara-server.log
```
Multiple entries within seconds → recursive loop. Fix: remove `switchPbTab('final')` from `validateAndCompilePrompt()` success handler.
