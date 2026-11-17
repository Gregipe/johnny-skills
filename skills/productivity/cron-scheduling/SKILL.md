---
name: cron-scheduling
description: "Use when creating, updating or debugging Hermes cron jobs."
version: 1.0.0
author: Johnny
license: MIT
metadata:
  hermes:
    tags: [cron, scheduling, ist, timezone, reminders]
    category: productivity
---

# Cron Scheduling for Greg

## When to Use

- Greg asks to create, move, pause or remove a scheduled job (briefing, check-in, reminder, flight check, lint)
- A cron misfires, fires at the wrong time, or delivers to the wrong channel

Creating, rescheduling and debugging the cron jobs that talk to Greg (morning briefing, Chief-of-Staff check-ins, reminders, flight checks, wiki lint).

## Hard rules

- **All Greg-facing times are IST.** Convert before writing any schedule field: UTC = IST − 5:30. 8:00 IST = 02:30 UTC (`30 2 * * *`); 9:00 IST = 03:30 UTC (`30 3 * * *`) — NOT `0 3` (that fires 8:30 IST). Do the arithmetic explicitly: the ±30 offset makes off-by-half-hour mistakes invisible until the job fires at the wrong time.
- **Verify after every create/update:** the result echoes `next_run_at` in UTC — convert it back to IST and confirm it equals the intended local time BEFORE telling Greg it's set.
- **List before update — never guess job_id.** Match by job name, then update. Prefer updating an existing job over creating a near-duplicate.
- One-shot reminders: `schedule` = ISO timestamp, omit `repeat` (repeat is an integer count; a string like 'once' fails validation).
- Deliver to Greg via `deliver: origin` (or the chat the job was created from); set `attach_to_session: true` for conversational jobs like the briefing so he can reply to them.
- Anything delivered to Greg stays inside 07:00–22:00 IST. If a computed fire time lands outside, adjust and tell him.

## Pitfalls

- Job prompts run in a fresh session with no chat context — the prompt must be self-contained (exact paths, names, what to check, output format), because the agent's final response IS the delivery.
- After rescheduling, `last_run_at` in the listing still shows the old run — the field that matters is `next_run_at`; don't try to "fix" history.
- Greg revises times minutes after setting them (e.g. 9:00 → 8:00 IST) — apply it as one atomic update to the same job, never a second job.
- For anything that needs web lookups at fire time (flight status, briefings), keep the job's toolset allowance sufficient — a restricted toolset that omits web produces a hollow briefing instead of failing loudly.
