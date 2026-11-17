---
name: ara-devops
description: ARA-specific DevOps workflows — QA gates, health checks, sidecar reliability, and dashboard integrity
---

# ARA DevOps

This skill covers ARA-specific deployment and operational workflows. Use the appropriate section for your task.

## QA Gate — Run Before Every Deploy

**When to use:** Before any deploy to production

**Workflow:** Three-layer gate that must all pass:
1. **Syntax check** — `py_compile` catches parse errors
2. **Mypy scoping** — catches used-before-def, name-errors
3. **pytest** — 113+ deterministic regression tests

All three must pass before the server restarts. If any layer fails, the deploy aborts before touching production.

### Shared Utils Pattern

The test suite uses a **shared-utils architecture**: pure functions live in `tests/enforcer_utils.py` and are imported by BOTH the test files AND production code. This means:
- One definition of the logic — tests and production share it
- Any change to the enforcer logic is tested automatically on next `pytest`
- Invalidating the shared utils = test failure. No silent drift.

---

## Server Healthcheck — Post-Restart Verification

**When to use:** After restarting the ARA server

**Workflow:** Full post-restart verification including:
- Server process is running (PID check)
- Health endpoint responds (`/api/health`)
- Database connection works
- WhatsApp sidecar is connected
- Recent logs show no errors

---

## Sidecar Reliability — Port Conflict Prevention

**When to use:** When working with WhatsApp Baileys sidecar or other sidecar services

**Workflow:** 
- Health-check hardening
- Port-conflict prevention
- Graceful degradation when sidecar is unavailable

---

## Dashboard Integrity Gate — Pre- and Post-Deploy Checks

**When to use:** Before and after deploying dashboard changes

**Workflow:**
- Pre-deploy: Verify `dashboard.js` loads correctly
- Post-deploy: Verify no JavaScript errors, all buttons work
- Prevents dashboard.js corruption from blocking deployments

---

## Daily Operational Cron Jobs

> Removed 2026-10-03: Greg stopped ARA and asked for all ARA cron jobs to be cleared. The jobs below no longer exist (daily-whatsapp-brief, ARA Weekly Synthesis, watchdog, learning extraction, wa-queue-drain, LLM health check, error-watcher). The `daily-whatsapp-brief` recipe stays here as the runbook if the job is ever recreated; its WhatsApp send path now belongs to the Hermes gateway (`whatsapp-integration` → `references/hermes-native-whatsapp.md`).

ARA ran several daily cron jobs (Hermes cron scheduler, profile `johnny`). The
`daily-whatsapp-brief` job (id `00fbbc53fd87`, `30 7 * * *`) sends Greg a WhatsApp morning brief
sourced from **production** ARA — see `references/daily-whatsapp-brief.md` for the full run
recipe (prod SSH access, DB table queries, the overdue filter, sidecar `/send` + msgId
verification).

## Related Skills

- `ara-production-deploy` — The actual deploy script
- `whatsapp-integration` — WhatsApp sidecar setup
- `test-first-release` — Release-level test enforcement
- `systematic-change-workflow` — Pre-flight checklist for any change