# Remote Patching — Python Escaping & Anchor Selection

When patching ARA's `server.py` (or any production Python file) via SSH + base64 piping, escaping through the pipeline is the #1 source of bugs. Here's how to do it cleanly.

## The Reliable Pattern (Recommended): write_file + scp

For any patch script, the SIMPLEST and most reliable approach:

```python
# 1. Write the patch locally
write_file("/tmp/patch.py", script_content)

# 2. scp to server, then ssh execute
result = terminal(f"scp /tmp/patch.py root@HOST:/opt/ara/patch.py && ssh root@HOST 'cd /opt/ara && python3 patch.py && rm patch.py'")
```

**Why this is better than base64:**
- Zero escaping issues — the file transfers as-is through scp
- No base64 encode/decode step
- Works for any-length scripts
- Can run multiple commands after scp (compile check, grep verify, etc.)
- The `rm` at the end keeps the server clean

## Fallback: write_file + base64 (when scp is unavailable)

If scp isn't available, use base64 piping:

```python
import base64
encoded = base64.b64encode(script.encode()).decode()
result = terminal(f"echo {encoded} | base64 -d | ssh root@HOST python3")
```

## The Pattern to AVOID: Inline Triple-Quoted Strings

```python
# DANGER — triple quotes inside triple quotes
script = """with open('/opt/ara/server.py') as f:
    c = f.read()
old = '''some text'''  # This breaks — nested '''

# f-strings inside triple-quotes with braces are a nightmare
new = f"""response = call_llm(messages, model={_model})"""  # {_model} evaluated locally, not on server
```

**Problems:**
- Nested triple quotes (`'''` inside `"""` or vice versa) cause `SyntaxError: invalid syntax`
- `f`-strings inside `"""` strings — the `{...}` are evaluated LOCALLY, not on the remote server, so variables like `_sug_org` that only exist on the remote will raise `NameError` at script runtime
- `\"` inside `'''...'''` is interpreted differently than inside `"""..."""` — escaping is not consistent across both
## Multi-Pass Patching for Large Refactors

For bulk changes (e.g., migrating 20+ return statements), **do NOT try one massive script.** Split into focused passes:

1. **Pass 1**: Simple string replacements (error returns → ToolResult.fail)
2. **Pass 2**: Complex replacements with params/quoting edge cases
3. **Pass 3**: Success returns with emoji literals
4. **Pass 4**: Test fixes (old-style string assertions → ToolResult field checks)

Each pass is a separate `write_file → scp → run → verify → rm` cycle. This makes debugging trivial — if QA catches an issue, you know exactly which pass caused it.

## Emoji/Unicode Fingerprinting

Local Python escape sequences (`\u2705`, `\U0001f3a4`) may **not** match the actual characters in the remote file. The file might have literal `✅` or `🎤` while your search uses escapes.

**Fix:** Always `grep` the target text BEFORE writing the replacement:

```bash
# Step 1: Check the actual bytes in the file
result = terminal("ssh server 'grep -n \"TARGET_STRING\" /opt/ara/server.py'")

# Step 2: Read a few lines to see the exact escape/character representation
result = terminal("ssh server 'sed -n \"LINE,LINE+3p\" /opt/ara/server.py | cat -A'")
```

If the grep shows the text but your replacement doesn't match, the encoding differs. Use the **actual characters** (copy-paste from grep output) instead of escape sequences in your search pattern.

**Common mismatches encountered:**
| In file (actual) | In search (local Python escape) |
|---|---|
| `✅` | `\u2705` |
| `🎤` | `\U0001f3a4` |
| `⚠️` | `\u26a0\ufe0f` |
| `—` (em dash) | `\u2014` or `—` (different encoding) |

**Shortcut:** use `repr(content[INDEX:INDEX+50])` in a Python check script (scp it) to see the exact escape representation the file uses, then match it exactly.

## Anchor Selection: Picking What to Match

The single most dangerous mistake in this session: using a generic anchor that appears MULTIPLE times in the file.

```python
# WRONG — multiple functions have "except Exception as e:"
old = '''    except Exception as e:
        return {"response": "I encountered an error...'''
# This matched the WRONG function — corrupted 4700+ lines of code
```

**Anchor rules:**
1. Use MULTI-LINE anchors that include surrounding context — enough to uniquely identify the location
2. Include 2+ lines above and 1+ lines below the target
3. For tool definitions: include the `elif tool_name == "..."` line plus the return
4. For function bodies: include the function signature line + first code line
5. Test in your head: "Is there ANY other place this exact string appears?" If yes, expand the anchor
6. After replacement, verify with `grep -n` that the change was applied at the right location and the old anchor no longer exists

## Escaping Through the Pipeline

When writing Python code that generates Python code (e.g., a patch script that writes a Python string constant):

### Triple Quoting: Use write_file

Any patch that needs to embed multi-line Python strings (with `'''` or `"""`) in the replacement text should DEFINITELY use the write_file + base64 pattern. The inline approach in `execute_code` with nested quoting is fragile.

### f-strings in Generated Code

If the patch script writes code that will run on the remote server and uses `f""` strings, remember:
- The patch script's `{...}` are evaluated at patch-time (locally)
- The generated code's `{...}` are evaluated at run-time (on the server)
- To write `{result_summary}` into the generated code, use `{{result_summary}}` in the patch

**Alternative:** Use string concatenation (`"text " + var + " more text"`) instead of f-strings in the generated code. Simpler escaping, zero confusion.

### Backslash Escaping

Each layer of Python adds one level of escaping:

| Layer | `\n` becomes |
|-------|-------------|
| In `write_file` file content | `\n` (literal newline) |
| In `execute_code` string literal | `\n` (newline escape) |
| In base64-encoded script | `\n` (two chars: backslash + n) |
| On remote server file | `\n` (two chars: backslash + n) |

If you need literal `\n` in the remote file's string (not a newline), use `\\n` in `write_file` content. If this gets confusing, use `r"raw string"` on the remote side where possible.

## Verification Protocol

After every remote patch:

```bash
# 1. Syntax check
ssh server 'cd /opt/ara && python3 -c "compile(open(\"server.py\").read(), \"server.py\", \"exec\"); print(\"Syntax OK\")"'

# 2. Verify the change location
ssh server 'grep -n "UNIQUE_STRING_FROM_YOUR_CHANGE" /opt/ara/server.py'
# Confirm the line number matches expectations

# 3. Verify the old anchor is gone
ssh server 'grep -n "OLD_ANCHOR_TEXT" /opt/ara/server.py'
# Should return nothing (or only expected remaining copies)

# 4. Re-read 5 lines around the change
ssh server 'sed -n "LINE_NUMBER-2,LINE_NUMBER+3p" /opt/ara/server.py'
```

## When to Use a Helper Script

For ANY patch that:
- Has string literals with quotes/backslashes
- Spans more than 10 lines
- Uses f-strings or `.format()`
- Modifies multiple locations

→ Always use the `write_file` + scp pattern. The extra 30 seconds saves 30 minutes of escaping debugging.

### Multi-Insertion Pattern (Adding Tool Handlers, Functions)

When adding multiple code blocks at specific positions in `server.py` (e.g., 3 tool schemas + 3 handlers), write a single Python script that:

1. Reads the file
2. Finds insertion points with `content.index(marker)`
3. Slices content around those points
4. Writes the modified file

```python
# Pattern: insert_handler.py
with open("server.py", "r") as f:
    content = f.read()

# Insert handler after a known marker
marker = 'elif tool_name == "create_deal":'
idx = content.index(marker)
# Find end of this handler block (next elif)
next_elif = content.index("elif tool_name ==", idx + 40)
end = content.rfind("\n        return", idx, next_elif)
end = content.index("\n", end + 5) + 1  # past the return line

handler = (
    '        elif tool_name == "new_tool":\n'
    '            ...\n'
    '            return f"result"\n'
    '\n'
)
content = content[:end] + handler + content[end:]

with open("server.py", "w") as f:
    f.write(content)
```

**Key tips:**
- Use `str.rfind()` to find the last return before the next elif
- Always add a blank line between handler blocks
- Verify with `grep -n "elif tool_name == \"new_tool\"" server.py` after insertion
- Delete the helper script from the server after use (`rm /opt/ara/insert_handler.py`)

This avoids the SSH heredoc escaping nightmare entirely.

## Anti-Patterns

- ❌ Matching on `except Exception` — guaranteed to find the wrong function
- ❌ Matching on single-line patterns that appear in multiple tools (`return f"... Created"`)
- ❌ Nested triple-quotes in `execute_code` strings
- ❌ f-strings in the patch code that reference variables meant for the remote context
- ❌ Not verifying the line number of the change after applying
- ❌ Assuming the first match of a `str.replace()` is the right one
