# Agent Context Injection — Wiring Data Into Ava's Awareness

## The Problem

Settings in the Settings tab are stored in the DB, but Ava may not know about them. The gap: she reads from her system prompt (injected at dispatch time) and from tools she calls — not directly from the DB. If a field exists in the database but is never wired into either injection path, Ava will truthfully answer "I don't have that information."

## Systematic Visibility Audit

When Greg says "what else doesn't she see?" — this is the protocol to follow.

### Phase 1: Map the DB Schema

Get the full table/column listing:

```python
from sqlalchemy import create_engine, inspect
engine = create_engine('sqlite:///ara.db')
inspector = inspect(engine)
for table_name in inspector.get_table_names():
    cols = inspector.get_columns(table_name)
    print(f'\n=== {table_name} ===')
    for c in cols:
        print(f'  {c["name"]} ({c["type"]})')
```

### Phase 2: Map Current Agent Visibility

Three categories of data reach Ava:

**Category A — System Prompt Context (always-on):**
- `_get_agent_context()` output: `{agent_name, owner_name, company, owner_phone, induction_completed, induction_score}`
- `## Context` section: current time, owner WhatsApp, induction status, email integration, pending action count
- System prompt static text: tone, rules, tool descriptions
- Live-dispatch data: lead list, skills context, document context, WhatsApp status

**Category B — Tool-Based (on-demand):**
- `get_system_map` → UI locations, cadence configs, tenant_info (segments, industry, induction)
- `get_cadence_config` → single template detail
- `get_action_items` → pending/open action items
- `search_leads`, `search_deals` → CRM data
- `read_logs`, `debug_schedule` → diagnostic data

**Category C — Invisible (only in DB, never reaches Ava):**
Everything else in the DB that's not covered by A or B.

### Phase 3: Cross-Reference and Identify Gaps

For each table in the DB, check against A and B:

| Table | Fields in Context? | Fields via Tool? | Gap |
|-------|-------------------|------------------|-----|
| `tenants` | name, owner_phone, induction status | segments, industry via get_system_map | ✅ mostly covered |
| `users` | name, phone | ❌ no tool | ❌ other users invisible |
| `agents` | agent_name | ❌ personality_tone, avatar not surfaced | minor |
| `integration_config` | email status (count) | ❌ no tool for detail | minor |
| `skills` | 133 skills in context | ❌ add_skill writes, no read-tool | ✅ covered by skills_context |
| `action_items` | count | get_action_items tool | ✅ covered |

### Phase 4: Fix Strategy

For each gap, decide:

| Criteria | Fix | Example |
|----------|-----|---------|
| Small, always relevant | Path A — add to `_get_agent_context()` + `## Context` section | owner_phone, induction status |
| Live/queries/conditional | Path B — new tool or extend existing | get_action_items, tenant_info in get_system_map |
| Both paths | Context for quick awareness + tool for deep query | Induction status in both context AND get_system_map |

**Order of changes:**
1. Update `_get_agent_context()` with new fields
2. Update the `## Context` section in the system prompt builder (line ~4594 in server.py)
3. For tool-based: add handler in `execute_tool()`, add to `AGENT_TOOL_SCHEMA`, add to read-only tools list, add example
4. Update the System Awareness section in the system prompt to describe the new tool
5. Restart server and verify

## Two Injection Paths

### Path A: System Prompt Context (Always-On)

For data Ava should **always know** — like the owner's name, phone, company, and current time. Injected at dispatch time, no tool call needed.

**Canonical injection point:** `_get_agent_context()` function in server.py.

**Current return shape (June 2026):**
```python
return {
    "agent_name": agent_name,
    "owner_name": owner_name,
    "company": company,
    "owner_phone": owner_phone,
    "induction_completed": induction_completed,
    "induction_score": induction_score,
}
```

**Display location** (system prompt line ~4610 in server.py):
```
## Context
Current time: Sunday, May 31, 2026 at 10:15 PM IST (UTC+5:30)
Owner WhatsApp: 919582549236
Indication: ⚠️ Not yet completed | Score: 75/100
Email integration: Connected
Pending action items: 0
```

**Use when:** The data is small (a few fields), always relevant, and the agent should never have to "look it up."

### Path B: Tool-Based (On-Demand)

For data that's large, queried conditionally, or changes at runtime. Expose via a tool Ava can call when needed.

**Use when:** The data is complex (multi-object), varies by lead/cadence, or would bloat the system prompt if always included.

### Choosing Between Paths

| Factor | Path A (Context) | Path B (Tool) |
|--------|-----------------|---------------|
| Data size | 1-5 fields | Any size |
| Always relevant? | Yes | Only when asked |
| Changes frequency | Rarely (tenant settings) | Per-query (live configs) |
| Token cost | Paid every turn | Paid only when called |
| Agent knows it? | Always, without thinking | Must learn to call tool |

**Rule of thumb:** If it's as fundamental as the owner's name, inject it. If it's system state or query results, use a tool. Do BOTH for data that benefits from quick awareness AND deep querying.

## Case Study: June 2026 Full Audit

After Greg asked "what else does she not see?" following the owner_phone fix, the full audit revealed 4 gaps:

### Gap 1: Induction Status
- **DB:** `tenants.induction_completed = 0`, `tenants.induction_score = 75.0`
- **Fix:** Path A — added to `_get_agent_context()` and `## Context` section
- **Also Path B** — added to `get_system_map` response

### Gap 2: Email Integration Status
- **DB:** `integration_config` table, `email-gmail: enabled=1`
- **Fix:** Path A — live query in the system prompt builder, added to `## Context` section
- Same pattern as WhatsApp status but simpler (DB check vs ws status_sync)

### Gap 3: Pending Action Items
- **DB:** `action_items` table — 4 items (all resolved), but the agent creates them and can't query them
- **Fix:** Path B — new `get_action_items` read-only tool, added to `AGENT_TOOL_SCHEMA`, System Awareness section, examples, and read-only tools list
- Also includes a count line in the `## Context` section so Ava always knows there are pending items

### Gap 4: Tenant Config (Segments + Industry)
- **DB:** `tenants.config` JSON — industry, segment definitions with keywords and company patterns
- **Fix:** Path B — extended `get_system_map` to return `tenant_info` block with industry, segments, induction data
- Not added to `## Context` because segment definitions are large (would bloat every turn)

## Audit Checklist

When wiring a new data source into Ava's awareness:

1. **Map the DB** — what tables/columns hold the data?
2. **Check Path A:** Should Ava always know this without asking?
   - If yes, add to `_get_agent_context()` and add a line in the `## Context` section
   - Keep context lines concise — one line per field
3. **Check Path B:** Should Ava be able to look this up on demand?
   - If yes, add a tool handler in `execute_tool()` or extend an existing tool
   - Add the tool description to `AGENT_TOOL_SCHEMA` (with correct numbering)
   - Add an example `[TOOL_CALL:` below the definitions
   - Add to the read-only tools list if applicable
   - Update the System Awareness section if applicable
4. **Verify by testing** — send Ava a message asking for that information

## Integration Points Reference

| What to update | Where in server.py | Purpose |
|----------------|-------------------|---------|
| `_get_agent_context()` | ~line 6192 | Always-on context fields |
| `## Context` section | ~line 4610 | Display context to Ava every turn |
| `execute_tool()` handler | ~line 3141 | Tool dispatch |
| `AGENT_TOOL_SCHEMA` string | ~line 4160+ | Tool descriptions + examples |
| System Awareness prompt section | ~line 4163 | Tool usage guidance |
| Read-only tools list | ~line 4456 | Confirmation gate exemption |
| `get_system_map` | ~line 3990 | Extend with new data blocks |

## Pitfalls

- **Don't assume the agent can read the DB** — Ava has no direct DB access. Everything must flow through her system prompt or tools.
- **The `_get_agent_context()` function is the single source of truth for always-on context.** When you add to it, verify every dispatch point (agent_chat, WhatsApp auto-responder, webhook handlers).
- **Two targets** — The Settings tab stores data (`PUT`), and the agent context reads it (`_get_agent_context()`) at dispatch time. Writing only the PUT handler leaves the gap.
- **When adding to the `## Context` section**, keep it concise — one line per field. The context section is read every turn.
- **Renumbering tools in AGENT_TOOL_SCHEMA** — When adding a tool between existing numbered tools, you must renumber every tool below it. Use `patch` on each `NN. tool_name` line individually.
- **Add to BOTH the tool description section AND the examples section** — Ava scans the examples for usage patterns. A tool described but not exemplified is less likely to be called.
- **Dual injection for high-importance data** — For data the agent should both "always know" and "be able to query deeply" (like induction status), use both Path A and Path B. Context for instant awareness, tool for detailed inspection.
- **Context field ordering matters** — Group related fields together (Owner fields, Integration status, System metrics) so the agent can scan them efficiently.
