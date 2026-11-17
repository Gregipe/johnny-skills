# Shareable Decks — Per-Stage Configuration

The Conversational Playbook (Outreach Central page) has 5 stages: **Engaged, Meeting Requested, Scheduled, Completed, Closed**. Each stage has a **Shareable Decks** section where you control which decks Ava can share during that stage of the conversation.

## Location

Outreach Central page → **Conversational Playbook** section → click **✎ Configure** on any stage (Engaged / Meeting Requested / Scheduled / Completed / Closed).

The stage expand/collapse uses `<details>`/`<summary>` HTML elements rendered by `renderPlaybookTab()` in `cadence_template.py`. Each stage's content includes a `#pbStageDecks-{stage}` div with the deck rows.

## Row Controls

Each deck in a stage has two controls:

| Control | CSS Class | Function | Behavior |
|---------|-----------|----------|----------|
| **Toggle** | `.pb-action-toggle` | `toggleStageDeck(el, stage, deckId)` | Enables/disables Ava from sharing this deck in this stage. `.on` class = enabled. Default: enabled. |
| **Pin** 📌 | `.pb-deck-pin` | `pinStageDeck(el, stage, deckId)` | Marks as **primary deck** for this stage. `.pinned` class = pinned. Only one pinned per stage. Title attribute: `"Pin as primary deck for this stage"`. |

So Ava knows: when a conversation reaches the Engaged stage — the **pinned** deck is the one to lead with, and the **toggled-on** decks are available to share as context-appropriate.

## Empty State

If no decks are selected in Outreach Template → Sector → Deck / Data References, the section shows:

> "No decks selected in Outreach Template → Sector → Deck / Data References. [Set up decks →]"

The link calls `closePlaybook(); openPromptBuilder(); switchPbTab('sector')` — navigating to the Prompt Builder's Sector Intelligence tab where decks are defined.

## Deck Metadata

Each deck shows:
- **Drag handle** (⠿) — `.pb-action-drag`
- **File type icon** — determined by extension:
  - `pdf` → 📕
  - `pptx`, `pptm` → 📊
  - `docx`, `docm` → 📝
  - `txt` → 📄
  - default → 📄
- **Name** — `.pb-action-label` with `.replace(/"/g, '&quot;')` escaping
- **Toggle** — `.pb-action-toggle` (`on` class if enabled)
- **Pin** — 📌 `.pb-deck-pin` (`pinned` class if pinned)

## Data Model

```javascript
// Per-stage deck config in template data
cfg.decks = [
  {
    id: "deck-uuid",
    pinned: true,     // is this the primary deck for this stage?
    enabled: true     // can Ava share this deck in this stage?
  }
]

// Source decks from Outreach Template → Sector
selectedDecks = tmpl.promptParts.sectorSpecific.selectedDecks
```

Each `selectedDecks` item has `{id, name}`. The per-stage `cfg.decks` array augments these with `pinned` and `enabled` flags. If a deck doesn't have a per-stage entry, it defaults to `pinned: false, enabled: true`.

## Rendered HTML (per deck)

```html
<div class="pb-action-row pb-stage-deck" data-stage="engaged" data-id="deck-uuid" data-name="Company Deck">
  <span class="pb-action-drag">⠿</span>
  <span class="pb-deck-icon">📊</span>
  <span class="pb-action-label">Company Deck</span>
  <span class="pb-action-toggle on" onclick="toggleStageDeck(this,'engaged','deck-uuid')"></span>
  <span class="pb-deck-pin pinned" onclick="pinStageDeck(this,'engaged','deck-uuid')" title="Pin as primary deck for this stage">📌</span>
</div>
```

## Implementation

- **Template file:** `cadence_template.py` — the `renderPlaybookTab()` function generates the stage HTML
- **Stage deck functions:** defined inline in `prompt_builder_template.py` (script tag at bottom):
  - `toggleStageDeck(el, stage, deckId)` — toggles `on` class, updates `t.config.engaged.decks` array in state
  - `pinStageDeck(el, stage, deckId)` — removes `pinned` from all other decks in same stage, adds to clicked one. Updates `t.config.engaged.decks`
- **Persistence:** Saved as part of `t.config` in the per-template JSON when Publish or Save is called
- **Deck definitions:** Pulled from `tmpl.promptParts.sectorSpecific.selectedDecks` — these are set in the Prompt Builder's Sector Intelligence tab

## Related Code

Search for `pbStageDecks`, `pb-deck-pin`, `pinStageDeck`, `toggleStageDeck` in `cadence_template.py` and `prompt_builder_template.py`.
