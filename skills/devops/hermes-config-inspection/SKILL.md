---
name: hermes-config-inspection
description: "Inspect Hermes's own config, profiles, and delegation state."
version: 1.0.0
author: Johnny (Chief of Staff)
platforms: [macos, linux]
---

# Hermes Config Inspection Skill

How to answer "what's the current setup of X" about Hermes itself — profiles,
model routing, delegation, cron, skills — by reading the live filesystem and
`config.yaml` instead of reciting memory or trusting a skill's cached notes.
Configs drift from both; the disk is the source of truth.

## When to Use

- Greg asks about the current profile, model-routing, delegation, cron, or skill setup.
- Before trusting or acting on a skill that describes "current" model/state values.
- Before or after changing `delegation.*` or `model.*` — verify what's actually on disk.

## Quick Reference

| Want | Command |
|------|---------|
| Active profile | `cat ~/.hermes/active_profile` |
| List profiles | `ls -1 ~/.hermes/profiles/` |
| Per-profile model | `grep -A3 '^model:' ~/.hermes/profiles/<name>/config.yaml` |
| Delegation config | `grep -A15 '^delegation:' ~/.hermes/profiles/<name>/config.yaml` |
| Aux overrides (vision, summarize) | `hermes config show` — "Auxiliary Models (overrides)" section |
| Full config | `read_file ~/.hermes/profiles/<name>/config.yaml` |

Profile homes live at `~/.hermes/profiles/<name>/`; the default profile lives at
`~/.hermes/` itself.

## Procedure

1. **Read the disk, not memory or skill notes.** Concrete case this session: the
   `model-routing-workflow` skill still said main = DeepSeek V4 Flash while
   `config.yaml` said DeepSeek V4 Pro. Reciting the skill would have been wrong;
   `grep -A3 '^model:'` gave the truth.
2. **Use `grep -A<n>`, not a bare `grep '^key:'`.** YAML values are NESTED under
   their key. `grep '^model:'` prints only the key line; `grep -A3 '^model:'`
   prints the value lines too.
3. **Reconcile any loaded skill against the verified disk state and patch it**
   (see `model-routing-workflow` for how its routing table was corrected).
4. Cross-check with `grep -rn` when a search tool returns 0 and you expect matches.

## Pitfalls

- **vision_analyze silently drops images when the vision override is a text-only model.**
  Observed Nov 2026 on this box: the tool returns success but the model reports
  "no image attached" — for local paths, copied paths, AND public URLs. Root cause
  confirmed: the Auxiliary Models override had Vision = MiniMax-M2.5, which takes
  text only, so image payloads were dropped before reaching any model. Diagnosis:
  `hermes config show` → "Auxiliary Models (overrides)" section names the vision
  model/provider. Fix: `hermes config set` the vision override to a vision-capable
  model — MiniMax's global API serves newer models under the SAME key (`GET
  https://api.minimax.io/v1/models` lists M3.1-Flash / M3 / M2.7; M3 is natively
  multimodal), so the swap is a model-name change only, no API/key changes. Probe
  image support empirically before and after switching: POST a
  `data:image/...;base64` URL in a chat-completions message and confirm the model
  describes the image. Fallback while broken: a subagent with tesseract OCR + web
  verification (slow, but accurate).
- **Nested YAML keys.** `grep '^model:'` / `grep '^(model|provider):'` return only
  the key line. Always add `-A<n>` to capture the indented value.
- **search_files can false-zero.** Content searches using alternation (`a|b`) or
  anchored (`^key`) patterns have returned 0 results where terminal `grep -rn`
  finds matches — observed against files under `~/.hermes` (a dot-directory).
  When a 0-result contradicts your expectation, verify with `grep -rn` before
  concluding "not found"; don't treat a search_files count as proof of absence.
- **`delegate_task` caches its model at agent startup.** Editing `delegation.model`
  mid-session has no effect until restart. Full routing semantics + the
  `hermes chat -q` subprocess workaround live in `model-routing-workflow`.
- **Skills drift from reality.** Treat a skill's "current model / state" claims as
  a hypothesis, not a fact — verify, then patch the skill to match the disk.
- **Direct config writes are REFUSED.** Hermes guards
  `~/.hermes/profiles/*/config.yaml` (and default `~/.hermes/config.yaml`) as
  security-sensitive — `patch`/`write_file` error with "Agent cannot modify
  security-sensitive configuration". Use the sanctioned CLI instead:
  `hermes config set <dotted.path> <value>`, and
  `hermes --profile <name> config set ...` for other profiles. A multi-file patch
  is refused **atomically** — the non-config hunks in the same patch (e.g. a
  SKILL.md edit) do NOT apply either, so redo them as a separate call.

## Verification

- Re-run the `grep -A<n>` command yourself before reporting values, and state the
  actual values Greg will act on — never recite them from memory.
