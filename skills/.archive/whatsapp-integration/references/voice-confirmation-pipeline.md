# Voice Confirmation Gating (July 2026)

Voice-to-CRM with a safety confirmation step for complex actions. Added because Whisper base.en struggles with Indian names (surnames, company names, places), and executing complex CRM changes on a mis-transcription is worse than not executing at all.

## Design Principle

**Simple actions execute immediately. Complex actions require confirmation.**

This balances speed (why voice notes are useful — 5s to add an email) with accuracy (don't create a wrong lead because Whisper heard "Swi-gee" instead of "Swiggy").

## Flow

```
Voice note → Whisper → Ava drafts action (no execution)
                            │
               ┌────────────┴────────────┐
               ↓                         ↓
          [EXECUTED]                [CONFIRM_REQUIRED: plan]
               ↓                         ↓
        Execute now              Save as pending, send:
        "Done ✅"                 "I heard: create lead
                                  Thomas George, Swiggy.
                                  Reply 'yes' to confirm."
                                           ↓
                                    User says "yes"
                                           ↓
                                    Ava executes draft
                                    "Done ✅"
```

## Simple vs Complex Classification

Ava decides, not a hardcoded rule. The voice prompt instructs Ava to prefix its response with:

- `[EXECUTED]` — SIMPLE: adding notes, emails, phone numbers, contact info updates. Execute immediately, no confirmation needed.
- `[CONFIRM_REQUIRED: <one-line plan>]` — COMPLEX: creating new leads, changing stages, scheduling meetings, creating action items, or anything modifying pipeline state. DO NOT execute yet — only draft.

This lets Ava use judgment: "add email" = simple, "change stage to meeting_booked" = complex.

## Code Architecture

### Phase 1: Voice Endpoint (`whatsapp_voice_inbound` in server.py)

```python
# Modified prompt wrapper — key change is the prefix instruction:
wrapped_msg = (
    f"[VOICE NOTE FROM FIELD AGENT — {duration}s]\n"
    f"Transcript: {transcript}\n\n"
    f"...standard instructions...\n\n"
    f"After you finish, prefix your FINAL response with exactly one of:\n"
    f"- [EXECUTED] if the action was SIMPLE (adding notes, emails, phone numbers)\n"
    f"- [CONFIRM_REQUIRED: <one-line summary>] if needs confirmation "
    f"(creating leads, changing stages, scheduling, action items)\n\n"
    f"For [CONFIRM_REQUIRED], DO NOT execute the action yet — only draft the plan."
)
```

After getting Ava's response:

```python
import re as _re
confirm_match = _re.match(r'^\[CONFIRM_REQUIRED:\s*(.+?)\]', ava_reply, _re.DOTALL)
executed_match = _re.match(r'^\[EXECUTED\]', ava_reply)

if confirm_match:
    plan = confirm_match.group(1).strip()
    # Save to in-memory dict, keyed by phone
    _pending_voice_confirmations[phone] = {
        "plan": plan,
        "thread_id": thread_id,
        "transcript": transcript,
        "timestamp": time.time(),
    }
    # Send confirmation request to WhatsApp
    confirmation_msg = (
        f"🎤 *I heard:* {plan}\n\n"
        f"Reply **'yes'** or **'send it'** to confirm, or record a new voice note."
    )
    _wa.send_to_jid(remote_jid, confirmation_msg)
    return {"status": "awaiting_confirmation"}

if executed_match:
    ava_reply = ava_reply[len("[EXECUTED]"):].strip()
    # Falls through to normal execution + confirmation
```

### Phase 2: Coaching Handler (`_handle_owner_coach_whatsapp`)

The in-memory dict `_pending_voice_confirmations` holds pending confirmations keyed by phone number. The coaching handler checks it BEFORE routing to normal Ava chat:

```python
# At the top of _handle_owner_coach_whatsapp, after dedup checks:
_confirm_keywords = ("yes", "send it", "confirm", "do it", "go ahead", "sure", "yeah", "yep", "execute")
if message.strip().lower().rstrip(".!") in _confirm_keywords:
    # Prune stale entries (>5 min)
    _stale = [p for p, v in _pending_voice_confirmations.items()
              if time.time() - v.get("timestamp", 0) > _PENDING_VOICE_TTL]
    for _p in _stale:
        del _pending_voice_confirmations[_p]

    pending = _pending_voice_confirmations.get(phone_clean)
    if pending:
        plan = pending["plan"]
        # Execute the confirmed plan via agent chat
        exec_msg = (
            "[CONFIRMED VOICE ACTION — EXECUTING]\n"
            f"The user confirmed the following plan. EXECUTE it now:\n"
            f"{plan}\n\n"
            f"Carry out every action described. Return a concise confirmation."
        )
        resp = requests.post(f"http://localhost:8766/api/agent/chat/{TENANT_ID}",
            json={"message": exec_msg, "thread_id": pending["thread_id"]},
            timeout=120)

        del _pending_voice_confirmations[phone_clean]
        # Send result back to WhatsApp
```

### State: `_pending_voice_confirmations`

In-memory dict, module-level, alongside the other coaching state:

```python
_pending_voice_confirmations = {}  # phone_clean -> {"plan", "thread_id", "transcript", "timestamp"}
_PENDING_VOICE_TTL = 300  # seconds (5 min to confirm before stale)
```

Keyed by `phone_clean` (owner's phone number, stripped of non-digits). Not persisted to DB — these are transient confirmations. If the server dies, the pending confirmation is lost and the user just re-records the voice note.

### Ownership: phone_clean match

The dict is keyed by the owner's phone (`phone_clean`), which is the same value extracted in both the voice endpoint (from `data.get("phone")`) and the coaching handler (from the webhook's `phone` extraction). This only works because the voice pipeline is self-chat only — only the owner's phone sends voice notes, and only the owner's phone replies to confirmation requests.

## Prompt Strategy for Phase 2 Execution

The "execute" message sent to Ava in Phase 2 is deliberately different from the Phase 1 draft:

```
[CONFIRMED VOICE ACTION — EXECUTING]
The user confirmed the following plan. EXECUTE it now:
{plan}

Original transcript: {transcript}

Carry out every action described. Return a concise confirmation of what was done.
```

This uses the SAME coaching thread (same `thread_id`) as the Phase 1 draft, so Ava has the full context. The original transcript is included as a reference so Ava can reach back to the raw transcription if the plan summary is too terse.

## Pitfalls

- **Message ID dedup can drop "yes"**: The coaching handler's content-hash dedup (`_coach_processed_hashes`) runs BEFORE the pending confirmation check. If the user sends "yes" and it's content-hash matched as a duplicate (same "yes" text within 60s), it gets dropped before the confirmation check runs. The confirmation check must run BEFORE the content-hash dedup. **Fix**: insert the pending confirmation check right after the rate limiter, before `_coach_processed_hashes` check.

  **Current code order (correct):** rate limiter → message_id dedup → content-hash dedup → **pending confirmation check** → typing keepalive → agent chat call

- **`phone` vs `phone_clean` mismatch**: Both the voice endpoint and the coaching handler derive the key from the same source (`phone` from the webhook payload). If they use different normalization (one strips `+91`, the other doesn't), the lookup fails silently. Always strip to digits-only before using as a dict key.

- **5-min TTL window**: After 5 minutes, the pending confirmation is pruned. The user saying "yes" after that point routes to normal Ava coaching instead. This is intentional — stale confirmations lose context. The user should re-record the voice note.

- **Confirmation is NOT at-mention or reply-thread**: The sidecar doesn't track which WhatsApp message a reply is responding to. The confirmation check uses pure content matching ("yes"/"send it") + phone matching. This means any "yes" message from the owner within 5min of a pending confirmation triggers it. Edge case: Greg texts "yes" as a coaching answer to Ava, and it accidentally executes a pending voice action instead. This is unlikely in practice since voice confirmations and coaching responses are distinct usage patterns.

- **In-memory state is ephemeral**: Server restart clears `_pending_voice_confirmations`. The user would need to re-record the voice note. For v1 this is acceptable — the confirmation step itself means the voice note was already transcribed, so re-recording is quick. For v2, persist to a `pending_voice_actions` DB table.

- **Ava's simple/complex classification is not guaranteed**: The prompt instructs Ava to use `[EXECUTED]` or `[CONFIRM_REQUIRED]`, but LLMs don't always follow prefix instructions. If Ava returns neither prefix (e.g., just a plain response), the code falls through to the `[EXECUTED]` path (stripping the non-existent prefix and sending the raw response). This means the action WAS executed but without the user seeing the confirmation. **To harden**: strip prefixes from the response display, or default to `[CONFIRM_REQUIRED]` when no prefix is detected (safer, but more friction).

## Future Improvements

1. **Stronger STT** — Swap to `medium.en` or `large-v3` Whisper, or OpenAI Whisper API. Better transcription = fewer confirmation prompts = faster flow.
2. **Confidence-gated** — Don't require confirmation for ALL complex actions. Use Whisper's per-segment confidence scores to decide: high confidence → execute immediately; low confidence → ask confirmation. This preserves speed for clear dictations.
3. **Persist pending actions to DB** — Survive server restarts.
4. **Reply-thread tracking** — Match confirmations to the specific WhatsApp message they're replying to, not just content + phone.
