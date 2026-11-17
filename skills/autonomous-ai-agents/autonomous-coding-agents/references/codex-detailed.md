# Codex Detailed Guide

This file contains the detailed Codex documentation migrated from the former `codex` skill.

## Prerequisites

- Codex installed: `npm install -g @openai/codex`
- OpenAI auth: either `OPENAI_API_KEY` or Codex OAuth from CLI login
- Must run inside a git repository
- Use `pty=true` in terminal calls

## One-Shot Tasks

```bash
codex exec 'Add dark mode toggle to settings'
```

For scratch work (needs git repo):
```bash
cd $(mktemp -d) && git init && codex exec 'Build a snake game in Python'
```

## Background Mode (Long Tasks)

```bash
# Start in background with PTY
codex exec --full-auto 'Refactor the auth module'

# Monitor progress
process(action="poll", session_id="<id>")
process(action="log", session_id="<id>")

# Send input if Codex asks a question
process(action="submit", session_id="<id>", data="yes")
```

## Key Flags

| Flag | Effect |
|------|--------|
| `exec "prompt"` | One-shot execution, exits when done |
| `--full-auto` | Sandboxed but auto-approves file changes |
| `--yolo` | No sandbox, no approvals (fastest, most dangerous) |
| `--sandbox danger-full-access` | No sandbox; use when bubblewrap fails |

## Hermes Gateway Caveat

When invoking Codex from a Hermes gateway/service context, sandboxing may fail. Use:

```bash
codex exec --sandbox danger-full-access "task"
```

## PR Reviews

Clone to temp directory for safe review:

```bash
REVIEW=$(mktemp -d) && git clone https://github.com/user/repo.git $REVIEW && cd $REVIEW && gh pr checkout 42 && codex review --base origin/main
```

## Parallel Issue Fixing with Worktrees

```bash
# Create worktrees
git worktree add -b fix/issue-78 /tmp/issue-78 main
git worktree add -b fix/issue-99 /tmp/issue-99 main

# Launch Codex in each
codex --yolo exec 'Fix issue #78' --workdir=/tmp/issue-78
codex --yolo exec 'Fix issue #99' --workdir=/tmp/issue-99

# Push and create PRs
cd /tmp/issue-78 && git push -u origin fix/issue-78
gh pr create --repo user/repo --head fix/issue-78 --title 'fix: ...'

# Cleanup
git worktree remove /tmp/issue-78
```

## Batch PR Reviews

```bash
# Fetch all PR refs
git fetch origin '+refs/pull/*/head:refs/remotes/origin/pr/*'

# Review multiple PRs in parallel
codex exec 'Review PR #86' --workdir=/project
codex exec 'Review PR #87' --workdir=/project
```

## Rules

1. Always use `pty=true` — Codex is interactive
2. Git repo required — use `mktemp -d && git init` for scratch
3. Use `exec` for one-shots
4. `--full-auto` for building
5. Background for long tasks
6. Don't interfere — monitor with poll/log
