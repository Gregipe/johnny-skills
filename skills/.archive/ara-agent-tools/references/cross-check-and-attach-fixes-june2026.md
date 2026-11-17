# Cross-Check Fix + attach_to_deal Auto-Primary (June 2026)

## Structural Cross-Check — `not first_pass` Bug

**Bug:** The text-vs-tools cross-check that verifies LLM text actions match tool calls used:
```python
if _missing and not first_pass:
```
The `not first_pass` condition BLOCKED detection on the initial generation pass — exactly when the mismatch occurs.

**Symptom:** LLM text says "attach Vinay Bhoj as contact" but only calls `create_deal` with no `attach_to_deal` call. System fails to catch it.

**Fix (June 16, 2026):** Changed to `if _missing:` (always check on every pass).
Location: observe loop, line ~5771, inside `if not confirmed and is_data_modifying:` block.

**Why `not first_pass` existed:** It was meant to only check after the LLM had a chance to fix itself on a second loop iteration. But the first pass is when the initial text+tool calls are generated — that's EXACTLY when the mismatch occurs.

## _pending_results in Multi-Step Path

In the multi-step branch of the confirmation executor:
```python
_pending_results = [_tr]  # MUST be set — downstream _tr_json builder expects it
```
Without this, `_tr_json` at line ~6306 stays None because `_pending_results` is only defined in the single-step path's loop.

## attach_to_deal Auto-Sets Primary Contact

**Change:** When `attach_to_deal` links a lead to a deal and the deal has NO primary contact, it now auto-sets the deal's primary contact fields:
```python
if not deal.lead_id:
    deal.lead_id = lead.id
    deal.contact_name = lead.name
    deal.contact_email = lead.email
    deal.contact_phone = lead.phone
```

This closes the gap where `attach_to_deal` (Lead.deal_id) didn't populate Deal.lead_id/contact_name/email/phone — leaving deals with attached leads but no primary contact.
