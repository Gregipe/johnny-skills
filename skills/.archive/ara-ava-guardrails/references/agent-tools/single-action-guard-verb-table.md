# Single-Action Guard Verb Table Maintenance

The `_guard_single_action` function (server.py) maps user-message action verbs to tool families. When adding a new data-modifying tool, update the `_VERBS` dict.

## Current Verb Table (June 2026)

| Verb | Tools |
|---|---|
| `send` | send_whatsapp, send_email, send_whatsapp_to_owner |
| `create` | create_lead, create_deal, create_action_item |
| `update`, `change`, `edit` | update_lead, update_deal, update_action |
| `set` | set_reminder, set_cron |
| `schedule` | set_reminder, set_cron, schedule_message, schedule_email |
| `remind` | set_reminder |
| `move` | update_lead_stage, update_deal_stage |
| `cancel`, `stop`, `delete`, `remove` | cancel_scheduled |
| `attach` | attach_to_deal |
| `trigger`, `start` | trigger_cadence |
| `escalate` | escalate_to_human |

## Adding a New Tool

1. Identify the primary verb users would use to invoke this tool
2. Add the tool name to the existing verb's list, OR
3. Create a new verb entry if no existing verb covers it
4. Example: adding `send_slack` → `"send": [..., "send_slack"]`

## Pitfall

If a tool is NOT in the verb table, `_guard_single_action` can't protect against over-generation for that tool — it won't match any verb, so it'll be dropped from multi-tool proposals when a single verb is detected. This means the guard could incorrectly trim a valid proposal.

Tools that are read-only or diagnostic (`get_*`, `search_*`, `check_*`, `read_*`, `list_*`) do NOT need entries because they don't go through `data_tools` (the guard only operates on `data_tools`, which excludes read-only tools via `get_tool_read_only()`).
