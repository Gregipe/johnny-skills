---
name: conversation-learning-extraction-cron
category: productivity
description: Run, fix, and maintain the daily Ava conversation learning extraction cron job
---

# Conversation Learning Extraction Cron

The daily cron job that scans Ava's conversations, extracts objection patterns, messaging wins, and engagement signals, and writes learnings to the skills table.

## Script Locations

| Role | Path |
|------|------|
| Cron wrapper (Hermes calls this) | /Users/greg/.hermes/profiles/johnny/scripts/daily_conversation_learning.sh |
| Actual extraction logic | /Users/greg/ara/extract_conversation_learnings.py |

## Why a Wrapper

The real script lives in the ARA project dir (/Users/greg/ara/) because it uses:
- `from induction_engine import call_llm` — relative import from the ARA project
- `DB_PATH = "ara.db"` — relative SQLite path

The cron job's `no_agent=true` script field resolves relative to `~/.hermes/profiles/johnny/scripts/`. The wrapper script `cd`s to `/Users/greg/ara/` and runs the real one via `./venv/bin/python`.

## Env Var Loading (Fixed May 2026)

Hermes overrides `HOME` to `/Users/greg/.hermes/profiles/johnny/home` for session isolation, so `~/.hermes/.env` resolves to a nonexistent path.

The script now loads env vars directly in Python before importing `induction_engine`:

```python
from dotenv import load_dotenv
load_dotenv("/Users/greg/.hermes/.env")
from induction_engine import call_llm
```

Critical: `load_dotenv()` MUST be called BEFORE `from induction_engine import call_llm` because `induction_engine.py` reads `DEEPSEEK_API_KEY = os.environ.get(...)` at module level. If loaded after, the key is empty and `call_llm` returns the "temporarily unavailable" error.

## Running Manually

```bash
cd /Users/greg/ara && ./venv/bin/python extract_conversation_learnings.py
```

No env vars needed — the script loads them itself.

## Junk Data Audit (June 2026)

The cron's output goes into two tables: `skills` and `learning_notifications`. Both can accumulate noise:

1. **`learning_notifications`** — 60 rows deleted in June 2026 audit. 47 were `action_failed` retry spam from bugs, 4 were `action_reminder` operational noise, 1 was a test escalation. **Rule:** If the table has more than 20 entries that are `action_failed` or `action_reminder`, the pipeline is generating noise that should be cleaned.

2. **`skills` table** — 66 junk rows deleted (proposition, gtm_learnings, inbound, learned_patterns). These are machine-extracted patterns with zero human review and confidence=0.0. **Rule:** Keep categories that have actual coaching value: coaching_general, objection_pattern, messaging_win, segment_signal, timing_pattern, guardrail/guardrails, learning_summary.

3. **Confidence scoring** — If avg confidence across skills is near 0% (175/177 had confidence=0.0), the promotion pipeline's `_promote_insights_to_skills` function is not carrying confidence from AvaInsight to Skill. The query at line ~7024 uses `func.avg(AvaInsight.confidence)` correctly but the write at line ~7076 may be computing it wrong.

**Cleanup script pattern:**
```sql
DELETE FROM learning_notifications WHERE tenant_id='3e736242';
DELETE FROM skills WHERE tenant_id='3e736242' 
  AND category IN ('proposition', 'gtm_learnings', 'inbound', 'learned_patterns');
```

**Reference:** See `ara-agent-learning-loop/references/junk-data-cleanup-pattern.md` for the full audit.

- **Time**: 7:00 AM IST daily
- **Cron**: `0 7 * * *`
- **Delivery**: no-agent script mode, stdout delivered on exit
