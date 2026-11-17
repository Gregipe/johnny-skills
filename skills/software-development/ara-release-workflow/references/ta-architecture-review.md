# TA Architecture Review — Delegation Workflow

When Greg provides a multi-issue build plan targeting ARA and wants architectural sign-off before implementation, delegate a comprehensive code audit to the TA subagent.

## Delegation Setup

```
delegate_task:
  goal: "Audit the ARA build plan against server.py and produce a signed-off (or revised) plan."
  toolsets: ["terminal", "file", "web", "skills"]
  model: glm-5.2 (provider: zai, set in delegation config)
```

The TA has 600s timeout and 50 iterations — enough for 12,690 lines of server.py.

## Context Assembly

Before delegating, assemble all context the TA needs:

1. **The build plan itself** — pass the full file path(s), or embed the content in the context field
2. **ARA release workflow skill** — instruct the TA to load it (`ara-release-workflow`)
3. **Server coordinates** — `root@46.224.132.99:/opt/ara/server.py` (12,690 lines)
4. **Sidecar coordinates** — `/opt/ara/whatsapp-sidecar/index.js`, `/opt/ara/whatsapp_sidecar_client.py`
5. **The audit criteria** (see below)

## Audit Criteria (pass in the goal/context)

### 1. Code correctness
- SSH to production and verify EVERY line number referenced in the plan
- Confirm proposed code won't break existing callers
- Verify imports are available
- Check for nonexistent modules, undefined variables, scoping errors

### 2. Blast radius
- Per issue: list all functions/code paths consuming the changed code
- Identify fragile edges from the release workflow Part 3

### 3. Completeness
- Are send paths fully covered? (plan may claim "all paths" but miss send_to_jid, send_document, etc.)
- Do regex patterns have false positives/negatives?
- Are there race conditions or transaction issues?

### 4. Implementation order
- Review recommended order against blast radius and dependencies

### 5. Test coverage
- Are test cases sufficient? What's missing?
- Are integration tests needed?

### 6. Risk matrix
- Per-issue risk rating + feature flag recommendation + rollback strategy

## Output Format

```
# TA Architecture Review — [SIGNED OFF / REVISIONS REQUIRED]

## 1. Code Audit (per issue)
## 2. Blast Radius (per issue)
## 3. Gaps Found
## 4. Implementation Order
## 5. Test Coverage Assessment
## 6. Risk Matrix
## 7. Final Verdict
```

## Pre-Flight Validation (do BEFORE delegating)

Run these quick checks from your own session to validate the plan's premises:
```bash
ssh root@46.224.132.99 'wc -l /opt/ara/server.py'
ssh root@46.224.132.99 'grep -n "<key function or line>" /opt/ara/server.py'
```

This catches: wrong line counts, nonexistent functions, stale references. If the plan references 12,690 lines and the file is now 12,750, some line numbers are off.

## Post-Review: Merge Corrections into Final Plan

The TA review will either SIGN OFF or say REVISIONS REQUIRED with specific gaps. If revisions:
1. Apply ALL must-fix gaps to the plan
2. Apply should-fix gaps if they're straightforward
3. Write the final signed-off plan as a new file (e.g., `build-plan-final.md`)
4. Include TA sign-off block at the bottom

## Session Example (2026-06-29)

Build plan: 677 lines covering 6 issues in ARA confirmation flow.
TA found: 5 critical/high gaps (entity injection DB corruption, nonexistent import, send_to_jid health-check bypass, _live NameError, infinite retry risk).
Revised implementation order: #5→#3→#6→#2→#1→#4 (was #6→#2→#3→#1→#5→#4).
8 missing test cases + 3 integration tests identified.
All gaps corrected in final plan (`build-plan-final.md`). Plan signed off.
