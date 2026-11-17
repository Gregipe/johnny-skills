# Cadence Auto-Assignment Implementation

Tracked from the May 23, 2026 session — building the lead→cadence mapping system.

## Design Decisions

1. **No separate DB fields for the audit trail** — Greg wanted `cadence_auto_assigned` and `cadence_updated_at` NOT visible as separate fields in the UI. Instead, they're stored in the DB but surfaced only via a ℹ️ hover tooltip on the "Cadence" label.

2. **Superscript ℹ️ pattern** — The `i` uses `vertical-align: super` to sit as a superscript next to the dropdown. Hover shows "Auto-assigned May 23" or "Manually set May 25".

3. **Manual override clears auto flag** — When the user changes the dropdown, `cadence_auto_assigned` flips to `"no"` and the timestamp updates. The tooltip text changes to "Manually set [date]". There's no way to re-enable auto-assignment from the UI (Greg didn't ask for it).

## SQLite Migration

```sql
ALTER TABLE leads ADD COLUMN cadence_type VARCHAR DEFAULT 'cold';
ALTER TABLE leads ADD COLUMN cadence_auto_assigned VARCHAR DEFAULT 'yes';
ALTER TABLE leads ADD COLUMN cadence_updated_at TIMESTAMP;
```

All existing leads get `cadence_type='cold'` and `cadence_auto_assigned='yes'` with null timestamp (tooltip shows just "Auto-assigned" without a date).

## Edge Cases

- **Lead created via CSV import** — gets `cadence_type='cold'` (CSV source doesn't match any mapping rule). Auto-assigned.
- **Lead created via form** — matches `form` → `inbound`. Auto-assigned.
- **Lead stage changes** — cadence is NOT re-evaluated on stage change. Only set at creation. Manual overrides stay manual.
- **Empty cadence_type** — the frontend defaults to `'cold'` via `l.cadence_type || 'cold'`, so null values render as "Cold Outreach".
