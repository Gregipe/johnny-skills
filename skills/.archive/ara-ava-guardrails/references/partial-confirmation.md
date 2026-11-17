# Partial Confirmation (`_split_partial_rejection`)

## What
Modifies the reject handler to handle "ignore X, just do Y" replies to multi-tool proposals — splitting pending tool calls instead of cancelling everything.

## Problem
When Ava proposes multiple tools (e.g., `create_deal` + `send_whatsapp`) and Greg replies "ignore the deal, just send the WhatsApp", the old `_classify_confirmation` returned `reject` — cancelling EVERYTHING including the WhatsApp Greg wanted.

## Architecture
- **Detection:** Regex patterns for skip ("ignore the X") and keep ("just handle Y")
- **Entity matching:** Extracted entity names matched against tool call args (lead_name, org_name, deal_name, etc.)
- **Splitting:** Tools matching skip → dropped. Tools matching keep → executed. Unmatched → kept (default execute).
- **Fallback:** Returns `(None, None)` for single-tool or no-pattern-detected → normal full reject.

## Location
- Function: `_split_partial_rejection()` in server.py, after `_classify_confirmation`
- Call site: `elif _verdict == "reject":` handler, BEFORE the full-cancel block

## Logging
`PARTIAL-REJECT: keeping=N, rejecting=M (skip=X, keep=Y)`
`PARTIAL-REJECT executing: N kept, M rejected`
