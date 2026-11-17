# Frontend Patterns (Merged from ara-frontend-patterns)

> **Source:** This content was merged from the now-deprecated `ara-frontend-patterns` skill. The authoritative reference for ARA frontend development is now the parent skill `ara-ui-patterns`.

## Design Philosophy

ARA UI should feel like a professional B2B tool — clean, dense, and information-rich. Not a consumer app with chunky cards.

## Global Design Rules

### Only Real Data — No Mockups, No Placeholders

Every UI surface must render **real data from the API**. No hardcoded sample/dummy data, no lorem ipsum, no placeholder cards that look real but aren't backed by data.

### Monochrome & Emoji-Free

**No emoji. Ever.** Plain text labels only. See the main skill for the full color palette.

### Core Visual Rules

- **Tables over cards** — Render lists as table rows
- **Compact spacing** — `padding: 10px 12px` for rows
- **Thin borders** — `1px solid #E5E5E7`
- **Indexed/numbered rows** — Every list gets a numbered column
- **Checkboxes on the left** — Hidden on idle, reveal on hover
- **Selected state** — `background: #F2F2F5` with `box-shadow: inset 2px 0 0 #111`

## Grid Layout for Table Rows

```css
.table .tr {
  display: grid;
  grid-template-columns: 36px 32px 1fr auto;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid #EDEDEF;
  cursor: pointer;
}
```

## Interaction Patterns

- **Hover** — Row gets `background: #F8F8FA`, checkbox fades in
- **Click on row** — Opens/navigates (unless clicking checkbox)
- **Click on checkbox** — `event.stopPropagation()` to avoid triggering row click
- **Select-all** — Header checkbox toggles all visible rows
- **Delete** — Show confirmation modal with count, use `POST /api/<resource>/bulk-delete`

## Unsaved Changes Warning

For editor pages where users make changes before saving/publishing, add a `beforeunload` listener. See main skill for implementation code.

## Inline Contenteditable Editing Pattern

Replace native `prompt()` popups with inline contenteditable for single-field text editing.

## Smart Channel Picker (dynamic filtering)

The "+ Add Channel" button shows only channels NOT already configured for the current template.

## See Also

- [Table-Grid Layout for Data Lists](#table-grid-layout-for-data-lists) (main skill)
- [Checkbox on Rows](#checkbox-on-rows) (main skill)
- [Bulk Operations](#bulk-operations) (main skill)
- [B&W Dialog Modal](#b-w-dialog-modal-replace-native-confirmalert) (main skill)
