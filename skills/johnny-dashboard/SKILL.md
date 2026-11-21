---
name: johnny-dashboard
description: Regenerate Greg's local CoS dashboard data (/Users/greg/johnny-dashboard/data.json). Use for the daily 7:30 IST refresh and any on-demand refresh of the Today/Tasks/Feed/Goals/Correspondence tabs. NEVER modify index.html or serve.sh.
---

# Johnny Dashboard Refresh

Regenerate `/Users/greg/johnny-dashboard/data.json` (atomic write) for the local CoS dashboard at http://127.0.0.1:8410.

## Procedure (daily 7:30 IST)

1. **Read the current `data.json`** — it is the schema authority. Top-level keys must remain exactly: `presence`, `briefing`, `tasks`, `feed`, `goals`, `correspondence`, `generated_at`.
2. **Live checks before writing:**
   - ARA: `ssh root@46.224.132.99` — `systemctl is-active ara-server ara-tunnel ara-whatsapp-sidecar`, `ss -tlnp | grep 7860`, `cd /opt/ara && git status --short` (uncommitted server.py diff is the #1 voice-breakage cause).
   - Gmail: raw refresh attempt against `https://oauth2.googleapis.com/token` with `state/gmail_token.json` + `state/oauth_client.json` credentials; `invalid_grant` ⇒ inbox still blind.
   - Dashboard server 8410 + bridge 8411: `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8410/`.
3. **Briefing:** ≤4 attention items (approvals/reviews genuinely needing Greg), one-sentence headline, fresh stats. `stats.tasks_due_today` counts ONLY tasks with `group: "today"`.
4. **Tasks:** carry open tasks forward; add new from ARA state, Hunar, Mondelez demo, LinkedIn cadence, thesis work; drop stale. Allowed groups: `today|week|delegated|waiting|goals`. The LinkedIn post task and thesis conversation-logging task live PERMANENTLY in `goals` group with `goal` field matching the goal's key (`LinkedIn`, `Startup`).
5. **Feed:** web_search for genuinely new items (AI, India startups, voice AI, faith). ≤12 items total, real source URLs, every item has `takeaway` and `why` tied to one of Greg's 3 goals (LinkedIn 5K→100K, start a company in India, stay close to family). Drop superseded/stale items.
6. **Goals:** update `progress`, `metric`, `latest_note`; every goal object keeps its `key` field (`LinkedIn`, `Startup`, `Faith`).
7. **Correspondence:** threads stay `sample: true` until Gmail phase 2; update `note` only.
8. **Write atomically:** build `data.json.new` in the same dir, `cp data.json data.json.bak-YYYYMMDD`, `mv data.json.new data.json`. Verify: `python3 -m json.tool data.json > /dev/null` and curl the served file at 8410.
9. **Verify tabs:** index must return 200 and serve the new `generated_at`. `open http://127.0.0.1:8410/` for Greg.
10. **Commit** the dashboard repo (`git add data.json && git commit`). Do NOT touch `index.html` or `serve.sh`.

## Reference
- Greg's goals: LinkedIn 5K→100K followers, start a company in India (thesis-led), stay close to family.
- Hunar.ai pricing: <5K mins ₹4.5, 5K-10K ₹2.5, 50K-1M ₹2.25, 1M+ ₹2/min (₹10/min is WRONG). Case studies: hunar.ai only.
- Feed IDs and task IDs keep incrementing across runs; never reuse a dropped ID.
