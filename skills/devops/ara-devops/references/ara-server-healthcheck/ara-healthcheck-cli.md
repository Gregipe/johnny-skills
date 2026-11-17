# ara-healthcheck CLI Tool

Location: `/Users/greg/bin/ara-healthcheck`
Shebang: `#!/usr/bin/env python3`
Type: Standalone Python script (no Hermes dependency)

## Invocation

```bash
ara-healthcheck          # if PATH includes ~/bin (it does — added in .zshrc)
~/bin/ara-healthcheck    # full path
```

## What It Checks (40 checks)

1. Server health: Landing (200), Dashboard (200)
2. UI Pages (6): Landing, Dashboard, Threads, Cadence, Induction, WhatsApp Link
3. Core API Reads (15): Tenants, Deals, Deal Stats, Activities, Insights, Insight Stats, Learning Stats, Actions, Action Stats, WhatsApp Status, Threads, Agent Suggestions, Knowledge, Skills, Cadence Config
4. Lead CRUD: Create → GET → Search → PATCH → Duplicate Check
5. Deal CRUD: Create → GET → PATCH → Attach Lead
6. Chat: Create Thread → Ava Responds → Messages Stored (thread + agent/chat endpoint)
7. Cadence: Preview endpoint returns data
8. Cleanup: Delete deal → bulk delete healthcheck leads → verify lead count restored

## Cleanup Guarantee

All test artifacts use `[HEALTHCHECK]` prefix. The script:
1. Deletes the test deal (detaches leads via API)
2. Searches for any remaining `[HEALTHCHECK]` leads
3. Bulk-deletes them via `POST /api/leads/bulk-delete`
4. Verifies lead count matches pre-test baseline

## Dependencies

- `curl` (macOS built-in)
- `python3` (stdlib only — json, subprocess, sys, time)
