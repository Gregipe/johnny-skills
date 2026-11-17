# Confirmation Flow Hardening (June 2026)

Three fixes deployed after Greg reported raw tool names (`save_memory; save_memory; save_memory`) appearing in chat and silent WhatsApp message failures during the confirmation flow.

## Fix 1: `_build_pending_description` missing tool cases

**Symptom:** When the LLM proposed `save_memory` actions, the pending confirmation prompt showed `save_memory; save_memory; save_memory` as literal text.

**Root cause:** `_build_pending_description()` (server.py line 6707) has explicit formatters for `send_whatsapp`, `create_lead`, `set_reminder`, etc. but no case for `save_memory` or `send_whatsapp_to_owner`. The generic fallback filters args by key names — `save_memory` uses `key`/`value` which weren't in the filter list, producing empty output and bare tool names.

**Fix:**
- Added `save_memory` case: renders as `💾 Save: {preview} — shall I save it?`
- Added `send_whatsapp_to_owner`/`send_whatsapp_instantly` case: renders as `💬 Send to you — shall I send it?`
- Expanded generic fallback arg filter to include `key` and `value`

## Fix 2: Perpetual PENDING_TTL + clarification gate

**Symptom:** Greg said "yes please" to pricing corrections 11 hours after they were proposed. The pending had expired (PENDING_TTL=600s). "yes please" fell through to the regular LLM loop where it hallucinated `save_memory; save_memory; save_memory` as text output.

**Root cause:** PENDING_TTL was 10 minutes — far too short for asynchronous chat. When the pending expired, `_live_pending_for_tenant()` returned None, the confirmation gate was completely bypassed, and the user message was routed as a fresh LLM conversation with no awareness of the prior proposal.

**Fix:**
- `PENDING_TTL` changed from 600s to 86400s (24h, garbage collection only)
- `_live_pending_for_tenant()` no longer filters by TTL — pending actions persist until explicitly resolved
- Clarification gate added: when user message matches confirmation patterns (`yes`, `ok`, `go ahead`, `did you do it?`, `any update?`, etc.) but NO live pending exists, system responds with explicit clarification instead of silent LLM fallthrough

Confirmation patterns detected (bare matches + short "yes" variants):
```
yes, yes please, yeah, yep, yup, ok, okay, sure, go ahead, do it, send it, send,
please do, confirmed, approve, approved, proceed, fine, good, great, perfect,
done?, is it done?, did you do it?, did you send it?, any update?, what happened?,
and?, go on, continue
```

## Fix 3: Post-execution sidecar health check

**Symptom:** WhatsApp messages appeared to send successfully ("✅ Messaged...") but were not delivered because the sidecar's WhatsApp session was corrupted (Bad MAC, missing sessions). The sidecar returned `{ ok: true }` despite being unable to deliver.

**Root cause:** The sidecar's `connectionState` stays `"connected"` even when the underlying session has decryption failures. `sendMessage()` returns a msgId that looks valid. The ARA server trusts the sidecar response unconditionally.

**Fix:** After the confirmation flow executes `send_whatsapp` tools (in the `for _i, _pc in enumerate(_pending_calls)` loop), it now pings `localhost:8767/status`. If the sidecar is disconnected or unreachable, a warning `ToolResult(ok=False)` is appended:
> "WhatsApp sidecar is not connected (state: awaiting_scan). Messages may not have been delivered. Check https://qr.move78.work/link to re-link."

This catches the false-positive case where the sidecar reports success but can't actually deliver.

## WhatsApp 401 device_removed (related)

During the June 29 session, the sidecar was kicked by WhatsApp with a stream-level 401 `conflict` error (`type: "device_removed"`). The sidecar cleared auth and restarted in `awaiting_scan` state. Messages sent in the same tick got msgIds but were not delivered. See `ara-sidecar-reliability` SKILL.md for the watchdog notification system that alerts Greg when this happens.
