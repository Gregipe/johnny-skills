# Prompt Template Injection — format() vs replace() Safety

## The Problem

System prompts need runtime values injected (e.g., today's date for relative date parsing). Python's `.format()` is tempting but dangerous with large prompts.

```python
# DANGEROUS — fails if prompt contains any unescaped { or }
system_prompt = DASHBOARD_SYSTEM_PROMPT.format(today=today_str)
```

Symptoms:
- `KeyError: 'some_unrelated_key'` — prompt contained `{some_unrelated_key}` (from JSON examples, tool schema descriptions, code snippets)
- Silent crash if wrapped in try/except
- Bot process dies on session start

## The Fix

Use `.replace()` for targeted substitution:

```python
# SAFE — only replaces the exact placeholder, ignores all other braces
system_prompt = DASHBOARD_SYSTEM_PROMPT.replace("{today}", today_str)
```

Requirements:
1. Placeholder must be unique — `{today}` works because it doesn't appear elsewhere
2. Avoid generic placeholders like `{date}` or `{time}` that might match tool descriptions or code snippets
3. The prompt must contain the EXACT placeholder string

## Verified Pattern (July 10, 2026)

5683-character DASHBOARD_SYSTEM_PROMPT with embedded tool schema descriptions (containing `{query}` patterns) survived `.replace("{today}", "Saturday, July 10, 2026")` without errors. The same prompt would have crashed with `.format(today=...)` due to unescaped braces in the tool descriptions.

## Bot.py Injection Code

```python
from datetime import datetime

# In bot() function:
today_str = datetime.now().strftime("%A, %B %d, %Y")
system_prompt = DASHBOARD_SYSTEM_PROMPT.replace("{today}", today_str)
```

The datetime import must be at the top of bot.py and the `{today}` placeholder must be in the DASHBOARD_SYSTEM_PROMPT string.
