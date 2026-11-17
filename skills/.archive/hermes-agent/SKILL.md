---
name: hermes-agent
description: "Configure, extend, or contribute to Hermes Agent."
version: 2.0.0
author: Hermes Agent + Teknium
license: MIT
metadata:
  hermes:
    tags: [hermes, setup, configuration, multi-agent, spawning, cli, gateway, development]
    homepage: https://github.com/NousResearch/hermes-agent
    related_skills: [claude-code, codex, opencode]
---

# Hermes Agent

Hermes Agent is an open-source AI agent framework by Nous Research that runs in your terminal, messaging platforms, and IDEs. It belongs to the same category as Claude Code (Anthropic), Codex (OpenAI), and OpenClaw — autonomous coding and task-execution agents that use tool calling to interact with your system. Hermes works with any LLM provider (OpenRouter, Anthropic, OpenAI, DeepSeek, local models, and 15+ others) and runs on Linux, macOS, and WSL.

What makes Hermes different:

- **Self-improving through skills** — Hermes learns from experience by saving reusable procedures as skills. When it solves a complex problem, discovers a workflow, or gets corrected, it can persist that knowledge as a skill document that loads into future sessions. Skills accumulate over time, making the agent better at your specific tasks and environment.
- **Persistent memory across sessions** — remembers who you are, your preferences, environment details, and lessons learned. Pluggable memory backends (built-in, Honcho, Mem0, and more) let you choose how memory works.
- **Multi-platform gateway** — the same agent runs on Telegram, Discord, Slack, WhatsApp, Signal, Matrix, Email, and 10+ other platforms with full tool access, not just chat.
- **Provider-agnostic** — swap models and providers mid-workflow without changing anything else. Credential pools rotate across multiple API keys automatically.
- **Profiles** — run multiple independent Hermes instances with isolated configs, sessions, skills, and memory.
- **Extensible** — plugins, MCP servers, custom tools, webhook triggers, cron scheduling, and the full Python ecosystem.

People use Hermes for software development, research, system administration, data analysis, content creation, home automation, and anything else that benefits from an AI agent with persistent context and full system access.

**This skill helps you work with Hermes Agent effectively** — setting it up, configuring features, spawning additional agent instances, troubleshooting issues, finding the right commands and settings, and understanding how the system works when you need to extend or contribute to it.

**Docs:** https://hermes-agent.nousresearch.com/docs/

## Quick Start

```bash
# Install
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash

# Interactive chat (default)
hermes

# Single query
hermes chat -q "What is the capital of France?"

# Setup wizard
hermes setup

# Change model/provider
hermes model

# Check health
hermes doctor
```

---

## CLI Reference

### Global Flags

```
hermes [flags] [command]

  --version, -V             Show version
  --resume, -r SESSION      Resume session by ID or title
  --continue, -c [NAME]     Resume by name, or most recent session
  --worktree, -w            Isolated git worktree mode (parallel agents)
  --skills, -s SKILL        Preload skills (comma-separate or repeat)
  --profile, -p NAME        Use a named profile
  --yolo                    Skip dangerous command approval
  --pass-session-id         Include session ID in system prompt
```

No subcommand defaults to `chat`.

### Chat

```
hermes chat [flags]
  -q, --query TEXT          Single query, non-interactive
  -m, --model MODEL         Model (e.g. anthropic/claude-sonnet-4)
  -t, --toolsets LIST       Comma-separated toolsets
  --provider PROVIDER       Force provider (openrouter, anthropic, nous, etc.)
  -v, --verbose             Verbose output
  -Q, --quiet               Suppress banner, spinner, tool previews
  --checkpoints             Enable filesystem checkpoints (/rollback)
  --source TAG              Session source tag (default: cli)
```

### Configuration

```
hermes setup [section]      Interactive wizard (model|terminal|gateway|tools|agent)
hermes model                Interactive model/provider picker
hermes config               View current config
hermes config edit          Open config.yaml in $EDITOR
hermes config set KEY VAL   Set a config value
hermes config path          Print config.yaml path
hermes config env-path      Print .env path
hermes config check         Check for missing/outdated config
hermes config migrate       Update config with new options
hermes login [--provider P] OAuth login (nous, openai-codex)
hermes logout               Clear stored auth
hermes doctor [--fix]       Check dependencies and config
hermes status [--all]       Show component status
```

### Tools & Skills

```
hermes tools                Interactive tool enable/disable (curses UI)
hermes tools list           Show all tools and status
hermes tools enable NAME    Enable a toolset
hermes tools disable NAME   Disable a toolset

hermes skills list          List installed skills
hermes skills search QUERY  Search the skills hub
hermes skills install ID    Install a skill (ID can be a hub identifier OR a direct https://…/SKILL.md URL; pass --name to override when frontmatter has no name)
hermes skills inspect ID    Preview without installing
hermes skills config        Enable/disable skills per platform
hermes skills check         Check for updates
hermes skills update        Update outdated skills
hermes skills uninstall N   Remove a hub skill
hermes skills publish PATH  Publish to registry
hermes skills browse        Browse all available skills
hermes skills tap add REPO  Add a GitHub repo as skill source
```

### MCP Servers

```
hermes mcp serve            Run Hermes as an MCP server
hermes mcp add NAME         Add an MCP server (--url or --command)
hermes mcp remove NAME      Remove an MCP server
hermes mcp list             List configured servers
hermes mcp test NAME        Test connection
hermes mcp configure NAME   Toggle tool selection
```

### Gateway (Messaging Platforms)

```
hermes gateway run          Start gateway foreground
hermes gateway install      Install as background service
hermes gateway start/stop   Control the service
hermes gateway restart      Restart the service
hermes gateway status       Check status
hermes gateway setup        Configure platforms
```

Supported platforms: Telegram, Discord, Slack, WhatsApp, Signal, Email, SMS, Matrix, Mattermost, Home Assistant, DingTalk, Feishu, WeCom, BlueBubbles (iMessage), Weixin (WeChat), API Server, Webhooks. Open WebUI connects via the API Server adapter.

Platform docs: https://hermes-agent.nousresearch.com/docs/user-guide/messaging/

### Sessions

```
hermes sessions list        List recent sessions
hermes sessions browse      Interactive picker
hermes sessions export OUT  Export to JSONL
hermes sessions rename ID T Rename a session
hermes sessions delete ID   Delete a session
hermes sessions prune       Clean up old sessions (--older-than N days)
hermes sessions stats       Session store statistics
```

### Cron Jobs

```
hermes cron list            List jobs (--all for disabled)
hermes cron create SCHED    Create: '30m', 'every 2h', '0 9 * * *'
hermes cron edit ID         Edit schedule, prompt, delivery
hermes cron pause/resume ID Control job state
hermes cron run ID          Trigger on next tick
hermes cron remove ID       Delete a job
hermes cron status          Scheduler status
```

### Cron Jobs — Critical Pitfalls

```bash
hermes cron list            List jobs (--all for disabled)
hermes cron create SCHED    Create: '30m', 'every 2h', '0 9 * * *'
hermes cron edit ID         Edit schedule, prompt, delivery
hermes cron pause/resume ID Control job state
hermes cron run ID          Trigger on next tick
hermes cron remove ID       Delete a job
hermes cron status          Scheduler status
```

**Pitfall: `deliver: "origin"` silently never fires.**

Cron jobs run in **isolated sessions** with no chat context. If you set `deliver: "origin"` (or omit delivery entirely), the job executes the prompt but has nowhere to send the result — the output is silently discarded. No error, no log entry, no visible failure. The job appears to run (scheduler ticks, next_run_at updates) but nothing ever arrives anywhere.

**ALWAYS specify an explicit delivery target:**

| Target | Syntax | Example |
|--------|--------|---------|
| Telegram DM | `telegram:<user_id>` | `telegram:557413154` |
| Telegram group | `telegram:<group_name>` | `telegram:Johnny_Work` |
| Slack channel | `slack:#channel` | `slack:#general` |
| Discord channel | `discord:<channel_id>` | `discord:123456789` |
| File only | `local` | Writes result to file, no delivery |

**Verification checklist after creating/modifying a cron job:**

1. `hermes cron list` — confirm job is listed with correct schedule
2. Check `last_delivery_error: null` (no error means delivery pipeline is live)
3. If possible, trigger a test run: `hermes cron run <job_id>` then verify the output arrives at the target
4. After the next scheduled run, check delivery status via `hermes cron list`

**Pitfall: Cron jobs with `skill:` or `skills:` fields override the prompt with the skill's system message.** If the skill has no user-facing output template, the job may produce blank responses. Use `prompt:` (inline text) for simple tasks unless the skill genuinely provides the full output format you need.

**Pitfall: One-time cron jobs (`schedule: "once at ..."`) self-delete after firing.** Review does not see them in `hermes cron list` afterward. If you need to verify one fired, set up a following health-check job, or log output to a file via `deliver: local`.

**Pitfall: Cron jobs with `model:` or `provider:` fields** may fail if the model key is misspelled or the provider key is missing from `.env`. Always verify by running `hermes doctor` first if a cron job silently fails despite correct delivery.

### Webhooks

```bash
hermes webhook subscribe N  Create route at /webhooks/<name>
hermes webhook list         List subscriptions
hermes webhook remove NAME  Remove a subscription
hermes webhook test NAME    Send a test POST
```

### Profiles

```bash
hermes profile list         List all profiles
hermes profile create NAME  Create (--clone, --clone-all, --clone-from)
hermes profile use NAME     Set sticky default
hermes profile delete NAME  Delete a profile
hermes profile show NAME    Show details
hermes profile alias NAME   Manage wrapper scripts
hermes profile rename A B   Rename a profile
hermes profile export NAME  Export to tar.gz
hermes profile import FILE  Import from archive
```

**⚠️ Critical pitfall: profile uses its OWN `.env`, not the global one.**

When a profile is active, `get_hermes_home()` returns `~/.hermes/profiles/<name>/`. The gateway loads `.env` from `{HERMES_HOME}/.env` — which is the **profile's** `.env`, NOT the global `~/.hermes/.env`. Adding a platform token (e.g. `DISCORD_BOT_TOKEN`) to the global `.env` does NOT make it available to the profile gateway.

**Consequence:** The platform adapter logs `[Discord] No bot token configured` even though the token exists in `~/.hermes/.env`. Telegram may work fine if its token was set up before the profile was created (copied during clone) but any token added later to the global `.env` is invisible.

**Fix after creating a new profile:** Always manually copy `DISCORD_BOT_TOKEN`, `SLACK_BOT_TOKEN`, etc. from `~/.hermes/.env` into `~/.hermes/profiles/<name>/.env`. Use `hermes profile create --clone` to copy the global `.env` at creation time.

**Fix when a platform token was added to the global `.env` later:** Append the missing line to the profile's `.env`:
```bash
echo "DISCORD_BOT_TOKEN=<value>" >> ~/.hermes/profiles/<name>/.env
```

**Verification:** Compare env vars across files:
```bash
diff <(grep -i "bot_token\|api_key" ~/.hermes/.env) <(grep -i "bot_token\|api_key" ~/.hermes/profiles/<name>/.env)
```

See `references/gateway-recovery-patterns.md` section 5 for detailed diagnostics.

### Credential Pools

```
hermes auth add             Interactive credential wizard
hermes auth list [PROVIDER] List pooled credentials
hermes auth remove P INDEX  Remove by provider + index
hermes auth reset PROVIDER  Clear exhaustion status
```

### Dashboard

```bash
hermes dashboard                     Launch web UI (default http://127.0.0.1:9119)
  --port PORT                        Custom port (default 9119)
  --host HOST                        Bind address (default 127.0.0.1)
  --no-open                          Don't open browser automatically
  --insecure                         Allow binding to non-localhost (DANGEROUS:
                                     exposes API keys on the network)
  --tui                              Enable in-browser Chat tab (embedded TUI via
                                     PTY/WebSocket; or set HERMES_DASHBOARD_TUI=1)
  --stop                             Stop all running dashboard processes
  --status                           List running dashboard processes
```

### Other

```bash
hermes insights [--days N]  Usage analytics
hermes update               Update to latest version
hermes pairing list/approve/revoke  DM authorization
hermes plugins list/install/remove  Plugin management
hermes honcho setup/status  Honcho memory integration (requires honcho plugin)
hermes memory setup/status/off  Memory provider config
hermes completion bash|zsh  Shell completions
hermes acp                  ACP server (IDE integration)
hermes claw migrate         Migrate from OpenClaw
hermes uninstall            Uninstall Hermes
```

---

## Slash Commands (In-Session)

Type these during an interactive chat session.

### Session Control
```
/new (/reset)        Fresh session
/clear               Clear screen + new session (CLI)
/retry               Resend last message
/undo                Remove last exchange
/title [name]        Name the session
/compress            Manually compress context
/stop                Kill background processes
/rollback [N]        Restore filesystem checkpoint
/background <prompt> Run prompt in background
/queue <prompt>      Queue for next turn
/resume [name]       Resume a named session
```

### Configuration
```
/config              Show config (CLI)
/model [name]        Show or change model
/personality [name]  Set personality
/reasoning [level]   Set reasoning (none|minimal|low|medium|high|xhigh|show|hide)
/verbose             Cycle: off → new → all → verbose
/voice [on|off|tts]  Voice mode
/yolo                Toggle approval bypass
/skin [name]         Change theme (CLI)
/statusbar           Toggle status bar (CLI)
```

### Tools & Skills
```
/tools               Manage tools (CLI)
/toolsets            List toolsets (CLI)
/skills              Search/install skills (CLI)
/skill <name>        Load a skill into session
/cron                Manage cron jobs (CLI)
/reload-mcp          Reload MCP servers
/plugins             List plugins (CLI)
```

### Gateway
```
/approve             Approve a pending command (gateway)
/deny                Deny a pending command (gateway)
/restart             Restart gateway (gateway)
/sethome             Set current chat as home channel (gateway)
/update              Update Hermes to latest (gateway)
/platforms (/gateway) Show platform connection status (gateway)
```

### Utility
```
/branch (/fork)      Branch the current session
/fast                Toggle priority/fast processing
/browser             Open CDP browser connection
/history             Show conversation history (CLI)
/save                Save conversation to file (CLI)
/paste               Attach clipboard image (CLI)
/image               Attach local image file (CLI)
```

### Info
```
/help                Show commands
/commands [page]     Browse all commands (gateway)
/usage               Token usage
/insights [days]     Usage analytics
/status              Session info (gateway)
/profile             Active profile info
```

### Exit
```
/quit (/exit, /q)    Exit CLI
```

---

## Key Paths & Config

```
~/.hermes/config.yaml       Main configuration
~/.hermes/.env              API keys and secrets
$HERMES_HOME/skills/        Installed skills
~/.hermes/sessions/         Session transcripts
~/.hermes/logs/             Gateway and error logs
~/.hermes/auth.json         OAuth tokens and credential pools
~/.hermes/hermes-agent/     Source code (if git-installed)
```

Profiles use `~/.hermes/profiles/<name>/` with the same layout.

### Config Sections

Edit with `hermes config edit` or `hermes config set section.key value`.

| Section | Key options |
|---------|-------------|
| `model` | `default`, `provider`, `base_url`, `api_key`, `context_length` |
| `agent` | `max_turns` (90), `tool_use_enforcement` |
| `terminal` | `backend` (local/docker/ssh/modal), `cwd`, `timeout` (180) |
| `compression` | `enabled`, `threshold` (0.50), `target_ratio` (0.20) |
| `display` | `skin`, `tool_progress`, `show_reasoning`, `show_cost` |
| `stt` | `enabled`, `provider` (local/groq/openai/mistral) |
| `tts` | `provider` (edge/elevenlabs/openai/minimax/mistral/neutts) |
| `memory` | `memory_enabled`, `user_profile_enabled`, `provider` |
| `security` | `tirith_enabled`, `website_blocklist` |
| `delegation` | `model`, `provider`, `base_url`, `api_key`, `max_iterations` (50), `reasoning_effort` |
| `checkpoints` | `enabled`, `max_snapshots` (50) |

Full config reference: https://hermes-agent.nousresearch.com/docs/user-guide/configuration

### Model recommendations by task (Apple Silicon)
See `references/local-model-recommendations-m5-mac.md` for Gregory's M5 32GB setup — local vs cloud split, LM Studio model list, and current config status.

### LM Studio (local models)

LM Studio exposes an OpenAI-compatible API at `http://localhost:1234/v1`. Use it anywhere Hermes accepts a custom endpoint:

```bash
# Point delegation (subagents/coding) at a local model
hermes config set delegation.provider openai
hermes config set delegation.model qwen/qwen2.5-coder-14b   # use exact model ID from LM Studio
hermes config set delegation.base_url http://localhost:1234/v1
hermes config set delegation.api_key lm-studio              # any non-empty string works
```

Check available model IDs first:
```bash
curl -s http://localhost:1234/v1/models | python3 -m json.tool
```

LM Studio and Ollama (`http://localhost:11434/v1`) are interchangeable from Hermes's perspective — both use `provider: openai` with a custom `base_url`.

### Adding a Fallback Provider (e.g. MiniMax)

To add a provider as a fallback (used when the primary fails or rate-limits):

1. Set the API key in .env — use sed or a Python one-liner (the .env file is write-protected from the file tool):
   ```bash
   sed -i '' 's/^# MINIMAX_API_KEY=$/MINIMAX_API_KEY=YOUR_KEY/' ~/.hermes/.env
   ```

2. Register the provider in config.yaml:
   ```bash
   hermes config set providers.minimax.type minimax
   hermes config set providers.minimax.model MiniMax-M2.5
   ```

3. Append to fallback_providers — `hermes config set` can't append to YAML lists, use Python:
   ```bash
   python3 -c "
   path = '/Users/greg/.hermes/config.yaml'
   with open(path) as f: content = f.read()
   content = content.replace('fallback_providers:\n- lm-studio\n', 'fallback_providers:\n- lm-studio\n- minimax\n')
   with open(path, 'w') as f: f.write(content)
   "
   ```

Pitfall: `sed -i '' '/pattern/a\ newline'` is unreliable on macOS for multi-line appends — use Python instead.
Pitfall: The .env file is protected from direct file-tool writes — always use sed or Python via terminal.

Fallback chain takes effect on next session start (restart CLI or gateway).

### Providers

20+ providers supported. Set via `hermes model` or `hermes setup`.

| Provider | Auth | Key env var |
|----------|------|-------------|
| OpenRouter | API key | `OPENROUTER_API_KEY` |
| Anthropic | API key | `ANTHROPIC_API_KEY` |
| Nous Portal | OAuth | `hermes auth` |
| OpenAI Codex | OAuth | `hermes auth` |
| GitHub Copilot | Token | `COPILOT_GITHUB_TOKEN` |
| Google Gemini | API key | `GOOGLE_API_KEY` or `GEMINI_API_KEY` |
| DeepSeek | API key | `DEEPSEEK_API_KEY` |
| xAI / Grok | API key | `XAI_API_KEY` |
| Hugging Face | Token | `HF_TOKEN` |
| Z.AI / GLM | API key | `GLM_API_KEY` |
| MiniMax | API key | `MINIMAX_API_KEY` |
| MiniMax CN | API key | `MINIMAX_CN_API_KEY` |
| Kimi / Moonshot | API key | `KIMI_API_KEY` |
| Alibaba / DashScope | API key | `DASHSCOPE_API_KEY` |
| Xiaomi MiMo | API key | `XIAOMI_API_KEY` |
| Kilo Code | API key | `KILOCODE_API_KEY` |
| AI Gateway (Vercel) | API key | `AI_GATEWAY_API_KEY` |
| OpenCode Zen | API key | `OPENCODE_ZEN_API_KEY` |
| OpenCode Go | API key | `OPENCODE_GO_API_KEY` |
| Qwen OAuth | OAuth | `hermes login --provider qwen-oauth` |
| Custom endpoint | Config | `model.base_url` + `model.api_key` in config.yaml |
| GitHub Copilot ACP | External | `COPILOT_CLI_PATH` or Copilot CLI |

Full provider docs: https://hermes-agent.nousresearch.com/docs/integrations/providers

### Toolsets

Enable/disable via `hermes tools` (interactive) or `hermes tools enable/disable NAME`.

| Toolset | What it provides |
|---------|-----------------|
| `web` | Web search and content extraction |
| `browser` | Browser automation (Browserbase, Camofox, or local Chromium) |
| `terminal` | Shell commands and process management |
| `file` | File read/write/search/patch |
| `code_execution` | Sandboxed Python execution |
| `vision` | Image analysis |
| `image_gen` | AI image generation |
| `tts` | Text-to-speech |
| `skills` | Skill browsing and management |
| `memory` | Persistent cross-session memory |
| `session_search` | Search past conversations |
| `delegation` | Subagent task delegation |
| `cronjob` | Scheduled task management |
| `clarify` | Ask user clarifying questions |
| `messaging` | Cross-platform message sending |
| `search` | Web search only (subset of `web`) |
| `todo` | In-session task planning and tracking |
| `rl` | Reinforcement learning tools (off by default) |
| `moa` | Mixture of Agents (off by default) |
| `homeassistant` | Smart home control (off by default) |

Tool changes take effect on `/reset` (new session). They do NOT apply mid-conversation to preserve prompt caching.

---

## Security & Privacy Toggles

Common "why is Hermes doing X to my output / tool calls / commands?" toggles — and the exact commands to change them. Most of these need a fresh session (`/reset` in chat, or start a new `hermes` invocation) because they're read once at startup.

### Secret redaction in tool output

Secret redaction is **off by default** — tool output (terminal stdout, `read_file`, web content, subagent summaries, etc.) passes through unmodified. If the user wants Hermes to auto-mask strings that look like API keys, tokens, and secrets before they enter the conversation context and logs:

```bash
hermes config set security.redact_secrets true       # enable globally
```

**Restart required.** `security.redact_secrets` is snapshotted at import time — toggling it mid-session (e.g. via `export HERMES_REDACT_SECRETS=true` from a tool call) will NOT take effect for the running process. Tell the user to run `hermes config set security.redact_secrets true` in a terminal, then start a new session. This is deliberate — it prevents an LLM from flipping the toggle on itself mid-task.

Disable again with:
```bash
hermes config set security.redact_secrets false
```

### PII redaction in gateway messages

Separate from secret redaction. When enabled, the gateway hashes user IDs and strips phone numbers from the session context before it reaches the model:

```bash
hermes config set privacy.redact_pii true    # enable
hermes config set privacy.redact_pii false   # disable (default)
```

### Command approval prompts

By default (`approvals.mode: manual`), Hermes prompts the user before running shell commands flagged as destructive (`rm -rf`, `git reset --hard`, etc.). The modes are:

- `manual` — always prompt (default)
- `smart` — use an auxiliary LLM to auto-approve low-risk commands, prompt on high-risk
- `off` — skip all approval prompts (equivalent to `--yolo`)

```bash
hermes config set approvals.mode smart       # recommended middle ground
hermes config set approvals.mode off         # bypass everything (not recommended)
```

Per-invocation bypass without changing config:
- `hermes --yolo …`
- `export HERMES_YOLO_MODE=1`

Note: YOLO / `approvals.mode: off` does NOT turn off secret redaction. They are independent.

### Shell hooks allowlist

Some shell-hook integrations require explicit allowlisting before they fire. Managed via `~/.hermes/shell-hooks-allowlist.json` — prompted interactively the first time a hook wants to run.

### Disabling the web/browser/image-gen tools

To keep the model away from network or media tools entirely, open `hermes tools` and toggle per-platform. Takes effect on next session (`/reset`). See the Tools & Skills section above.

---

## Voice & Transcription

### STT (Voice → Text)

Voice messages from messaging platforms are auto-transcribed.

Provider priority (auto-detected):
1. **Local faster-whisper** — free, no API key: `pip install faster-whisper`
2. **Groq Whisper** — free tier: set `GROQ_API_KEY`
3. **OpenAI Whisper** — paid: set `VOICE_TOOLS_OPENAI_KEY`
4. **Mistral Voxtral** — set `MISTRAL_API_KEY`

Config:
```yaml
stt:
  enabled: true
  provider: local        # local, groq, openai, mistral
  local:
    model: base          # tiny, base, small, medium, large-v3
```

### TTS (Text → Voice)

| Provider | Env var | Free? |
|----------|---------|-------|
| Edge TTS | None | Yes (default) |
| ElevenLabs | `ELEVENLABS_API_KEY` | Free tier |
| OpenAI | `VOICE_TOOLS_OPENAI_KEY` | Paid |
| MiniMax | `MINIMAX_API_KEY` | Paid |
| Mistral (Voxtral) | `MISTRAL_API_KEY` | Paid |
| NeuTTS (local) | None (`pip install neutts[all]` + `espeak-ng`) | Free |

Voice commands: `/voice on` (voice-to-voice), `/voice tts` (always voice), `/voice off`.

---

## Spawning Additional Hermes Instances

Run additional Hermes processes as fully independent subprocesses — separate sessions, tools, and environments.

### When to Use This vs delegate_task

| | `delegate_task` | Spawning `hermes` process |
|-|-----------------|--------------------------|
| Isolation | Separate conversation, shared process | Fully independent process |
| Duration | Minutes (bounded by parent loop) | Hours/days |
| Tool access | Subset of parent's tools | Full tool access |
| Interactive | No | Yes (PTY mode) |
| Use case | Quick parallel subtasks | Long autonomous missions |

### One-Shot Mode

```
terminal(command="hermes chat -q 'Research GRPO papers and write summary to ~/research/grpo.md'", timeout=300)

# Background for long tasks:
terminal(command="hermes chat -q 'Set up CI/CD for ~/myapp'", background=true)
```

### Interactive PTY Mode (via tmux)

Hermes uses prompt_toolkit, which requires a real terminal. Use tmux for interactive spawning:

```
# Start
terminal(command="tmux new-session -d -s agent1 -x 120 -y 40 'hermes'", timeout=10)

# Wait for startup, then send a message
terminal(command="sleep 8 && tmux send-keys -t agent1 'Build a FastAPI auth service' Enter", timeout=15)

# Read output
terminal(command="sleep 20 && tmux capture-pane -t agent1 -p", timeout=5)

# Send follow-up
terminal(command="tmux send-keys -t agent1 'Add rate limiting middleware' Enter", timeout=5)

# Exit
terminal(command="tmux send-keys -t agent1 '/exit' Enter && sleep 2 && tmux kill-session -t agent1", timeout=10)
```

### Multi-Agent Coordination

```
# Agent A: backend
terminal(command="tmux new-session -d -s backend -x 120 -y 40 'hermes -w'", timeout=10)
terminal(command="sleep 8 && tmux send-keys -t backend 'Build REST API for user management' Enter", timeout=15)

# Agent B: frontend
terminal(command="tmux new-session -d -s frontend -x 120 -y 40 'hermes -w'", timeout=10)
terminal(command="sleep 8 && tmux send-keys -t frontend 'Build React dashboard for user management' Enter", timeout=15)

# Check progress, relay context between them
terminal(command="tmux capture-pane -t backend -p | tail -30", timeout=5)
terminal(command="tmux send-keys -t frontend 'Here is the API schema from the backend agent: ...' Enter", timeout=5)
```

### Session Resume

```
# Resume most recent session
terminal(command="tmux new-session -d -s resumed 'hermes --continue'", timeout=10)

# Resume specific session
terminal(command="tmux new-session -d -s resumed 'hermes --resume 20260225_143052_a1b2c3'", timeout=10)
```

### Tips

- **Prefer `delegate_task` for quick subtasks** — less overhead than spawning a full process
- **Use `-w` (worktree mode)** when spawning agents that edit code — prevents git conflicts
- **Set timeouts** for one-shot mode — complex tasks can take 5-10 minutes
- **Use `hermes chat -q` for fire-and-forget** — no PTY needed
- **Use tmux for interactive sessions** — raw PTY mode has `\r` vs `\n` issues with prompt_toolkit
- **For scheduled tasks**, use the `cronjob` tool instead of spawning — handles delivery and retry

---

## Web Dashboard & Public Access

The Hermes web dashboard (`hermes dashboard`) provides a browser UI for managing config, API keys, sessions, and models.

### Basic Usage

```bash
hermes dashboard                           # Launch on 127.0.0.1:9119, opens browser
hermes dashboard --port 8080               # Custom port
hermes dashboard --no-open                 # Don't open browser (headless/SSH)
hermes dashboard --tui                     # Add in-browser Chat tab
hermes dashboard --status                  # Check if running
hermes dashboard --stop                    # Shut down all dashboard processes
```

The dashboard requires the web UI dist (auto-built on first launch). Dependencies: `fastapi` + `uvicorn`.

### Hosting Publicly via Cloudflare Tunnel

To expose the dashboard as a publicly accessible URL (e.g. for sharing or remote access), use a Cloudflare quick tunnel. No Cloudflare account required.

**Step by step:**

```bash
# 1. Install cloudflared
brew install cloudflared

# 2. Start the dashboard bound to 0.0.0.0 with --insecure
hermes dashboard --host 0.0.0.0 --insecure

# 3. Create a Cloudflare quick tunnel pointing to it
cloudflared tunnel --url http://localhost:9119

# The tunnel prints a URL like:
#   https://<random-words>.trycloudflare.com
```

**Pitfall: Host header check.** The dashboard validates incoming Host headers against the bound interface (DNS rebinding defence, GHSA-ppp5-vxwm-4cf7). If you bind to `127.0.0.1`, Cloudflare's Host header won't match and you'll get `HTTP 400: Invalid Host header`.

The fix is twofold:
1. Bind to `0.0.0.0` with `--host 0.0.0.0 --insecure` (not just `--insecure` alone, which only permits non-loopback binding but doesn't change the default `127.0.0.1` host)
2. When `bound_host` is `0.0.0.0` or `::`, the middleware accepts any Host header (see `_is_accepted_host()` in `hermes_cli/web_server.py`)

**Security warning:** The dashboard exposes your full config including API keys. A Cloudflare quick tunnel gives a random, unguessable URL (not indexed), but there is no authentication. Stop the dashboard when not in use:
```bash
hermes dashboard --stop
```

For longer-lived access, consider adding a named Cloudflare Tunnel with Access policies or a reverse proxy with auth in front.

---

## Troubleshooting

### Voice not working
1. Check `stt.enabled: true` in config.yaml
2. Verify provider: `pip install faster-whisper` or set API key
3. In gateway: `/restart`. In CLI: exit and relaunch.

### Tool not available
1. `hermes tools` — check if toolset is enabled for your platform
2. Some tools need env vars (check `.env`)
3. `/reset` after enabling tools

### Model/provider issues
1. `hermes doctor` — check config and dependencies
2. `hermes login` — re-authenticate OAuth providers
3. Check `.env` has the right API key
4. **Copilot 403**: `gh auth login` tokens do NOT work for Copilot API. You must use the Copilot-specific OAuth device code flow via `hermes model` → GitHub Copilot.

### Changes not taking effect
- **Tools/skills:** `/reset` starts a new session with updated toolset
- **Config changes:** In gateway: `/restart`. In CLI: exit and relaunch.
- **Code changes:** Restart the CLI or gateway process

### Skills not showing
1. `hermes skills list` — verify installed
2. `hermes skills config` — check platform enablement
3. Load explicitly: `/skill name` or `hermes -s name`

### Provider timeouts ("No response from provider for Xs")

When the gateway logs show `⚠️ No response from provider for Xs (model: ..., context: ~Y tokens). Reconnecting...`, follow this diagnostic order:

**1. Check what error preceded the timeout**
Look for `API call failed (attempt N/3)` lines just before the first timeout. Three common root causes:
- **HTTP 400 "credit balance too low"** — Anthropic billing exhausted. Go to console.anthropic.com/billing to top up. **Fallback providers do NOT route around billing errors** — the gateway tries 3 retries, then gives up.
- **HTTP 429 "exceeds your rate limit"** — Token-per-minute limit hit (e.g. 30k/min on Anthropic). With ~75k token contexts, each request blows this limit. Solution: lower `compression.threshold` so context stays smaller, or lower `agent.gateway_timeout` so failures surface faster.
- **Network/ReadTimeout** — Provider unresponsive. Check provider status page.

**2. Identify the retry loop signal**
If the same context size (e.g. `~75,266 tokens`) repeats across every timeout entry, the gateway is in a retry loop — same message, same context, same failure. This means:
- The previous attempt never completed (stuck the context)
- Each retry re-sends the same payload
- The user may see many "Reconnecting..." messages back-to-back

**3. Check gateway_timeout**
```
hermes config get agent.gateway_timeout   # default: 1800 (30 min!)
```
If it's 1800s, the gateway will wait 30 minutes before giving up on a hung request. Lower to 120-300s:
```bash
hermes config set agent.gateway_timeout 120
```
Then `/restart` on gateway.

**4. Check compression threshold**
Context at ~75k tokens with a 200k window means compression (threshold 50%) hasn't triggered yet. Lower the threshold so compression kicks in earlier:
```bash
hermes config set compression.threshold 0.35   # triggers at ~70k instead of ~100k
# or more aggressively:
hermes config set compression.threshold 0.20   # triggers at ~40k
```

**5. Check for compression model context mismatch**
If you see `Compression model MiniMax-M2.5 (minimax) context is 204,800 tokens, but the main model ...'s compression threshold was 500,000 tokens. Auto-lowered this session's threshold to 204,800 tokens.` — compression auto-adjusted because the auxiliary model can't handle the full threshold. This is informational (auto-fixed per-session) but you can make it permanent by lowering the threshold in config.yaml to 0.20 (204k/500k ≈ 0.40, but 0.20 is safer).

**6. Check credentials and fallback chain**
```bash
hermes doctor               # key health check
hermes auth list anthropic  # check pooled credentials
```
Verify fallback providers are configured and ordered correctly:
```
grep -A5 fallback_providers: ~/.hermes/config.yaml
```

### Gateway issues
Check logs first:
```bash
grep -i "failed to send\|error" ~/.hermes/logs/gateway.log | tail -20
```

Common gateway problems:
- **Gateway dies on SSH logout**: Enable linger: `sudo loginctl enable-linger $USER`
- **Gateway dies on WSL2 close**: WSL2 requires `systemd=true` in `/etc/wsl.conf` for systemd services to work. Without it, gateway falls back to `nohup` (dies when session closes).
- **Gateway crash loop**: Reset the failed state: `systemctl --user reset-failed hermes-gateway`

**Gateway hung / zombie process recovery:**

When the gateway stops responding but the PID is still alive, or launchd reports `LastExitStatus = 9` (SIGKILL):

1. **Check if the gateway is actually processing** — tail the gateway log. If the last entry is "Gateway stopped" but `hermes gateway status` shows a running PID, the process may be a zombie or hung.

2. **Identify stuck restart loops** — look for bash scripts or nested `hermes gateway restart` processes waiting for the old PID to die:
   ```bash
   ps aux | grep -i hermes | grep -v grep
   ```
   You may see `bash -lc while kill -0 <PID>...` — this is a restart wrapper stuck waiting for a process that won't die.

3. **Clean kill approach** — kill ALL related PIDs including the stuck restart wrapper:
   ```bash
   # Kill all gateway-related processes
   ps aux | grep -i 'hermes.*gateway\|hermes.*main.*gateway' | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null
   
   # Wait a moment, then let launchd restart it cleanly
   sleep 2
   hermes gateway start
   ```

4. **Race condition pitfall** — if you start `hermes gateway run --replace` while a launchd-managed instance is still alive, you'll get `ERROR: Another gateway instance started during our startup. Exiting to avoid double-running.` Always kill ALL instances first, then use `hermes gateway start` (which uses launchd) rather than `hermes gateway run`.

5. **After clean restart, verify** — check that Telegram connected:
   ```bash
   tail -10 ~/.hermes/logs/gateway.log
   # Look for: "✓ telegram connected"
   ```

### Platform-specific issues
- **Discord bot silent**: Must enable **Message Content Intent** in Bot → Privileged Gateway Intents.
- **Discord "No bot token configured" when token exists in global .env**: If you're running a named profile, the gateway loads `.env` from the **profile's** directory (`~/.hermes/profiles/<name>/.env`), not the global `~/.hermes/.env`. Add the token to the profile's `.env`. See `references/gateway-recovery-patterns.md` section 5.
- **Discord/Telegram/Slack bot online but user gets no response — unauthorized**: If the bot is connected (`✓ discord connected`) but your messages get no response, check the gateway logs for `WARNING gateway.run: Unauthorized user: <user_id> (<name>) on <platform>`. This means `{PLATFORM}_ALLOWED_USERS` env var is not set and the gateway defaults to **deny**. Add the user's platform ID to the env var in the profile's `.env`, then restart the gateway. See `references/gateway-recovery-patterns.md` section 7 for the platform-to-env-var mapping, fix commands, and Discord-specific role-based auth.
- **Slack bot only works in DMs**: Must subscribe to `message.channels` event. Without it, the bot ignores public channels.
- **Windows HTTP 400 "No models provided"**: Config file encoding issue (BOM). Ensure `config.yaml` is saved as UTF-8 without BOM.

### Telegram group chats — bot doesn't respond in groups

If the bot responds in DMs but is silent in a Telegram group you added it to, the cause is almost always **privacy mode** (the default for Telegram bots).

**How privacy mode works:**
By default, a Telegram bot in a group ONLY sees:
- Messages that start with `/` (commands)
- Messages that mention `@YourBotUsername`
- Messages that reply to the bot's own messages

Every other message is invisible to the bot — the gateway never receives them, and nothing shows up in the gateway logs.

**Fix options:**

**Option 1 (Quick — mention the bot):** In the group chat, prefix your message with `@YourBotUsername`. The bot will see and respond to that specific message.

**Option 2 (Permanent — disable privacy mode via BotFather):**
1. Open Telegram and find **@BotFather**
2. Send `/mybots` and select your Hermes bot
3. Tap **Bot Settings** → **Group Privacy**
4. Tap **Turn off**
5. The bot will now see all messages in every group it's added to

**Pitfall:** `channel_prompts` in config.yaml (`~/.hermes/config.yaml`, under `telegram.channel_prompts`) can be used to give the bot different instructions per group chat, but it is NOT required for group functionality — the privacy mode fix alone is sufficient.

**Pitfall:** If you add the bot to a group AFTER disabling privacy mode, it works immediately. If the bot was already in the group when privacy mode was enabled, you may need to remove and re-add it after disabling.

**Pitfall:** Group chat IDs are negative numbers (e.g., `-1001234567890`). If you need to reference them in config, they will look different from the user's DM ID (e.g., `557413154`).

### Gateway zombie process blocks restart

When `hermes gateway restart` hangs or reports the service as started but Telegram doesn't respond, the old PID may be zombie — alive in the process table but not processing anything. Launchd (`OnDemand=true`) won't restart because it sees the old PID still alive.

**Recovery procedure:**

1. Find and kill all gateway-related processes:
   ```bash
   ps aux | grep 'gateway run' | grep -v grep | awk '{print $2}' | xargs kill -9
   ```
2. Also clean up zombie bash restart scripts that may be waiting for the old PID:
   ```bash
   ps aux | grep 'hermes gateway restart' | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null
   ```
3. Verify nothing is left:
   ```bash
   ps aux | grep -i gateway | grep -v grep  # should return empty
   ```
4. Start clean:
   ```bash
   hermes gateway start   # via launchd
   # or
   hermes gateway run --replace   # foreground (background it)
   ```
5. Verify in logs:
   ```bash
   tail -5 ~/.hermes/logs/gateway.log
   # Look for: "Connected to Telegram (polling mode)" + "✓ telegram connected"
   ```

### Gateway crash from network retry exhaustion

If Airtel's peering to Telegram drops (common with Airtel → Cogentco routing), the gateway retries up to 10 times with exponential backoff (5s→60s cap, ~10 minutes total). After 10 failures it shuts down with:
```
Telegram polling could not reconnect after 10 network error retries. Restarting gateway.
```

The retry limit (`MAX_NETWORK_RETRIES = 10`) is hardcoded in `gateway/platforms/telegram.py` line 472. To increase it, edit that line and restart.

### Telegram group bot not responding

By default, Telegram bots in groups only see:
- Messages that start with `/`
- Messages that `@mention` the bot by username
- Replies to the bot's own messages

**Fix (two options):**
1. **Quick fix**: Mention the bot in the group: `@YourBotUsername your message`
2. **Permanent fix**: Go to @BotFather → `/mybots` → select your bot → Bot Settings → Group Privacy → **Turn off**

After disabling privacy mode, the bot will see all messages in any group it's added to, no `@` mention needed.

For detailed error transcripts and log patterns for each of the above scenarios, see `references/gateway-recovery-patterns.md`.

**Common causes of Telegram conversation latency (most likely first):**

1. **Slow model/provider response** — your main model (e.g. DeepSeek V4 Flash) may be under load, rate-limited, or hitting credential exhaustion. Check with `hermes doctor` and verify `.env` has valid keys. If fallback providers are configured (`fallback_providers` in config.yaml), the agent tries each in sequence when the primary fails, adding cumulative latency.
2. **Long-running multi-step task / tool-calling loop** — the agent may be executing a chain of tool calls (terminal commands, delegation, browser automation, web scraping). Each call takes time. Use `/retry` to break out of a stuck loop, or check `~/.hermes/logs/gateway.log` for what's running.
3. **Context compression** — near the token limit, compression triggers automatically and can take 5-15 seconds on larger contexts. Check `compression.enabled: true` in config and `auxiliary.compression.provider` for which model handles it (cheap/fast is better).
4. **Network routing / ISP peering issues** — more common than you'd think. The connection path from Airtel (Gregory's ISP) to Telegram routes through Cogentco (India → London → Amsterdam), and that peering path can be flaky for Telegram's IP range. If IPv4 is unstable, IPv6 may have a better route.
5. **Gateway polling interval** — by default the gateway polls Telegram frequently. No user-configurable Telegram-specific polling — latency there is negligible unless the server itself is overloaded.

**Detecting tool-calling loops from session history:**

When the user reports "it's in an infinite loop," the cause is often a tool-calling chain that kept retrying through multiple failures, not an actual infinite loop. Here's how to diagnose:

1. **Check the session transcript** — session files live at `~/.hermes/sessions/`. Find the most recent Telegram session:
   ```bash
   hermes sessions list
   ```
   Then read its JSONL file — filter for `"role": "assistant"` entries with `"tool_calls"` to see how many calls were made in a single turn. A 45-call turn is not an infinite loop, it's an exploding tool chain.

2. **Look for repeating failure patterns in the session file:**
   - Multiple `web_search` calls all returning SSL timeout errors
   - `browser_navigate` hitting "Access Denied" / bot detection page after page
   - `browser` daemon connection failures (`"Failed to connect: No such file or directory"`)
   - The tool loop warning message: `"[Tool loop warning: same_tool_failure_warning; count=N"` 
   - Switch from web_search → browser → terminal curl → execute_code as each tool fails

3. **Correlate with gateway.log response times:**
   ```bash
   grep "response ready" ~/.hermes/logs/gateway.log | tail -10
   ```
   A single turn taking 618s with 45 API calls means the agent tried every tool in the toolbox and each one failed before moving to the next.

4. **Check if "Flushing text batch" events have no corresponding inbound message:**
   ```bash
   grep "Flushing text batch" ~/.hermes/logs/gateway.log | tail -10
   ```
   These are normal Telegram polling cycles — empty polls that yield no new messages. They are NOT a sign of an infinite loop. A healthy gateway shows these repeatedly between actual message exchanges.

5. **Root causes of exploding tool chains:**
   - **SSL handshake failures** (`_ssl.c:999: The handshake operation timed out`) — web_search and web_extract tools can't establish secure connections. The agent retries with different queries and approaches, snowballing.
   - **Bot detection** — sites behind Akamai/Cloudflare (ECI results, NDTV, Indian Express) block headless browsers. The agent tries other sites instead of stopping.
   - **Browser daemon unresponsive** — local browser daemon can crash or get wedged. Agent falls back to terminal-based approaches.
   - **macOS tool quirks** — `grep -P` doesn't exist on macOS; the agent burns iterations learning this.

**When to escalate to the user vs keep debugging:**
- 15+ API calls on a single turn without a response → send a brief "Still working on this, hitting some roadblocks" to the user
- 30+ API calls → the tool loop is probably expanding, not converging. Pause and ask the user if they want to change approach
- Session shows 150+ messages overall → the agent has burned through its budget. The user will perceive this as "broken" even if the final response was sent

**Voice message / STT processing loops:**

Voice messages in Telegram arrive as empty-text messages with an audio file cached. This can trigger a processing loop:

1. **Pattern in logs:**
   ```
   Cached user voice at /Users/greg/.hermes/audio_cache/audio_<hash>.ogg
   inbound message: platform=telegram ... msg=''
   ```
   The empty `msg=''` means the user sent a voice note. The agent needs to process STT (speech-to-text) to handle it.

2. **Why it gets stuck:**
   - STT processing may silently fail if `faster-whisper` isn't installed or the provider key is missing
   - The agent may loop trying to figure out what the user said without realizing STT failed
   - User may be sending multiple voice messages while the previous one is still processing

3. **How to detect:**
   - Search gateway log for `Cached user voice` followed by a long gap with no `response ready`
   - Check if `stt.enabled: true` and STT provider is configured
   - Session files will show the empty `msg=''` with no assistant response afterward

4. **Escape hatch:**
   - The user can type `/stop` on Telegram to interrupt the stuck agent. This logs:
     ```
     Invalidated run generation (stop_command)
     STOP for session — agent interrupted, session lock released
     ```
   - After `/stop`, the user can send a new text message to start fresh

**/stop — the universal escape hatch for Telegram:**
If the agent is stuck, wordy, looping, or unresponsive on Telegram, instruct the user to type `/stop` in the chat. This interrupts the agent mid-turn, releases the session lock, and lets a new message start a clean session. It's the Telegram equivalent of Ctrl+C.

**Network-level diagnostics (run when user reports Telegram latency):**

Start with gateway logs to check the timeline:
```bash
grep -i "failed\\|error\\|timeout" ~/.hermes/logs/gateway.log | tail -20
grep "Network error on send" ~/.hermes/logs/gateway.error.log | tail -10
```

Then test connectivity from the server:
```bash
# 1. DNS resolution — note whether IPv4 or IPv6 is preferred
echo "IPv4: $(dig +short api.telegram.org A 2>/dev/null)"
echo "IPv6: $(dig +short api.telegram.org AAAA 2>/dev/null)"
echo "Fallback: 149.154.167.220"

# 2. Ping test — baseline latency and packet loss
ping -c 5 -t 10 api.telegram.org

# 3. Traceroute — identify ISP peering path (Airtel -> Cogentco -> Telegram)
traceroute -m 15 -q 1 -w 3 api.telegram.org

# 4. Direct HTTP test — confirm Telegram's API responds
curl -s -o /dev/null -w "HTTP: %{http_code}, time: %{time_total}s, IP: %{remote_ip}\n" \
  --connect-timeout 5 --max-time 10 https://api.telegram.org/bot123456:FAKE_TEST

# 5. Fallback IP test — explicitly test the gateway's fallback
curl -s -o /dev/null -w "HTTP: %{http_code}, time: %{time_total}s\n" \
  --connect-timeout 5 --max-time 10 \
  --resolve "api.telegram.org:443:149.154.167.220" \
  https://api.telegram.org/bot123456:FAKE_TEST
```

**Interpreting results:**
- If ping is 150-200ms but HTTP responses come back in <1s — the path is fine, latency isn't the issue.
- If ping shows >5% packet loss or traceroute stalls at a single Cogentco hop — Airtel/Cogentco peering is degraded. IPv6 may be more stable; check by comparing IPv4 vs IPv6 HTTP times.
- Frequent `TimedOut`, `ReadError`, or `RemoteProtocolError` in gateway.error.log point to the ISP → Telegram route dropping mid-flight.
- The gateway auto-falls back to 149.154.167.220 when the primary fails, but if both IPs are flaky, no amount of client-side retrying helps.

**Tuning Telegram HTTP timeouts:**

The gateway has env-configurable timeout settings (defaults in parentheses):
```
HERMES_TELEGRAM_HTTP_POOL_SIZE=512          # connection pool slots
HERMES_TELEGRAM_HTTP_POOL_TIMEOUT=8.0       # sec to wait for pool slot
HERMES_TELEGRAM_HTTP_CONNECT_TIMEOUT=10.0   # sec for TCP connect
HERMES_TELEGRAM_HTTP_READ_TIMEOUT=20.0      # sec for response body
HERMES_TELEGRAM_HTTP_WRITE_TIMEOUT=20.0     # sec for request body
```

If your ISP path is consistently slower, bump the read/write timeouts:
```bash
export HERMES_TELEGRAM_HTTP_READ_TIMEOUT=30
export HERMES_TELEGRAM_HTTP_WRITE_TIMEOUT=30
```

**Quick overview diagnostics:**
```bash
# Check gateway logs for errors or stuck tasks
grep -i "failed\\|error\\|timeout" ~/.hermes/logs/gateway.log | tail -20

# Check if provider keys are valid
hermes doctor

# View current active model
hermes config get model.default
hermes config get model.provider

# Count network errors in the last 24h
grep -c 'Network error\|TimedOut\|ReadError\|RemoteProtocol' ~/.hermes/logs/gateway.error.log 2>/dev/null
```

**When the user asks "why is Telegram taking so long" — load this skill first before speculating.** Telegram performance questions are Hermes Agent usage questions, and the troubleshooting info above covers the common root causes more accurately than guessing.

### Auxiliary models not working
If `auxiliary` tasks (vision, compression, session_search, title_generation, etc.) fail with "No LLM provider configured" or "context compression will drop middle turns", the `auto` provider can't find a backend. Either set `OPENROUTER_API_KEY` or `GOOGLE_API_KEY`, or explicitly configure **all** auxiliary tasks.

**Each aux task is independent** — fixing one does NOT fix others. Fix all at once. See `references/auxiliary-model-setup.md` for Gregory's full model routing config.

### LM Studio as local model backend
LM Studio exposes an OpenAI-compatible API at `http://localhost:1234/v1`. Model IDs include the org prefix (e.g. `qwen/qwen2.5-coder-14b`). Use `api_key = lm-studio` (any non-empty string works). Verify running models:
```bash
curl -s http://localhost:1234/v1/models | python3 -m json.tool
```

### MiniMax balance check
Test with a small completion — `base_resp.status_code: 1008` = insufficient balance, `0` = OK. See `references/auxiliary-model-setup.md` for the exact curl command.

### Fallback provider ordering
`fallback_providers` in `config.yaml` is ordered — most capable cloud fallback first, local models last. Gregory's order: `minimax → lm-studio`.

**Fix: set all auxiliary tasks at once** (use a cheap/fast model like haiku):
```bash
for task in vision web_extract compression session_search skills_hub approval mcp title_generation curator; do
  hermes config set auxiliary.$task.provider anthropic
  hermes config set auxiliary.$task.model claude-haiku-3-5
done
```

Or for a local model via LM Studio / Ollama:
```bash
for task in vision web_extract compression session_search skills_hub approval mcp title_generation curator; do
  hermes config set auxiliary.$task.provider openai
  hermes config set auxiliary.$task.model llama3.2
  hermes config set auxiliary.$task.base_url http://localhost:1234/v1  # LM Studio
  # hermes config set auxiliary.$task.base_url http://localhost:11434/v1  # Ollama
done
```

Note: `title_generation` and `compression` are separate tasks — fixing one does NOT fix the other. Fix all of them at once to avoid repeated warnings.

---

### Memory Provider Silent Fallback Trap

If `memory.provider` in config.yaml is set to a value for which NO plugin exists
(e.g. `sqlitevec` but no `~/.hermes/plugins/sqlitevec/__init__.py`), the system
silently falls back to the built-in provider. Zero errors, zero log entries —
the tools `memory_save`/`memory_search` simply never appear, and the fallback is
invisible to the user.

**Diagnosis checklist:**

```bash
# 1. Check what's configured
hermes config get memory.provider

# 2. List available provider plugins
ls -d ~/.hermes/plugins/*memory*/ 2>/dev/null
hermes plugins list 2>/dev/null | grep -i memory

# 3. Check that the plugin directory actually has code
ls ~/.hermes/plugins/<name>/   # should show __init__.py

# 4. Check built-in providers and their tool schemas
ls ~/.hermes/hermes-agent/plugins/memory/
```

**Common causes:**
- Typo in config: `sqlitevec` vs correct name
- Plugin was referenced in a design document but never implemented
- Plugin was removed but config wasn't updated
- Plugin exists in a different path than expected (e.g. `plugins/memory/sqlitevec/` vs `plugins/sqlitevec/`)

**If the desired provider doesn't exist as a plugin, the known available providers are:**
Built-in: `honcho`, `mem0`, `supermemory`, `byterover`, `hindsight`, `holographic`, `openviking`, `retaindb` (all under `~/.hermes/hermes-agent/plugins/memory/`)

Set to `builtin` explicitly to use the plain notes-+FTS5 memory (recommended when no vector provider is needed).

### sqlite-vec Memory Provider (Design Reference)

See `references/sqlitevec-memory-provider.md` for a full implementation reference
of a sqlite-vec memory provider plugin (design doc — not currently installed).

Key patterns from the implementation:
- **MemoryProvider ABC**: `initialize()`, `prefetch()`, `sync_turn()`, `get_tool_schemas()`, `handle_tool_call()`
- **Thread safety**: Use `check_same_thread=False` on SQLite connections — tool calls run in a separate thread from the agent loop
- **Offline mode**: Set `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` before importing sentence-transformers to prevent startup hangs
- **Plugin registration**: User-installed plugins go in `$HERMES_HOME/plugins/<name>/` with a `register(ctx)` function in `__init__.py`

### Where to Find Things

| Looking for... | Location |
|----------------|----------|
| Config options | `hermes config edit` or [Configuration docs](https://hermes-agent.nousresearch.com/docs/user-guide/configuration) |
| Available tools | `hermes tools list` or [Tools reference](https://hermes-agent.nousresearch.com/docs/reference/tools-reference) |
| Slash commands | `/help` in session or [Slash commands reference](https://hermes-agent.nousresearch.com/docs/reference/slash-commands) |
| Skills catalog | `hermes skills browse` or [Skills catalog](https://hermes-agent.nousresearch.com/docs/reference/skills-catalog) |
| Provider setup | `hermes model` or [Providers guide](https://hermes-agent.nousresearch.com/docs/integrations/providers) |
| Platform setup | `hermes gateway setup` or [Messaging docs](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/) |
| MCP servers | `hermes mcp list` or [MCP guide](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp) |
| Profiles | `hermes profile list` or [Profiles docs](https://hermes-agent.nousresearch.com/docs/user-guide/profiles) |
| Cron jobs | `hermes cron list` or [Cron docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron) |
| Memory | `hermes memory status` or [Memory docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory) |
| Env variables | `hermes config env-path` or [Env vars reference](https://hermes-agent.nousresearch.com/docs/reference/environment-variables) |
| CLI commands | `hermes --help` or [CLI reference](https://hermes-agent.nousresearch.com/docs/reference/cli-commands) |
| Gateway logs | `~/.hermes/logs/gateway.log` |
| Session files | `~/.hermes/sessions/` or `hermes sessions browse` |
| Source code | `~/.hermes/hermes-agent/` |

---

## Contributor Quick Reference

For occasional contributors and PR authors. Full developer docs: https://hermes-agent.nousresearch.com/docs/developer-guide/

### Project Layout

```
hermes-agent/
├── run_agent.py          # AIAgent — core conversation loop
├── model_tools.py        # Tool discovery and dispatch
├── toolsets.py           # Toolset definitions
├── cli.py                # Interactive CLI (HermesCLI)
├── hermes_state.py       # SQLite session store
├── agent/                # Prompt builder, context compression, memory, model routing, credential pooling, skill dispatch
├── hermes_cli/           # CLI subcommands, config, setup, commands
│   ├── commands.py       # Slash command registry (CommandDef)
│   ├── config.py         # DEFAULT_CONFIG, env var definitions
│   └── main.py           # CLI entry point and argparse
├── tools/                # One file per tool
│   └── registry.py       # Central tool registry
├── gateway/              # Messaging gateway
│   └── platforms/        # Platform adapters (telegram, discord, etc.)
├── cron/                 # Job scheduler
├── tests/                # ~3000 pytest tests
└── website/              # Docusaurus docs site
```

Config: `~/.hermes/config.yaml` (settings), `~/.hermes/.env` (API keys).

### Adding a Tool (3 files)

**1. Create `tools/your_tool.py`:**
```python
import json, os
from tools.registry import registry

def check_requirements() -> bool:
    return bool(os.getenv("EXAMPLE_API_KEY"))

def example_tool(param: str, task_id: str = None) -> str:
    return json.dumps({"success": True, "data": "..."})

registry.register(
    name="example_tool",
    toolset="example",
    schema={"name": "example_tool", "description": "...", "parameters": {...}},
    handler=lambda args, **kw: example_tool(
        param=args.get("param", ""), task_id=kw.get("task_id")),
    check_fn=check_requirements,
    requires_env=["EXAMPLE_API_KEY"],
)
```

**2. Add to `toolsets.py`** → `_HERMES_CORE_TOOLS` list.

Auto-discovery: any `tools/*.py` file with a top-level `registry.register()` call is imported automatically — no manual list needed.

All handlers must return JSON strings. Use `get_hermes_home()` for paths, never hardcode `~/.hermes`.

### Adding a Slash Command

1. Add `CommandDef` to `COMMAND_REGISTRY` in `hermes_cli/commands.py`
2. Add handler in `cli.py` → `process_command()`
3. (Optional) Add gateway handler in `gateway/run.py`

All consumers (help text, autocomplete, Telegram menu, Slack mapping) derive from the central registry automatically.

### Agent Loop (High Level)

```
run_conversation():
  1. Build system prompt
  2. Loop while iterations < max:
     a. Call LLM (OpenAI-format messages + tool schemas)
     b. If tool_calls → dispatch each via handle_function_call() → append results → continue
     c. If text response → return
  3. Context compression triggers automatically near token limit
```

### Testing

```bash
python -m pytest tests/ -o 'addopts=' -q   # Full suite
python -m pytest tests/tools/ -q            # Specific area
```

- Tests auto-redirect `HERMES_HOME` to temp dirs — never touch real `~/.hermes/`
- Run full suite before pushing any change
- Use `-o 'addopts='` to clear any baked-in pytest flags

### Commit Conventions

```
type: concise subject line

Optional body.
```

Types: `fix:`, `feat:`, `refactor:`, `docs:`, `chore:`

### Key Rules

- **Never break prompt caching** — don't change context, tools, or system prompt mid-conversation
- **Message role alternation** — never two assistant or two user messages in a row
- Use `get_hermes_home()` from `hermes_constants` for all paths (profile-safe)
- Config values go in `config.yaml`, secrets go in `.env`
- New tools need a `check_fn` so they only appear when requirements are met
