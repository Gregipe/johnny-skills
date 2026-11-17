# Systematic Pattern Audit — "Grep, Fix All, Verify Zero"

## When This Matters

Greg's signal: "this [X] thing either has not been coded in very well or generically
enough or you've just missed a lot of places where it's still calling [Y]."

This means: you've been patching individual occurrences instead of auditing ALL
occurrences at once. He expects you to find every instance, fix them all, and
verify none remain — in one pass.

## The Pattern

### 1. GREP — Find every occurrence

```bash
grep -n "PATTERN" file.py
```

For ARA on remote server:
```bash
ssh root@46.224.132.99 'grep -n "PATTERN" /opt/ara/server.py'
```

Categorize the results into groups:
- **Already correct** — leave alone
- **Wrong, needs fixing** — these are your targets
- **Ambiguous** — investigate further

### 2. GROUP — Plan the fix

Don't fix them one at a time. Group by:
- Same fix applied uniformly → use `replace_all=True` or a Python script
- Different fix per occurrence → batch by pattern, use targeted `patch()` calls
- Need context → read surrounding lines for each

### 3. FIX — Apply systematically

Prefer order of efficiency:
1. `patch()` with `replace_all=True` — when the pattern is uniform
2. Python regex script (`write_file` → `scp` → `ssh run`) — when logic is needed
3. Individual `patch()` calls — when each fix is unique

### 4. VERIFY — Zero remaining

After all fixes, re-run the original grep with inverted logic:
```bash
grep -n "PATTERN" file.py  # Should return zero or only correct instances
```

If ANY remain, fix them. Do not deploy with known leaks.

## Real Example: Timezone Leak Audit (June 2026)

Greg: "This UTC to IST timezone thing either has not been coded in very well...
Could you please ensure that every single communication that is fired to the
frontend or received from the frontend from a user is always in tenant_timezone?"

### Step 1 — Grep
```bash
grep -n 'isoformat() + "Z"\|\.strftime\|str(dt)\[:10\]' server.py
```
Found 22+ occurrences in 3 categories:
- 8x `.isoformat() + "Z"` — falsely claimed UTC
- 12x `.strftime()` on naive UTC datetimes
- 2x `str(dt)[:N]` raw string slicing

### Step 2 — Group
| Category | Fix |
|----------|-----|
| `.isoformat() + "Z"` | → `to_ist()` |
| `.strftime()` on naive UTC | → `(dt + IST_OFFSET).strftime()` |
| `str(dt)[:N]` | → `to_ist()[:N]` |
| Hardcoded `+ timedelta(hours=5, minutes=30)` | → `datetime.now(IST_TZ)` |

### Step 3 — Fix
Applied `patch(replace_all=True)` for uniform patterns, Python regex for `.strftime()`.

### Step 4 — Verify
```bash
grep -n 'isoformat() + "Z"' server.py     # → zero
grep -n 'created_at\.strftime' server.py  # → zero
grep -n 'str(d\.created_at)\[:' server.py  # → zero
```
All 22+ leaks fixed in one pass. Deployed. Reminders now show "Jun 16, 09:00 AM IST" instead of "2026-06-16 03:30".

## The Anti-Pattern

❌ "I see one leak, I fix one leak. Greg spots another. I fix that. Then another..."
✅ "I find ALL leaks via grep, fix ALL at once, verify zero remain, deploy once."

The anti-pattern is what triggered Greg's frustration. The systematic approach is
what he expects.
