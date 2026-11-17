# System Prompt Safety Audit — All Overwrite Paths

## Why This Exists

Greg's explicit concern: "I do not want any processes to overwrite the system prompt." This document catalogs every code path that can modify `systemPrompt` in the ARA backend and frontend, and what protects each one.

---

## Backend (server.py) — 5 Endpoints

### 1. `POST /api/cadence/publish` (line 2066)

**Overwrites systemPrompt?** YES — if the request includes it.

**Mechanism:** Full merge loop (`for k, v in template.items()`). The `template` dict comes from the frontend and includes `systemPrompt` if the caller sends it.

**Callers:**
- `publishCadence()` (main page) — sends full `t` object (includes `systemPrompt` from localStorage)
- `publishPromptBuilder()` (prompt builder) — sends `{promptParts, systemPrompt}` 

**Safeguards:**
- ✅ Merge pattern: only updates fields present in request, preserves all others
- ✅ `systemPrompt` is only overwritten if the request includes a non-empty value (the merge loop skips `None` and `''`)

**Risk:** LOW. merge is additive, not destructive.

---

### 2. `POST /api/cadence/publish-global` (line 2111)

**Overwrites systemPrompt?** YES — on ALL THREE templates.

**Mechanism:** Direct assignment:
```python
existing.config["previous_systemPrompt"] = existing.config.get("systemPrompt", "")
existing.config["promptParts"] = prompt_parts
existing.config["systemPrompt"] = compiled_prompt
```

**Callers:**
- `publishPromptBuilder()` (prompt builder) — INTENTIONAL, shares prompt across templates
- ~~`publishCadence()` (main page)~~ — **REMOVED June 2026**
- ~~`savePromptAndClose()` (legacy prompt editor)~~ — **REMOVED June 2026**

**Required guard:** `if not compiled_prompt: return {"error": ...}` — prevents empty overwrite.

**Safeguards:**
- ✅ `previous_systemPrompt` backed up before overwrite
- ✅ Empty prompt rejected
- ❌ Blast radius: 3 templates at once

**Risk:** MEDIUM. High blast radius but only called from prompt builder flows now. The main-page caller was removed.

---

### 3. `POST /api/cadence/save-draft` (line 2202)

**Overwrites systemPrompt?** YES — if the request includes a non-empty value.

**Mechanism:** Conditional update:
```python
if system_prompt:
    cfg["systemPrompt"] = system_prompt
```

**Safeguards:**
- ✅ Only overwrites if `system_prompt` is truthy
- ✅ Only one template at a time

**Risk:** LOW.

---

### 4. `POST /api/cadence/generate-prompt` (line 3144)

**Overwrites systemPrompt?** YES — on ALL THREE templates.

**Mechanism:** Direct assignment after generation:
```python
existing.config["previous_systemPrompt"] = existing.config.get("systemPrompt", "")
existing.config["systemPrompt"] = full_prompt
```

**Callers:**
- API endpoint (explicit POST)
- Induction completion (auto-triggered by Ava)

**Safeguards:**
- ✅ `previous_systemPrompt` backed up
- ✅ Only called explicitly (no auto-trigger outside induction)
- ❌ Blast radius: 3 templates

**Risk:** LOW. Only fires on explicit request. Always generates a complete prompt.

---

### 5. `POST /api/cadence/preview` (line 2706)

**Overwrites systemPrompt?** NO. Read-only.

**Mechanism:** `system_prompt = config.get("systemPrompt", "")` — reads only.

**Safeguards:**
- ✅ Pure read operation

**Risk:** NONE.

---

## Frontend — 4 Callers

### 1. `publishCadence()` (cadence_template.py:1589)

**Sends systemPrompt?** YES — sends the full `t` object which includes `systemPrompt`.

**Calls endpoint:** `POST /api/cadence/publish` only (the `publish-global` call was **REMOVED**).

**Safeguards:**
- ✅ No longer overwrites other templates' prompts
- ✅ Sends full template data — server merge preserves everything

**Risk:** LOW after fix.

---

### 2. `savePromptAndClose()` (cadence_template.py:2172)

**Sends systemPrompt?** ~~YES~~ **NO — REMOVED.** Previously called `POST /api/cadence/publish-global`. Now saves to localStorage only and closes the editor — the publish-global call was removed June 2026.

**Calls endpoint:** None. Legacy editor now saves locally only.

**Risk:** NONE after removal.

---

### 3. `savePromptBuilder()` (prompt_builder_template.py:1275)

**Sends systemPrompt?** YES — calls `POST /api/cadence/save-draft` with promptParts + systemPrompt.

**Calls endpoint:** `POST /api/cadence/save-draft` — conditional update, only overwrites if non-empty.

**Safeguards:**
- ✅ Only updates one template
- ✅ save-draft is conditional on non-empty

**Risk:** LOW.

---

### 4. `publishPromptBuilder()` (prompt_builder_template.py:1375)

**Sends systemPrompt?** YES — calls `POST /api/cadence/publish` then `POST /api/cadence/publish-global`.

**Calls endpoint:** publish (single template), then publish-global (all 3).

**Safeguards:**
- ✅ `previous_systemPrompt` backup (built into publish-global)
- ✅ Intentional — user explicitly publishing prompt changes

**Risk:** LOW (intentional publish action).

---

## Recovery Mechanisms

| Mechanism | Where | What it does |
|-----------|-------|-------------|
| `previous_systemPrompt` | publish-global, generate-prompt | Saves old prompt before overwriting |
| `POST /api/cadence/draft-cleanup` (line ~2166) | server.py | Swaps systemPrompt with previous_systemPrompt |
| Restore button in prompt builder | prompt_builder_template.py | Calls draft-cleanup then refreshes UI |

## Summary

| Path | Blast Radius | Safeguard | Status |
|------|-------------|-----------|--------|
| publish (main page) | 1 template | Merge pattern + publish-global removed | ✅ Safe |
| publish (prompt builder) | 1 template → 3 templates | Backup saved | ✅ Safe |
| publish-global (legacy editor) | 3 templates | Backup saved | **Caller removed** — endpoint still exists but no UI calls it | |
| save-draft | 1 template | Conditional update | ✅ Safe |
| generate-prompt | 3 templates | Backup saved + explicit trigger | ✅ Safe |
| preview | 0 (read-only) | — | ✅ Safe |
