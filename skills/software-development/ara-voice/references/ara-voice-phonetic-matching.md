# ARA Voice Phonetic Matching

Three-layer fix for STT mis-transcription of Indian names ("Ramiz" → "Rameez", "Shireen" → "Sarin").

## Layer 1: Consonant-Skeleton Matching (server.py)

```python
def _phonetic_match(query: str, names: list[str], threshold: float = 0.6) -> list[str]:
    """Return names that phonetically match query."""
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
        skel_match = (q_skel == n_skel and len(q_skel) >= 2)
        ratio = SequenceMatcher(None, query.lower(), n_lower).ratio()
        if skel_match or ratio >= threshold:
            matches.append((name, max(1.0 if skel_match else 0, ratio)))
    matches.sort(key=lambda x: x[1], reverse=True)
    return [m[0] for m in matches[:5]]
```

Applied as fallback when `search_leads` returns empty:
```python
if not leads:
    all_leads = db.query(Lead.name).filter(...).all()
    all_names = [l[0] for l in all_leads]
    fuzzy = _phonetic_match(query, all_names)
    if fuzzy:
        leads = db.query(Lead).filter(Lead.name.in_(fuzzy)).limit(5).all()
```

**Must be applied to BOTH paths:** the REST API `search_leads` AND the voice tool handler `elif tool_name == "search_leads"`.

Also applied as 4th fallback in `resolve_lead()`.

## Layer 2: STT Keyterms Vocabulary (bot.py)

ElevenLabs Scribe v2 Realtime supports `keyterms` for vocabulary bias. Inject lead names at session start:

```python
# In bot() function:
stt_keyterms = []
resp = await http.get(f"{ARA_BASE}/api/tenants/{tenant_id}/leads")
if resp.status_code == 200:
    leads = resp.json()
    stt_keyterms = [l["name"] for l in leads if l.get("name")]
    # Also add first-name-only variants
    for name in list(stt_keyterms):
        parts = name.split()
        if len(parts) > 1:
            stt_keyterms.extend(parts)
    stt_keyterms = list(set(stt_keyterms))[:100]
```

Pass to build_pipeline and into STT Settings:
```python
settings=ElevenLabsRealtimeSTTService.Settings(
    model=STT_MODEL,
    keyterms=stt_keyterms or [],
    ...
)
```

Max 100 keyterms, 50 chars each. Deduplicate via `set()`. First-name-only variants help match partial queries.

## Layer 3: Disambiguation Prompt (system prompt)

```
SEARCH SMART + STT DISAMBIGUATION
The system phonetically matches names. If a search returns no results, try common 
Indian name variations — swap vowels (i/e, a/u), try without spaces, try first name 
only. If the system says "(heard XYZ)", acknowledge the correction and use the 
matched name going forward. When you get a phonetic match, say: "I heard XYZ — did 
you mean [matched name]?"

Never give up after one search — the second attempt with a variation usually finds 
the lead.
```

## _did_you_mean() Helper (server.py)

```python
def _did_you_mean(query: str, matches: list[str]) -> str:
    if len(matches) == 1:
        return f"I heard '{query}' — did you mean {matches[0]}?"
    return f"I heard '{query}' — did you mean one of: {', '.join(matches)}?"
```

## Verified Matches (as of July 10, 2026)

| STT hears | matches | via |
|-----------|---------|-----|
| "Ramiz" | "Rameez" | consonant skeleton (`rmz` = `rmz`) |
| "Sarin" | "Devashish Sarin" | difflib ratio (0.67) |
| "Ram Gopal" | "Ramgopal Nanda" | space-normalized ilike |
