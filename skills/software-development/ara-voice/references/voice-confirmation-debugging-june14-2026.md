# Voice Confirmation Debugging — June 14, 2026

## Incident

Greg sent a voice note asking to set a reminder. Ava processed the transcription, asked for confirmation, but:
1. Greg's "yes" reply was swallowed — no reaction, no execution, no response
2. A follow-up voice note executed immediately without asking for confirmation
3. "set it in" wasn't recognized as confirmation, fell through to agent_chat as orphan

## Debugging Trace

### The two-dict architecture

Two independent confirmation systems in the codebase, disconnected:

| Dict | Location | Written by | Read by |
|------|----------|------------|---------|
| `_pending_voice_confirmations` | `app/dedup.py` → imported as `pending_confirmations` | **NEVER** — no assignment anywhere | `_handle_owner_coach_whatsapp` confirm handler |
| `_pending_actions` | `server.py ~line 291` (module-level) | `agent_chat` → `_run_observe_loop` on `[ACTION: ASK]` | `agent_chat` confirm handler (line 5141) |

The confirm handler in `_handle_owner_coach_whatsapp` only checked `_pending_voice_confirmations` — always empty → always `None` → confirmation never triggered.

### Fix attempt 1: Fallback to `_pending_actions`

Added fallback in the confirm handler to scan `_pending_actions` when `_pending_voice_confirmations` is empty. Used wrong import: `from app.dedup import pending_actions` — raised `ImportError`, caught by outer `except`, silently swallowed the entire handler. Greg's "yes" messages were discarded with zero feedback.

### Fix attempt 2: Remove bad import

`_pending_actions` is module-level in `server.py` (line 291) — no import needed. Removed the `from app.dedup import pending_actions` line.

### Bug 1: LLM ignores `[ACTION: ASK]` for voice notes

Despite strengthened prompt and message-level tag, the LLM occasionally uses `[ACTION: NOW]` → executes without confirmation → nothing stored in `_pending_actions` → "yes" finds empty dict → swallowed.

**Fix:** Code-level gate — `voice_note: True` flag in agent_chat JSON body. `_run_observe_loop` reads the flag and forces `intent = "ask"` for any data-modifying tool regardless of what marker the LLM emits.

### Bug 2: Infinite confirmation loop (masked by Bug 1)

When Bug 1 is fixed and "yes" finds a pending entry, the exec_msg re-enters `_run_observe_loop` without `[ACTION: NOW]` → gets re-gated → creates another `[PENDING]` → confirm → confirm forever.

**Fix:** `pre_confirmed: True` flag in exec_msg call. `_run_observe_loop` reads the flag and forces `confirmed = True`, bypassing the gate.

### Bug 3: Confirm word collision — "set it in" not recognized

Greg replied "set it in" to a voice confirmation. Neither confirm handler recognized it — "set" wasn't in any confirm word list. The message fell through to agent_chat as an orphan, where Ava had no context.

**First attempt (WRONG — b73843f):** Added "set", "set it" to confirm regex + agent_chat's `_confirm_words` + `startswith("set")`.

**Why dangerous:** "set" is a command verb, not a pure affirmation. With a stale pending entry sitting in `_pending_actions` (TTL prune only runs inside confirm blocks — stale entries can linger for hours), typing "set Rajesh's stage to engaged" would trigger the confirm handler and execute the OLD pending action. Silent data corruption.

**Correct fix (60bac75):** Split confirm detection into two tiers:
1. **Safe words** (yes, yeah, yep, sure, send it, do it, go ahead, confirm, execute) — always match. Pure affirmations, never command verbs.
2. **Contextual words** (set, set it) — only count as confirmation WHEN `_pending_actions` has a live entry for this tenant. No pending entry → "set..." routes to agent_chat as a normal command.

Agent chat reverted to safe words only. Contextual match lives only in the voice handler with the pending-entry guard.

### TTL prune scope issue

Both prune loops run ONLY inside their respective confirm blocks. If no confirm-looking message arrives, stale entries persist indefinitely. This makes contextual gating essential — without it, a "set..." command arriving hours later would fire the wrong action.

### Architecture principle

1. Text markers (`[ACTION: NOW]`, `[ACTION: ASK]`) are unreliable — they depend on the LLM. JSON flags (`voice_note`, `pre_confirmed`) are invariants set by code, not the model.
2. Confirm word lists must ONLY contain pure affirmation words — never command verbs. Use contextual gating when you need to add words that double as commands.
3. The `🎤` emoji prefix is fragile coupling — use explicit flags, not message-format detection.

### Data format difference

`_pending_voice_confirmations` stores `{"plan": "...", "transcript": "...", "timestamp": ...}` while `_pending_actions` stores `{"tool_calls": [...], "response_clean": "...", "timestamp": ...}`. The confirm handler must handle both formats. Detect via `"plan" in pending` vs `"tool_calls" in pending`. Cleanup must delete from whichever dict the entry came from.

## Key Files Modified

- `server.py` ~line 291 — `_pending_actions` dict (module-level)
- `server.py` ~line 4908 — `_run_observe_loop` signature (+ `voice_note`, `pre_confirmed`)
- `server.py` ~line 4983 — gate enforcement logic
- `server.py` ~line 5347 — call site passing flags from `data`
- `server.py` ~line 9207 — `_handle_owner_coach_whatsapp` confirm handler + fallback + contextual gating
- `server.py` ~line 9289 — exec_msg call with `pre_confirmed: True`
- `server.py` ~line 9619 — voice-inbound with `voice_note: True`

## Commits

```
d41cd40 — fix: voice confirmation context loss — check _pending_actions fallback
53e7949 — fix: voice notes must use [ACTION: ASK] — stronger prompt + VOICE NOTE tag
4586a5d — fix: remove bad app.dedup import — _pending_actions is module-level
3a77211 — fix: code-level voice gate + pre_confirmed flag — Bugs 1 & 2 resolved
b73843f — fix: add set/set it to confirm word lists (REVERTED — bare command-verb matching)
60bac75 — fix: contextual confirm — "set" only triggers confirmation when pending entry exists
```
