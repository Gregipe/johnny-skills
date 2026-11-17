# Remote Code Insertion: sed `r` Command

## When to Use

When you need to insert a multi-line code block into a file on the production server, and Python scripts over SSH keep failing due to quote/escape hell.

## The Pattern

```bash
# 1. Write the handler code to a local temp file
cat > /tmp/handler.txt << 'EOF'
        elif tool_name == "my_tool":
            ...multi-line handler code...
            return result
EOF

# 2. SCP the temp file to the server
scp /tmp/handler.txt root@HOST:/opt/ara/

# 3. Use sed 'r' to read and insert at exact line number
ssh root@HOST 'cd /opt/ara && sed -i "3315 r handler.txt" server.py'
```

The `sed` `r` command reads a file and inserts its content after the specified line number. Unlike `sed i` (insert before), `r` takes a filename as argument, not inline text — which means no escaping issues.

## Why This Beats Python SSH

| Approach | Escaping | Reliability |
|----------|----------|-------------|
| Python script via heredoc (`<< 'PYEOF'...`) | Multiple layers: bash → Python → file content | Nightmare with any quotes or backslashes |
| Python script via scp + run | Better, but must handle file encoding precisely | Moderate |
| `sed r` command | Zero — no escaping needed | ✅ Most reliable |

## Pitfalls

- Line numbers shift after insertions — re-verify with `grep -n` before each insert
- `sed -i "LINENO r FILE"` inserts AFTER the line, not before. Use `sed -i "LINENO i TEXT"` for before-line insertion (but `i` requires inline text, defeating the purpose)
- Multiple inserts in one command must be ordered back-to-front (insert later lines first) to avoid number shifts

## Example from ARA

Adding three tool handlers to `server.py`:

```bash
# After line 3315 (create_deal handler) 
sed -i "3315 r handler_create_action.txt" server.py

# After line 3500 (query_leads handler) — NOTE: line number shifted
sed -i "3500 r handler_query_actions.txt" server.py

# Before line 4339 (update_deal_stage) — use r on the PRECEDING line
sed -i "4339 r handler_update_action.txt" server.py
```
