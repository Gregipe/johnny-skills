# Partial Confirmation (`_split_partial_rejection`)

## What
Modifies the reject handler in the confirmation flow to handle "ignore X, just do Y" replies to multi-tool proposals.

## Problem
When Ava proposes multiple tools (e.g., `create_deal` + `send_whatsapp`) and Greg replies "ignore the deal, just send the WhatsApp", the old `_classify_confirmation` returned `reject` — cancelling EVERYTHING including the WhatsApp Greg wanted.

## Architecture

### Detection (regex patterns)
Scans user reply for:
- **Skip patterns:** `ignore the X`, `skip the X`
- **Keep patterns:** `just handle Y`, `only do Y`, `but handle Y`

### Entity matching
Extracted entity names (`shriram finance deal`, `whatsapp to jimmie`) are matched against tool call args:
```
lead_name, org_name, deal_name, name, title, message
```

### Splitting
- Tools matching skip entity → dropped
- Tools matching keep entity → executed
- Unmatched tools → kept (default: execute)

### Fallback
Returns `(None, None)` when:
- Only one tool pending (single-tool = normal reject)
- No skip/keep patterns detected
- All tools matched skip (full rejection)

## Location
- Function: `_split_partial_rejection()` — inserted after `_classify_confirmation` in server.py
- Call site: In the `elif _verdict == "reject":` handler, BEFORE the full-cancel block

## Logging
Prefix: `PARTIAL-REJECT: keeping=N tools, rejecting=M tools (skip=X, keep=Y)`
Executing: `PARTIAL-REJECT executing: N kept, M rejected`

## Example
```
User: "Ignore the shriram finance deal for now and just handle the whatsApp to Jimmie please."
Pending: [create_deal(org_name="Shriram Finance"), send_whatsapp(lead_name="Jimmie Tete")]
Result: skip=create_deal, keep=send_whatsapp → WhatsApp sent, deal dropped
```
