# _BUILD_DESC_FALLBACK_COUNT — Uninitialized Variable Crash (July 12, 2026)

## The Bug
Any voice-write tool without an explicit `elif` case in `_build_pending_description()` crashes with:
```
NameError: name '_BUILD_DESC_FALLBACK_COUNT' is not defined
```

This causes `POST /api/voice/stage` → 500 → LLM retries → infinite loop.

## Trigger Chain
1. LLM calls a tool in `VOICE_WRITE_TOOLS` (e.g., `update_action`)
2. Voice agent stages it via `POST /api/voice/stage`
3. `voice_stage()` (server.py:13077) calls `_build_pending_description()`
4. Tool has no explicit `elif` case → falls to generic `else:` branch
5. `else:` branch hits `_BUILD_DESC_FALLBACK_COUNT.get(name, 0)`
6. Dict was never initialized → `NameError` → 500
7. LLM retries with different params → same 500 → loop

## Root Cause
`_BUILD_DESC_FALLBACK_COUNT` exists ONLY on lines 7010-7011 of server.py:
```python
_BUILD_DESC_FALLBACK_COUNT[name] = _BUILD_DESC_FALLBACK_COUNT.get(name, 0) + 1
if _BUILD_DESC_FALLBACK_COUNT[name] == 3:
```

Zero initialization anywhere in the codebase. The developer wrote the audit counter code but forgot `_BUILD_DESC_FALLBACK_COUNT = {}`.

## Fix
1. Add `_BUILD_DESC_FALLBACK_COUNT = {}` after `_cf_log` at line 322
2. Add explicit `elif` cases for commonly used tools (see below)

## Affected Tools
Any tool in `VOICE_WRITE_TOOLS` without an explicit `elif` case:
`update_action`, `update_deal`, `schedule_follow_up`, `schedule_message`, `schedule_email`, `send_attachment`, `send_internal_note`, `mark_meeting_booked`, `evaluate_qualification`, `log_insight`, `save_learning`, `add_to_watchlist`, `resolve_watchlist_item`, `import_leads_from_text`, `upload_document`

## Design Rule
Every time you add a tool to `VOICE_WRITE_TOOLS`, add an explicit `elif name == "your_tool"` case in `_build_pending_description()`. The generic fallback exists as a safety net, not a primary path. The dict init needs to exist regardless, but every tool should have a proper user-facing description.
