# Diagnostic Tools for Ava (May 2026)

Two read-only diagnostic tools added to help Ava investigate errors without user-facing technical details.

## Tool: `read_logs` (tool #31)

- **Args:** `{"lines": 50, "level": "ERROR"}`
- **Returns:** Last N server log lines from 200-line in-memory ring buffer
- **Level filter:** `ERROR`, `WARNING`, `INFO` — case-insensitive match
- **Handler:** `server.py` — `execute_tool()` at lines ~3750
- **Log buffer:** `LogRingBuffer` class at `server.py` line ~28 (attached to root logger)

### When to use
- Any tool returns an unexpected error — call `read_logs(level="ERROR")` immediately
- Ava gets an "internal backend glitch" message — logs show the actual traceback
- Server crashes on startup — logs show import errors, DB connection failures, or config issues

### How it works
```python
class LogRingBuffer(logging.Handler):
    def __init__(self, capacity=200):
        super().__init__()
        self.capacity = capacity
        self.buffer = []
    def emit(self, record):
        self.buffer.append(self.format(record))
        if len(self.buffer) > self.capacity:
            self.buffer = self.buffer[-self.capacity:]
    def tail(self, n=50, level=None):
        lines = list(self.buffer)
        if level:
            lines = [l for l in lines if f"[{level}]" in l or f" {level} " in l]
        return "\n".join(lines[-n:])
```

Attached to root logger at module level:
```python
_log_ring = LogRingBuffer()
_log_ring.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s", "%H:%M:%S"))
logging.getLogger().addHandler(_log_ring)
```

Buffer survives restarts of the Python process, not across process restarts (obviously).

## Tool: `debug_schedule` (tool #32)

- **Args:** `{"lead_name": "Gregory Ipe"}`
- **Returns JSON object with:**
  - `lead` — lead name
  - `stage` — current stage
  - `cadence_type` — assigned cadence type or "none"
  - `template_published` — boolean, whether the template exists
  - `total_scheduled_would_create` — count of actions that would be created
  - `steps` — array of step summaries ("whatsapp x8 (delay 0h, interval 1h)")
  - `pending_actions` — count of existing pending/firing actions
  - `issues` — array of blocking reasons (empty = ready to go)
  - `ready` — boolean shortcut

### When to use
- `trigger_cadence` returns an error — call debug_schedule to see EXACTLY what's blocking
- Greg asks "why isn't Gregory receiving outreach?" — debug_schedule shows stage, cadence_type, template status
- Before calling trigger_cadence on an existing lead — check if there's a blocking issue first

### Common blocking issues
| Issue | Meaning | Fix |
|-------|---------|-----|
| "No cadence_type assigned" | Lead.cadence_type is null | Auto-assign via update_lead |
| "stage='engaged'" | Lead past the cadence window | Reset stage to 'reached_out' or 'new' |
| "No published template" | Template not published in Cadence Builder | Publish the template first |
| "Template has no steps" | Template exists but no steps defined | Add steps via Cadence Builder |
| "N pending actions exist" | Stale pending actions from previous cycle | Cancel pending + retry |

### Expected behavior
The tool NEVER modifies data. It's a pure read — queries the DB, checks conditions, summarizes. Safe to call at any time.

## Error Handling Protocol Flow

```
User asks Ava to do something
  ↓
Ava's tool returns an error
  ↓
Ava calls read_logs(level="ERROR") to find traceback
  ↓
Ava calls debug_schedule(lead_name="...") to check cadence state
  ↓
Ava identifies root cause (e.g. "stage=engaged" in logs)
  ↓
Ava tells user in ONE plain English sentence
  ↓
Ava offers 1-2 actionable options
```

The user never sees raw logs, error codes, or tool JSON output.
