---
name: cron-daily-briefing
description: "Create daily research/curation cron jobs with structured briefing format — 3-panel layout (India startup scene, global AI, goal-specific items), quick-scan-with-implications, delivery to Discord/Telegram."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [cron, briefing, daily, research, news, curation, discord, delivery]
---

# Cron Daily Briefing

Class-level skill for creating daily briefing cron jobs that research, curate, and deliver structured news briefings. Used for morning briefings, evening recaps, industry monitoring, or any recurring research+delivery pattern.

## User's Preferred Format

Based on Greg's explicit instructions, the briefing uses this structure (plain
text — renders cleanly in Discord and WhatsApp self-chat):

```
━━━━━━━━━━━━━━━━━━━━━━
🌅 MORNING BRIEFING — Monday, May 18
━━━━━━━━━━━━━━━━━━━━━━

🇮🇳 INDIA STARTUP & AI SCENE
• [Brief headline] — [2-3 line summary including what it means. Link]
• [Next item] — ...

🤖 GLOBAL AI DEVELOPMENTS
• [Headline] — [2-3 line summary including implication. Link]
• [Next item] — ...

🎯 FOR YOUR GOALS
• [Item relevant to LinkedIn/content strategy] — ...
• [Item relevant to starting a company] — ...
• [Other relevant news] — ...

━━━━━━━━━━━━━━━━━━━━━━
Produced by Johnny — Chief of Staff
```

### Format Rules (embedded from user preference)

- **Quick scan with links** — 5-8 items per section, each with a URL and 2-3 lines explaining why it matters
- **Implications over summaries** — Don't just recap news. Tell the reader why they should care
- **No markdown formatting** — Discord strips most markdown. Use plain text, emoji dividers, plain URLs
- **3 sections always** — India startup (section 1), Global AI (section 2), For Your Goals (section 3)
- **7 days a week** — Never skip weekends
- **English only**

## Cron Setup Pattern

```bash
# Create the cron
cronjob(
    action='create',
    name='morning-briefing',
    schedule='30 7 * * *',    # Cron expression (system timezone — verify with `date`)
    deliver='discord:#morning-briefing',
    enabled_toolsets=['web', 'file'],   # Restrict to needed tools — save tokens
    prompt='''[See prompt template below]'''
)
```

### Delivery Pipeline Verification — Do This IMMEDIATELY After Creating

**Critical:** Before the first scheduled fire, verify the delivery pipeline works. A cron job can report `last_status: ok` while silently delivering nowhere.

```python
# 1. Check the target platform is connected
grep "Platform.*discord\|telegram.*connected\|discord.*Connected as" <profile>/logs/gateway.log | tail -5

# 2. Check the channel directory has targets
send_message(action='list')
# → If the target platform/channel is missing from the list, fix the platform first

# 3. Check gateway state for active platforms
cat ~/.hermes/profiles/<profile>/gateway_state.json | grep active_platforms

# 4. Check for delivery errors in cron job output
ls ~/.hermes/cron/output/ | grep <job_id_prefix>
```

**5. Test-fire, then read the authoritative record.** After creating OR changing a
job's `deliver` target, fire it once (`cronjob(action='run', ...)` with a run
prompt that marks the output as a test) and check
`sqlite3 <profile>/cron/executions.db "SELECT status, delivery_outcome, error FROM executions WHERE job_id='<id>' ORDER BY claimed_at DESC LIMIT 1"`.
Only `delivery_outcome='delivered'` counts; a `failed` outcome names the reason
(e.g. `no delivery target resolved for deliver=whatsapp`). The runner's own
completion message is not proof of delivery.

**Common failure modes detected by this checklist:**
- Platform disconnected (DNS issues, token expired, crashed) → cron output exists but never delivered
- Channel not in directory → delivery target `discord:#morning-briefing` resolves to nothing
- `last_status: ok` but `last_delivery_error: null` → **does NOT mean delivery succeeded**. The cron agent produced output. The delivery layer may have silently dropped it.

For the full diagnostic workflow when delivery fails, see `references/cron-delivery-debugging.md`.

### Toolset Restriction

Always restrict toolsets to just `web` and optionally `file`. The cron job doesn't need terminal access, browser, or other heavy tools. This keeps token costs low and context small.

### Schedule Notes

- The cron runs on **system timezone** (`date` to check; `file /etc/localtime` to see timezone)
- If system is IST (Asia/Kolkata): 7:30 AM IST = `30 7 * * *`
- If system is UTC: 7:30 AM IST = `30 1 * * *` (IST = UTC+5:30)
- For 7 days a week, use `*` for day-of-week in the cron expression

## Prompt Template

The cron prompt must be fully self-contained — the job runs with no user present and cannot ask questions.

```text
You are Johnny, Greg's Chief of Staff. Produce a crisp morning briefing for Greg.

Greg's three goals:
1. Grow LinkedIn from 5K→100K followers (content about AI meets real-world business)
2. Start his own company in India
3. Stay close to family/friends

[Use the format from the "User's Preferred Format" section above]

Research instructions:
1. Use web_search broadly for India startup news — check sources like YourStory, Entrackr, Inc42, Economic Times, Moneycontrol, Business Standard. Focus on AI companies, funding rounds, policy changes, and notable startup moves.
2. Search for global AI developments — frontier models (OpenAI, Anthropic, Google DeepMind, Meta, DeepSeek), AI regulation, enterprise AI adoption, interesting research papers or demos.
3. Search for anything directly relevant to Greg's goals — LinkedIn growth strategies, founder stories from India, business opportunities in AI/voice AI space.
4. Include actual URLs for each item so Greg can click through.
5. Keep it tight — no fluff. Each item should tell Greg why he should care.

Important: Do NOT ask any questions or request clarification. The user will not see this message until delivery. Just research and write the briefing.
```

## Adding X/Twitter Search

If `xurl` is installed and authenticated, extend the prompt to also search X:

```text
6. Also use `xurl search "your_query" -n 5` to search X for real-time takes from accounts like @yourstory, @inc42, @bhash, @techcrunch, and AI thought leaders.
```

Requires `xurl` in PATH. If the cron runs with restricted toolsets, `xurl` lives outside the Hermes tool system — call it via the `terminal` tool, which means you need `terminal` in enabled_toolsets too.

## Pitfalls

- **Self-contained prompt is non-negotiable** — The cron job has zero conversational context. Every instruction must be in the prompt. You can't ask follow-up questions.
- **No clarify calls allowed** — If the prompt triggers a `clarify` call, it silently fails. Design prompts that don't need user input.
- **Verify `date` timezone first** — Scheduling "7:30 AM" in a cron when the system is on UTC gives you 7:30 AM UTC, not IST. Always check with `date`.
- **Discord delivery format** — Don't use markdown (bold, italic, code blocks). Discord doesn't render `*italic*` in webhook-like messages. Use emoji, `━━━` separators, and plain URLs.
- **WhatsApp delivery needs an explicit LID target** — bare `deliver='whatsapp'` fails with "no delivery target resolved" (self-chat registers no home channel; Telegram resolves via `TELEGRAM_HOME_CHANNEL`, WhatsApp has no equivalent). Use `deliver='whatsapp:<lid>'` — the live morning-briefing uses `whatsapp:37039848317007@lid`. Target format and verification: `hermes-whatsapp-bridge` skill.
- **Don't over-schedule** — A cron that runs every 15 minutes with extensive web_search calls will burn through tokens fast. Daily is usually right for briefings.
- **If the user asks to update the cron** — list first to get the job_id, then update with `cronjob(action='update', job_id=..., ...)`.
- **The first delivery always comes the next scheduled run** — not immediately on creation.
- **`last_status: ok` ≠ delivery succeeded** — The cron agent may have run perfectly and produced output, but if the target platform (Discord, Telegram, etc.) was disconnected at delivery time, the output goes nowhere. The cron system marks `last_status: ok` based on agent completion, not delivery confirmation. `last_delivery_error: null` is also NOT a guarantee — the delivery layer may have silently dropped the message without raising an error.
- **Verify the delivery target before the first fire** — Use `send_message(action='list')` after creating the cron to confirm the target platform+channel actually exist in the channel directory. If the array is empty (e.g. `discord: []`), the cron will produce output that evaporates.
- **Platform DNS issues can break delivery silently** — Intermittent DNS resolution failures (e.g. `nodename nor servname provided, or not known` on Discord's gateway) can cause platform disconnection that you won't notice until the user asks where their briefing went. Monitor gateway error logs for these.

## Related Skills

- **`whatsapp-integration`** — For ARA operational morning briefs that send business metrics (deals, action items) via WhatsApp to the tenant owner from a cron job. See `whatsapp-integration > references/ara-cron-brief-pattern.md` for the full workflow: ARA runs locally on Greg's MacBook (no SSH needed), API fragility patterns (many endpoints 500 even when health is green), SQLite DB fallback queries, sidecar health checks, and the canonical message format. **Key takeaway:** The ARA API is unreliable — always have DB fallback queries ready and prefer `sqlite3 /Users/greg/ara/ara.db` over API calls for action items, tenants, and deals.
