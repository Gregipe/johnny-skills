# The June 13-14 DeepSeek Key Loss Incident

## What happened

1. Greg placed the new DeepSeek API key (`sk-...cf85`) in `/opt/ara/.env` on June 11
2. On June 13 at 15:15 IST, Johnny created a **new** `/opt/ara/.env` via `write_file`, containing only Google OAuth credentials. This silently overwrote the existing file that held the DeepSeek key.
3. The running server kept the old environment (loaded at process start) — things worked until the next restart
4. At ~19:45 IST, Johnny deployed code changes via SCP and restarted the server. The systemd service loaded the new `/opt/ara/.env` (no DEEPSEEK_API_KEY), fell back to `/root/.hermes/.env` (old deprecated key `sk-...c84f` that expired/was revoked)
5. All DeepSeek calls started returning 401 at ~01:10 AM June 14
6. **Compounding:** Johnny also SCP'd a stale monolithic local copy of `server.py` that was completely different from the modular production codebase — nuking model routing, imports, and the entire application architecture

## Root causes

1. **`write_file` on env files** — always overwrites, never appends
2. **No pre-check** — didn't read `/opt/ara/.env` before writing
3. **SCP deployment** — bypassed git, overwrote the wrong codebase
4. **Stale local copy** — hadn't pulled from origin before developing

## What changed to prevent this

- `deploy.sh` now has a diff-size guard (>1000 lines → warning)
- `deploy.sh` now runs LLM smoke test after restart (401 → abort)
- Cron health watchdog checks DeepSeek every 15 min
- This skill documents the "never overwrite .env" rule
- Local repo synced to origin/main before any development

## Detection signals

If this happens again:
- `journalctl | grep 401` — DeepSeek auth failures after deploy
- `/opt/ara/.env` mtime is newer than expected
- `grep DEEPSEEK_API_KEY /opt/ara/.env` returns nothing
- The file was overwritten with only partial content
