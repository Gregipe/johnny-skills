# ARA Prototype Build — May 2026 Session Reference

This document captures the key debugging stories and techniques discovered during the Autonomous Revenue Agent (ARA) prototype build in May 2026. Use this as a reference when similar patterns appear.

## 1. The "Skills Lost" Bug (API Path Mismatch)

**Symptom:** After server restart, the induction UI showed "0 facts" and the sidebar displayed stale data. Greg reported "my skills seem lost."

**Root Cause:** The frontend JavaScript called `/api/induction/{id}/state` but the backend endpoint was registered at `/induction/chat/{id}/state` (no `/api` prefix). The 404 was silently swallowed by `catch(e) {}`.

**Lesson:** API URL path prefixes must match exactly between frontend and backend. Decide on ONE convention at the start and stick to it. The induction endpoints were split between `/api/induction/` and `/induction/chat/` — this inconsistency caused the bug.

**Fix:** Corrected the frontend fetch URL. Added `console.warn` and `console.error` to the catch block instead of silent swallow.

## 2. The Broken Initial Message (Python→JS Escaping)

**Symptom:** The entire inline `<script>` block silently failed. `loadState`, `updateUI`, `sendMsg` were all undefined. The page rendered but was completely non-interactive.

**Root Cause:** `\\'` inside a Python triple-quoted string (`"""..."""`) gets processed by Python. The sequence `\\\\'` becomes `\\'` in the string value, but the rendering path strips the backslash, producing invalid JavaScript: `You've` instead of `You\\'ve`. This breaks the single-quoted JS string containing an apostrophe.

**Detection:** The browser console shows `Unexpected identifier 've'` and empty JS errors. All functions defined after the bad line are undefined. `typeof loadState === 'undefined'` was the tell.

**Fix:** Rewrite to avoid apostrophes in single-quoted JS strings when embedded in Python:
- `You've` → `You have`
- `Let's` → `Let us`
- `I'll` → `I will`
- `Don't` → `Do not`

**Verification:** After writing JS inside Python triple-quoted strings, curl the rendered page and check for missing backslash characters in the output.

## 3. Server Restart Process Management

**Symptom:** Background processes accumulated after context compression. Killing and restarting led to port binding failures (`address already in use`). Launcher script mitigated this.

**Key commands:**
```bash
# Clean up zombies
lsof -ti:8766 | xargs kill -9 2>/dev/null
sleep 2
lsof -ti:8766 2>/dev/null || echo "Port clear"

# Verify new process
curl -s -o /dev/null -w "%{http_code}" http://localhost:8766/
```

**Launcher pattern:**
```bash
#!/bin/bash
export DEEPSEEK_API_KEY="sk-..."
cd /Users/greg/ara
while true; do
    /venv/bin/python -u server.py 2>&1
    sleep 2
done
```

## 4. Continue vs Start Induction (State-Dependent UI)

**Problem:** The button always said "Start Induction" and navigated to Module 1 regardless of actual progress. Greg: "the CTA is Start Induction - it should be Continue Induction."

**Three layers that must all be state-aware:**
1. **Button text** — "Start Induction" (0 skills) vs "Continue Induction" (1+ skills)
2. **Tab navigation** — Always open the first incomplete module, not always Proposition
3. **Welcome message** — Show a module-specific question, not generic "send your first answer"
4. **LLM system prompt** — Tell the LLM which module to start with, derived from DB state

**Implementation pattern:**
```javascript
// Frontend: find first incomplete module
function startInduction() {
    var target = 'proposition';
    for (var m of window._moduleState) {
        if (!m.covered) { target = m.category; break; }
    }
    switchTab(target);
}
```

```python
# Backend: tell LLM the right module
next_idx = min(skills_state['covered_count'], skills_state['total_modules'] - 1)
next_module = skills_state['modules'][next_idx]
module_instruction = f"Start with Module {next_idx + 1}: {next_module['name']}"
```

## 5. LLM Self-Reporting is Unreliable for State

**Problem:** The LLM said "module complete" but no skills were actually saved in the database. The induction had zero persisted data.

**Root Cause:** The extraction regex wasn't prominent enough in the system prompt. The LLM didn't emit `[SAVE_SKILL]` blocks at all.

**Fix:** 
- Use extremely visible block delimiters: `===SAVE_SKILL===\n{...}\n===END_SAVE_SKILL===`
- Validate state against DB, not against LLM self-report
- Require minimum skill count per module before marking complete
- Print the `===` blocks in the system prompt as raw examples

## 6. Error Message Hygiene

**Problem:** The induction engine returned `"DEEPSEEK_API_KEY not set"` as a user-facing error message. Greg: "Could you not blast the message about DeepSeek API key etc to the user? It should be a more dignified error."

**Fix:** All user-facing errors must be clean and generic. No provider names, API keys, status codes, or stack traces. See `web-prototype-building` SKILL.md for the full error message table.

## 7. The One-File Trap (write_file vs patch)

**Problem:** `write_file` was used intending to replace a section of server.py, but it overwrote the ENTIRE file, destroying 600+ lines of code.

**Fix:** Always use `patch()` for targeted changes. Read the full file first with `read_file` to get exact context. Only use `write_file` for NEW files. If you do accidentally destroy a file, you know the architecture well enough to rebuild — but it costs time.
