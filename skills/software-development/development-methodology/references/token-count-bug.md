# Security Token Count Bug Pattern

## The Bug

In `server.py` `validate_cadence_prompt()`:
```python
"security": len(prompt_parts.get("security", "")) // 4,
```

`security` is a **dict** (with keys like `injectionPrevention`, `restrictedClaims`, etc.), not a string. `len(dict)` returns the **number of keys**, not the character count. With 4 keys → `4 // 4 = 1` token shown.

Other dict-typed fields (`brand`, `sector`, `channels`) used `json.dumps()` correctly — security was the exception.

## The Fix
```python
"security": len(json.dumps(prompt_parts.get("security", {}))) // 4,
```

## Related: LLM prompt formatting

The Security section in the LLM validation prompt was also interpolating the raw dict:
```python
{prompt_parts.get('security', '(not provided)')}
```

Which renders as `{'injectionPrevention': '...', 'restrictedClaims': '...', ...}` — ugly but functional.

**Fix**: Format each field individually with labels:
```python
Injection Prevention: {prompt_parts.get('security', {}).get('injectionPrevention', '(not provided)')}
Restricted Claims: ...
Escalation: ...
FAQs: ...
```

## Pattern to watch for

Whenever you see `len(obj.get("field", ""))` where `field` might be a dict, verify the data type. Dicts need `json.dumps()` serialization first for character-length metrics.
