# June 2026 Architecture Overhaul — New Patterns

## New Trigger Conditions

These symptoms now have known root causes and fixes:

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| "Hi Ava → full capability dump" | Full pipeline injected on every message; LLM parrots most salient item | Tiered context injection (smalltalk/status/command) |
| "She says 'Done' but nothing changed" | Prose and tool calls decoupled; LLM describes action without calling tool | Delete regex guards, add prose-after-result invariant |
| "Voice note triggered creating Ajay/Shriram" | Alphabetically-first pipeline items are most salient in context | Tiered injection + pipeline data quarantine |
| "Yes please → re-lists everything" | Confirmation fires in bloated observe loop context; original intent buried | Re-anchor confirmation to pending action's stored intent |
| "Update due date → 3 queries then gave up" | Redundant tools (query_actions, get_action_items, query_database) | Remove redundant tools from schema |
| "Max tool steps reached" | 6-step limit with "STOP" nudge | Raise to 10, change nudge to "continue" |

## Architecture Principles (from advisor)

1. **Remove text, don't add it.** Every guard/nudge/correction injected into context displaces the original user message.
2. **Tiered context injection.** Don't inject pipeline data for smalltalk and status messages.
3. **Prose-after-result.** Never describe a write as done without tool confirmation.
4. **Thread quarantine.** Archive poisoned threads; never let them accumulate.

## Implementation Details

See `ara-ava-guardrails` skill, `references/context-discipline-june2026.md` for:
- Tiered context injection code (classification call, conditional injection)
- Regex guard deletion list (8 guards removed)
- Prose-after-result invariant
- Case studies

See `whatsapp-integration` skill, `references/inbox-durability-june2026.md` for:
- Inbox-first message durability
- pending.json → SQLite inbox_messages migration
