---
name: systematic-change-workflow
description: >
  Mandatory pre-flight checklist for ANY cross-cutting change.
  Load before touching UI, API, DB, or deployment.
  Follow every step. Do not skip. Do not call "done" until all checks pass.
---

# Systematic Change Workflow

## Companion: `test-first-release`

Load this skill AND `test-first-release` BEFORE starting any ARA production change session. Order:

1. **`systematic-change-workflow`** — map the chain, enumerate risks, identify all entry points
2. **`test-first-release`** — identify test coverage gaps, write RED tests for the affected layer, THEN code

The two skills together cover the full workflow: pre-flight analysis → test-first implementation → verification → deploy.

## When to load this skill
- Any change touching >1 file
- Any change to save/publish/persistence logic
- Any change to the prompt builder, cadence template, or API endpoints
- Any deployment / server restart

## Phase 0: Map the Chain

Before writing a single line of code, trace the full chain:

```
click/handler → function call → API endpoint → DB write → response → 
callback → localStorage → page reload → initialization → API fetch → 
apply to DOM
```

For each link, write:
- What file/function handles it?
- What could go wrong? (null element, failed fetch, stale cache, overwrite)
- How will I verify it?

## Phase 1: Before Code

- [ ] Is the server running the latest code? Check PID start time vs git commit time: `ps -p $(pgrep -f '...server.py$') -o lstart=` vs `git log -1 --format='%ai'`. If PID started BEFORE the commit, restart.
- [ ] Verify the browser isn't serving cached JS — check via `fn.toString().includes('expected-pattern')` in console. Server-rendered HTML (Jinja2 templates) can also be cached by the browser. Use `?cb=1` cache-busting on the URL if needed.
- [ ] Map all surfaces — list every file, function, and API endpoint data flows through
- [ ] **Audit both code paths** — For any data operation (create/update/delete), check BOTH the REST API route handler AND the agent `execute_tool()` handler. They are independent implementations in `server.py` and can silently diverge. The REST route might have validation/duplicate-checking/auth that the tool handler lacks, or vice versa. `grep -n 'def execute_tool\|@app\.\(post\|put\|delete\|get\)'` to find both sides.
- [ ] Identify all cached/stale data sources — browser cache, localStorage, Python import cache, server process
- [ ] List all verification points — how will I verify each link?

## Phase 2: During Code

- [ ] Change one link at a time — fix, verify, move on
- [ ] Validate compilation immediately — `py_compile.compile(file, doraise=True)` after every edit
- [ ] Restart server explicitly — `pkill -f "venv/bin/python server.py"` then `nohup ./venv/bin/python server.py &`
- [ ] Verify server serves changes — `curl -s ... | grep -c '<marker>'`
- [ ] Hard refresh browser — Cmd+Shift+R, verify via `performance.getEntriesByType('resource')`

## Phase 3: After Code — Full Round Trip

- [ ] API works — `curl -X POST ...` directly, check response body
- [ ] DB persisted — query database, confirm value matches
- [ ] Browser shows success — status message appears in DOM
- [ ] localStorage updated — `localStorage.getItem('ara_cadence_data')` has the value
- [ ] Page reload preserves data — navigate away, back, check data is there
- [ ] Data not overwritten by other loads — verify prefill/API calls on init don't clobber saved data
- [ ] JS function source matches expected fix — `fn.toString().includes('expected-code')` in browser console

## Phase 4: Commit & Deploy

- [ ] Commit message describes the full chain, not just the symptom
- [ ] Pushed + confirmed — `git push`, verify remote has the commit
- [ ] Server restarted AFTER push — verify PID matches post-push time
- [ ] Tell user: "Hard refresh Cmd+Shift+R needed" or what they must do

## Common Failure Modes (from real debugging)

| Failure | Sign | Fix |
|---------|------|------|
| Stale Python module | Server uses old code from import cache | Full server restart |
| Browser script cache | JS changes not visible | Cmd+Shift+R hard refresh; verify via `fn.toString()` |
| Prefill overwrites draft | Data there on save, gone on refresh | Deep merge, don't assign |
| Promise chain swallows errors | No error shown, nothing happens | Add .catch() to every fetch |
| Multiple save buttons | User clicks wrong one | Give each button a unique ID |
| Undefined scope variable | Function silently crashes | Add `var pb = ...` at top of each function |
| Stale server PID | Old process still serving | `pkill -f` (more specific). Check PID start vs file mtime via `ps -p <pid> -o lstart=` + `ls -l <file>` |
| Local import shadows module-level name | UnboundLocalError: cannot access local variable 'X' where it is not associated with a value | **Root cause:** `from module import X` inside function body creates a LOCAL variable that shadows the module-level import. Python treats ALL references to `X` in that function as local. Code paths that read `X` before the import line executes raise UnboundLocalError. **Fix:** Remove the redundant local import — the module-level import already exists. If truly needed only in one function, use `import module; module.X` syntax instead. **Hunting pattern:** Search for `from.*import` inside function bodies where the same name exists at module level. **This hit TWICE in a single ARA debugging session** (email_utils.py: plain-text email `msg` variable not assigned in else branch; server.py: `from database import Conversation` inside `get_summary` handler). Always check that every code path assigns the variable before it's read — Python doesn't warn about this at module load time. |
| Python `.strip()` on dict | API returns `{status:"error"}` silently, save chain stops | Check `isinstance()` before `.strip()` on values that might be dicts |
| Validate endpoint is a save-gate | Save button flashes then resets, no feedback | Save calls validate FIRST; if validate returns error, save-draft never runs |
| migrateToGlobalPromptParts clears promptParts | Data there on save, gone on page load. localStorage has `promptParts: {}` | Remove the clearing loop — the full-screen Prompt Builder reads from `t.promptParts`, not `globalPromptParts` |
| prefillFromInduction overwrites saved data | Loaded data shows prefill values instead of user's saved values after refresh | Add early-return guard: skip prefill if `t.promptParts` already has brand data |
| Server errors hidden from browser | No console errors, but save fails | Server returns 200 with `{status:"error"}` — check API response body, not just HTTP status |
| Feedback element missing from HTML | Save works (API+DB+localStorage) but user sees nothing | Verify status element exists in the DOM |
| Helper function under route decorator | Python error: helper defined where route handler expected - decorator applies to wrong function | Place helper functions ABOVE the decorator, not between it and the handler |
| Helper function under route decorator | Python error: helper defined where route handler expected — decorator applies to wrong function | Place helper functions ABOVE the `@app.route(...)` decorator, not between it and the handler |
| Surface audit gap | You change one file but miss the 3 other files that reference it — imported templates, lifespan migrations, frontend JS | Phase 0 "map the chain" must enumerate EVERY file/function/endpoint the feature touches. After writing code, run `grep -r 'newFunction\\|newSymbol'` across the project to catch missed surfaces. Greg's #1 frustration is "we cannot spend 2 hours debugging basic syntax or overlooked issues" — a full surface audit is not optional. |
| Systematic pattern leak | Greg: "this [X] thing either has not been coded in very well or generically enough or you've just missed a lot of places." You've been patching individual occurrences instead of finding ALL instances. | **Load `references/systematic-pattern-audit.md`** — the "grep all, fix all, verify zero" technique. Find every occurrence with grep, categorize, fix all at once with replace_all or a Python script, then verify zero remain. Never deploy with known leaks. Anti-pattern: fix one, deploy, user finds another, repeat. |
| Datetime timezone leak (ARA-specific) | API returns `due_at: "2026-06-16T03:30:00Z"` (UTC), reminder says "due 2026-06-16 03:30", dashboard shows times 5.5h off | **Load `references/datetime-timezone-leak-pattern.md`** — three leak patterns: `.isoformat()+"Z"`, `.strftime()` on naive UTC, `str(dt)[:N]`. Fix: `to_ist()` for API, `(dt+IST_OFFSET).strftime()` for text, `datetime.now(IST_TZ)` for "now". Audit command included. |
| Mirrored/duplicate UI implementations (ARA-specific) | You fix the prompt builder in cadence_template.py for 2 hours while the user is using prompt_builder_template.py. Same bug exists in both files with different function names and data flows. | Before changing any UI feature, run `grep -rn 'overlay|open.*Builder|open.*Editor|Overlay|PromptBuilder' /Users/greg/ara/*.py` to find ALL template files that implement similar functionality. The ARA codebase has THREE prompt builder files (cadence_template.py, prompt_builder_template.py, prompt_editor_mod.py) — editing the wrong one produces ZERO visible change for the user. After finding all implementations, verify which one the user actually interacts with by checking which overlay has display:flex/fixed CSS and which onclick handler the button calls. |
| Full-file rewrite breaks working features | You corrupted a file with replace_all, git checkout reverted to old version, then full rewrite introduced path mismatches (sidecar used `/react` instead of `/api/react`) that silently broke reactions and typing | NEVER full-file-rewrite production code. Always use targeted patch() calls. If git checkout is needed to recover from corruption: (1) re-read the ACTUAL running code (not git's version) to learn endpoint paths and conventions, (2) verify what the SERVER calls before writing the handler, (3) test the fix chain end-to-end before cleaning up debug logging. A partial restore + re-apply of patches is always safer than rewriting from scratch. |

| LLM overuse for trivial string ops | Prompt builder "Final" tab called `/api/cadence/validate` which sent ALL prompt parts to DeepSeek just to concatenate them in order (Brand → Objective → Sector → Security → Channels). Every view cost tokens for a string join. Same pattern: using an LLM to sort, format, or join data that could be done with native code. | **Don't use an LLM for operations that pure code can do.** Concatenation, sorting, formatting, filtering, and aggregation should be done client-side or server-side in Python/JS. Reserve LLM calls for tasks that need reasoning: contradiction detection, semantic analysis, content generation. When in doubt, ask: "Is there a native way to do this that doesn't burn tokens?" If yes, use that. The user's reaction to this pattern: "waste of tokens... that's horrible." |

| Manually-maintained allowlists go stale (ARA-specific) | `data_modifying_tools` set missing `create_lead` — the single most common data-modifying operation was absent from the voice-note gate. The set existed, was maintained during initial build, but when execute_tool's bulk migration added new ToolResult returns, the set wasn't revisited. A voice note with `[TOOL_CALL: create_lead]` bypassed confirmation and created the lead instantly. | When adding/refactoring any tool, grep for ALL manually-maintained sets/lists that reference tools: `grep -rn '\"create_lead\"\\|data_modifying_tools\\|AUTO_APPROVE_TOOLS' server.py`. Add new tools to EACH set they belong in. The `data_modifying_tools` set in agent_chat must include EVERY tool that creates or updates lead/deal/message data. It doesn't inherit from the tool registry — it's a separate declaration. |
| Regex serialization format mismatch | `[TOOL_CALL:]` marker changed from flat format (`create_lead(name="John")`) to JSON (`{"tool": "create_lead", "args": {"name": "John"}}`). The strip regex `r'\[TOOL_CALL:\s*\{.*?\}\s*\]'` used non-greedy `{.*?}` which matched the INNER `}` of nested JSON, leaving trailing `}]` unmatched — the entire match failed and the raw `[TOOL_CALL:]` leaked into the user-facing response. | When changing any SERIALIZATION FORMAT (flat → JSON, XML → YAML, text → structured), grep for ALL regex patterns, parsers, and strip functions that operate on the old format. Update each one. The most common hit: `grep -rn 'TOOL_CALL.*\\\\['` or search for the format marker across all `.py` files. Test with nested structures (objects within objects) — if the regex uses `.*?` non-greedy between delimiters, it breaks on nesting. |
| Regression from removing a complex subsystem | You replace a working subsystem (e.g., a 2-LLM-call follow-up pipeline) with a simpler single-call approach. 3 bugs appear immediately because the old code had invisible edge cases: error diagnosis, SUGGEST_DEAL injection, natural language synthesis, fallback handling — none were obvious from reading the code. | **Before cutting any subsystem, enumerate every output it produces and every edge case it handles.** The follow-up pipeline had 4 responsibilities beyond "rephrase": error diagnosis, deal suggestion, fallback on crash, and synthetic natural language. Removing it silently dropped all 4. Trace every conditional branch in the old code (if/elif patterns with separate follow-ups per error type, per result marker, per success condition). For each, ask: "Is this handled in the replacement?" Only remove the old code when all branches are covered. A design review with a code advisor (see `writing-plans` skill, Step 2.5) typically catches these gaps before code is written.

| Stale notification count from orphaned refs | Bell icon showed 34 notifications. Root cause: `action_scheduled` notifications linked to ScheduledActions that were already `completed`. Action had fired days ago but the notification was still unacknowledged and counted. Also: `action_failed` notifications from before sidecar was working (stale >24h). | **A notification count that feels wrong is almost always counting records whose underlying ref is stale.** Debug pattern: (1) Query the raw notification records by type, (2) For each ref_type/ref_id, check if the referenced record is still in an actionable state (pending/firing not completed/cancelled), (3) Filter out notifications that link to dead refs OR are informational-only types (synthesis_ready). The design principle from Greg: "the bell should only show items that are new AND open — requiring action, not just informational." Apply this filter to BOTH the notification list endpoint AND the unread count in stats. |

| Two code paths (REST vs tool handler) | Data validation/filtering works on the REST route but silently fails on the agent tool-call path, or vice versa. **Example from ARA:** `check_duplicate_lead()` was called in the REST `create_lead` route handler (line 631) but NOT in the `execute_tool('create_lead', ...)` handler (line 3240). A voice note → Whisper → agent_chat → [TOOL_CALL: create_lead] created a duplicate lead with no error, because it went through the unguarded path. The test suite only tested the REST route. | **Before any data-modifying change, enumerate all entry points: (1) the REST route (FastAPI decorator), (2) the tool handler (execute_tool switch), (3) any internal calls (scheduler, webhook, voice pipeline).** For each, check if the validation/duplicate-check/auth applies. Use `grep -n '\"create_lead\"'` or similar to find tool-call references. Add a test for EACH path — don't assume coverage of one covers the other. In ARA specifically: `grep -n 'def execute_tool\|@app\\.\\(post\\|put\\|delete\\)' server.py` to enumerate both sides. |

| Overwriting .env or config files without reading first | Server works fine, then after restart DeepSeek returns 401, Gmail breaks, or other env-dependent features fail. `grep DEEPSEEK_API_KEY /opt/ara/.env` returns nothing — the file was replaced with partial content. **Example:** `write_file` on `/opt/ara/.env` replaced the full file (DEEPSEEK_API_KEY + GOOGLE creds + TAVILY) with only GOOGLE creds. Lost API key, server fell back to deprecated key, everything broke after restart. | **Before writing any env file:** `cat <path>` to see what's there. If the file already has secrets, APPEND don't overwrite (`echo "NEW_KEY=val" >> <path>`). After any env change, verify: `grep <KEY_NAME> <path>`. For systemd services with `EnvironmentFile`, the env file is THE authoritative source — it takes precedence over `load_dotenv` paths. Never create an env file from scratch when one already exists. Use skill_manage or targeted `echo >>` appending. |

## Remote Server Modification Pattern (June 2026 — ARA Hetzner)

When modifying code on a **remote production server** (SSH to root@ip, files at /opt/ara), the local-editing approach used for dev work doesn't apply. Use this pattern.

### The Pattern

1. **Write the edit script locally** — Use `write_file` to create a Python script in `/tmp/`. The script reads/writes the file using Python `open()`, not shell commands. This avoids all ssh-quoting issues.
2. **scp to server** — `scp /tmp/script.py root@host:/opt/ara/script.py`
3. **Run on server** — `ssh root@host 'cd /opt/ara && python3 script.py 2>&1'`
4. **Verify syntax** — `ssh root@host 'cd /opt/ara && python3 -c "import py_compile; py_compile.compile('target_file.py', doraise=True); print('OK')"'`
5. **Cleanup** — `ssh root@host 'rm /opt/ara/script.py'` (or let git track them, then `git rm` after)

### When to use write_file + scp vs terminal heredoc

| Approach | When | Danger |
|----------|------|--------|
| `write_file` + `scp` + `ssh` run | Multi-file changes, any Python with complex string literals | Works; always prefer |
| `terminal("python3 << 'XEOF'")` | Single-line fixes, no complex quotes | Heredoc quoting breaks with nested single quotes, f-strings with `\` escapes, Unicode escape sequences |
| `terminal("sed -i ...")` | Simple text replacement, no special chars | `sed` with Python literals is quote-hell |
| `patch()` tool | Single-file change **on local machine** | Does NOT work on remote files |

### Bulk migration in passes

When you need to change many call sites on a production server (e.g., adding a `params` kwarg to every `ToolResult.fail()` call, or converting all string returns to objects):

1. **Write a scanner first** — A Python script that finds all unmigrated patterns (`grep -n 'return f"✅'` or similar). Run it to get the baseline count.
2. **Group changes by pattern** — Don't try to change everything in one script. Use passes:
   - **Pass 1**: Basic/catch-all patterns (e.g., all `"Error: missing_arg"` → `ToolResult.fail("MISSING_ARG", params={"field": ...})`)
   - **Pass 2**: Specific patterns that need custom handling (archived leads, unreachable contacts)
   - **Pass 3**: Edge cases that the first two passes missed (emoji-based success returns, exception handlers)
3. **Re-scan after each pass** — Re-run the scanner to see what's left. Stop when count hits zero.
4. **Fix tests after each pass** — Changing a function's return type (string → ToolResult) breaks any test that does `assert "emoji" in result`. Fix these inline before running QA:
   - Old: `assert "✅" in result`
   - New: `assert result.ok`
   - Old: `assert "Error" in result`
   - New: `assert not result.ok`
   - Old: `assert "⚠️" in result`
   - New: `assert not result.ok and result.error.code == "DUPLICATE_PHONE"`
5. **QA after every pass** — syntax → mypy → pytest (full suite). Don't accumulate passes without verifying.
6. **Commit early, commit often** — Each pass can be its own commit. This makes rollback precise if a pass introduces a bug.

### Key pitfalls

- **Import paths**: Scripts run on the server at /opt/ara, so imports are relative to that directory. No need for sys.path hacks.
- **git state**: If you corrupt the file, `git checkout -- <file>` restores it. Always check git status before applying new patches.
- **Multiple temp files**: Name them semantically (`apply_part0.py`, `fix_results_json.py`) so you can tell at a glance which to clean up.
- **Syntax check on server**: Always compile AFTER writing:
  ```python
  import py_compile
  py_compile.compile("server.py", doraise=True)
  ```
- **The `patch()` tool cannot read remote files** — only use it for local edits. For remote files, always use the write+scp+run pattern.

### Verification cadence

After every change on the remote server:
1. `py_compile.compile("file.py", doraise=True)` — syntax check
2. `bash scripts/qa-gate.sh` — mypy + pytest (230+ tests)
3. `curl -s http://localhost:8766/api/health` — server alive
4. `git commit && git push && bash deploy.sh` — deploy

### Naming convention for temp scripts

```
/opt/ara/apply_<module>.py   — applying changes
/opt/ara/fix_<bug>.py        — fixing a specific issue
/opt/ara/add_<feature>.py    — adding a feature
```

Delete them after they've been committed or `git clean -fd` after the deploy.

## Monolith Extraction Pattern (server.py → modular packages)

When extracting a section from a monolithic server.py into `app/services/` and `app/api/` modules.

### Workflow

1. **Read the full section** first — understand all function boundaries, internal references, and dependencies (models, constants, helper functions, `__file__`-relative paths)
2. **Create the target module file** directly on the server (scp a Python script, don't pipe through ssh quoting)
3. **Verify imports** — `cd /opt/ara && /opt/ara/venv/bin/python3 -c "from app.services.newmodule import ..."` — catch module-not-found errors early
4. **Create a Python script** that edits server.py (not sed/awk/ssh-inline) — use `write_file` on local, then scp + run on server
5. **Remove inline code** from server.py in the edit script
6. **Add imports/router includes** for the new module
7. **Add import aliases** for any function the extracted code exported that's still called from OTHER sections of server.py (e.g. `from app.services.cadence import schedule_cadence_for_lead as _schedule_cadence_for_lead`)
8. **Compile-check** — `compile(open("server.py").read(), "server.py", "exec")`
9. **Run QA gate** — mypy + pytest
10. **Verify server starts** — `from server import app; print(len(app.routes))` — check total route count matches

### Pitfalls

| Trap | Sign | Fix |
|------|------|-----|
| **Patch deletes adjacent code** | Function you didn't intend to remove disappears from file | When matching `old_string` in patch(), include enough surrounding context (3+ lines before + after) to uniquely identify the boundary. After patching, `grep` for the function name to confirm it still exists. |
| **`__file__`-relative path breaks** | Module loads fine but runtime fails with FileNotFoundError | `pathlib.Path(__file__).parent` changes when code moves from `server.py` (project root) to `app/api/cadence.py` (2 levels down). Multiply `.parent` calls: `pathlib.Path(__file__).resolve().parent.parent.parent` to reach project root. Or set a project-root constant. |
| **Inline `__file__`-relative code doesn't work in imported module** | Same as above — resource file not found | Before moving, check if the section uses `__file__` at module level (e.g. `pathlib.Path(__file__).parent / "prompt_templates.json"`). Adjust path resolution in the new module. |
| **Import alias missing** | mypy error: `Name "X" is not defined` in sections that called the extracted function | Search for ALL references to the extracted function name across server.py. Any call in a section NOT being extracted needs an import alias in server.py's preamble. The `_` prefix convention (server-internal) can obscure this — check with `grep -n "function_name" server.py`. |
| **Python-quoting hell with ssh inline** | SyntaxError, unclosed parens, unterminated strings | Don't pipe Python through `ssh -c "python3 -c '...'"`. Write a `.py` file locally, scp it to the server, run it there. Write the edit script with write_file() → scp → ssh 'python3 /tmp/script.py'. |
| **Circular import after extraction** | ModuleNotFoundError or ImportError on startup | Check if the extracted module imports something that imports server.py (which now imports the new module). Keep imports one-directional: `app.services.*` → `app.db` and `app.config`, never back into `server.py`. If cross-references exist, refactor the shared code into a neutral module first. |
| **Route count changes after router include** | Missing or duplicated routes on restart | Before removing inline code, count server.py routes. After adding `app.include_router(router)`, verify `len(app.routes)` matches. If routes are duplicated, the inline `@app.route(...)` decorators weren't removed. |

### Verification command

```bash
cd /opt/ara && /opt/ara/venv/bin/python3 -c "
from server import app
print(f'Total routes: {len(app.routes)}')
# Check specific new routes exist
paths = [r.path for r in app.routes]
assert '/api/cadence/publish' in paths  # example
"
```

## Reference Files

- `references/save-chain-map.md` — Full persistence chain map from ARA prompt builder debugging. Contains the link-by-link trace, all bugs found in order (Bugs 1-6), and reusable verification commands.
- `references/persistence-bugs-7-8.md` — Additional persistence bugs from later sessions: migrateToGlobalPromptParts wipes promptParts, prefillFromInduction overwrites saved data.
- `references/persistence-debugging-protocol.md` — Step-by-step debugging protocol for ARA data persistence issues. Six steps from localStorage inspection through server process verification.
- `references/ara-feature-addition-chain.md` — Repeatable pattern for adding a new feature to ARA (DB model → API → frontend → verify). Covers migration, endpoint patterns, JS escaping, and the full verify chain.
- `references/ara-feature-addition-chain.md` — Repeatable pattern for adding a new feature to ARA (DB model → API → frontend → verify). Covers migration, endpoint patterns, JS escaping, and the full verify chain.
- `references/notification-ref-tracing.md` — Debugging stale notification counts: cross-reference refs against underlying record status. Use when any badge count feels wrong.
- `references/tool-result-architecture.md` — ToolResult + render_results architecture for structured tool execution output. Covers error taxonomy, dependency map, renderer formats, and migration status.
- `references/systematic-pattern-audit.md` — The "grep all, fix all, verify zero" technique for systematic pattern fixes. Use when Greg signals frustration with patchwork one-by-one fixes. Includes real example from June 2026 timezone leak cleanup.
- `references/datetime-timezone-leak-pattern.md` — ARA-specific bug class: datetime values displayed in UTC instead of tenant timezone. Three leak patterns with fixes, audit command, and helpers reference.

## Verification Script

```bash
# Check server vs code freshness
echo "Server: $(ps -p $(pgrep -f 'venv/bin/python server.py$') -o lstart= 2>/dev/null)"
echo "Commit: $(cd /Users/greg/ara && git log -1 --format='%ai %s')"

# Test API
curl -s -X POST http://localhost:8766/api/cadence/save-draft \
  -H "Content-Type: application/json" \
  -d '{"template_id":"cold","promptParts":{"brandPersonality":{"personality":"verify"}},"systemPrompt":"verify"}'

# Verify DB
cd /Users/greg/ara && python3 -c "
from database import CadenceConfig, init_db
db = init_db()
cfg = db.query(CadenceConfig).filter(CadenceConfig.template_id == 'cold').first()
bp = cfg.config.get('promptParts', {}).get('brandPersonality', {}) if cfg else {}
pers = bp.get('personality', '')
print('Personality:', repr(pers))
db.close()
"
```