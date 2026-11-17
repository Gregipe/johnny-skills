# Confirmation Flow Build Plan Summary (2026-06-29)

Full implementation plan for 6 confirmation-flow failure modes discovered during systematic debugging of Ava's agent chat.

## 6 Issues (in implementation priority)

| # | Issue | Symptom | Root Cause | Files |
|---|-------|---------|------------|-------|
| 6 | Sidecar false-positive | "✅ Messaged..." but never delivered | Baileys connectionState stays "connected" on dead sessions; server trusts `{ok:true}` unconditionally | index.js, whatsapp_sidecar_client.py, server.py |
| 2 | Echo message poisoning | "✨ Ava: Not yet..." → cancels pending | No echo detection before _classify_confirmation | server.py |
| 3 | Variant confirmation gate | "yes - run all three" bypasses gate | Exact-set match, not regex; misses ^yes\b variants | server.py |
| 1 | Step-count mismatch | Text says 3 steps, only 2 tool calls | No cross-check between enumerated steps and tool call count | server.py |
| 5 | Generic tool descriptions | Raw tool names in confirmation text | _build_pending_description else clause ignores TOOL_SCHEMAS | server.py |
| 4 | Entity preservation | Sai Bharat dropped on re-proposal | LLM has no in-band memory of pending entities | server.py |

## Architecture principle

**Every fix goes at the choke point, not the symptom site.** Fix #6 goes in `send_message_sync()` (all send paths), not just confirmation flow. Fix #2 goes before the classifier (all user messages), not in specific patterns. Fix #1 goes at pending creation (prevents mismatch from reaching the user).

## Feature flags

Each fix is independently toggleable via env var:
- `ARA_SIDECAR_HEALTH_CHECK=1`
- `ARA_ECHO_DETECTION=1`
- `ARA_VARIANT_CONFIRM_GATE=1`
- `ARA_STEP_COUNT_CHECK=1`
- `ARA_GENERIC_TOOL_DESC=1`
- `ARA_ENTITY_INJECTION=1`

## How to verify

After implementing all 6:
1. `cd /opt/ara && python3 tests/full_battery.py` — all green
2. `python3 tests/gate_synth.py` — synthesis pass gates
3. `python3 tests/gate_retry.py` — retry logic gates
4. `python3 tests/gate_tier.py` — tier classification gates
5. New regression tests for each fix (self-cleaning)
6. `systemctl restart ara-server && systemctl is-active ara-server`

Full implementation details (exact line numbers, code snippets) in `/Users/greg/.hermes/hermes-agent/ara-analysis/build-plan.md`.
