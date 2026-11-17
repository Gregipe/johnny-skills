# OpenCode Detailed Guide

This file contains the detailed OpenCode documentation migrated from the former `opencode` skill.

## When to Use

- User explicitly asks to use OpenCode
- External coding agent for implement/refactor/review
- Long-running coding sessions with progress checks
- Parallel task execution in isolated workdirs/worktrees

## Prerequisites

- OpenCode installed: `npm i -g opencode-ai@latest` or `brew install anomalyco/tap/opencode`
- Auth configured: `opencode auth login` or set provider env vars
- Verify: `opencode auth list`
- Git repository for code tasks
- `pty=true` for interactive TUI sessions

## Binary Resolution

Shell environments may resolve different OpenCode binaries:

```bash
which -a opencode
opencode --version
```

If needed, pin explicit path:
```bash
$HOME/.opencode/bin/opencode run '...'
```

## One-Shot Tasks

Use `opencode run` for bounded, non-interactive tasks:

```bash
opencode run 'Add retry logic to API calls and update tests'
```

Attach context files with `-f`:
```bash
opencode run 'Review this config for security issues' -f config.yaml -f .env.example
```

Force a specific model:
```bash
opencode run 'Refactor auth module' --model openrouter/anthropic/claude-sonnet-4
```

## Interactive Sessions (Background)

For iterative work requiring multiple exchanges:

```bash
opencode  # starts TUI
# Returns session_id

# Send a prompt
process(action="submit", session_id="<id>", data="Implement OAuth refresh flow")

# Monitor progress
process(action="poll", session_id="<id>")
process(action="log", session_id="<id>")

# Exit with Ctrl+C
process(action="write", session_id="<id>", data="\x03")
# Or kill
process(action="kill", session_id="<id>")
```

**Important:** Do NOT use `/exit` — it opens agent selector. Use Ctrl+C.

### TUI Keybindings

| Key | Action |
|-----|--------|
| Enter | Submit message (press twice if needed) |
| Tab | Switch between agents |
| Ctrl+P | Open command palette |
| Ctrl+X N | New session |
| Ctrl+C | Exit OpenCode |

## Common Flags

| Flag | Use |
|------|-----|
| `run 'prompt'` | One-shot execution |
| `--continue` / `-c` | Continue last session |
| `--session <id>` / `-s` | Continue specific session |
| `--agent <name>` | Choose agent (build or plan) |
| `--model provider/model` | Force specific model |
| `--format json` | Machine-readable output |
| `--file <path>` / `-f` | Attach files |

## PR Review Workflow

```bash
opencode pr 42
```

Or review in temporary clone:
```bash
REVIEW=$(mktemp -d) && git clone https://github.com/user/repo.git $REVIEW && cd $REVIEW && opencode run 'Review this PR vs main'
```

## Parallel Work Pattern

Use separate workdirs/worktrees:
```bash
opencode run 'Fix issue #101 and commit' --workdir=/tmp/issue-101
opencode run 'Add parser regression tests' --workdir=/tmp/issue-102
```

## Session & Cost Management

```bash
opencode session list
opencode stats
opencode stats --days 7 --models anthropic/claude-sonnet-4
```

## Pitfalls

- Interactive sessions require `pty=true`
- `/exit` is NOT valid — use Ctrl+C
- PATH mismatch can select wrong binary
- Enter may need to be pressed twice to submit

## Verification

```bash
opencode run 'Respond with exactly: OPENCODE_SMOKE_OK'
```

Success: Output includes the response, no provider errors.
