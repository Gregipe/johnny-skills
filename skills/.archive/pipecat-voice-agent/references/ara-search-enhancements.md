# ARA Search Enhancements — Implementation Reference

## Overview

Three server-side enhancements to `search_leads` that make Ava robust against STT mis-transcriptions and Indian name variants:

1. **Phonetic matching** — consonant-skeleton + difflib fallback when exact search returns nothing
2. **Space normalization** — "Ram Gopal" matches "Ramgopal"
3. **Action enrichment** — lead search results include pending action counts

These are applied to BOTH the voice tool handler and the REST API in `/opt/ara/server.py`.

---

## 1. Phonetic Matching Helper

Add this function before `def search_leads(q, db)`:

```python
def _phonetic_match(query: str, names: list[str], threshold: float = 0.6) -> list[str]:
    """Return names that phonetically match query using consonant-skeleton + difflib."""
    from difflib import SequenceMatcher
    import re
    
    def _skeleton(s: str) -> str:
        """Extract consonant sequence: 'Rameez' → 'rmz', 'Ramiz' → 'rmz'"""
        return re.sub(r'[aeiou]', '', s.lower())
    
    q_skel = _skeleton(query)
    matches = []
    for name in names:
        n_lower = name.lower()
        n_skel = _skeleton(name)
        # Consonant skeleton must match exactly OR difflib ratio must exceed threshold
        skel_match = (q_skel == n_skel and len(q_skel) >= 2)
        ratio = SequenceMatcher(None, query.lower(), n_lower).ratio()
        if skel_match or ratio >= threshold:
            matches.append((name, max(1.0 if skel_match else 0, ratio)))
    matches.sort(key=lambda x: x[1], reverse=True)
    return [m[0] for m in matches[:5]]
```

**Threshold:** 0.6 catches "Ramiz"→"Rameez" while avoiding false positives. Consonant skeleton matching overrides threshold (always matches).

**Dependencies:** stdlib only — `difflib`, `re`. No new packages.

---

## 2. Voice Tool Handler Path

In the `elif tool_name == "search_leads":` block, replace the handler with:

```python
elif tool_name == "search_leads":
    query = args.get("query", "")
    if not query:
        return "Error: 'query' is required"
    query_norm = query.replace(" ", "")
    leads = db.query(Lead).filter(
        Lead.tenant_id == tenant_id,
        (Lead.name.ilike(f"%{query}%")) |
        (func.replace(Lead.name, " ", "").ilike(f"%{query_norm}%")) |
        (Lead.company.ilike(f"%{query}%")) |
        (func.replace(Lead.company, " ", "").ilike(f"%{query_norm}%")) |
        (Lead.phone.ilike(f"%{query}%")) | (Lead.email.ilike(f"%{query}%"))
    ).limit(5).all()
    
    fuzzy_used = False
    if not leads:
        # Phonetic fallback
        all_leads = db.query(Lead.name).filter(
            Lead.tenant_id == tenant_id, Lead.stage != "archived"
        ).all()
        all_names = [l[0] for l in all_leads]
        fuzzy = _phonetic_match(query, all_names)
        if fuzzy:
            leads = db.query(Lead).filter(
                Lead.tenant_id == tenant_id, Lead.name.in_(fuzzy)
            ).limit(5).all()
            fuzzy_used = True
    
    if not leads:
        return f"No leads found matching '{query}'"
    
    lines = []
    for l in leads:
        # Include pending actions count
        pending_count = db.query(ActionItem).filter(
            ActionItem.tenant_id == tenant_id,
            ActionItem.ref_id == l.id,
            ActionItem.execution_state.in_(["pending", "staged", "in_progress"]),
        ).count()
        action_note = f" | Actions: {pending_count} pending" if pending_count > 0 else " | No pending actions"
        line = f"- {l.name} | {l.company or '--'} | Stage: {l.stage or 'new'} | Email: {l.email or '--'} | Phone: {l.phone or '--'}{action_note}"
        if fuzzy_used:
            line += f" [phonetic match: heard '{query}']"
        lines.append(line)
    return "\n".join(lines)
```

**Key details:**
- `func.replace(Lead.name, " ", "")` needs `from sqlalchemy import func` at the top of `server.py`
- The `ActionItem` model reference must be in scope
- `fuzzy_used` flag adds the `[phonetic match: heard '...']` annotation so the LLM can disambiguate

---

## 3. REST API Path

In `def search_leads(q: str = "", db: DBSession = Depends(get_db)):`, add the phonetic fallback:

```python
leads = db.query(Lead).filter(
    Lead.tenant_id == tenant.id,
    Lead.stage != "archived",
    (Lead.name.ilike(q_like)) |
    (func.replace(Lead.name, " ", "").ilike(q_norm_like)) |
    (Lead.phone.ilike(q_like)) | (Lead.email.ilike(q_like)) | (Lead.company.ilike(q_like))
).order_by(Lead.created_at.desc()).limit(50).all()

# Phonetic fallback
if not leads:
    all_leads = db.query(Lead.name).filter(
        Lead.tenant_id == tenant.id, Lead.stage != "archived"
    ).all()
    all_names = [l[0] for l in all_leads]
    fuzzy = _phonetic_match(q, all_names)
    if fuzzy:
        leads = db.query(Lead).filter(
            Lead.tenant_id == tenant.id, Lead.name.in_(fuzzy)
        ).limit(5).all()

return [{...} for l in leads]  # unchanged return format
```

---

## 4. Important: Both Paths Must Be Updated

The voice tool handler and the REST API are **separate code paths** in `server.py`. Fixing one without the other leaves the other broken. Search for BOTH:
```bash
grep -n "elif tool_name == \"search_leads\"" server.py   # voice tool path
grep -n "def search_leads(q:" server.py                   # REST API path
```

---

## 5. Verification

```bash
# Voice tool path
curl -X POST localhost:8766/api/voice/tool \
  -H "Content-Type: application/json" \
  -d '{"secret":"...","tool":"search_leads","args":{"query":"Ramiz"},"tenant_id":"3e736242"}'

# Expected: returns Rameez with "[phonetic match: heard 'Ramiz']"

# REST API path
curl "localhost:8766/api/leads/search?q=Ramiz"

# Expected: returns [{"name": "Rameez", ...}]
```

---

## 6. STT Keyterms — Lead Name Vocabulary Bias

**Problem:** Even with phonetic matching on the server side, STT mis-transcriptions still happen at the speech recognition level. "Rameez" → "Ramiz", "Sarin" → "Shireen." Fixing it at the STT level prevents the round-trip.

**Fix — pass lead names as `keyterms` to ElevenLabs Scribe v2 Realtime:**

```python
# In bot(), before building the pipeline:
async with httpx.AsyncClient(timeout=10.0) as http:
    # Fetch lead names for STT vocabulary bias
    stt_keyterms = []
    try:
        resp = await http.get(f"{ARA_BASE}/api/tenants/{tenant_id}/leads")
        if resp.status_code == 200:
            leads = resp.json()
            stt_keyterms = [l["name"] for l in leads if l.get("name")]
            # Also add first-name-only variants
            for name in list(stt_keyterms):
                parts = name.split()
                if len(parts) > 1:
                    stt_keyterms.extend(parts)
            stt_keyterms = list(set(stt_keyterms))[:100]  # dedupe, max 100
            logger.info(f"Loaded {len(stt_keyterms)} STT keyterms")
    except Exception as e:
        logger.warning(f"Could not fetch lead names for STT: {e}")

# Pass to build_pipeline:
pipeline, transport = build_pipeline(
    runner_args, system_prompt, voice_tools, app_resources,
    stt_keyterms=stt_keyterms,
)

# In build_pipeline(), pass to STT Settings:
stt = ElevenLabsRealtimeSTTService(
    settings=ElevenLabsRealtimeSTTService.Settings(
        keyterms=stt_keyterms or [],  # biases Scribe toward these words
    ),
)
```

---

## 7. Pitfall: Route Decorator Drift After Insert

**Symptom:** After inserting `_phonetic_match()` before `search_leads()`, the REST API returns a Pydantic validation error: `Field required: query`. The `@app.get(\"/api/leads/search\")` decorator is now on `_phonetic_match` instead of `search_leads`.

**Root cause:** In `server.py`, the route decorator is on the line immediately above the function:
```python
@app.get("/api/leads/search")   # ← line 1392
def search_leads(q, db):        # ← line 1393
```

Inserting `_phonetic_match` between them places the decorator on the helper:
```python
@app.get("/api/leads/search")   # ← still line 1392, now applies to...
def _phonetic_match(...):       # ← ...this function instead of search_leads
```

**Fix:** Move the helper BEFORE the route decorator, and re-add the decorator on `search_leads`:
```python
def _phonetic_match(...):       # ← helper, no decorator
    ...

@app.get("/api/leads/search")   # ← re-added on the correct function
def search_leads(q, db):
    ...
```

**Detection:** `grep -B1 \"@app.get\" server.py` should show the decorator immediately above `def search_leads`, not above `def _phonetic_match`. `ElevenLabsRealtimeSTTService.Settings` accepts `keyterms` as a list of strings (confirmed: Pipecat 1.4.0).

**Pitfall:** The ARA endpoint is `/api/tenants/{tenant_id}/leads`, NOT `/api/leads`. Getting the URL wrong silently fails (try/except catches the 404, keyterms stay empty).

**Lazy loading:** Keyterms are fetched per-session (in `bot()`), not at bot startup. This means they only load when a voice session connects — the first session after a restart has fresh lead names.
