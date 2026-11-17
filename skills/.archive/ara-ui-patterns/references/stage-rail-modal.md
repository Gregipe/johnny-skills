# Stage Rail Modal Pattern

A large centered modal with a horizontal lifecycle stage rail and two-column layout (workspace + live preview). Used by the Conversational Playbook on the Outreach Central page.

## When to Use

Any configuration surface that follows a lifecycle or sequential stages — where the user configures per-stage behavior and needs to see a preview of the result.

## Structure

```
┌────────────────────────────────────────────────────────────┐
│ Header: Title + subtitle + [Save] [✕]                      │
├────────────────────────────────────────────────────────────┤
│ Stage Rail: Stage 1 → Stage 2 → Stage 3 → Stage 4 → Stage 5│
├──────────────────────────────┬─────────────────────────────┤
│                              │                             │
│   Left Column: Workspace     │   Right Column: Preview     │
│   (scrolls, configures)      │   (live, updates on change) │
│                              │                             │
└──────────────────────────────┴─────────────────────────────┘
```

## HTML Pattern

```html
<div class="playbook-overlay" id="playbookOverlay">
  <div class="playbook-modal">
    <!-- Header -->
    <div class="playbook-header">
      <div class="playbook-header-left">
        <div class="playbook-title">Title</div>
        <div class="playbook-subtitle">Subtitle</div>
      </div>
      <div class="playbook-header-right">
        <button class="btn btn-primary" onclick="save()">Save Changes</button>
        <button class="playbook-close" onclick="close()">✕</button>
      </div>
    </div>

    <!-- Stage Rail -->
    <div class="playbook-rail" id="playbookRail">
      <div class="playbook-rail-stage active" data-stage="stage1" onclick="switchStage('stage1')">
        <span class="prs-name">Stage 1</span>
        <span class="prs-desc">Description</span>
      </div>
      <div class="playbook-rail-arrow">→</div>
      <div class="playbook-rail-stage" data-stage="stage2" onclick="switchStage('stage2')">
        <span class="prs-name">Stage 2</span>
        <span class="prs-desc">Description</span>
      </div>
      ...
    </div>

    <!-- Two-column body -->
    <div class="playbook-body">
      <div class="playbook-workspace" id="playbookWorkspace">
        <!-- Rendered by JS -->
      </div>
      <div class="playbook-preview" id="playbookPreviewPanel">
        <div class="playbook-preview-header">Preview</div>
        <div class="playbook-preview-body" id="playbookPreviewBody">
          <!-- Rendered by JS -->
        </div>
      </div>
    </div>
  </div>
</div>
```

## CSS Pattern

```css
/* Overlay — fixed, fullscreen with blur */
.playbook-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.4);
  backdrop-filter: blur(4px);
  z-index: 10000;
  display: none; opacity: 0;
  align-items: center; justify-content: center;
  transition: opacity 0.2s;
}
.playbook-overlay.open { display: flex; opacity: 1; }

/* Modal — large, centered, card */
.playbook-modal {
  background: #fff; border-radius: 16px;
  width: 92vw; max-width: 1200px;
  height: 88vh; max-height: 900px;
  display: flex; flex-direction: column;
  box-shadow: 0 20px 60px rgba(0,0,0,0.15);
  overflow: hidden;
  animation: pbFadeIn 0.2s ease-out;
}
@keyframes pbFadeIn {
  from { opacity: 0; transform: scale(0.97) translateY(10px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

/* Rail — horizontal with overflow */
.playbook-rail {
  display: flex; align-items: center; gap: 4px;
  padding: 16px 24px;
  border-bottom: 1px solid #E5E5E7;
  overflow-x: auto;
}
.playbook-rail-stage {
  display: flex; flex-direction: column; align-items: center;
  padding: 10px 16px; border-radius: 10px;
  cursor: pointer; border: 1px solid transparent;
  min-width: 100px;
}
.playbook-rail-stage.active { background: #111; border-color: #111; }
.playbook-rail-stage.active .prs-name,
.playbook-rail-stage.active .prs-desc { color: #fff; }
.prs-name { font-size: 12px; font-weight: 600; color: #111; }
.prs-desc { font-size: 10px; color: #6E6E73; }
.playbook-rail-arrow { color: #D2D2D5; font-size: 14px; margin: 0 4px; }

/* Two-column body */
.playbook-body { display: flex; flex: 1; min-height: 0; }
.playbook-workspace { flex: 1; overflow-y: auto; padding: 24px; }
.playbook-preview {
  width: 320px; flex-shrink: 0;
  border-left: 1px solid #E5E5E7;
  background: #FAFAFA;
  display: flex; flex-direction: column;
}
.playbook-preview-body { flex: 1; overflow-y: auto; padding: 16px; }
```

## JS Pattern

```javascript
// Data model stored on the parent object (e.g., template config)
var data = null;
var activeStage = 'stage1';

function open() {
  data = getData(); // initialize if needed
  document.getElementById('overlay').classList.add('open');
  switchStage('stage1');
}

function close() {
  document.getElementById('overlay').classList.remove('open');
}

function switchStage(stage) {
  activeStage = stage;
  document.querySelectorAll('.playbook-rail-stage').forEach(function(el) {
    el.classList.toggle('active', el.dataset.stage === stage);
  });
  renderWorkspace(stage);
  renderPreview(stage);
}

function renderWorkspace(stage) {
  var config = data[stage] || getDefaults(stage);
  var html = '';
  // Build HTML for each section (intents, actions, rules, etc.)
  document.getElementById('workspace').innerHTML = html;
}

function renderPreview(stage) {
  var config = data[stage] || getDefaults(stage);
  var html = '';
  // Build preview based on current config
  document.getElementById('previewBody').innerHTML = html;
}
```

## Key Design Decisions

1. **No emoji icons in stage names or section headers** — plain text only (monochrome rule)
2. **Stage rail uses arrows (→) between stages** — indicates sequential lifecycle flow
3. **Active stage has black (#111) background** — high contrast, instantly scannable
4. **No icons in action rows** — text labels only, drag handles use ⠿ (braille pattern)
5. **Toggle switches are black when on (#111)** — consistent with monochrome palette
6. **Right column preview updates live** — every toggle/switch triggers `renderPreview()`
7. **Section cards use #F8F8FA background** — subtle distinction from white action rows

## See Also

- `ara-cadence-logic` SKILL.md section 12 — Conversational Playbook data model and defaults
- Color scheme: `#111`, `#6E6E73`, `#E5E5E7`, `#F5F5F7`, `#FAFAFA`, white
