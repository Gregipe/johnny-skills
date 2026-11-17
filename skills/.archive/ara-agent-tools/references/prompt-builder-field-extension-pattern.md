# Prompt Builder Field Extension Pattern

Adding a new field to the Prompt Builder (full-screen slide-over) requires touching **5 surfaces**. Missing any one means the field either doesn't save, doesn't load, or doesn't make it into Ava's system prompt.

## The 5 Surfaces

| # | File | Function / Section | What to add |
|---|------|-------------------|-------------|
| 1 | `prompt_builder_template.py` | HTML template (Brand tab ~line 113-170) | `<textarea>` or `<select>` with unique `id` attribute |
| 2 | `prompt_builder_template.py` | `applyPbData()` (~line 842) | `setPbVal('pe_fieldName', bp.fieldName \|\| '')` — populate from saved data |
| 3 | `prompt_builder_template.py` | `collectPbParts()` (~line 897) | `fieldName: gvPbVal('pe_fieldName')` — read back for save |
| 4 | `server.py` | `/api/cadence/validate` endpoint (~line 1536) | `FieldName: {prompt_parts.get('brandPersonality', {}).get('fieldName', '(not provided)')}` — include in LLM compilation prompt |
| 5 | `cadence_template.py` | `assembleSystemPrompt()` (~line 2026) | `parts.push('FieldName: ' + bp.fieldName)` — inject into Ava's system prompt |

## Also Check (if applicable)

- **`prefill_generator.py`** — if the new field should be pre-filled from induction data, add it to the `brandPersonality` dict returned by `_generate_induction_prefill()` (~line 321)
- **Inline builder in `cadence_template.py`** — if the old inline builder also needs the field (rare — new fields usually go to the full-screen builder only)

## Bug Pattern: Validate-Without-Save

When the user clicks **"Save Changes"** on a field for the first time, the flow is:

1. `savePromptBuilder()` collects data and checks `pbFinalPrompt.textContent`
2. If the prompt hasn't been validated yet, it goes to the **else branch**
3. The else branch validates via `/api/cadence/validate` but historically **did not persist**
4. User refreshes → all data lost

**The fix:** The else branch must chain: `validate` → on success → `save-draft` → `saveCurrentState()`.

```javascript
// Correct pattern — the else branch in savePromptBuilder()
fetch('/api/cadence/validate', { body: JSON.stringify({ ... }) })
  .then(r => r.json())
  .then(data => {
    if (data.status === 'ok') {
      // Set compiled prompt
      document.getElementById('pbFinalPrompt').textContent = data.compiled_prompt;
      t.systemPrompt = data.compiled_prompt || '';
      // NOW save
      return fetch('/api/cadence/save-draft', { body: JSON.stringify({ ... }) });
    }
  })
  .then(r => r.json())
  .then(data => {
    if (data.status === 'ok') {
      saveCurrentState();  // Persists to localStorage
    }
  });
```

## Verification

After adding a new field:

1. Hard refresh the dashboard
2. Open the Prompt Builder
3. Fill in the new field
4. Click **"Save Changes"** or **"Validate & Save"** (whichever flow)
5. Look for `✓ Saved to draft` status message
6. Refresh the page, reopen the builder — field should still be populated
7. Click **Publish** or check `assembleSystemPrompt()` output — field should be in the compiled prompt
