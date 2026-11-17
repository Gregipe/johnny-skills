# Outreach Central Page Layout (May 2026)

## Canonical Page Structure

```
┌────────────────── Sidebar (240px) ──────────────────┐ ┌──────── Main Content ─────────┐
│ AR / Autonomous Revenue Agent v1.0                   │ │ Outreach Central              │
│ Main: Home, Leads, Deals, Activities                 │ │ Design intelligent outreach…  │
│ Intelligence: Actions, Outreach Central              │ │ [Reset to Default] [Publish]  │
│ Learning: Knowledge Base, Induction, Learnings       │ │                              │
│ Configuration: Integrations, Threads                 │ │ LEAD → CADENCE MAPPING       │
│                                                      │ │ Reachout + Inbound → Inbound  │
│                                                      │ │ Reachout + Outbound → Cold    │
│ G Greg / Business Lead · Hunar.ai                    │ │ Dormant / Churned → Nurture  │
└──────────────────────────────────────────────────────┘ │ Booked / Won → Out of scope   │
                                                         │                              │
                                                         │ OUTREACH TEMPLATE (global)   │
                                                         │ ✎ Open Builder               │
                                                         │ [Objective] [Brand] [Sector] │
                                                         │ [Security] [WhatsApp] [Email]│
                                                         │ [Call] [Sequence] ← chips    │
                                                         │                              │
                                                         │ CONVERSATIONAL PLAYBOOK      │
                                                         │ ✎ Configure                  │
                                                         │ [Engaged] [Meeting...]       │
                                                         │ [Scheduled] [Completed]      │
                                                         │ [Closed] ← stage pills       │
                                                         │                              │
                                                         │ [🎯 Outbound] [🔥 Inbound]   │
                                                         │ [🌱 Nurture] ← template cards│
                                                         │                              │
                                                         │ OBJECTIVE                    │
                                                         │ ✎ Edit                      │
                                                         │ [Objective text preview]     │
                                                         │                              │
                                                         │ ┌─── 50/50 Split ──────────┐│
                                                         │ │ STEPS     │ PREVIEW      ││
                                                         │ │ ⠿ 1 💬   │ [Step desc]   ││
                                                         │ │ ...    │ CONDITIONS   ││
                                                         │ │ + Add     │ Reachout  ☑  ││
                                                         │ └──────────┴──────────────┘│
                                                         └──────────────────────────────┘
```

## Key Rules

1. **Global tiles always at top** — OUTREACH TEMPLATE and CONVERSATIONAL PLAYBOOK render first, above template cards and per-template sections
2. **Template cards in middle** — Outbound/Inbound/Nurture selection below global tiles
3. **Objective per-template** — Below template cards, above cadence steps
4. **Cadence steps + conditions** — Same 50/50 split as before
5. **Promised/planned** — All tiles are clickable (no dead cards)

## Migration Pattern: Per-Template → Global

When a UI feature needs to move from per-template (set individually for cold/inbound/nurture) to global (shared across all templates):

1. Create a JS variable at page level (e.g., `var globalPromptParts = null`)
2. Add a `migrateToGlobal*()` function that copies from the first template's data on page load
3. Strip migrated data from `TEMPLATES` objects (keep only per-template fields)
4. Update all read paths to check the global variable first
5. Update all write paths to write to the global variable
6. Update the Prompt Builder (remove any tabs that are now per-template)
7. Add a per-template tile on the main page for fields that differ per template
