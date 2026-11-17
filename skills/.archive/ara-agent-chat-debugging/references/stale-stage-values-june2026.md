# Stale Stage Values in AGENT_TOOL_SCHEMA (June 2026)

## The Bug

Ava's tool definitions (in `AGENT_TOOL_SCHEMA` in server.py) used outdated stage values that didn't match the actual DB model. This caused the LLM to form invalid tool calls that the handler rejected, leading to fallback guessing.

## Affected Locations

All places in `AGENT_TOOL_SCHEMA` where valid stages are listed:

| Location | Old (stale) | New (correct) |
|----------|-------------|---------------|
| Tool #1 `update_lead` | `contacted`, `proposal`, `closed_won`, `closed_lost` | `reached_out`, `meeting_booked`, `deal_won`, `lost` |
| Tool #4 `create_deal` | `reachout`, `negotiation`, `closing_won`, `lost` | `new`, `reached_out`, `engaged`, `qualified`, `meeting_booked`, `deal_won`, `lost`, `dormant` |
| Tool #35 `update_lead_stage` | `closed_won`, `closed_lost` | `deal_won`, `lost` |
| Examples (create_deal) | `"stage": "reachout"` | `"stage": "reached_out"` |

Also in the tool dispatch handler (`execute_tool`), the `update_lead_stage` handler's valid stages tuple:

```python
# BEFORE
valid = ('new','reached_out','engaged','qualified','meeting_booked','dormant','closed_won','closed_lost','lost')

# AFTER
valid = ('new','reached_out','engaged','qualified','meeting_booked','deal_won','lost','dormant')
```

## Why It Happened

The DB model (`Deal` table) uses `deal_won` and `lost` as stage values, but the tool schema was written earlier with different naming conventions that were never updated when the DB schema changed. The tool schema is maintained independently from the DB model — there is no automated sync.

## The Fix

1. Edit `AGENT_TOOL_SCHEMA` in server.py — find every tool definition that lists valid stages and update to match the current DB values
2. Edit the `valid` tuple in the `update_lead_stage` handler's `elif` block in `execute_tool()`
3. Edit examples at the bottom of `AGENT_TOOL_SCHEMA`
4. Verify by searching for ALL occurrences of stale stage names (`contacted`, `proposal`, `closed_won`, `closed_lost`, `reachout`, `negotiation`, `closing_won`) in server.py

## Related Changes Made In This Session

- Added `update_deal_stage` tool (tool #36) to let Ava move deals through the pipeline independently
- Added `_sync_deal_stage_from_lead()` call to `update_lead_stage` handler so lead stage changes also sync the deal
- Added `_sync_deal_stage_from_lead()` call inside the `lead.stage == "new"` transition in `_execute_cadence_action()` (the first-outbound WhatsApp path)

## Prevention

When changing stage names in the DB model or migration, search `AGENT_TOOL_SCHEMA` for the old value. There is no automated link between model defaults and tool schema strings.
