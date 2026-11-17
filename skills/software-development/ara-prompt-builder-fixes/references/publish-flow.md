# Prompt Builder Publish Flow

## Data Flow
```
User fills constituents → collectPromptParts()
                               │
                               ▼
                    Assemble (if no published prompt exists)
                    OR show published prompt (t.systemPrompt)
                               │
                               ▼
                    User clicks Save & Close
                               │
                               ▼
                    reads aggregatedPrompt.textContent
                               │
                               ▼
                    t.systemPrompt = compiledPrompt
                    POST /api/cadence/publish-global
                    { promptParts: parts, compiled_prompt: compiledPrompt }
                               │
                               ▼
                    Server writes to all 3 template configs
```

## State Matrix

| Scenario | Final tab shows | Save & Close saves |
|----------|----------------|-------------------|
| First time opening, no published prompt | assemblySystemPrompt() output | assembled version |
| Opening after publish | t.systemPrompt (published) | same published prompt |
| Edit constituent, save without tab switch | published prompt (stale) | published content (not updated!) |
| Edit constituent, switch to Final, save | assembled version | new assembled version |
| Edit constituent, switch to Final, no save | assembled in Final | NOT persisted |

## Key Rule
The Final tab is NOT reactive. Changing a constituent does NOT auto-update the Final tab. User must switch to the Final tab (which triggers re-assembly) then Save & Close. This prevents accidental publishes and keeps the sealed-document feel.

## Viewing published prompt on cadence page
- `systemPromptPreview` div shows the chips with filled/unfilled state
- Overview chips updated by `renderPromptOverview()` — checks for any meaningful content per section
- Clicking the preview box opens the prompt builder
