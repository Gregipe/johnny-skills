# The June 14 Production Nuke — Stale Local Copy Overwrites Modular Codebase

## What happened

1. Production ran commit `18e3c24` — a modular, refactored codebase with `app/config.py`, `app/schemas.py`, `app/dedup.py`, model routing in `agent_chat` (`_chat_model = "deepseek-v4-pro"`), RotatingFileHandler logging, etc.
2. Local `/Users/greg/ara/` was a **stale monolithic copy** — completely different architecture, had diverged from production at some earlier point and nobody noticed.
3. Johnny developed the email pipeline against this stale local copy.
4. At 19:45 IST June 13, SCP'd the local `server.py` to production: `scp /Users/greg/ara/server.py root@46.224.132.99:/opt/ara/server.py`. This didn't add changes — it **replaced the entire file** with a structurally different version.
5. `git diff --stat` showed **4,463 lines changed** — impossible for "adding an email pipeline." Nobody checked.
6. Everything broke: model routing disappeared, imports failed, DeepSeek started returning 401 at 01:10 AM.

## Root causes

1. **No `git pull` before development** — started from stale code
2. **SCP bypassed version control** — replaced instead of patching
3. **No pre-deploy diff** — 2-second `git diff --stat` would have caught 4,463 lines
4. **No post-deploy smoke test** — verified server was "up" (HTTP 200) but didn't test an LLM call

## Detection — suspicious signals

- `git diff --stat` shows >500 lines changed in a single file
- `grep "^from app\\." server.py` returns nothing on production (modular imports are gone)
- Journal loses "Model routing: user_msg_keywords=True/False" messages
- After deploy, LLM calls return 401/errors that weren't there before

## Prevention — what's now in place

- `deploy.sh` diff-size guard: warns if >1000 lines, pauses 5s for Ctrl+C
- `deploy.sh` LLM smoke test: calls DeepSeek after restart, aborts if 401
- Cron health watchdog: alerts every 15min if DeepSeek is down
- `git pull origin main` mandatory before any development work
- This incident documented so the pattern is recognizable
