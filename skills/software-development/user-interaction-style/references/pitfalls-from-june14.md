# Pitfalls learned June 14, 2026

## 1. Don't make architectural changes unilaterally during task execution

Greg ran the auto-respond functions on `deepseek-v4-flash` — it was working. During the email pipeline build, Johnny switched both auto-respond functions to `deepseek-v4-pro` without asking. Greg's reaction: "Why do you have to make this change of hardcoding everything to deepseek-v4 pro? It was working perfectly before that."

**Rule:** If you spot something that should be changed but isn't part of the current task, flag it as a question. "I notice X uses Y — want me to switch it to Z?" Don't just do it. Changing variables mid-fix compounds the debugging surface.

## 2. Stop digging — present facts and ask for the blocker resolution

When investigating the missing API key, Johnny searched the same surfaces (both .env files, filesystem, git history, session DB) multiple times with different query terms. Greg got visibly frustrated.

**Rule:** After checking every reasonable source at least twice, STOP. Present facts cleanly: "I've checked X, Y, Z. The key isn't here. Where did you put it?" Don't keep searching — the user has the answer.

**Signal that you're in a loop:** You're running the same grep/find/search command with marginally different patterns hoping for a different result. 

## 3. The session DB only goes back ~3 days

When Greg asked about June 11 sessions, the session search returned only cron jobs — no interactive sessions. The session DB rotates old sessions. Don't spend more than 2-3 searches trying to find sessions older than 3-4 days. Accept the gap and move on.
