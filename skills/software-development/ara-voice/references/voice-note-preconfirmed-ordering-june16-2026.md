# Voice Note Pre-Confirmed Ordering Bug — June 16, 2026

## Incident

Greg sent a voice note via WhatsApp: "send the deck to Jimmie with attachment." The LLM processed it, called `get_lead_detail` + `list_documents` + `send_email` with `[ACTION: NOW]`, and the email was sent without asking for confirmation — wrong deck, no confirmation prompt.

## Root Cause

The `_run_observe_loop` had two safeguards that conflicted due to execution order:

```python
# WRONG ORDER (before fix 414c6eb):
if voice_note and is_data_modifying:
    intent = "ask"  # safeguard 1: voice notes must ask

if pre_confirmed:
    confirmed = True
    intent = "now"  # safeguard 2: confirmed actions execute immediately
    # ← OVERRIDES safeguard 1!
```

**Why it broke:** When the LLM outputs `[ACTION: NOW]` on a voice note, the request body includes `pre_confirmed=True`. The code:
1. Sets `intent = "ask"` (voice note safeguard)
2. Sets `intent = "now"` (pre_confirmed override — CL OBBERS IT)
3. `confirmed = True` → skips the gate entirely
4. Tool executes without confirmation

The voice note safeguard was designed to catch this case, but it ran BEFORE `pre_confirmed` and got overridden. The LLM's `[ACTION: NOW]` marker on voice notes produced `pre_confirmed=True`, which is exactly the wrong behavior when combined with `voice_note=True`.

## Fix (414c6eb)

Reverse the order — voice note check MUST run LAST:

```python
# CORRECT ORDER:
if pre_confirmed:
    confirmed = True
    intent = "now"

if voice_note and is_data_modifying:
    intent = "ask"
    confirmed = False  # force confirmation even against pre_confirmed
    # ← Voice notes ALWAYS win
```

**The principle:** `pre_confirmed` is a general bypass mechanism for confirmed actions. `voice_note` is a HARDER constraint that says "no matter what the LLM emitted, voice notes must ask." The harder constraint must run LAST.

## Verification

Before fix: WhatsApp voice note "send email to Jimmie with deck" → `[ACTION: NOW]` → email sent immediately, no confirmation.

After fix: Same voice note → `voice_note=True` detected → `intent="ask"` forced → `confirmed=False` → proposal shown → user must confirm "yes" before sending.

## Architecture Lesson

When two safeguards produce conflicting outcomes, the STRICTER one must run after the more PERMISSIVE one. `voice_note` says "always ask" — stricter than `pre_confirmed` which says "skip the gate." The stricter check goes last.
