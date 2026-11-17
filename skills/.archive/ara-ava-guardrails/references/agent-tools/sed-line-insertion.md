# Sed Line Insertion for Tool Handlers

When adding tool handlers to `server.py`'s `execute_tool()` function, **never use Python heredocs or string manipulation** — SSH escaping will destroy them. Use `sed` with the `r` command instead.

## The Pattern

```bash
# 1. Write the handler to a .txt file (on the server)
# 2. Insert it after a known line number:
sed -i "LINE_NUM r handler_file.txt" server.py

# 3. Verify syntax:
venv/bin/python -c "import py_compile; py_compile.compile('server.py', doraise=True)"
```

The `r` command reads the file and inserts its content after the specified line. This preserves indentation and avoids ALL escaping issues.

## Inserting Before a Line

```bash
# Use `i` (insert before) instead of `a` (append after):
sed -i "LINE_NUM i handler_file.txt" server.py
```

The `i` command inserts before the specified line. Note: `i` doesn't work with `cat $(file)` syntax — use `r` when possible.

## Why Not Python Scripts

```python
# BROKEN — over SSH, every quote/backslash gets mangled:
ssh host "python3 -c 'content = open(\"file\").read()...'"

# BROKEN — even SCP'd Python scripts fail when the insert logic is fragile:
content = content[:idx] + handler_code + content[idx:]
# Fails if idx is wrong, if there are duplicate markers, etc.
```

Python string insertion scripts are fragile: duplicate markers, shifted line numbers, and wrong indentation all cause silent failures. Sed `r` is surgical — one line, one command, deterministic.

## Real Example (create_action handler)

```bash
# On the server:
cat > handler_create_action.txt << 'HERE'
        elif tool_name == "create_action":
            desc = args.get("description", "")
            if not desc:
                return "Error: 'description' is required"
            # ... handler body ...
HERE

# Insert after create_deal handler (line 3315):
sed -i "3315 r handler_create_action.txt" server.py
```

## When to Use

- Adding new `elif tool_name == ...` branches to `execute_tool()`
- Adding entries to `TOOL_SCHEMAS` dict (insert after the previous alphabetical entry)
- Adding new functions before existing ones in the file
