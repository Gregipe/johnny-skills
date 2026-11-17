---
name: github
description: "Complete GitHub workflow — authentication, repository management, issues, PRs, code review, and CI/CD."
category: devops
trigger: GitHub operations, PR workflow, repo management, code review
---

# GitHub Skills

Complete guide to GitHub operations via CLI.

## Overview

This skill consolidates:
1. **Authentication** — SSH keys, tokens, gh CLI login
2. **Repository Management** — Clone, create, fork, remotes
3. **Issues** — Create, triage, label, assign
4. **PR Workflow** — Branch, commit, open, review, merge
5. **Code Review** — Inline comments via gh or REST

---

## 1. Authentication

### SSH Key Setup

```bash
# Generate Ed25519 key
ssh-keygen -t ed25519 -C "github-$(whoami)" -f ~/.ssh/id_ed25519

# Add to GitHub: github.com → Settings → SSH and GPG keys → SSH keys
```

### GitHub CLI Login

```bash
gh auth login
# 1. GitHub.com
# 2. HTTPS (recommended)
# 3. Paste auth token
# 4. "Login to a GitHub account"
```

### Verify

```bash
gh auth status
ssh -T git@github.com
```

---

## 2. Repository Management

### Clone

```bash
gh repo clone <owner>/<repo>
# or
git clone git@github.com:<owner>/<repo>.git
```

### Create New

```bash
gh repo create <repo-name> --public --clone
# or via web: github.com/new
```

### Fork and Clone

```bash
gh repo fork <owner>/<repo> --clone
```

### Manage Remotes

```bash
git remote -v
git remote add upstream git@github.com:<owner>/<repo>.git
git fetch upstream
```

---

## 3. Issues

### Create

```bash
gh issue create --title "Bug: description" --body "Details..."
gh issue create --title "Feature: description" --label "enhancement"
```

### Triage, Label, Assign

```bash
gh issue edit 123 --add-label "bug,priority"
gh issue edit 123 --add-assignee @me
gh issue close 123
gh issue reopen 123
```

### List and Search

```bash
gh issue list --state all --label "bug"
gh issue list --search "is:issue is:open assign:@me"
```

---

## 4. PR Workflow

### Create Branch

```bash
git checkout -b feature/my-feature
```

### Commit

```bash
git add .
git commit -m "feat: add feature"
git push -u origin feature/my-feature
```

### Open PR

```bash
gh pr create --title "Feature: description" --body "Details..."
# or via web: github.com/<owner>/<repo>/pull/new/<branch>
```

### List PRs

```bash
gh pr list --state all
gh pr view 123
```

### Merge

```bash
gh pr merge 123 --squash --delete-branch
# Options: --squash, --merge, --rebase
```

---

## 5. Code Review

### Review PR

```bash
gh pr review 123 --approve
gh pr review 123 --comment --body "LGTM"
gh pr review 123 --request-changes --body "Fix X first"
```

### View Diff

```bash
gh pr diff 123
gh pr checks 123
```

### Inline Comments

```bash
gh pr comment 123 --body "Comment" --path server.py --line 45
```

---

## CI/CD Notes

### Secrets

Add via: Repository → Settings → Secrets → Actions

### Runners

GitHub-hosted or self-hosted runners available.

---

## References

- `references/ci-cd-workflow.md` — Full CI/CD pipeline
- `references/deploy-key-setup.md` — Deploy key configuration