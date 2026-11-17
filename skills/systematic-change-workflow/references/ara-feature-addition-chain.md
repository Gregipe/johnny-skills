# ARA Feature Addition Chain

Pattern for adding a new feature to ARA that touches DB + API + frontend. Apply after Phase 0 (map the chain) of the parent skill.

**Lightweight variant (no new DB model):** For endpoints that reuse existing tables (e.g., a sync endpoint against `mentionable_items`), skip steps 1-2 (DB model + migration). Start at step 3 (API) and step 4 (frontend). See `ara-frontend-patterns/references/toggle-sync-pattern.md` for a concrete example — the `POST /api/mentions/sync-deck/` endpoint that creates @-mentionable items from toggled KB documents.

## The Chain (in order)

```
DB Model (database.py) 
  → Migration (server.py lifespan) 
  → API Endpoints (server.py) 
  → Frontend JS (prompt_builder_template.py or dashboard.js)
  → Compile check (py_compile)
  → Server restart
  → API verification (curl)
  → DB verification (python -c query)
  → Frontend verification (browser / curl HTML)
```

## Step-by-step

### 1. DB Model (`database.py`)
- Add the SQLAlchemy model class before `# ---- Engine Factory ----`
- Use existing patterns: UUID primary key, tenant_id FK, utcnow defaults
- Use `sqlalchemy.UniqueConstraint` in `__table_args__` for multi-column uniqueness
- Import new model in `server.py` import line

### 2. Migration (`server.py` lifespan)
- Insert raw SQL `CREATE TABLE` migration after the `cadence_configs` migration block
- Check `if '<table>' not in tables:` before creating
- Add useful indexes on tenant_id, status, type etc.
- `Base.metadata.create_all(engine)` in `init_db()` handles SQLAlchemy model-tables automatically; manual SQL is needed only for tables created before the model existed, or for tables with SQLite-incompatible features

### 3. API Endpoints (`server.py`)
- Group related endpoints under a `# ---- Feature Name API ----` section comment
- Use existing patterns: `@app.get/post`, `DBSession = Depends(get_db)`, `TENANT_ID` constant
- Accept `data: dict` for POST bodies (avoid Pydantic for simple endpoints)
- Return dicts (FastAPI auto-serializes to JSON)
- Use `JSONResponse` with status_code for errors
- For file uploads: `file: UploadFile = File(...)` with `await file.read()`

### 4. Frontend Integration
- **Prompt builder textareas**: JS goes into `prompt_builder_template.py` inline script
- **Dashboard pages**: JS goes into `static/dashboard.js` (bump `?v=N` cache-buster)
- **Standalone pages** (cadence, threads): Inline JS in respective `_template.py`
- JS escaping in Python raw strings: `\\'` not `\\\\'` or `\\\\\\\\'` (see ara-frontend-patterns pitfall #20)
- For modal/drawer UI: create elements dynamically with JS (try creating, check if exists, append to body)

### 5. Compile & Restart
```bash
cd /Users/greg/ara
python3 -c "import py_compile; py_compile.compile('server.py', doraise=True); py_compile.compile('database.py', doraise=True)"
lsof -ti:8766 | xargs kill -9 2>/dev/null; sleep 1
# Use background=true pattern (not nohup):
cd /Users/greg/ara && ./venv/bin/python server.py
```

### 6. Verify API
```bash
# Test endpoint responds
curl -s "http://localhost:8766/api/feature/endpoint"

# Test POST
curl -s -X POST "http://localhost:8766/api/feature/endpoint" \
  -H "Content-Type: application/json" \
  -d '{"key": "value"}'

# Test file upload
curl -s -X POST "http://localhost:8766/api/mentions/upload/TENANT_ID" \
  -F "file=@/tmp/test.txt" \
  -F "display_name=Test" \
  -F "is_shareable=true"
```

### 7. Verify DB
```bash
cd /Users/greg/ara && python3 -c "
from database import init_db, NewModel
from sqlalchemy import inspect
db = init_db()
inspector = inspect(db.get_bind())
tables = inspector.get_table_names()
print('Table exists:', 'new_table' in tables)
db.close()
"
```

### 8. Verify Frontend
```bash
# Check JS is present in rendered HTML
curl -s http://localhost:8766/cadence | grep -c 'functionName\|elementId'
```

## Pitfalls

- **Server restart race**: `pkill -f` can match the shell running the restart command itself. Use `lsof -ti:8766 | xargs kill` instead, then wait 2 seconds before starting.
- **DB lock during server runtime**: SQLite is single-writer. Can't query/write from both server and CLI simultaneously. Test DB writes with the server running but expect failures from CLI scripts.
- **Python raw string + JS escaping**: Inside `r"""..."""`, `\\'` produces `\'` in the rendered JS. This is the correct pattern for embedded onclick handlers. See pitfall #20 in `ara-frontend-patterns`.
- **Frontend check requires cache-busting**: Server-rendered HTML isn't cached, but browser DevTools may show stale output. Use `Cmd+Shift+R` for hard refresh, then verify with `typeof functionName === 'function'` in console.
- **All surfaces audit**: When adding a feature, check ALL files the feature touches — not just the primary edit file. This session's build touched: `database.py`, `server.py` (3 locations: import, lifespan, endpoints), `prompt_builder_template.py` (inline JS). The `systematic-change-workflow` Phase 0 "map the chain" step catches this — do not skip it.
