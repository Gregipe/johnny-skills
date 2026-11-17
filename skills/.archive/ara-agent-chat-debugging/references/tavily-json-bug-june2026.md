# Tavily `resp.json()` Bug — June 2026

## Problem

Tavily search silently failed even with a valid API key. Ava fell through to DuckDuckGo which rate-limited, producing "Search failed (Tavily and DuckDuckGo both unavailable)."

## Root Cause

`urllib.request.urlopen()` returns `http.client.HTTPResponse`, which does NOT have a `.json()` method. That's a `requests` library API.

```python
# server.py, _search_tavily() at line ~3218:

# BROKEN — raises AttributeError, caught by blanket except
results = resp.json().get("results", [])

# FIXED — use json.loads(resp.read())
results = json.loads(resp.read()).get("results", [])
```

The `AttributeError` was caught by the blanket `except Exception as e: return None, str(e)`, which silently failed Tavily and fell through to DuckDuckGo.

## How It Was Found

1. Greg reported that Ava said searches were failing ("the search engine is being a bit slow" / "rate-limited")
2. Checked the Tavily API key via `resolve_api_key("tavily", "3e736242")` — key resolved correctly (tvly-dev-...)
3. Tested the Tavily API directly with urllib → worked (HTTP 200, 3 results)
4. Tested through `web_search()` → failed with `'HTTPResponse' object has no attribute 'json'`
5. Examined `_search_tavily()` → found `resp.json()` which doesn't exist on urllib's HTTPResponse

## Diagnosis Command

```bash
cd /Users/greg/ara && venv/bin/python -c "
from server import web_search
result = web_search('test query', max_results=3, tenant_id='3e736242')
print(result[:200])
" 2>&1
# Stderr shows: [web_search] Tavily failed ('HTTPResponse' object has no attribute 'json')
```

## Files Modified

- `server.py` — line 3218: `resp.json()` → `json.loads(resp.read())`

## Verification After Fix

```bash
# Same test — should now return real results
cd /Users/greg/ara && venv/bin/python -c "
from server import web_search
result = web_search('Xpressbees logistics', max_results=3, tenant_id='3e736242')
print('OK' if 'Xpressbees' in result else 'FAIL')
"
# Expected: OK
```
