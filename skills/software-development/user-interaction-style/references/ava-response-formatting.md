# Ava Response Formatting Rules

Greg's explicit preferences for how Ava (and Johnny) should format structured output.

## Bold Headers

Use bold section headers. No ASCII art. No emoji-only lines. No walls of text.

## Briefing Sections

Organize end-of-day or status briefings into:
- ✅ ACCOMPLISHED — what was completed today
- ⏳ PENDING — not yet done, not past due
- 🔴 OVERDUE — past due date, not completed
- 📚 TODAY'S LEARNINGS — learnings from today only (not lifetime dump)

## Action Item Format

Every action must show three things:
1. **Description** — what needs to be done
2. **Lead name** — who it's for
3. **Due date** — when it's due

Format: `• Description — Lead Name | ⏰ Due Date, Time IST`

Overdue items get 🔴 prefix before the description.

## Anti-Patterns

NEVER dump raw action items as:
```
[status] title (action_type) -- date [id=abc123]
```
This format was explicitly rejected. Every action is a human-readable line with lead context.
