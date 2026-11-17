# Conversation History Poisoning — LLM Hallucination Cascade

When the LLM writes a hallucinated "tool failed" response into the DB, every subsequent request on the same thread reads that failure and repeats it. The cascade compounds with each request.

See `ara-ava-guardrails/references/conversation-history-poisoning.md` for full documentation.

## Quick Reference

- **Detection:** 3+ consecutive assistant responses with the same failure message + no [TOOL_CALL:] block = hallucination cascade
- **Fix:** Delete hallucinated responses from DB + add prompt rule to ignore past failures
- **Prevention:** Dedup prevents new duplicates from processing; enforcer's `_has_data_tool` check prevents the first hallucination
- **Thread hygiene:** If >5 poisoned responses in history, cleaning the DB is more reliable than prompt rules
