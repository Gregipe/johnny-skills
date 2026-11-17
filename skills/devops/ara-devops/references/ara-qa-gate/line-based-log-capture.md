# Line-Based Log Capture for Tier Verification

## Problem

`journalctl --since 8s ago` closes before the TIER: log line lands, producing "unknown" false negatives. Time-windowed grep is unreliable for short operations.

## Fix: Journal Cursor Positioning

Record the journal cursor BEFORE sending a message, then poll forward from that cursor.

```python
# Record cursor
r = subprocess.run(["journalctl", "-u", "ara-server", "-n", "0", "--show-cursor", "--no-pager"],
                   capture_output=True, text=True)
cursor = None
for line in r.stdout.split("\n"):
    if line.startswith("-- cursor:"):
        cursor = line.split(":", 1)[1].strip()

# Send message
# ...curl...

# Poll forward from cursor
for attempt in range(15):
    time.sleep(1)
    r = subprocess.run(["journalctl", "-u", "ara-server", f"--after-cursor={cursor}", "--no-pager"],
                       capture_output=True, text=True)
    for line in r.stdout.split("\n"):
        if "TIER:" in line:
            if "TIER: smalltalk" in line: tier = "smalltalk"
            elif "TIER: status" in line: tier = "status"
            elif "TIER: command" in line: tier = "command"
    if tier != "unknown":
        break
```

## Key Properties

- Up to 15-second polling window (generous timeout)
- Returns immediately when TIER: line found
- Zero "unknown" results across 10 consecutive runs
- No racing a fixed clock — tailing from a known offset

## When to Use

Any test that needs to verify server-side log output from a specific API call. Prefer this over `--since Ns ago` whenever the log line might arrive after the time window closes.
