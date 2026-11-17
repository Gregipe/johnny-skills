---
name: multi-agent-dispatch
category: devops
description: Use when triaging any task — route to the right agent.
version: 1.0.0
author: Johnny (Chief of Staff)
license: MIT
metadata:
  hermes:
    tags: [multi-agent, orchestration, routing, delegation]
    related_skills: [model-routing-workflow, hermes-config-inspection, user-interaction-style]
---

# Multi-Agent Dispatch — Greg's Firm

Johnny is the orchestrator of a five-role firm. This skill is the org chart, the
routing table, and the handoff contracts. Load it before triaging any non-trivial
task. Model-level mechanics (providers, cost tables, pitfalls) live in
`model-routing-workflow`; disk-state verification lives in
`hermes-config-inspection`.

## When to Use

- Any task bigger than a quick lookup — decide who handles it BEFORE starting work.
- Whenever delegating, spawning subagents, or shelling out to another profile.
- When Greg asks about the multi-agent setup or model routing.

## The Org Chart (Oct 2026 — THE living model table)

Greg updates the model pool over time. **This table is the single source of truth
for which agent uses which model.** When the pool changes, update this table,
then `model-routing-workflow`, then the per-profile configs (see Model Update
Protocol below).

| Agent | Mechanism | Model (Oct 2026) | Cost band | Mandate |
|---|---|---|---|---|
| **Johnny** (orchestrator) | this profile | deepseek-v4-pro / deepseek | workhorse | Triage, planning, delegation, verification, comms with Greg. Never hand off what a specialist should own; never do heavy lifting a specialist can. |
| **Morpheus** (research) | morpheus profile, shell-out | deepseek-v4-pro / deepseek | workhorse | Long-form, cited research: markets, competitors, thesis, literature. Charter: `morpheus-charter` skill in its profile. |
| **Architect** (design) | architect profile, shell-out | claude-opus-4-8 / anthropic | premium — spend sparingly | Design judgment, system architecture, hard planning, first-principles pushback. Charter: `architect-charter`. |
| **Technical Advisor** (review) | technical-advisor profile, shell-out | glm-5.3 / zai (thinking enabled) | cheapest reasoning | Second-opinion code review, root-cause debugging, 5-failure handoffs. Charter: `technical-advisor-charter`. |
| **Swarm** (subagents) | delegate_task | glm-5.3 / zai (delegation config) | cheapest reasoning | Parallel mechanical work, context-flooding subtasks. Up to 10 concurrent, depth ≤ 2. |
| **Cipher** (spare) | cipher profile | deepseek-v4-pro | workhorse | Scratch experiments, throwaway sessions. |

## Triage Flow (run on every incoming task)

1. **Classify**: admin / research / design / code / parallelizable / comms.
2. **Admin, quick lookup, or anything conversational with Greg** → do it myself.
3. **Long-form cited research** → Morpheus (shell-out).
4. **Design judgment, architecture, hard planning, complex debugging strategy** → Architect. Design-first is Greg's preference — when in doubt, this is a design question, not a code question.
5. **Code review, second opinion, or a debug session past ~5 failed iterations** → Technical Advisor (see Escalation).
6. **Parallelizable or would flood my context** → delegate_task swarm, one task per independent workstream, each with an output schema.
7. **Uncertain classification** → do it myself but cheaply; escalate if it turns out heavy.

## Handoff & Verification Contracts (non-negotiable)

- **Full context in every brief.** Subagents and shelled-out profiles know nothing
  of this conversation. Repeat everything they need: files, values, constraints.
- **Verifiable handles for external effects.** A child claiming "uploaded" or
  "wrote" must return a URL / ID / absolute path — and Johnny verifies it before
  telling Greg it succeeded. Self-reports are not facts.
- **Single writer per artifact.** Only one agent edits any given file/DB at a time.
- **Output schemas on spawn** (delegate_task `output_schema`) — bounded, forgiving,
  only fields Johnny will actually read.
- **Profiles are islands.** Morpheus/Architect/TA do not share Johnny's memory or
  skills — briefs must be self-contained. Results come back as text (files), so
  ask for the exact artifact path or paste-ready content in the brief.
- **Timebox + honest partials.** Never unbounded. A bounded honest summary beats a
  silent failure.

## Invocation Patterns

### Specialist profiles (shell-out — the only reliable cross-model route)

Before first dispatch to a specialist profile in a session:
`hermes --profile <name> config check` — profiles rot (duplicate YAML keys,
stale delegation models). Fix drift with `hermes --profile <name> config set`.

Write the brief to a file first (shell-escaping large prompts fails silently),
then:

```bash
# Research → Morpheus (model comes from the profile's config)
hermes --profile morpheus chat -q "$(cat /tmp/brief.txt)" --quiet 2>&1 | tee /tmp/morpheus-out.txt

# Design/architecture → Architect
hermes --profile architect chat -q "$(cat /tmp/brief.txt)" --quiet 2>&1 | tee /tmp/architect-out.txt

# Code review / root-cause → Technical Advisor
hermes --profile technical-advisor chat -q "$(cat /tmp/brief.txt)" --quiet 2>&1 | tee /tmp/ta-out.txt
```

Run via `terminal` with `background=true, notify=true` and the timeout on the
terminal call. **`--timeout` is NOT a flag of `hermes chat`** — it errors.

### Swarm (parallel subagents)

`delegate_task` reads `delegation.model/provider` **at agent startup and caches
it** — mid-session config changes have no effect. Before relying on it:
`hermes config show | grep -A3 delegation` (expect glm-5.3 / zai). If a task needs
a different model, use the shell-out pattern above, never a config swap mid-session.

### Escalation (debugging stalls)

After ~5 failed debug iterations: stop guessing, write a TA handoff prompt
(server access, what's confirmed working, root-cause candidates, exact file
paths) and dispatch to the Technical Advisor profile. Continue only with its
analysis in hand.

## Known Pitfalls (fixed Oct 2026 — re-check after config changes)

- **GLM-5.3 / ZAI rejects reasoning effort levels other than low/high/max.**
  `medium` → HTTP 400 "This model always engages in thinking and cannot be
  disabled". Profiles whose main model is GLM (technical-advisor) must keep
  `agent.reasoning_effort: high`.
- **Profile config rot is real.** morpheus's config.yaml had a duplicate
  `agent.reasoning_effort` key (unparseable since ~Jun 2026) and stale
  delegation (qwen2.5-coder-14b via LM Studio); technical-advisor had the same
  delegation drift. Run `hermes --profile <name> config check` on dispatch.
- **Keys are profile-scoped.** morpheus has no GLM_API_KEY (delegation is
  deepseek); technical-advisor has GLM_API_KEY (delegation is zai). Never assume
  a key exists in another profile's .env — check `grep -oE '^[A-Z_]+'`
  (names only, never values) before re-pointing a profile at a new provider.

## Cost Discipline

Greg runs minimal cloud tokens. Volume work → DeepSeek/GLM. Opus is reserved for
work where design/architectural judgment is the actual bottleneck. Batch swarm
tasks instead of sequential calls. Never use an LLM for what native code does.

## Model Update Protocol (when Greg changes the pool)

1. Update the org-chart table in THIS skill.
2. Update the routing table in `model-routing-workflow`.
3. Per profile: `hermes --profile <name> config set model.default <model>` and
   `model.provider <provider>` (direct YAML edits are refused by Hermes).
4. Verify on disk (`hermes-config-inspection` procedure), then restart sessions —
   delegation and model configs are cached at process start.
5. Never re-litigate the pool (no Gemini/GPT) unless Greg reopens it.
