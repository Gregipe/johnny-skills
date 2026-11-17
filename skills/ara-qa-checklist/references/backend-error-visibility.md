# Backend Error Visibility — ARA Server

## The Silent LLM Failure Pattern

### How Chat Dies Without Anyone Noticing

1. `server.py` starts → imports `induction_engine` → `DEEPSEEK_API_KEY = os.environ.get(...)` runs at module level → if .env wasn't loaded yet, key is `""`
2. User types a message in Ava chat → `/api/agent/chat/{tenant}` calls `call_llm(messages)`
3. `call_llm()` checks `if not DEEPSEEK_API_KEY` → returns `"⚠️ service temporarily unavailable"`
4. Agent chat endpoint wraps this in `try/except Exception` → returns to user
5. **Server log: nothing.** No error printed anywhere.
6. User sees: "chat is down"
7. Developer sees: server running, dashboard loading, no errors in console

### The Fix Chain

**Step 1 — .env loading (import ordering):**
```python
# RIGHT: load before importing modules that read env vars
from dotenv import load_dotenv
load_dotenv("/Users/greg/.hermes/.env")

from induction_engine import call_llm  # now DEEPSEEK_API_KEY is set
```

```python
# WRONG: induction_engine reads env at import time, before load_dotenv runs
from induction_engine import call_llm  # DEEPSEEK_API_KEY = ""
from dotenv import load_dotenv
load_dotenv("/Users/greg/.hermes/.env")  # too late!
```

**Step 2 — Add logging to every exception handler:**
```python
# induction_engine.py — before returning polite message
except Exception as e:
    print(f"ERROR [call_llm]: {e}")         # <-- ADD THIS LINE
    return "⚠️ I'm sorry — the service is..."
```

```python
# server.py — agent_chat endpoint
except Exception as e:
    print(f"ERROR [agent_chat]: {e}")       # <-- ADD THIS LINE
    return {"response": "I encountered an error..."}
```

### Diagnosis Protocol

When someone says "the chat interface seems down":

```
1.  curl -s http://localhost:8766/api/agent/chat/3e736242 \
      -X POST -H "Content-Type: application/json" \
      -d '{"message":"ping"}'
    → If response contains "temporarily unavailable" → LLM is down
    → If response contains "encountered an issue" → LLM call crashed

2.  grep the server output for ERROR — is anything logged?

3.  DEEPSEEK_API_KEY check:
    lsof -ti:8766 | xargs ps -o pid= -p | xargs -I{} bash -c \
      'cat /proc/{}/environ 2>/dev/null | tr "\0" "\n" | grep DEEPSEEK' \
      || echo "Not in process env"

4.  .env file check:
    grep DEEPSEEK ~/.hermes/.env
    → Must contain: DEEPSEEK_API_KEY=sk-...

5.  Import order check:
    grep -n "load_dotenv\|from induction_engine\|from dotenv" server.py
    → load_dotenv() MUST be before "from induction_engine import"
```

### Prevention Rules

1. Every `except Exception` in a user-facing handler MUST log the actual error before returning.
2. Server restart checklist must include a live LLM test (not just "server responded 200").
3. Module-level `os.environ.get()` is a code smell when the env file is loaded separately — prefer lazy initialization or assert the key is set at startup.
