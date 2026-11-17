---
name: formal-release-cycle
description: "Formal 7-phase release pipeline: BRD → Sprint Plan → Advisor Sparring → Implementation → Two-Stage Review → QA Gate → Production Release. No production code is touched before all gates pass."
version: 1.0.0
author: Johnny (Chief of Staff)
---

# Formal Release Cycle

**Binding rule:** No production code is modified, deployed, or released until ALL phases of this pipeline complete with PASS status. Johnny enforces this gate — if Greg asks for a production change, Johnny pushes back for a BRD first.

## Why This Exists

The prior workflow was diagnosis → code → deploy with no formal review gate. Bugs shipped to production and were caught by Greg in real usage (e.g., the two-axis state drift that sat latent for weeks). This pipeline puts a formal sparring + review + QA gate between every change and production.

## Pipeline Overview

```
PHASE 1: BRD Gathering ──→ BRD approved
PHASE 2: Sprint Planning ──→ PRD + scope locked
PHASE 3: Advisor Review (Claude Sonnet) ──→ Review report
PHASE 4: Johnny ↔ Advisor Sparring ──→ Consensus
PHASE 5: Implementation (DeepSeek Pro) ──→ Code + tests
PHASE 6: Two-Stage Review ──→ Spec PASS + Quality PASS
PHASE 7: QA Gate ──→ All test suites green
────────────────────────────────────────────
RELEASE TO PRODUCTION
```

Each phase has an explicit gate. No phase begins before the previous one completes.

---

## Phase 1: BRD Gathering

**Goal:** Collect requirements into a Business Requirements Document before any planning or coding.

### Johnny's Responsibility
- When Greg asks for a feature or fix, push back: "Before I plan anything, what's the BRD?"
- Extract: problem statement, success criteria, constraints, affected surfaces, acceptance tests
- Draft the BRD as a concise markdown document
- **Time zone check:** If the change touches dates, times, due_at, scheduled_at, or reminders — load `references/ara-timezone-patterns.md` and verify no ad-hoc IST/UTC conversions are introduced
- Get Greg's explicit approval before moving to Phase 2

### BRD Template
```markdown
# BRD: [Title]

## Problem
[What broke? What's the user impact?]

## Success Criteria
- [ ] [Measurable outcome]
- [ ] [Measurable outcome]

## Affected Surfaces
- [ ] Server endpoints
- [ ] Database queries
- [ ] Tools/functions
- [ ] Frontend/WhatsApp UX

## Constraints
- [Data migration? Read-path-only? Backward compat?]

## Acceptance Tests
- [ ] [Test scenario]
- [ ] [Test scenario]

## Fragile Edges Check
- [ ] Checked against known couplings in fragile-edges doc
```

### Gate: Greg approves the BRD. Do not proceed otherwise.

---

## Phase 2: Sprint Planning

**Goal:** Convert the BRD into a scoped, sequenced Product Requirements Document with bite-sized tasks.

### Johnny's Responsibility
- Break the BRD into implementable tasks (2-5 minutes each)
- Sequence for dependency order
- Identify shared files/touchpoints (for parallelization constraints)
- Flag which tests need to be written first (test-first)
- Lock scope — no additions mid-sprint without restarting Phase 2

### PRD Template
```markdown
# PRD: [Title]

## Scope
[Exactly what will be built. Explicitly: what will NOT be built.]

## Task Sequence
1. [Task 1 — file(s), description, test-first]
2. [Task 2 — file(s), description]
...

## Test Plan
- [ ] T1: [Description]
- [ ] T2: [Description]

## Risk Register
- Risk: [What could go wrong] → Mitigation: [How we prevent it]
```

### Gate: Greg approves the PRD. Scope is locked. Phase 3 begins.

---

## Phase 3: Advisor Review

**Goal:** An independent model (Claude Sonnet) reviews the PRD + BRD before any code is written. Catches design flaws when they're cheapest to fix.

### Johnny's Responsibility
- Dispatch a `hermes chat -q` sub-process with Claude Sonnet
- Feed it: the full BRD + PRD + fragile-edges map + relevant code sections
- Prompt template:

```
You are a technical advisor reviewing a PRD before implementation.

CONTEXT:
[BRD text]
[PRD text]
[Fragile-edges map — known coupling points]
[Relevant code sections — affected files]

TASK:
1. Find design flaws, missing edge cases, or scope gaps
2. Check against fragile edges — will any of these changes break coupled surfaces?
3. Identify any assumptions in the PRD that need verification
4. Flag tests that are missing from the test plan
5. Rate the PRD: APPROVED / CHANGES_REQUESTED

Be specific. Every finding must reference a concrete line or section.
```

### Gate: Advisor report is received. If CHANGES_REQUESTED, return to Phase 2 with findings. If APPROVED, proceed to Phase 4.

---

## Phase 4: Johnny ↔ Advisor Sparring

**Goal:** Johnny and the advisor reach binding consensus on the implementation approach. Neither ships without the other's agreement.

### Process
1. Johnny reads the advisor's review
2. Johnny challenges every finding: "Is this actually a bug or a theoretical concern? Let me check against the data."
3. If Johnny disagrees with a finding, send counterpoints back to the advisor via another sub-process call
4. Advisor responds to counterpoints
5. Repeat until every finding is either:
   - **Accepted** (fix included in implementer prompt)
   - **Dismissed with evidence** (data disproves the concern)
   - **Deferred** (real but out of scope, with a ticket)

### Consensus Format
The output of this phase is a **Consensus Implementer Prompt** — a single document containing:
- The agreed-upon changes
- Rejected findings with reasons
- Deferred items (tickets)
- The implementer prompt (exact text to feed Phase 5)

### Gate: All findings are resolved (accepted, dismissed, or deferred). Consensus document exists.

After sparring completes and implementation is built, run targeted integration tests against every advisor finding. Copy `scripts/advisor_tests_template.py` to the server, customize the test groups for the current sprint's findings, and run it. The script covers: JS function unit tests via `node -e`, file-content assertions, API route tests, regression checks, code quality assertions, event handler wiring, and version serving verification. See `references/advisor-integration-tests.md` for the detailed pattern. Run before Phase 7 (QA gate).

---

## Phase 5: Implementation

**Goal:** Execute the consensus implementer prompt via `delegate_task`.

### Johnny's Responsibility
- Dispatch `delegate_task` with the consensus implementer prompt + full context
- Subagent uses DeepSeek V4 Pro (default delegation model)
- TDD enforced: test first, then code
- Monitor for failures; if subagent fails, create a fix subagent — do not fix manually
- **Dashboard.js changes MUST pipe through `/opt/ara/tests/safe_write.py`** — never write directly, never pipe through shell
- Backup files before any write (`cp file file.sprintN.bak`)
- Re-run all deterministic tests after each task

### Gate: All tasks from PRD completed. All new tests pass. No regressions introduced. Dashboard integrity test passes.

---

## Phase 6: Two-Stage Review

**Goal:** Independent review of the implementation against the original spec and code quality standards.

### Stage 1: Spec Compliance Reviewer
Dispatched via `delegate_task`. Checks:
- [ ] All BRD requirements implemented?
- [ ] All PRD tasks completed?
- [ ] File paths match plan?
- [ ] Behavior matches expected?
- [ ] Nothing extra added (no scope creep)?
- [ ] Fragile edges checked — no coupled surface broken?

Output: PASS or list of spec gaps.

### Stage 2: Code Quality Reviewer
Dispatched via `delegate_task` only AFTER spec compliance passes. Checks:
- [ ] Follows project conventions?
- [ ] Proper error handling?
- [ ] SQL NULL trap avoided?
- [ ] IST/UTC handling correct?
- [ ] No security issues?
- [ ] Adequate test coverage?
- [ ] No obvious bugs or missed edge cases?

Output: APPROVED or REQUEST_CHANGES with categorized issues (Critical / Important / Minor).

### Gate: BOTH reviews return PASS. If either fails, fix and re-review. Do not skip re-review.

---

## Phase 7: QA Gate

**Goal:** All test suites pass before production deployment.

### Required Tests
1. **Drift regression test** (`test_action_item_drift.py`) — 16/16
2. **Agreement test** (`t2_agreement.py`) — 3/3
3. **Write-path roundtrip test** (`test_write_path_roundtrip.py`) — 15/15
4. **Dashboard integrity test** (`dashboard_integrity_test.py`) — 12/12, catches frontend corruption
5. **Gate suites** (`gate_synth.py`, `gate_retry.py`) — if applicable
6. **Full battery** (`full_battery.py`) — if LLM API timing allows
7. **Test residue cleanup** — all test actions, deals, leads, and SAs created during testing MUST be deleted from production DB. Test scripts should self-clean. If any [REGRESSION] actions remain, deploy is blocked.
6. **Any new tests** from the sprint's test plan

### Gate: ALL test suites pass with zero failures. No exceptions. If full_battery times out, gate_synth + gate_retry + drift + roundtrip must all pass.

---

## Release to Production

**Only after all 7 phases complete with all gates green:**

1. Tag the release in git
2. Deploy to production server
3. Restart service
4. Health check (curl dashboard, verify 200)
5. Run drift test against production — confirm deployed code works
6. Log release in fragile-edges doc with date and scope

---

## Phase Durations & Cost Estimates

| Phase | Duration | Cost | Models |
|-------|----------|------|--------|
| 1 — BRD | 5-15 min (human) | $0 | Greg + Johnny |
| 2 — Sprint | 5-10 min (agent) | ~$0.01 | DeepSeek Flash |
| 3 — Advisor | 2-5 min | ~$0.10-0.30 | Claude Sonnet ($3/$15 per M) |
| 4 — Sparring | 5-15 min | ~$0.20-0.60 | Claude + Johnny |
| 5 — Implement | 5-20 min | ~$0.10-0.50 | DeepSeek Pro ($2/$8 per M) |
| 6 — Review | 5-10 min | ~$0.10-0.30 | DeepSeek Pro × 2 |
| 7 — QA | 2-10 min | ~$0.05-0.20 | Gate suites (Pro) |
| **Total** | **30-80 min** | **~$0.50-2.00** | |

Per-fix cost: under $2. The alternative — one production bug caught by Greg — costs 30+ minutes of his time plus potential live-lead contacts. This pipeline pays for itself on the first prevented incident.

---

### Advisor Pitfalls (learned Sprint 2-3)

- **False positives happen.** Advisor reported "undefined 'now'" in `_build_recent_actions_block`. The function uses `datetime.min` — no undefined reference. Verify advisor findings against actual code before accepting. A finding that can't be reproduced with a line number is a question, not a directive.
- **Advisor runs in an isolated environment (June 2026).** The `technical-advisor` profile has `file,terminal,web` toolsets but operates in its own Hermes session — it may be on a different machine, inside a Docker container, or otherwise unable to reach the production server (46.224.132.99). The advisor claimed submitted MD5 hashes were "fabricated" because it ran `md5sum` on local files and got different values. In reality, the hashes came from `ssh root@46.224.132.99 "md5sum /opt/ara/.../dashboard.js"` — correct, just from a host the advisor couldn't reach. When the advisor disputes file evidence (paths, hashes, sizes, function presence), verify: (1) the advisor's `grep`/`md5sum`/`wc` ran against local files, not the production server; (2) re-run the commands yourself via `ssh root@46.224.132.99` to confirm; (3) if the data is real, dismiss the finding with a note about host isolation. Don't waste sparring rounds on an environment disconnect — one round-trip max per such finding.
- **Advisor line numbers may be stale (June 2026).** The advisor flagged a route collision at L2552/L6961 in server.py. These offsets were from a different codebase snapshot — the current code had the routes at L2884 and L8093, and the single-action route worked correctly (verified via live curl). When advisor findings cite line numbers, always verify against the ACTUAL current code: `grep -n "@app.get.*actions" /opt/ara/server.py` and curl-test both routes. Line numbers drift between sessions as code is added.
- **Functional regressions pass all syntax gates (June 2026).** dashboard.js lost 8 functions (16KB) between backups: `editActionItem`, `saveEditedAction`, `deleteActionItem`, `_stripActionPrefix`, `_fillDealLead`, `_hideMenus`, `renderUnifiedTab`. `node -c` and `dashboard_integrity_test.py` both passed because the code was syntactically valid. The dashboard was functionally dead — zero action editing mechanisms, no deal lead picker. The test suite caught nothing because the removed functions had no dedicated tests. When rewriting functions that lack test coverage, do a keyword audit against the most recent backup before deploying. Any function present in the backup but absent from the rewrite is a regression.
- **Dynamic fixtures > hardcoded.** T2 used a hardcoded open-set that went stale when an item resolved mid-sprint. Replaced with DB query. Any test that compares against a known set must discover that set dynamically.
- **Token efficiency.** Advisor SOUL.md compressed from 2,575 to 953 chars (~63%). Keep advisor personality lean — Claude tokens are $3/$15 per M. Every sentence in SOUL.md costs money every review.
- **Post-implementation review catches what pre-review misses.** Sprint 3 Phase 3 (pre-review) went clean. Phase 7 (post-implementation advisor review) caught a copy-paste bug: Created column sort compared `a.created_at` against `a.created_at` instead of `b.created_at`. Pre-review validates design; post-review validates code. Both are necessary.
- **Default filter changes break client-side consumers silently.** Sprint 2 changed `/api/action-items` default from legacy-status to open-only. The history tab called the same endpoint with no params — expected resolved items, got zero. The API returned 200 with empty data, no error. Audit every client-side caller of any endpoint whose default changes. See `references/sprint3-history-regression.md` for the full incident report and audit checklist.

See `references/sprint2-sparring.md` for the full Sprint 2 sparring transcript — the advisor findings that reshaped the PRD from 5 tasks to 10.

### Johnny's Enforcement Rules

1. **No production code changes without a BRD.** If Greg asks "fix X," respond: "Before I touch anything, let's draft the BRD. What's the problem, what's the success criteria, what surfaces are affected?"
2. **No skipping phases.** Even "small" fixes go through the pipeline. A one-line fix that skips review is how the two-axis drift shipped.
3. **No scope creep mid-sprint.** If a new requirement emerges during implementation, it goes into the next sprint's BRD. Do not add to the current sprint.
4. **No deployment without all gates green.** If a test fails, fix it. If it's a pre-existing failure, document it explicitly as deferred — don't silently ship past it.
5. **Push Greg for clarity.** Ambiguous requirements → ambiguous implementation → production bugs. Johnny's job is to force specificity before code is written.
6. **UI-only sprints may skip advisor review (Phases 3-4) at Greg's discretion.** When all changes are in dashboard.js or CSS with zero server/DB risk, Greg can approve bypassing the advisor sparring. But Phase 2 (PRD), Phase 5 (implementation), Phase 6 (syntax verification including duplicate-function grep), and Phase 7 (QA gate) still apply. No sprint skips Phase 7 — every change gets tested.
7. **Never restore an old backup without a feature audit.** Sprint 3 rolled dashboard.js back to a Jun 15 backup that predated Sprint 2 — silently removing overdue detection from the actions table. June 20 regression lost 8 functions including the entire action edit/delete flow and deal lead picker. Before any revert or when a feature is discovered missing: run the full feature regression audit (see `references/feature-regression-audit.md`): identify the time window, function-level diff, keyword audit, dangling reference check, event handler audit, escape corruption check. Blind reverts cause regressions that no test catches because the feature predates the test suite.

---

## Fragile Edges Map (always consulted in Phase 3)

These are the known coupling points where changes in one surface break another. The advisor MUST check every PRD against this list.

- **Readers must agree:** `get_action_items`, `action_item_stats`, `list_action_items`, `query_actions`, and the agent-context `pending_actions` count must all use the identical open/closed filter. Change one → change all five.
- **Writers must transition, not overwrite:** PATCH endpoint maps each user action to a specific field update. `execution_state` and `outcome_state` are semi-independent. No transition resets both.
- **Tool ↔ API agreement:** The `get_action_items` tool (called by Ava) and the `/api/action-items` endpoint must use the same filter. Two surfaces, one definition.
- **Stats ↔ List agreement:** The badge count from stats must equal the open count from the list. They must never disagree.
- **Overdue detection:** `is_overdue` in `list_action_items` must use two-axis state (`outcome_state IS NULL`), not legacy `status`. Overdue resolved items must not appear.
- **Every consumer of `/api/action-items` with default filter:** Sprint 2 changed the default filter from legacy status to open-only. The history tab called the same endpoint with the default — silently broke because it expected resolved items. Audit every caller: pending tab, history tab, lead-view actions, scheduled actions. Any consumer that relied on the old default returning resolved/cancelled items must explicitly request `?status=resolved` or `?status=dismissed`.
- **ActionItem creation paths must set two-axis fields:** Any code path that creates an ActionItem must set `execution_state` and `outcome_state`. Missing → NULL → potential drift.
- **SQL NULL trap:** `field != "value"` drops NULL rows. Every filter comparing a nullable field must account for NULL explicitly. Applies to `status`, `execution_state`, and `outcome_state`.
- **IST/UTC boundary:** All datetime comparisons must account for timezone. Naive vs aware datetime comparison crashes silently.
- **Periodic notification checks MUST have quiet-hours gates:** Any `_check_*_notifications()` or similar periodic function that sends WhatsApp/email MUST gate on hour-of-day. Without it, dedup window resets at midnight trigger spam. See `references/quiet-hours-gate.md`.
- **Prompt extraction examples prime the LLM to hallucinate:** If an extraction prompt contains a format example with specific fake data (e.g., pricing tiers), the LLM will copy those numbers even when the source document has none. Audit all extraction prompts: format examples must use generic placeholders. See `references/prompt-audit-anti-hallucination.md`.
- **Document text was silently truncated to 6000 chars:** The original `extract_skills_from_document()` used `text[:6000]` — only ~2 pages of any document were skill-extracted. Fixed with per-chunk extraction. Any future extraction pipeline should chunk, not slice. See `references/chunked-document-extraction.md`.

---

## Model Assignments for This Pipeline

| Role | Model | Provider | Cost (per M tok) | Why |
|------|-------|----------|------------------|-----|
| Orchestrator (Johnny) | deepseek-v4-flash | deepseek | $0.50 / $2 | Fast, cheap for routing decisions |
| Advisor (Phases 3-4) | claude-sonnet-4-20250514 | anthropic | $3 / $15 | `technical-advisor` profile — rigorous review, catches subtle bugs |
| Implementer (Phase 5) | deepseek-v4-pro | deepseek | $2 / $8 | Reliable tool-calling, cost-effective |
| Spec Reviewer (Phase 6) | deepseek-v4-pro | deepseek | $2 / $8 | Fast verification |
| Quality Reviewer (Phase 6) | deepseek-v4-pro | deepseek | $2 / $8 | Code review + edge case detection |

### Why Claude Sonnet for advisor, not Opus
Opus costs $15/$75 per M tok — 5x Sonnet. For code review against a BRD/PRD, Sonnet catches the same classes of bugs. Opus is reserved for architecture-level questions that Sonnet gets wrong. If a review is clean with Sonnet, it ships. If Sonnet flags something ambiguous, Johnny can escalate a specific question to Opus as a one-off.

### Routing method
Phases 3-4 use the `technical-advisor` Hermes profile. This profile is configured with Claude Sonnet and has read-only access (file, terminal, web toolsets). 

**Release testing thread:** All sprint agent_chat calls route to thread `13a09e93` ("🧪 Release Testing") to keep test noise out of Greg's main conversation. Include `thread_id: "13a09e93"` in all agent_chat test payloads.

To dispatch the advisor:
```bash
# Phase 3: Initial review
bash /Users/greg/.hermes/profiles/johnny/scripts/advisor_review.sh \
  "Review this PRD against the BRD + fragile-edges: [prompt]" \
  --output /tmp/advisor_review.txt

# Phase 4: Sparring (continue session with counterpoints)
hermes --profile technical-advisor chat -q \
  "Johnny challenges finding #3: [counterpoint]. Respond." \
  --continue --toolsets file,terminal,web --quiet \
  2>&1 | tee /tmp/advisor_response.txt
```

Profile: `/Users/greg/.hermes/profiles/technical-advisor/` | Model: `claude-sonnet-4-6` | Tools: `file,terminal,web`

**PITFALL: `~` path resolution in subprocess calls.** When `terminal()` spawns a subprocess from within a Hermes session, `~` resolves to the PROFILE's home (`~/.hermes/profiles/<name>/home/`), not Greg's real home. Always use absolute paths (`/Users/greg/...`) when calling scripts or tools from within `terminal()`. The Python wrapper `advisor_review.py` was broken by this until replaced with `advisor_review.sh` which uses absolute paths. See `references/advisor-review-examples.md` for real review output.

Phases 5-6 use `delegate_task` (default delegation model: DeepSeek Pro).

### PITFALL: delegate_task caches model at startup

`delegate_task` reads the delegation config from `config.yaml` at agent process startup and caches it. Changing `delegation.model` mid-session via `hermes config set` will NOT take effect. To switch the delegation model:

1. Change the config: `hermes config set delegation.model deepseek-v4-pro`
2. Restart the Hermes session (requires a new shell)

Without restart, `delegate_task` continues using the cached model — which may be the wrong model (e.g., local Qwen with 4K context) and will fail with context-window errors.

**Session restart cost:** ~5 seconds. Always verify with a quick `hermes config show | grep delegation` before starting a session where `delegate_task` will be used.

### Fallback: hermes chat -q subprocess

When `delegate_task` can't be used (wrong model cached) or when model-specific routing is needed, use the `hermes chat -q` subprocess pattern:

```bash
# Write prompt to a file (avoids shell escaping issues)
write_file("/tmp/sprint_prompt.txt", "<full prompt>")

# Dispatch with specific model
terminal(background=true, notify_on_complete=true, command=
  'hermes --profile johnny chat -q "$(cat /tmp/sprint_prompt.txt)" '
  '--model deepseek-v4-pro --provider deepseek '
  '--toolsets terminal,file,web --quiet '
  '2>&1 | tee /tmp/sprint_output.txt')
```

**PITFALL: Write the prompt to a file.** Shell escaping of large multi-line prompts (quotes, newlines, special chars) fails silently. Always write the prompt to a temp file and read with `$(cat /tmp/file)`.

**PITFALL: Escape mangling when pipe/tee captures hermes output.** The `hermes chat -q` output piped through `tee` or `>` can double-escape JavaScript/HTML string literals. `\\'` becomes `\\\\'` and breaks syntax. After ANY implementation that uses `hermes chat -q | tee`, verify the output file with:
```bash
node -c /opt/ara/static/dashboard.js  # for JS
python3 -c "compile(open('/opt/ara/server.py').read(),'server.py','exec')"  # for Python
```
If syntax errors found, DO NOT hand-edit escape sequences — revert to the pre-sprint backup and re-apply changes using a clean Python script with byte-level string matching. See `references/escape-mangling.md` for the full Sprint 3 incident and recovery procedure.
