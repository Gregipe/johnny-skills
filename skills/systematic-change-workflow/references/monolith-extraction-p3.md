# Pass 3 Extraction: Cadence Engine → app/services/ + app/api/

## What was extracted

| Section | Lines removed | Target module |
|---------|-------------|---------------|
| Cadence Config API (routes: publish, config CRUD, validate, trigger, generate-prompt) | 356 | `app/api/cadence.py` (APIRouter, 11 routes) |
| Cadence Scheduling Engine (interpolate_message, next_working_time, schedule_cadence_for_lead, generate_step_message) | 772 | `app/services/cadence.py` |

## Extraction steps taken

1. Created `app/services/__init__.py` and `app/api/__init__.py`
2. Wrote `app/services/cadence.py` — renamed all functions from `_prefixed` to public (removed underscore) since they're now in a module
3. Wrote `app/api/cadence.py` — `APIRouter()` instead of `@app.route()`, 11 routes. Fixed `__file__` path for `prompt_templates.json` (2 levels deeper than server.py)
4. Added `TENANT_ID` to `app/config.py` (was inline in server.py)
5. Created Python edit script on local, scp'd to server, ran there to:
   - Replace `TENANT_ID = "3e736242"` with `from app.config import TENANT_ID`
   - Add `from app.api.cadence import router` + `app.include_router(router)` before Tenant Endpoints
   - Remove 1128 lines of inline cadence code
6. Added import aliases for functions still called from server.py sections:
   - `from app.services.cadence import schedule_cadence_for_lead as _schedule_cadence_for_lead`
   - `from app.services.cadence import generate_step_message as _generate_step_message`
   - `from app.api.cadence import generate_system_prompt`
7. Added smoke tests to `tests/test_refactor_smoke.py`
8. QA gate: 117 tests pass, mypy clean
9. Deployed

## Key decisions

- **Single module vs split**: Kept engine functions and routes separate. Engine = pure functions (testable without FastAPI). API = route handlers with APIRouter.
- **Import aliases**: The `_schedule_cadence_for_lead` alias preserves backward compatibility for 4 call sites in server.py (lead creation, CSV import, cadence retrigger, lead update). Without aliases, those 4 sites would need internal refactoring too.
- **Path resolution**: `SYSTEM_PROMPT_SECTIONS_INHERITED` loads from `prompt_templates.json` at project root. In server.py: `pathlib.Path(__file__).parent`. In app/api/cadence.py: `pathlib.Path(__file__).resolve().parent.parent.parent`.

## Net result

server.py: 9,965 → 8,840 lines (-1,125). Test count: 113 → 117.
