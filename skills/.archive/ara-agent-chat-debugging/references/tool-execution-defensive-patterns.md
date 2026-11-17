# Tool Execution Defensive Patterns (June 2026)

Three server-side enhancements beyond prompt engineering that prevent LLM runaway, persist context, and normalize responses.

## Pattern 1: Notes Persistence on Tool Execution

### Problem
When tools modify a lead's state (stage change, outreach), the LLM's reason/rationale was ephemeral — it appeared in the response text but vanished on page refresh. Future queries couldn't answer "why was this changed."

### Solution
Have the tool execution code append a timestamped note to the Lead's `notes` field whenever a reason is provided.

### Implementation (in `execute_tool()` or the tool function itself)

```python
# Inside update_lead_stage handler, after stage change:
if reason:
    ts = datetime.now(timezone.utc).strftime("%b %d, %H:%M")
    old_stage = lead.stage  # Capture BEFORE change
    note = f"[{ts}] Stage {old_stage} → {new_stage}: {reason}"
    if lead.notes:
        lead.notes += "\n" + note
    else:
        lead.notes = note
```

### Tool Description Update
The tool schema in `AGENT_TOOL_SCHEMA` must instruct the LLM to always provide a reason:

```
update_lead_stage — Move a lead to a new pipeline stage.
Args: {"lead_name": "...", "stage": "...", "reason": "..."}
Always include a 'reason' describing why — it gets saved as a persistent note.
```

### Data Model
- Notes accumulate in `Lead.notes` (free-text column, not a separate table)
- Each entry has format: `[Timestamp] Old → New: free-text reason`
- Can be queried by substring search (no structured query needed for small volumes)
- Existing notes (automated messages like "Initial outreach sent") coexist with human-provided reasons

### Verification
```python
lead = db.query(Lead).filter(Lead.id == lead_id).first()
assert "[Jun 04, 06:30] Stage new → meeting_booked: Had a chat with Rajesh" in lead.notes
```

### Key Design Decisions
| Question | Decision | Rationale |
|----------|----------|-----------|
| Single column vs separate table? | Single `notes` column | Simple, no migration needed, no new model |
| Timestamp format? | `[Mon DD, HH:MM]` | Human-readable, sort alphabetically |
| Append vs replace? | Append (never overwrite) | Preserves full history |
| Only for stage changes? | Start with stage changes | Most common action. Extend to other tools as needed |

### User Preference Embedded
Greg explicitly asked for stage change reasons to be saved as persistent notes. This is now a requirement for the `update_lead_stage` tool.

---

## Pattern 2: Coaching Rate Limiter (Defense-in-Depth, Layer 3)

### The Three-Layer Defense
| Layer | Where | What | Failure Mode |
|-------|-------|------|-------------|
| 1. Sidecar dedup | `index.js` | `forwardedMsgIds + sentMsgIds` check | Sidecar restarts (in-memory sets clear) |
| 2. Server dedup | `server.py` | `forwardedMsgIds` webhook check | Rate limiter hits BEFORE dedup can fire |
| 3. Rate limiter | `server.py` | Max N responses per T seconds per chat | Stops cascade even if both dedups fail |

### Problem
Even with dual dedup (sentMsgIds + forwardedMsgIds), a server restart clears in-memory sets. If the sidecar re-sends old messages on reconnect (common with Baileys), the first 2-3 messages slip through before the dedup re-populates. Without a rate limiter, this produces a cascade of coaching responses.

### Implementation

```python
from collections import defaultdict
from datetime import datetime, timezone

# Module-level rate limiter
_coach_rate_history = defaultdict(list)  # chat_id -> list of datetimes

def _check_coach_rate(chat_id: str, max_count: int = 3, window_seconds: int = 30) -> bool:
    """Returns True if rate limit is exceeded (should BLOCK the response)."""
    now = datetime.now(timezone.utc)
    # Prune older than window
    _coach_rate_history[chat_id] = [
        t for t in _coach_rate_history[chat_id]
        if (now - t).total_seconds() < window_seconds
    ]
    if len(_coach_rate_history[chat_id]) >= max_count:
        return True  # Rate limited — block
    # Record this attempt
    _coach_rate_history[chat_id].append(now)
    return False
```

### Integration Point

Called inside `_handle_owner_coach_whatsapp()` before anything else:

```python
# At the top of the function:
if _check_coach_rate(chat_id):
    logger.warning(f"Rate limited coaching for {chat_id}")
    # Don't fire typing reaction either — just return silently
    return
```

### Parameters
| Param | Value | Rationale |
|-------|-------|-----------|
| `max_count` | 3 | Allows a reconnect burst of 2-3 messages through dedup before rate limiter catches |
| `window_seconds` | 30 | Short enough that a one-time burst doesn't block legitimate messages for long |
| `chat_id` | Per-chat | Prevents one noisy lead from starving another |

### Won't Rate Limit Real Messages
- A human sends 1 message → gets 1 response → resets after 30s
- Only cascading reconnects (3+ messages in 30s without human action) trigger the limiter
- Typical coaching pattern: 1 user message → 1 response → free to send again

### Edge Cases
- **Sidecar reconnect burst:** After a disconnect, Baileys fires `messages.upsert` for all undelivered messages. If dedup misses (in-memory sets cleared on restart), rate limiter catches at the 4th message.
- **Backlogged messages >15s:** The 15-second backlog filter should skip these, but if the filter is bypassed or misconfigured, rate limiter is the safety net.
- **Clean state:** On ARA server restart, `_coach_rate_history` resets. This is fine — a restart should not permanently inhibit coaching. The dedup layers (sidecar) survive restart independently.

---

## Pattern 3: Response Prefix Normalization

### Problem
The response builder in `_handle_owner_coach_whatsapp()` constructs the user-facing message by concatenating `lead_name` and `action_text`. When `action_text` itself already contains a `✅ lead_name:` prefix (because the tool result or canned response already includes it), the result is:

```
✅ Rajesh Sharma: ✅ Rajesh Sharma: Stage: meeting_booked → meeting_booked — Greg spoke with Rajesh
```

### Root Cause
The `action_text` variable was built from the tool's canned response template which includes emoji + name prefix, while the builder prepended its own copy.

### Fix
Strip any leading emoji+name pattern from `action_text` before joining:

```python
import re as _re

# Strip leading "✅ Name:" or "✅ Name —" from action_text to prevent double prefix
action_text = _re.sub(
    r'^[✅📞📧✉️📱]+ [\w\s\-\.]+[:—]\s*',
    '',
    action_text,
    count=1
)

# Now safe to build the response
response = f"✅ {lead_name}: {action_text}"
```

### Key Insight
Always inspect what your template variables actually contain. A variable named `action_text` may already include the prefix you're about to add. The fix is defensive: strip before wrapping.

### When This Pattern Applies
Any time the response is built from concatenated parts where each part could independently have a prefix/emoji/formatting:
- Tool result messages that include lead name
- Canned response templates with emoji prefixes
- Multi-tool responses where each tool's output is joined
