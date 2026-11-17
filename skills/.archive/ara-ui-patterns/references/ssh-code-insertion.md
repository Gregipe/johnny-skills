# SSH Code Insertion Pattern

When adding code blocks (tool handlers, functions) to ARA's `server.py` on the production
Hetzner server, avoid Python scripts passed over SSH with heredocs. The multi-level escaping
(SSH → bash → Python → literal code with backslashes/quotes) makes errors near-impossible to
debug and likely to corrupt the file.

## ✅ Safe: `sed -i "LINE r file"`

Write the handler code to a local `.txt` file, SCP it to the server, then insert it with
sed's `r` (read file) command:

```bash
# 1. Write handler to a local file (correct indentation, no escaping needed)
write_file handler_create_action.txt  # local — clean Python code

# 2. SCP to server
scp handler_create_action.txt root@HETZNER:/opt/ara/

# 3. Insert after a specific line number
ssh root@HETZNER 'cd /opt/ara && sed -i "3315 r handler_create_action.txt" server.py'
```

The `r` command reads the entire file and inserts it after the target line. No escaping,
no heredocs, no Python string wrapping — the handler code stays exactly as written.

## ❌ Broken: Python scripts over SSH with heredocs

```bash
ssh root@HETZNER 'python3 << '\''PYEOF'\''
# ... multiple layers of escaping through SSH, bash, and Python
PYEOF'
```

This fails because:
1. Backslashes in Python strings need escaping at the bash level
2. Python `f"..."` strings with `\\n` need double-escaping over SSH
3. Error messages are often `ValueError: substring not found` inside Python, not the actual syntax error

## ❌ Broken: `sed -i "LINE i TEXT"` for multi-line blocks

The `i` (insert) command works for single lines but can't handle multi-line blocks well.
Use `r` (read file) instead — it's designed for inserting file contents.

## When lines shift

If sed insertions change line numbers (earlier insertions shift later lines), re-grep
the target lines AFTER each insertion, or insert in descending line-number order
(highest line first → lowest last) to avoid shifting.
