# Cron Delivery Failure — Diagnostic Workflow

When a user says "I didn't get the briefing" but the cron job reports `last_status: ok`, follow this diagnostic chain.

## Step 1: Confirm the Cron Fired

```python
cronjob(action='list')
# Check: last_run_at, last_status, last_delivery_error
```

If `last_status: ok` and `last_run_at` is recent, the agent ran. Move to Step 2.

## Step 2: Check the Gateway Is Running and Connected

```bash
hermes gateway status
# → Shows PID, platform states

ps aux | grep 'gateway run'
# → Confirm the process is alive

cat ~/.hermes/profiles/<profile>/gateway_state.json
# → Check active_platforms — does the target platform appear?
```

**Expected:** Both Telegram and Discord (or whatever platforms are configured) should show `"state": "connected"`.

**If the platform is missing** from active_platforms, the delivery failed because there was no connected platform to deliver to.

## Step 3: Check the Channel Directory

```python
send_message(action='list')
# → Shows all available delivery targets
```

**Expected:** The target channel (e.g. `discord:#morning-briefing`) appears in the list.

**If the array is empty** (e.g. `discord: []`), the platform is not connected or has never successfully populated its channel list. The cron delivery target resolves to nothing.

## Step 4: Check Gateway Logs Around the Cron Fire Time

```bash
# Gateway log — look for connect/disconnect events, delivery attempts
grep -i "discord.*connect\|platform.*discord\|deliver" <profile>/logs/gateway.log | tail -30

# Error log — look for DNS, auth, or connection failures
grep -n "error\|fail\|dns\|Unauthorized" <profile>/logs/gateway.error.log | tail -20
```

**Common findings:**
- `ClientConnectorDNSError: Cannot connect to host gateway-us-east1-b.discord.gg:443` — DNS resolution intermittent
- `No bot token configured` — Credential not being read (check profile `.env` vs main `.env`)
- `Unauthorized user: USER_ID (USERNAME) on discord` — Allowlist env var missing
- Discord reconnecting repeatedly — Network instability on the host

## Step 5: Check Cron Output (If Available)

```bash
ls ~/.hermes/cron/output/
```

Cron output files may contain delivery error details not surfaced in `cronjob(list)`.

## Step 6: Test Delivery Directly

```python
# Send a test message to the same target
send_message(target='discord:#morning-briefing', message='Test ping — checking delivery pipeline')
```

If this also fails, the issue is in the delivery pipeline (platform disconnected, channel not found), not the cron job.

## Root Cause Summary (From This Session, May 17, 2026)

| Symptom | What We Found | Fix |
|---------|---------------|-----|
| `last_status: ok` but nothing delivered | Discord platform dropped offline due to DNS issues; channel directory showed `discord: []` | Fix the Discord gateway connection (DNS, token, network) or redirect to Telegram |
| `last_delivery_error: null` | Cron system only tracks agent completion, not delivery confirmation | A known design gap — verify delivery separately |
| Discord disconnecting repeatedly | `nodename nor servname provided, or not known` DNS errors on the Mac | Check network/DNS configuration; may be intermittent |
