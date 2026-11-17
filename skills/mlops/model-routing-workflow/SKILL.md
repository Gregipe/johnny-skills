---
name: model-routing-workflow
description: "Model routing: DeepSeek V4 Pro, Claude Opus 4.8, GLM-5.3."
version: 1.3.0
author: Hermes Agent
---

# Model Routing Workflow

Gregory's orchestration pattern: one main model with specialized sub-agent delegation.

## Model Assignments

| Role | Model | Provider | Cost (per M tok in/out) | Use When |
|------|-------|----------|--------------------------|----------|
| **Main/Orchestrator** | deepseek-v4-pro | deepseek | $0.66/$1.98 off-peak (×2 peak) | All conversations, routing decisions (pool final: Sep 2026) |
| **Planning & Strategy** | claude-opus-4-8 | anthropic | premium | Architecture design, approach planning, complex reasoning |
| **Deep Research** | deepseek-v4-pro | deepseek | $0.66/$1.98 off-peak (×2 peak) | Web research, paper analysis, data synthesis |
| **Heavy coding** (architecture, multi-file) | claude-opus-4-8 | anthropic | premium | Product architecture, API integration, complex features |
| **Mid-tier coding** | deepseek-v4-pro | deepseek | $0.66 / $1.98 off-peak (×2 peak) | Good middle ground |
| **ARA agent_chat (ALL requests)** | deepseek-v4-pro | deepseek | $0.66 / $1.98 off-peak (×2 peak) | **Default: always Pro.** See "Architecture History" section below for why. This is a *correctness-first* policy — a wrong route to Flash costs a silently dropped action; a wrong route to Pro costs $0.02–0.05. Flash was removed from the agent loop path entirely after cumulative fixes showed the correction cascade (enforcer re-call + phantom-update correctors) spent 2-3 extra Pro calls anyway, offsetting any cost savings. |
| **Utility coding** (snippets, fixes) | qwen2.5-coder-7b-instruct-mlx | lm-studio (local) | Free (local) | Optional/legacy — not part of the cloud pool. LM Studio at http://127.0.0.1:1234/v1 |
| **Default delegation** | glm-5.3 | zai | $1.4 / $4.4 | Set in config.yaml — delegate_task routes here. reasoning_effort=high, 32K ctx, 50 iters, 30-min timeout |
| **TA (Technical Advisor) scope review** | glm-5.3 (high reasoning) | zai (Z.AI) | $1.4 / $4.4 | `/tmp/ta_direct.py` — calls ZAI API directly with `thinking: {type: "enabled", budget_tokens: 4096}`. Switched from deepseek-v4-flash in June 2026 for stronger reasoning. API key (`GLM_API_KEY`) lives in `~/.hermes/profiles/johnny/.env`, NOT in ARA's `.env`. |

**Reasoning effort:** DeepSeek's API accepts `low`/`high`/`max`; Hermes's `xhigh` maps to max. Johnny's profile sets `agent.reasoning_effort: xhigh` (max reasoning); the provider default is `high`, so if that config key is dropped the model silently runs a tier weaker. Delegation (glm-5.3) runs `reasoning_effort: high`.

## Current Profile Map (verified Sep 2026)

| Profile | Purpose | Model / Provider |
|---------|---------|------------------|
| johnny (active) | Chief of Staff | deepseek-v4-pro / deepseek |
| morpheus | Deep research | deepseek-v4-pro / deepseek |
| architect | Planning & architecture | claude-opus-4-8 / anthropic |
| technical-advisor | TA scope review | glm-5.3 / zai |
| cipher | Spare | deepseek-v4-pro / deepseek |

Cloud model pool is final (Sep 2026): DeepSeek V4 Pro, Claude Opus 4.8, GLM-5.3 only. No Gemini/GPT keys — don't re-litigate. Local Qwen via LM Studio remains configured but is optional/legacy.

Open-weight competitor landscape (AA Intelligence Index v5 scores + pricing): `references/open-weight-competitor-landscape.md`.

## How to Route Tasks

For WHO (which agent/role) handles what, load `multi-agent-dispatch` — the
firm org chart, triage flow, and handoff contracts. This skill covers the
model-level mechanics and invocation patterns.

When Gregory gives you a task:

1. **Assess the task type** — is it quick chat, planning-heavy, research-heavy, or code-heavy?
2. **Route accordingly** using one of these patterns:

### Pattern A: Spawn a sub-process (the only reliable approach)

**IMPORTANT PITFALL**: `delegate_task` reads the delegation config at agent process startup and caches it. `hermes config set` changes the file on disk but the running agent DOES NOT re-read it. So swapping the delegation config before calling delegate_task will NOT route to the intended model — it still uses the cached value from startup.

Instead, ALWAYS use a sub-process for model-specific routing:

```bash
# Planning with Claude
hermes chat -q "Plan this approach for: <task>" --model claude-opus-4-8 --provider anthropic

# Deep research with DeepSeek V4 Pro
hermes chat -q "Research this topic deeply: <topic>" --model deepseek-v4-pro --provider deepseek

# Coding with Qwen Coder (local, optional/legacy)
hermes chat -q "Write code for: <task>" --model qwen2.5-coder-7b-instruct-mlx --provider lm-studio
```

Run via `terminal` tool with `background=true` and `timeout` set on the **terminal call** (not on the hermes command). Capture output with a `tee` or file redirect:

```bash
terminal(command="hermes chat -q 'research task...' --model deepseek-v4-pro --provider deepseek 2>&1 | tee /tmp/research.txt", background=true, notify_on_complete=true)
```

**PITFALL: `--timeout` is NOT a valid flag for `hermes chat`.** The `timeout` parameter belongs on the `terminal()` tool invocation (it's a terminal-level timeout for the whole subprocess). Don't pass `--timeout 300` inside the query string — `hermes` will error: `unrecognized arguments: --timeout`.

**PITFALL: DeepSeek V4 Pro is a reasoning model.** It produces `reasoning_content` (like R1/DeepThink). Response times are slower than a non-reasoning model because it spends tokens on chain-of-thought before answering. This is fine for research — the reasoning makes the output better — but expect 2-3x longer wall-clock time.

## Architecture History

The ARA agent loop was migrated from keyword-based model routing to Pro-by-default in June 2026. This section documents why for future reference.

### Old Architecture (before June 13, 2026)

The agent_chat function used a keyword-based router:
```python
_model_routing_keywords = {"email", "phone", ..., "start", "outbound", ...}
_chat_model = "deepseek-v4-pro" if bool(words & keywords) else "deepseek-v4-flash"
```

This caused three classes of silent failure:
1. **Missing keyword** — "start an outbound sequence" had no trigger words → Flash → no tool call → "internal error" response
2. **Voice notes** — "🎤 latest news about ExpressBees" had no trigger words → Flash → returned fabricated "✅ 1 action(s) completed" instead of calling web_search
3. **Natural language queries** — "what's new with Swiggy's hiring" had no trigger words → Flash → no tool call

Each fix was an additive patch: add more keywords → add regex fallback → add voice-note prefix check. The set grew but the pattern remained: **any miss meant a silently dropped action**.

### Migration Decision (June 13, 2026)

A technical review identified the fundamental asymmetry:
> A wrong route toward Pro costs ~$0.02–0.05. A wrong route toward Flash costs a **silently dropped action** — which Ava's correctors (enforcer re-call, phantom-update corrector, phantom-lookup corrector) then spend 2-3 extra Pro calls to claw back.

The decision was to **default the entire agent loop to Pro** and remove keyword routing entirely.

### Current Architecture

```python
# server.py, agent_chat() — always uses the reliable tool-caller
_chat_model = "deepseek-v4-pro"
```

Flash (deepseek-v4-flash) is preserved only for explicitly-invoked non-agentic subtasks where there's no `[TOOL_CALL:]` contract and the call is made explicitly by Python code, not the LLM deciding:
- Insight extraction from conversations (`_extract_insights_from_conversation`)
- Conversation analysis (`analyze_conversation`)
- Stage change detection (`_detect_stage_changes`)
- Cadence message generation
- Any JSON-in/JSON-out extraction where `call_llm()` is called directly with `model="deepseek-v4-flash"`

### Verification

Post-migration test (June 13, 2026):
```
User: "Hey Ava, I have a meeting with ExpressBees, give me two lines about latest news"
→ Pro → ✅ Web Search — E-commerce logistics startup Xpressbees turns unicorn
```

The exact query that failed earlier on Flash now works because Pro reliably emits `[TOOL_CALL: web_search]`.

### If Cost Becomes an Issue in the Future

The advisor recommended a staged approach:
1. ✅ **Done**: Default agent loop to Pro
2. ✅ **Done**: Structured per-turn logging (`agent_turn` log line) — logs tenant, thread, model, tools_called, tool_args, tool_failures, intent, executed. Part of the native function calling migration (see next section).
3. **Only if needed**: Reintroduce a Flash downgrade gate for *read-only* turns, decided structurally (no data-modifying tool in play), not by keyword matching

## Native Function Calling Migration (June 2026 — In Progress)

After the Pro-by-default migration, the next architectural improvement is switching from text-marker `[TOOL_CALL: {...}]` parsing to **native function calling** via the OpenAI-compatible `tools` API parameter. This removes the 60-line balanced-brace parser (`_parse_tool_calls`) which is the #1 source of silently dropped tool calls (malformed JSON, missing brackets, nested brace mismatches).

### Architecture (Parts 1-7)

The migration follows a formal build spec from an external technical advisor (see `references/native-function-calling-build-spec.md`):

| Part | Status | What |
|------|--------|------|
| **Part 1** — `call_llm_with_tools` | ✅ Done | New function in `induction_engine.py`. Sends `tools` + `tool_choice="auto"` to DeepSeek. Returns structured dict: `{text, tool_calls[{id, name, args}], raw_tool_calls, raw, error}`. Lower temperature (0.2) for tool-deciding turn. Existing `call_llm` untouched. |
| **Part 3** — `build_tools_schema()` | ✅ Done | Generates OpenAI-format JSON schema for all 50 tools in `execute_tool()`. One entry per tool with description, `read_only` flag. `TOOL_SCHEMAS` dict at module level. Coverage test (`test_schema_coverage.py`) diffs schema keys against execute_tool branches and fails on drift. |
| **Part 2** — Observe loop | 🔧 In progress | Replaces single-call-then-parse with a bounded loop (`MAX_TOOL_STEPS=4`) that feeds tool results back to the model for retry/chaining. Replaces the enforcer, phantom-update corrector, and phantom-lookup corrector with one `_claims_action_without_call` check. |
| **Part 6a** — Structured logging | ✅ Done | `agent_turn` log line at end of each agent_chat turn. |
| **Part 6b** — 15-conversation fixture | ✅ Done | `test_conversation_fixture.py` — 15 scenarios mocking `call_llm_with_tools`. |
| **Part 4** — System prompt swap | ⏳ Pending | User (Greg) has a copy on Desktop. Will replace the prompt and remove `AGENT_TOOL_SCHEMA` from prompt-append path. |
| **Part 5** — Delete correctors | ⏳ Pending | Enforcer, phantom-update, phantom-lookup blocks — replaced by observe loop. |
| **Part 7** — Text fallback | ⏳ Pending | `_parse_tool_calls` kept as time-boxed fallback, deletion ticket to be opened. |

### Key Design Decisions

- **`tool_choice="auto"`** — model is free to answer simple questions with no tool call
- **No forced tool** — never `tool_choice` to a specific tool
- **Claim/no-call detection** — replaces the keyword-based enforcer. Checks for a mismatch between what the model's PROSE says it did and whether a tool call was actually emitted. More accurate than keyword matching.
- **Observe loop feeds results back** — model sees tool results and can retry with corrected args or chain the next tool. This eliminates the need for the corrector cascade.
- **`MAX_TOOL_STEPS=4` hard stop** — never unbounded; honest partial summary on timeout.

### Test Coverage

All new tests pass together:
```
pytest tests/test_conversation_fixture.py tests/test_native_tools.py tests/test_schema_coverage.py -v
# 22 passed
```

### Reference

See `references/native-function-calling-build-spec.md` for the full technical advisor spec that defines this migration.

### Pattern B: delegate_task (verify config before use!)

The delegation config determines which model `delegate_task` uses. This is CACHED at agent startup — changing `config.yaml` mid-session does NOT take effect.

**Before using delegate_task in a session, verify:**
```bash
hermes config show | grep -A3 delegation
# Should show: model: glm-5.3, provider: zai
```

If it shows a different model (e.g., `qwen/qwen2.5-coder-14b`), change it **via `hermes config set` — never `patch`/`write_file` the YAML directly. Hermes refuses direct edits to `~/.hermes/**/config.yaml` ("Agent cannot modify security-sensitive configuration"); the sanctioned path is the `hermes config` CLI, which works for any profile via `hermes --profile <name> config set <dotted.path> <value>`.**
```bash
hermes config set delegation.model glm-5.3
hermes config set delegation.provider zai
```
Then RESTART the Hermes session for the change to take effect.

**PITFALL:** The config may drift from the skill's recommendation. This happened June 19, 2026 — delegation was set to local Qwen (4K context) instead of DeepSeek Pro (128K). `delegate_task` failed with context-window errors until the config was corrected AND the session restarted.

When `delegate_task` is unavailable (wrong model cached), use the `hermes chat -q` subprocess fallback:
```bash
terminal(background=true, notify_on_complete=true, command=
  'hermes --profile johnny chat -q "$(cat /tmp/prompt.txt)" '
  '--model deepseek-v4-pro --provider deepseek '
  '--toolsets terminal,file,web --quiet '
  '2>&1 | tee /tmp/output.txt')
```
Always write the prompt to a file first — shell escaping of large multi-line prompts fails silently.

**CRITICAL PITFALL: delegate_task caches its model config at agent-process startup.** Changing `delegation.model` via `hermes config set` updates the file on disk but the RUNNING agent does NOT re-read it. The subagent will still use the old model until the session is restarted (`/reset` or new `hermes` invocation). This was discovered June 19 when the delegation config was set to `qwen/qwen2.5-coder-14b` (4K context) and switching to `deepseek-v4-pro` mid-session had no effect — `delegate_task` kept using Qwen and failing with context-window errors.

**Workaround:** When a model-specific subagent is needed and the delegation config is wrong or needs a different model, use `hermes chat -q` sub-processes instead:

```bash
# Dispatch implementation with a specific model
terminal(command="hermes chat -q '$(cat /tmp/prompt.txt)' \
  --model deepseek-v4-pro --provider deepseek \
  --toolsets terminal,file,web --quiet \
  2>&1 | tee /tmp/result.txt",
  background=true, notify_on_complete=true)
```

This bypasses the cached delegation config entirely and is the reliable way to route to a specific model mid-session.

Use `delegate_task` for:
- Research synthesis subtasks
- Multi-file code generation (when delegation config is correct)
- Parallel analysis workstreams
- Any mid-tier work where the main model (Pro) isn't enough but Claude is overkill

**PITFALL: Stale model names in cloned profiles.** When cloning a profile (e.g., `hermes profile create technical-advisor --clone-from architect`), the cloned model name may be stale. `claude-sonnet-4-20250514` was a valid name at clone time but returned HTTP 404 later. Always verify with a one-shot test after cloning: `hermes --profile <name> chat -q "hello" --quiet`. Fix with: `hermes --profile <name> config set model.default <current-name>`.

### Pattern C: Sub-process routing (the only reliable cross-model approach)

For model-specific routing that differs from the default delegation model, use `hermes chat -q` sub-processes via the `terminal` tool. This is the ONLY reliable way to route to a specific model — `delegate_task` caches its config at startup and cannot be changed mid-session.

```bash
# Planning with Claude
hermes chat -q "Plan this approach for: <task>" --model claude-opus-4-8 --provider anthropic

# Deep research with DeepSeek V4 Pro  
hermes chat -q "Research this topic deeply: <topic>" --model deepseek-v4-pro --provider deepseek

# Coding with Qwen Coder (local, optional/legacy)
hermes chat -q "Write code for: <task>" --model qwen2.5-coder-7b-instruct-mlx --provider lm-studio
```

Run via `terminal` tool with `background=true` and `notify_on_complete=true`. Capture output with `tee` or file redirect. The `timeout` parameter belongs on the `terminal()` tool invocation, not inside the query string.

## ZAI / GLM-5.3 Provider

GLM-5.3 is available via ZAI (Z.AI / Zhipu AI) at `https://api.z.ai/api/paas/v4`. The API key (`GLM_API_KEY`) lives in `~/.hermes/profiles/johnny/.env`, NOT in ARA's `/opt/ara/.env`. GLM-5.3 supports high reasoning via the `thinking` parameter: `{"type": "enabled", "budget_tokens": 4096}`. The response includes a separate `reasoning_content` field alongside `content`. See `references/zai-glm-reasoning-api.md` for full API details, Python usage pattern, and the TA script architecture.

**Verification gotcha:** GLM-5.3's default thinking mode spends the token budget as `reasoning_tokens` — a tiny `max_tokens` (16–64) returns `content: ""` with no error even though the call succeeded. When smoke-testing the model name/key against Z.AI, use `max_tokens>=300` to actually see text back (e.g. `{"model":"glm-5.3","max_tokens":300,"messages":[{"role":"user","content":"Reply with exactly: OK"}]}`).

## Fallback Behavior

- If Claude is rate-limited (Anthropic 429): fall back to doing the planning myself or try again after delay
- If DeepSeek V4 Pro is unavailable: route research to GLM-5.3 and flag to Gregory
- If GLM-5.3 (ZAI) is unavailable: run delegation on DeepSeek V4 Pro and flag to Gregory
- If LM Studio is down: skip it — local Qwen is optional/legacy, not part of the cloud pool

## Product-Building Model Suitability

When building an AI product (not just using Hermes), different models suit different roles within the product. This section captures learnings from the ARA (Autonomous Revenue Agent) product design session.

### Model-to-Role Mapping

| Role in Product | Best Model | Why |
|----------------|-----------|-----|
| **SDR conversation** (real-time lead chat) | DeepSeek V4 Flash | Fast (~3-5s API latency), strong tool-use agentic loops, reliable for structured conversational workflows |
| **Induction/coaching** (parsing docs, extracting structure, Socratic dialogue) | Claude Sonnet | Better at complex reasoning, extracting meaning from messy documents, handling nuanced conversational feedback loops |
| **Skill updates from coaching** | DeepSeek V4 Flash | Proven in Hermes's own architecture — the "customer corrects → agent updates skills" loop works well here |
| **Voice call** (real-time, sub-500ms) | ❌ None of current models | DeepSeek Flash is 3-5s, Claude is similar. Purpose-built low-latency voice models needed (Hunar's conversational AI, ElevenLabs Conversational AI, or similar) |
| **Weekly performance review generation** | Claude Sonnet | Better at synthesis across many conversations, pattern detection, structured reporting |

### Key Architectural Insight

For a multi-agent product (LDR → BDR → SDR agents):
- **Same LLM can serve all agents** with different system prompts/personalities
- No need for per-agent model specialization unless latency or cost constraints demand it
- Voice is the exception — requires a completely different inference pipeline (STT → fast LLM → TTS with <2s end-to-end)

### Tools Available for Building

| Capability | Available | Notes |
|-----------|-----------|-------|
| LLM (chat) | DeepSeek V4 Flash + Claude Sonnet | Both API keys configured |
| TTS (voice output) | Edge TTS, ElevenLabs | Configured |
| Email | Himalaya | Works |
| Chat channel proxy | Telegram | Already integrated |
| Database | SQLite + SQLAlchemy | Good for prototype |
| Web backend | Install FastAPI + uvicorn | 30s to install |
| Voice calling | Need Hunar/Twilio keys | Not configured |

See `user-interaction-style/references/ara-product-vision-may2026.md` for the full product architecture that informed this assessment.

After routing a complex task:
1. Confirm the sub-agent result before presenting to Gregory
2. If delegation config was swapped, verify it was restored afterward
3. Log which model was used for what part of the task
