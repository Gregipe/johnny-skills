# Claude Code Detailed Guide

This file contains the detailed Claude Code documentation migrated from the former `claude-code` skill.

## Prerequisites

- **Install:** `npm install -g @anthropic-ai/claude-code`
- **Auth:** run `claude` once to log in (browser OAuth for Pro/Max, or set `ANTHROPIC_API_KEY`)
- **Console auth:** `claude auth login --console` for API key billing
- **SSO auth:** `claude auth login --sso` for Enterprise
- **Check status:** `claude auth status` (JSON) or `claude auth status --text` (human-readable)
- **Health check:** `claude doctor` — checks auto-updater and installation health
- **Version check:** `claude --version` (requires v2.x+)
- **Update:** `claude update` or `claude upgrade`

## Two Orchestration Modes

Hermes interacts with Claude Code in two fundamentally different ways:

### Mode 1: Print Mode (`-p`) — Non-Interactive (PREFERRED)

Print mode runs a one-shot task, returns the result, and exits. No PTY needed.

```bash
claude -p 'Add error handling to all API calls in src/' --allowedTools 'Read,Edit' --max-turns 10
```

**When to use print mode:**
- One-shot coding tasks
- CI/CD automation
- Structured data extraction with `--json-schema`
- Piped input processing

### Mode 2: Interactive PTY via tmux — Multi-Turn Sessions

Interactive mode gives a full conversational REPL. Requires tmux orchestration.

```bash
# Start tmux session
tmux new-session -d -s claude-work -x 140 -y 40
tmux send-keys -t claude-work 'cd /path/to/project && claude' Enter

# Wait for startup, then send task
sleep 5
tmux send-keys -t claude-work 'Refactor the auth module to use JWT tokens' Enter

# Monitor progress
tmux capture-pane -t claude-work -p -S -50

# Exit when done
tmux send-keys -t claude-work '/exit' Enter
```

## PTY Dialog Handling (CRITICAL)

Claude Code presents confirmation dialogs. Handle via tmux send-keys:

### Dialog 1: Workspace Trust
```
❯ 1. Yes, I trust this folder    ← DEFAULT (just press Enter)
  2. No, exit
```
**Handling:** `tmux send-keys -t <session> Enter`

### Dialog 2: Bypass Permissions Warning
```
❯ 1. No, exit                    ← DEFAULT (WRONG choice!)
  2. Yes, I accept
```
**Handling:** Must navigate DOWN first, then Enter:
```bash
tmux send-keys -t <session> Down && sleep 0.3 && tmux send-keys -t <session> Enter
```

## Print Mode Deep Dive

### Structured JSON Output
```bash
claude -p 'Analyze auth.py for security issues' --output-format json --max-turns 5
```

Returns JSON with session_id, num_turns, total_cost_usd, etc.

### Session Continuation
```bash
# Start a task
claude -p 'Start refactoring' --output-format json --max-turns 10 > /tmp/session.json

# Resume with session ID
claude -p 'Continue and add connection pooling' --resume $(cat /tmp/session.json | python3 -c 'import json,sys; print(json.load(sys.stdin)["session_id"])') --max-turns 5

# Continue most recent session
claude -p 'What did you do last time?' --continue --max-turns 1
```

## CLI Flags Reference

### Session & Environment
| Flag | Effect |
|------|--------|
| `-p, --print` | Non-interactive one-shot mode |
| `-c, --continue` | Resume most recent conversation |
| `-r, --resume <id>` | Resume specific session |
| `-w, --worktree [name]` | Run in isolated git worktree |

### Model & Performance
| Flag | Effect |
|------|--------|
| `--model <alias>` | Model: sonnet, opus, haiku |
| `--max-turns <n>` | Limit agentic loops (print mode only) |
| `--max-budget-usd <n>` | Cap API spend |

### Permission & Safety
| Flag | Effect |
|------|--------|
| `--dangerously-skip-permissions` | Auto-approve all tool use |
| `--allowedTools <tools...>` | Whitelist specific tools |

### Output Format
| Flag | Effect |
|------|--------|
| `--output-format json` | Machine-readable output |
| `--json-schema <schema>` | Force structured JSON output |

## Interactive Session: Slash Commands

| Command | Purpose |
|---------|---------|
| `/help` | Show all commands |
| `/compact` | Compress context |
| `/review` | Request code review |
| `/plan` | Enter Plan mode |
| `/exit` | End session |

## PR Review Pattern

### Quick Review (Print Mode)
```bash
git diff main...feature-branch | claude -p 'Review this diff for bugs and style problems' --max-turns 1
```

### Deep Review (Interactive + Worktree)
```bash
claude -w pr-review --tmux
# Then: Review all changes vs main
```

## Settings & Configuration

### Settings Hierarchy
1. CLI flags (override everything)
2. Local project: `.claude/settings.local.json`
3. Project: `.claude/settings.json`
4. User: `~/.claude/settings.json`

### Permissions in Settings
```json
{
  "permissions": {
    "allow": ["Bash(npm run lint:*)", "WebSearch", "Read"],
    "deny": ["Read(.env)", "Bash(rm -rf *)"]
  }
}
```

## Hooks — Automation on Events

```json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Write(*.py)",
      "hooks": [{"type": "command", "command": "ruff check --fix $CLAUDE_FILE_PATHS"}]
    }]
  }
}
```

## MCP Integration

```bash
# GitHub
claude mcp add -s user github -- npx @modelcontextprotocol/server-github

# PostgreSQL
claude mcp add -s local postgres -- npx @anthropic-ai/server-postgres --connection-string postgresql://localhost/mydb
```

## Cost & Performance Tips

1. Use `--max-turns` in print mode to prevent runaway loops
2. Use `--effort low` for simple tasks
3. Use `--bare` for CI/scripting
4. Pipe input instead of having Claude read files
5. Start new sessions for distinct tasks

## Pitfalls

1. Interactive mode REQUIRES tmux
2. `--dangerously-skip-permissions` dialog defaults to "No" — must navigate Down+Enter
3. `--max-budget-usd` minimum is ~$0.05
4. `--max-turns` is print-mode only
5. Context degradation above 70% usage
