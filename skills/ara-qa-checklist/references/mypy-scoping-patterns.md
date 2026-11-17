# Python 3.12+ Scoping Crash Patterns in ARA

These are the crash patterns that run-time scoping errors (`UnboundLocalError`, `used-before-def`) manifest as in ARA's codebase. All are caught by `mypy --check-untyped-defs` at compile time.

## Pattern 1: Missing `global` Declaration

**Symptom:** `cannot access local variable 'X' where it is not associated with a value`

**Root cause:** A function reads AND assigns a module-level variable without declaring `global X`.

**Example — this crashed on the 2nd voice note:**
```python
# BAD — whatsapp_voice_inbound modifies _DEDUP_LAST_SAVE without global
def whatsapp_voice_inbound(data: dict):
    logger = logging.getLogger("whatsapp")
    ...
    if _module_time.time() - _DEDUP_LAST_SAVE > 5:  # reads module var
        _save_dedup()
        _DEDUP_LAST_SAVE = _module_time.time()       # ALSO assigns → Python treats as local
```

**Fix:**
```python
def whatsapp_voice_inbound(data: dict):
    global _DEDUP_LAST_SAVE   # <--- required
    logger = logging.getLogger("whatsapp")
```

**mypy signal:** `Name "_DEDUP_LAST_SAVE" is used before definition [used-before-def]`

**ARA files hit by this:**
- `server.py` — `whatsapp_inbound_webhook` (fixed), `whatsapp_voice_inbound` (fixed), `_handle_owner_coach_whatsapp` (fixed)

## Pattern 2: `logger` Referenced Without Definition

**Symptom:** `NameError: name 'logger' is not defined` at runtime

**Root cause:** A function uses `logger.warning()`, `logger.info()`, etc. without a preceding `logger = logging.getLogger(...)` in that function scope.

**Example:**
```python
# BAD — logger used but never defined in this scope
def execute_tool(tool_name, args, db, wa, tenant_id):
    ...
    elif tool_name == "send_whatsapp":
        ...
        logger.warning(f"BLOCKED...")   # CRASH — logger doesn't exist here
```

**Fix:**
```python
def execute_tool(tool_name, args, db, wa, tenant_id):
    import logging
    _tool_log = logging.getLogger("ara")    # <--- define it
    ...
    elif tool_name == "send_whatsapp":
        ...
        _tool_log.warning(f"BLOCKED...")
```

**mypy signal:** `Name "logger" is not defined [name-defined]`

**ARA files hit by this:** `server.py` `execute_tool()` (fixed)

## Pattern 3: `.replace()` on `None`

**Symptom:** `AttributeError: 'NoneType' object has no attribute 'replace'`

**Root cause:** A variable can be `None` (returned from a function that returns `str | None`) but is used without a null guard.

**Example:**
```python
# BAD — _extract_domain returns str | None, but .replace() assumes str
_org_domain = _extract_domain(l.email or "")
...
_deal_target = _org_name or _org_domain.replace(".com", "").replace(".", " ").title()
```

**Fix:**
```python
_deal_target = _org_name or (_org_domain or "").replace(".com", "").replace(".", " ").title()
```

**mypy signal:** `Item "None" of "str | None" has no attribute "replace" [union-attr]`

**ARA files hit by this:** `server.py` `create_lead` tool handler (fixed)

## Pattern 4: `.rsplit()` on `None` (UploadFile.filename)

**Symptom:** `AttributeError: 'NoneType' object has no attribute 'rsplit'`

**Root cause:** FastAPI's `UploadFile.filename` is typed as `str | None`, but the code calls `.rsplit()` on it without a guard.

**Example:**
```python
# BAD — file.filename can be None
slug = _slugify(display_name or file.filename.rsplit(".", 1)[0])
```

**Fix:**
```python
slug = _slugify(display_name or (file.filename or "").rsplit(".", 1)[0])
```

**mypy signal:** `Item "None" of "str | None" has no attribute "rsplit" [union-attr]`

**ARA files hit by this:** `server.py` `upload_mention_document()` (fixed — 4 usages)

## Pattern 5: SQLAlchemy Column Objects As Plain Values

**Symptom:** mypy flags `Incompatible types` or `Column[str]` passed where `str` expected

**Root cause:** SQLAlchemy ORM attributes (e.g. `Lead.email`) are `Column[str]` at the type level, not plain `str`. Pass `.email` directly to a function expecting `str` and mypy complains.

**Example:**
```python
# BAD — tenant.id is Column[str], not str
return list_leads(tenant.id, db=db)  # mypy: expected str, got Column[str]

# BAD — l.email is Column[str], not str
org_domain = _extract_domain(l.email or "")
```

**Does this crash at runtime?** Usually not — SQLAlchemy Columns evaluate to their values in most contexts. But mypy flags them and they're a code smell that signals the developer didn't think about types.

**Fix:** Accept that SQLAlchemy ORM code will have false positives. The `--disable-error-code arg-type` and `--disable-error-code assignment` flags in the QA gate suppress these.

**mypy signals:**
- `Argument 1 to "list_leads" has incompatible type "Column[str]"; expected "str" [arg-type]`
- `Incompatible types in assignment (expression has type "dict[Any, Any]", variable has type "Column[Any]") [assignment]`

## Running Mypy on ARA

```bash
# Full QA gate (recommended):
cd /opt/ara && bash deploy.sh

# Manual run with scoping-focused flags:
cd /opt/ara && /opt/ara/venv/bin/python3 -m mypy server.py \
  --ignore-missing-imports \
  --disable-error-code valid-type \
  --disable-error-code misc \
  --disable-error-code var-annotated \
  --disable-error-code call-overload \
  --disable-error-code assignment \
  --disable-error-code dict-item \
  --disable-error-code arg-type \
  --disable-error-code union-attr \
  --disable-error-code operator \
  --check-untyped-defs
```

The `--disable-error-code` flags suppress noise from:
- `valid-type`, `misc` — SQLAlchemy `Base` declarative model
- `var-annotated` — missing type hints on module-level dicts
- `call-overload`, `assignment`, `dict-item`, `arg-type` — SQLAlchemy Column/value impedance
- `union-attr`, `operator` — false positives from database access patterns

The check that matters most is `used-before-def` and `name-defined`, which catch the scoping crashes.
