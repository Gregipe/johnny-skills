# 35-Message Firehose Incident (June 15, 2026)

## Root Cause Chain

1. Prashant Rai created with `stage = "engaged"` via dashboard
2. `_check_silence_resume()` matched him immediately:
   - Stage filter: `Lead.stage.in_(["engaged", "qualified"])` — matched
   - Conversations: new lead, zero conversations — matched
   - Lead age: NO age gate existed — matched
3. Created follow-up `scheduled_at = now + timedelta(hours=1)` (1 hour in future)
4. IST timezone bug made `scheduled_at` string-comparison pass: `"14:08" <= "18:50"` → TRUE
5. Same tick: follow-up fired immediately → marked `completed`
6. Next tick (30s later): no pending follow-up (previous completed) → creates another
7. Loop × 35 times → 35 outbound messages in 5 minutes

## Contributing Factors

| Factor | Detail |
|--------|--------|
| Silent TypeError | `utcnow()` (aware) vs naive `scheduled_at` → `except Exception:` swallowed it |
| IST adjustment | `now + 5.5h` made UTC dates appear as IST strings — future dates looked past-due |
| No rate-limit | `_check_silence_resume()` ran every 30s tick |
| No age gate | Brand-new leads (zero convos) matched the silence query |
| Same-tick fire | Create in tick → fire in same tick → no pending guard survives |

## Fixes Applied

| Fix | Location |
|-----|----------|
| Rate-limit: once per hour (timestamp file guard) | `_check_silence_resume()` |
| Lead age gate: `created_at <= now - 7 days` | Silence query |
| UTC normalization: store UTC, compare UTC | All ScheduledAction creation + scheduler |
| Zero auto-cadence: no auto-schedule on create/import | `create_lead`, `upload_csv` |
| `except Exception:` replaced with proper logging | `_run_scheduler()` |

## Prevention Rules

1. Any follow-up engine within the 30s scheduler tick MUST be rate-limited
2. Any "silence" check MUST exclude leads younger than the silence threshold
3. Never create-and-fire in the same tick without a durable pending guard
4. `except Exception:` in scheduled jobs must log the actual error, not swallow it
5. Date comparisons must use the same timezone convention on both sides
