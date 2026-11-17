# Pending-Action Confirmation System

> **Reworked 2026-06 — DB-backed, LLM-classified.** The previous design (in-memory
> `_pending_actions` dict + `_pending_voice_confirmations` dict + keyword/regex matchers
> + 900s TTL) was fully removed. If you see references to those symbols anywhere, they
> are dead. The sections below describe the CURRENT system.

## Architecture (current)

`ActionItem` is the single source of truth. A proposed data-modifying action is persisted
as a row, not held in memory — so it **survives a server restart**: a voice note proposed
before a restart can still be confirmed after it.

```
Ava proposes (ask intent) → observe loop gates the data-modifying action
    ↓
Persist ActionItem(execution_state="awaiting_approval", requires_confirmation=True,
                   owner="ava", description=response_clean,
                   pending_tool_calls=json([{tool,args}]), created_at=now)
    ↓
User replies → prune stale rows → _live_pending_for_tenant() gate → LLM classify
    ↓
confirm   → deserialize pending_tool_calls, execute via pre_confirmed path, state="fired"
reject    → state="cancelled", acknowledge, execute nothing
unrelated → leave row awaiting_approval, route the message normally (fresh request)
```

## Single TTL constant

`PENDING_TTL = 120` (seconds). One constant for the entire pending lifetime — prune and
the live-pending gate both use it, so they can't diverge. Short window deliberately bounds
the blast radius of an LLM misclassification: a stale row is pruned before it can be matched.

The old `_PENDING_ACTIONS_TTL = 900` and `_PENDING_VOICE_TTL` are gone. **Never reintroduce
a second pending-lifetime constant** — that drift was a real bug (900s vs 300s on the same
logical state).

## Helpers (server.py)

- `_prune_pending_actions(db, tenant_id)` — marks (does not delete) `awaiting_approval` rows
  older than `PENDING_TTL` as `execution_state="cancelled"`, keeping an audit trail.
  Idempotent. **Called at the top of every message on BOTH paths, before any confirm logic.**
- `_live_pending_for_tenant(db, tenant_id)` — newest non-stale `awaiting_approval` row, else
  `None`. The ONLY "is there something to confirm" check. Applies the TTL guard defensively
  even though prune ran. Backed by index `(tenant_id, execution_state)`.
- `_classify_confirmation(proposed_text, user_msg)` — one low-temp `call_llm`, returns exactly
  `confirm | reject | unrelated`. Parses the first token, exact-matches an allowlist, and
  **defaults to `unrelated` on anything malformed or on any LLM exception** (fail-safe: an
  ambiguous reply never auto-executes a pending write).

## Two-tier check — why both tiers matter

- **Tier 1** (`_live_pending_for_tenant`): if `None`, route normally with NO LLM call. This
  keeps the common case (no pending proposal) cheap and deterministic.
- **Tier 2** (LLM): only runs when a live row exists. It receives BOTH what Ava proposed AND
  the user's message, so it can distinguish:
  - live pending + `"set it in"` → **confirm** (answering the proposal)
  - live pending + `"set Rajesh to qualified"` → **unrelated** (a fresh command that merely
    starts with the same verb — the old regex `startswith("set")` got this wrong)

## Confirm executes STORED structured calls, not re-derived prose

On confirm, deserialize `pending_tool_calls` and execute those exact `[{tool, args}]` calls
via the `pre_confirmed` path (gate-skip). Do NOT re-POST the prose to the LLM to re-derive
tool calls — the structured calls are the truth. The `pre_confirmed` gate-skip in
`_run_observe_loop` is intentionally left untouched; this rework only changed WHERE the plan
is stored and HOW a reply is recognised as confirming it.

## Coach path is now a thin forwarder (fixes thread_id=None context loss)

`_handle_owner_coach_whatsapp` no longer does its own confirmation detection. It prunes stale
rows, then forwards the message to `agent_chat` **on the persistent coaching thread** — so the
proposal the user is replying to is in visible thread history, and `agent_chat`'s prune +
two-tier classifier does all the work. This fixed a prior bug where confirmations were
re-POSTed to a fresh `thread_id=None` thread with no history.

## Schema

`ActionItem.pending_tool_calls` (TEXT, nullable) holds the serialized `[{tool, args}]` list,
populated only for `awaiting_approval` rows. Added via the `init_db()` migration pattern
(ALTER TABLE if column absent), plus index `ix_action_items_tenant_exec` on
`(tenant_id, execution_state)`. `execution_state` now also takes the string values
`awaiting_approval` and `cancelled` (no enum constraint exists — plain strings).

## Worker note

Pending state is in the DB, so the historical single-worker assumption near `uvicorn.run`
is irrelevant for pending-action correctness. The "most-recent `awaiting_approval` by
`created_at`" selection remains a single-owner simplification (with one owner there's at most
one live proposal); multi-owner tenants would need per-owner scoping on the live-pending query.

## Test recipe (what the acceptance tests assert)

`tests/test_pending_confirmation.py` — monkeypatch `_classify_confirmation` for wiring tests,
monkeypatch `induction_engine.call_llm` for parser tests, and gate live LLM tests behind a
`_llm_reachable()` probe (key present AND a trivial classification returns `confirm`) — NOT
mere `os.getenv("DEEPSEEK_API_KEY")`, because a present-but-401 key would make them fail
instead of skip. Cases: restart-persistence (write row, no in-memory state, confirm fires);
`"set it in"`→confirm; `"set Rajesh to qualified"`→unrelated (row untouched); stale row +
`"yes"`→ pruned, classifier never runs, routes normally; `"no, cancel"`→ cancelled, nothing
executes. Stub `execute_tool` returns `ToolResult.success(tool, summary=...)` (factory is
`.success`, NOT `.ok`).
