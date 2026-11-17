---
name: autonomous-coding-agents
description: "Delegate coding tasks to external AI coding agents (Claude Code, Codex, OpenCode). Covers orchestration patterns, PTY handling, session management, and parallel execution via worktrees."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Coding-Agent, Claude, Codex, OpenCode, Code-Review, Refactoring, PTY, Automation]
    related_skills: [hermes-agent]
---

# Autonomous Coding Agents

Orchestrate external AI coding agents (Claude Code, Codex, OpenCode) via Hermes terminal tools. Use these when you need autonomous implementation, refactoring, or code review beyond what the current LLM can provide.

## When to Use

- Implementing features requiring full file creation/modification across multiple files
- Large-scale refactoring across a codebase
- PR code review at scale
- Batch issue fixing with parallel worktrees
- Tasks requiring deep codebase understanding beyond current context

## Related Skills (Merged)

| Former Skill | Content Now In |
|--------------|----------------|
| `codex` | This skill - Codex section |
| `claude-code` | This skill - Claude Code section |
| `opencode` | This skill - OpenCode section |

## Supported Agents

### Claude Code (Anthropic)

See `references/claude-code-detailed.md` for comprehensive Claude Code documentation including:
- Print mode (`-p`) for non-interactive one-shot tasks
- Interactive PTY mode via tmux for multi-turn sessions
- Dialog handling (workspace trust, permissions)
- JSON output, session continuation, worktrees
- Slash commands, MCP integration, hooks

**Quick start:**
```bash
terminal(command="claude -p 'Add error handling to all API calls in src/' --allowedTools 'Read,Edit' --max-turns 10", workdir="/path/to/project")
```

### Codex (OpenAI)

See `references/codex-detailed.md` for comprehensive Codex documentation including:
- One-shot exec mode
- Background/full-auto mode
- PR reviews with worktrees
- Sandbox bypass for Hermes gateway contexts

**Quick start:**
```bash
terminal(command="codex exec 'Add dark mode toggle to settings'", workdir="~/project", pty=true)
```

### OpenCode (Open-source)

See `references/opencode-detailed.md` for comprehensive OpenCode documentation including:
- `opencode run` for bounded tasks
- Interactive TUI sessions
- PR review workflow
- Session management

**Quick start:**
```bash
terminal(command="opencode run 'Add retry logic to API calls'", workdir="~/project")
```

## Common Patterns

### Parallel Issue Fixing with Worktrees

```bash
# Create worktrees for parallel fixes
git worktree add -b fix/issue-78 /tmp/issue-78 main
git worktree add -b fix/issue-99 /tmp/issue-99 main

# Launch agents in parallel
terminal(command="claude -p 'Fix issue #78' --max-turns 10", workdir="/tmp/issue-78", background=true)
terminal(command="codex exec 'Fix issue #99'", workdir="/tmp/issue-99", background=true, pty=true)
```

### PR Review

```bash
# Claude Code
terminal(command="claude -p 'Review this diff' --max-turns 5", workdir="/path/to/repo")

# Codex
terminal(command="codex review --base origin/main", workdir="/tmp/review", pty=true)
```

## Selection Guide

| Agent | Best For | PTY Required |
|-------|----------|--------------|
| Claude Code | Complex reasoning, large refactors, MCP integration | Optional (-p mode) |
| Codex | Fast implementation, GitHub integration | Yes |
| OpenCode | Provider-agnostic, lightweight tasks | Optional (run mode) |

## Rules

1. **Always set workdir** — keep the agent focused on the correct project
2. **Use --max-turns in print mode** — prevents runaway loops
3. **Monitor background sessions** — use process(action="poll"/"log")
4. **Report results** — summarize file changes and test outcomes
5. **Clean up worktrees** — after parallel tasks, remove temp directories
