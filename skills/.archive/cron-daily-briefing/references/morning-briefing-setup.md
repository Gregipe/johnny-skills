# Morning Briefing — Setup Reference (May 16, 2026)

## Delivery Status (May 17, 2026 Update)

**❌ Discord delivery is broken.** The cron fires and produces output (`last_status: ok`) but Discord delivery silently fails:

1. Discord gateway has intermittent DNS failures (`ClientConnectorDNSError: Cannot connect to host gateway-us-east1-b.discord.gg:443`)
2. Channel directory shows `discord: []` — no channels registered
3. Gateway state shows only Telegram as active platform

**Until Discord is fixed, consider redirecting to Telegram** (`deliver='telegram:557413154'` or `discord:#morning-briefing` → change the deliver target).

## Cron Job Details
- **Job ID:** 91ce9b0b331f
- **Name:** morning-briefing
- **Schedule:** `30 7 * * *` (7:30 AM IST daily)
- **Delivery:** `discord:#morning-briefing`
- **Toolsets:** `web`, `file`
- **First delivery attempted:** May 17, 2026 at 7:30 AM IST — failed silently

## User Preferences (embedded from conversation)
- **Depth:** Quick scan — 5-8 bullets per section with links and 2-3 lines on implications
- **Frequency:** 7 days a week
- **Time:** 7:30 AM IST
- **Language:** English
- **Sources:** "Credible sources" — YourStory, Entrackr, Inc42, ET, Moneycontrol, Business Standard for India; major tech/ai outlets for global
- **Format:** Discord-friendly plain text (no markdown, emoji dividers, plain URLs)

## Sections (always 3)
1. 🇮🇳 India Startup & AI Scene — India-focused startup/AI news
2. 🤖 Global AI Developments — Frontier models, regulation, adoption
3. 🎯 For Your Goals — Items directly relevant to Greg's 3 goals

## xurl (Twitter/X) Status
`xurl` CLI is installed at `/Users/greg/.local/bin/xurl` but NOT yet authenticated. Greg needs to complete OAuth 2.0 setup:
1. Create app at https://developer.x.com.com
2. Run `xurl auth apps add my-app --client-id ... --client-secret ...`
3. Run `xurl auth oauth2 --app my-app`
