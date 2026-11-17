# Ava Memory System Architecture (June 2026)

Three-tier memory architecture: skills injection, proactive recall triggers, and auto-save on action completion.

## Problem

Ava had memory tools (`save_memory`, `search_memory`, `add_skill`, `search_knowledge_base`) but:

1. **Skills were invisible**: `add_skill` stored to the `skills` table (category != "memory"), but only `category="memory"` entries were injected into agent_chat context. Every learned pattern was invisible.
2. **Wrong tools in prompt**: The "Learning the User" section told Ava to use `save_learning`/`add_skill` (→ skills table → invisible) instead of `save_memory`/`search_memory` (→ skills table with category="memory" → injected).
3. **No proactive recall**: Ava never called `search_memory` before responding. She only used it if explicitly asked.

## Solution

### 1. Universal Skills Injection

Changed the context injection to load ALL skills (not just category="memory"), grouped by category:

```python
# BEFORE: only category="memory"
_recent_mems = db.query(Skill).filter(
    Skill.tenant_id == tenant_id,
    Skill.category == "memory",
).order_by(Skill.created_at.desc()).limit(20).all()

# AFTER: all skills, grouped by category
_all_skills = db.query(Skill).filter(
    Skill.tenant_id == tenant_id,
).order_by(Skill.created_at.desc()).limit(50).all()

_mem_entries = []
_skill_by_cat = {}
for _s in _all_skills:
    if _s.category == "memory":
        _mem_entries.append(f"• {_s.key}: {_s.value[:200]}")
    else:
        _skill_by_cat.setdefault(_s.category, []).append(f"• {_s.key}: {_s.value[:200]}")

if _mem_entries:
    system_prompt += "\n## Your Memories (persisted across sessions)\n" + "\n".join(_mem_entries)
for _cat, _items in _skill_by_cat.items():
    system_prompt += f"\n## Your Skills / Knowledge: {_cat}\n" + "\n".join(_items[:10])
```

### 2. Prompt Redirect: save_memory not add_skill

Rewrote "Learning the User" section:

```
## Learning the User (your memory is your tools)
You have persistent memory that loads every session.

- Use **save_memory** to record facts that matter across sessions
- Use **search_memory** BEFORE assuming any preference
- Use **update_lead notes** for lead-specific context

TRIGGER RULE: After completing any action, ask: "Did I learn something durable?" 
If yes, call save_memory immediately. Don't announce it — learn quietly.

Before responding to any message referencing a person, company, or deal:
call search_memory to check what you already know.
```

### 3. Proactive Memory Check in Reasoning Preamble

Added MEMORY CHECK step before plan formulation:

```
MEMORY CHECK: Before stating your plan, if the message references a person,
company, or deal, call search_memory(query="[name or company]") to check
what you already know from past sessions. This prevents duplicate work and
lost context. If search_memory returns relevant facts, incorporate them
into your plan.
```

## Verification

Test: "Create a check-in for the PayTM deal tomorrow morning"

1. ✅ Called `search_memory("PayTM")` → found "PayTM deal has Vinay Bhoj as primary contact"
2. ✅ Called `search_deals("PayTM")` → current stage "new"
3. ✅ Called `get_lead_detail("Vinay Bhoj")` → full context with attachment info
4. ✅ Proposed check-in with full context, no duplicate deal creation

## Tool Storage

| Tool | Table | Category | Injected? |
|------|-------|----------|-----------|
| `save_memory` | skills | `memory` | ✅ Yes |
| `search_memory` | skills | `memory` | N/A (read tool) |
| `add_skill` | skills | any (user-specified) | ✅ Yes (after fix) |
| `search_knowledge_base` | skills | any | N/A (read tool) |
| `save_learning` | skills | `learning` | ✅ Yes (after fix) |

## Pitfalls

- **ILIKE on SQLite**: `search_memory` uses SQLAlchemy `.ilike()` which translates to `LOWER(col) LIKE LOWER(pat)` on SQLite. Case-insensitive matching works but can be slow on large tables.
- **Injection size**: 50 skills × 200 chars each = ~10KB. Fits comfortably in the system prompt but monitor for growth.
- **Duplicate keys**: `save_memory` doesn't dedup by key. Multiple entries with the same key create confusion. Consider adding `ON CONFLICT DO UPDATE` for key-based upserts.
