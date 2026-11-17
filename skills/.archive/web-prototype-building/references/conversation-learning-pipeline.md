# Conversation Learning Extraction Pipeline

For AI agents that have conversations and should learn from them: a daily cron that scans agent chat messages, extracts objection patterns, messaging wins, and engagement signals via LLM analysis, and writes structured learnings to a skills table.

## Architecture

```
agent's conversations (last 24h)
         │
         ▼
extract_conversation_learnings.py
         │
         ├── Groups messages by thread/lead
         ├── Calls LLM with compact summaries
         ├── Parses structured JSON: objections[], wins[], engagement_signals[]
         └── Writes to skills table
                 │
                 ▼
         prefill templates read skills table
         → Prompt Builder sections auto-update
```

## Implementation (Python)

```python
import sqlite3, json, logging
from datetime import datetime, timedelta, timezone

LOOKBACK_HOURS = 24

def get_recent_conversations():
    """Get agent chat messages from the last 24h, grouped by thread."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    conn = sqlite3.connect("ara.db")
    conn.row_factory = sqlite3.Row
    
    rows = conn.execute("""
        SELECT m.role, m.content, m.created_at, t.lead_id, t.title
        FROM agent_chat_messages m
        JOIN chat_threads t ON m.thread_id = t.id
        WHERE m.created_at >= ?
        ORDER BY t.id, m.created_at
    """, (cutoff,)).fetchall()
    conn.close()
    
    threads = {}
    for r in rows:
        tid = r["title"] or r["lead_id"] or "unknown"
        threads.setdefault(tid, []).append({
            "role": r["role"], "content": r["content"], "time": str(r["created_at"])
        })
    return threads


def extract_learnings(threads):
    """Call LLM to extract patterns from conversation threads."""
    if not threads:
        return {"objections": [], "wins": [], "engagement_signals": []}
    
    thread_summaries = []
    for tid, msgs in threads.items():
        parts = [f"--- {tid} ---"]
        for m in msgs:
            role_label = "LEAD" if m["role"] == "user" else "AVA"
            parts.append(f"{role_label}: {m['content'][:200]}")
        thread_summaries.append("\n".join(parts))
    
    prompt = f"""Analyze these AI SDR conversations. Extract structured learnings:
{chr(10).join(thread_summaries)[:8000]}

Return JSON:
{{
  "objections": [{{"topic": "...", "how_handled": "...", "effective": true/false}}],
  "wins": [{{"pattern": "...", "why_effective": "..."}}],
  "engagement_signals": [{{"signal": "...", "segment": "..."}}],
  "summary": "One-line takeaway"
}}"""
    
    response = call_llm([
        {"role": "system", "content": "You analyze AI SDR conversations and return structured JSON."},
        {"role": "user", "content": prompt}
    ], temperature=0.3)
    
    # Parse JSON from response, stripping markdown code blocks
    text = response.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    return json.loads(text)
```

## Skill Keys Written

| Category | Key Pattern | Source |
|----------|-------------|--------|
| `objection_pattern` | `objection_{topic}` | Extracted objections with handling |
| `messaging_win` | `messaging_win_{date}_{n}` | What worked, why |
| `segment_signal` | `engagement_pattern_{date}` | Engagement trends per segment |
| `learning_summary` | `daily_summary_{date}` | One-line takeaway |

## Scheduling via Cron

```bash
# Daily at 6AM IST — script-based, no LLM agent overhead
hermes cron create \
  --name "Conversation Learning" \
  --schedule "0 6 * * *" \
  --script extract_conversation_learnings.py \
  --deliver local
```

The `--deliver local` means results are logged but not messaged. The cron runs with `no_agent=True` (script-only mode) — no LLM overhead for the scheduler itself. The script calls the LLM internally for extraction.

## Requirements

- `agent_chat_messages` and `chat_threads` tables with role, content, thread_id, created_at
- `skills` table with columns: tenant_id, category, key, value, created_at
- `call_llm()` function available (from induction_engine or similar)
- Needs `DEEPSEEK_API_KEY` or equivalent in environment

## Pitfalls

- **Idempotency:** The cron writes NEW skill rows each time — it doesn't update existing ones. Old keys accumulate. Optionally clean up old daily_summary keys older than 30 days.
- **Empty conversations:** If there's no activity in 24h, the cron exits early. Log as info, not warning.
- **LLM extraction failure:** The JSON parsing needs fallback handling (see `prefill_generator.py` in ARA for patterns).
- **Token limits:** Keep the prompt under 8000 chars. Truncate long conversations, don't send everything.
- **Thread grouping:** Messages must be grouped by thread to give the LLM conversational context rather than isolated messages.
