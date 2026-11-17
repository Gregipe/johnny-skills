# Catalog-Driven Integrations UI Pattern

Built during May 2026 session. A reusable pattern for adding a dynamic integrations/configurations UI page to a FastAPI + vanilla JS dashboard.

## Architecture

```
server.py                                  dashboard_template.py
┌──────────────────────────┐               ┌───────────────────────────────┐
│ INTEGRATIONS_CATALOG     │  GET /api/    │ renderIntegrations()          │
│  └─ id, name, subtitle   │  integra-    │  └─ Search bar                │
│  └─ description, icon    │  tions       │  └─ Category pills            │
│  └─ category, coming_soon│              │  └─ renderIntCards()          │
│  └─ link, taggable       │              │     └─ fetch + render         │
│                          │              │                                │
│ _get_integration_status()│              │ toggleIntegration(el)           │
│  └─ checks runtime state │              │  └─ POST connect/disconnect   │
│                          │              │                                │
│ POST /connect            │              │ filterIntCat(cat)             │
│ POST /disconnect         │              │  └─ filter + re-render        │
└──────────────────────────┘               └───────────────────────────────┘
```

## Backend Pattern

### Catalog Definition

Define a static `INTEGRATIONS_CATALOG` list at module level in `server.py`. Each entry has:

```python
{
    "id": "whatsapp-self",          # Unique slug
    "name": "WhatsApp",             # Display name
    "subtitle": "Self",             # Badge/variant label
    "description": "Connect your personal WhatsApp...",  # 2-line description
    "icon": "W",                    # Single character or emoji
    "icon_bg": "#25D366",           # Icon background color
    "category": "messaging",        # One of: messaging, phone, productivity
    "coming_soon": False,           # True = greyed out, disabled toggle
    "link": "/api/whatsapp/link",   # URL to open for connection flow (or None)
    "taggable": True,               # Whether search shows this card
}
```

### Live Status Check

Each integration has a runtime status checker. For WhatsApp, poll the actual Playwright state:

```python
def _get_integration_status(integration_id: str) -> dict:
    if integration_id == "whatsapp-self":
        try:
            return wa.status_sync()  # Returns {"authenticated": bool, "connected": bool}
        except Exception:
            return {"connected": False, "authenticated": False}
    return {"connected": False}  # Default for unconnected integrations
```

### Unified List Endpoint

Single endpoint returns catalog enriched with live status:

```python
@app.get("/api/integrations")
def list_integrations():
    results = []
    for intg in INTEGRATIONS_CATALOG:
        status = _get_integration_status(intg["id"])
        connected = status.get("authenticated", False) or status.get("connected", False)
        results.append({**intg, "connected": connected})
    return results
```

### Action Endpoints

```python
@app.post("/api/integrations/{id}/connect")
def connect_integration(id: str):
    if id == "whatsapp-self":
        if not wa._ready:
            t = threading.Thread(target=_start_wa, daemon=True)
            t.start()
        return {"status": "starting", "redirect": "/api/whatsapp/link"}
    return {"status": "not_implemented"}

@app.post("/api/integrations/{id}/disconnect")
def disconnect_integration(id: str):
    if id == "whatsapp-self":
        wa._ready = False
        # Close browser page
        return {"status": "disconnected"}
    return {"status": "not_implemented"}
```

## Frontend Pattern

### renderIntegrations() — Page Shell

Renders the static page structure once. The `renderIntCards()` function handles dynamic content:

```javascript
async function renderIntegrations() {
    var cp = document.getElementById('centerPanel');
    cp.innerHTML =
        '<div class="page-title">Integrations</div>' +
        '<div class="page-subtitle">Connect your channels...</div>' +
        // Search bar
        '<div class="int-search-wrap">' +
            '<span class="int-search-icon">🔍</span>' +
            '<input type="text" id="intSearch" placeholder="Search..." oninput="renderIntCards()">' +
        '</div>' +
        // Category pills
        '<div class="int-categories">' +
            '<button class="int-cat-pill active" data-cat="all" onclick="filterIntCat(&#39;all&#39;)">All</button>' +
            '<button class="int-cat-pill" data-cat="messaging" onclick="filterIntCat(&#39;messaging&#39;)">Messaging</button>' +
            // ... more pills
        '</div>' +
        '<div id="intCardsContainer"></div>' +
        '<div id="intEmpty" class="int-empty hidden">No integrations match.</div>';
    renderIntCards();
}
```

### renderIntCards() — Dynamic Card Rendering

Fetches from API, filters by search + category, renders cards grouped by category:

```javascript
async function renderIntCards() {
    var query = (document.getElementById('intSearch')?.value || '').toLowerCase();
    var r = await fetch('/api/integrations');
    var integrations = r.ok ? await r.json() : [];

    var html = '';
    var total = 0;
    var catKeys = ['messaging', 'phone', 'productivity'];

    for (var ci = 0; ci < catKeys.length; ci++) {
        var cat = catKeys[ci];
        if (filterCat !== 'all' && filterCat !== cat) continue;

        var catInts = integrations.filter(function(ix) { return ix.category === cat; });
        if (query) {
            catInts = catInts.filter(function(ix) {
                return ix.name.toLowerCase().indexOf(query) >= 0 ||
                       ix.subtitle.toLowerCase().indexOf(query) >= 0 ||
                       ix.description.toLowerCase().indexOf(query) >= 0;
            });
        }
        if (catInts.length === 0) continue;
        total += catInts.length;

        html += '<div class="int-category">';
        html += '<div class="int-category-title">' + cats[cat] + '</div>';

        for (var i = 0; i < catInts.length; i++) {
            var ix = catInts[i];
            html += '<div class="int-card' + (ix.coming_soon ? ' coming-soon' : '') + '">';
            html += '  <div class="int-card-icon" style="background:' + ix.icon_bg + '">' + ix.icon + '</div>';
            html += '  <div class="int-card-body">';
            html += '    <div class="int-card-name">' + ix.name + '<span class="int-card-subtitle">' + ix.subtitle + '</span></div>';
            html += '    <div class="int-card-desc">' + ix.description + '</div>';
            html += '  </div>';
            html += '  <div class="int-card-actions">';
            html += '    ' + getBadgeHtml(ix);
            html += '    <label class="toggle' + (ix.coming_soon ? ' coming-soon' : '') + '">';
html += '      <input type="checkbox" data-id="' + ix.id + '"' + (ix.connected ? ' checked' : '') + (ix.coming_soon ? ' disabled' : '') + ' onchange="toggleIntegration(this)">' +
            html += '      <span class="toggle-slider"></span>';
            html += '    </label>';
            html += '  </div>';
            html += '</div>';
        }
        html += '</div>';
    }
    container.innerHTML = html;
}
```

### Toggle Switch — CSS-Only Visual

No JS needed for the visual slider. Pure CSS checkbox hack:

```css
.toggle { position: relative; width: 44px; height: 24px; cursor: pointer; }
.toggle input { opacity: 0; width: 0; height: 0; }
.toggle-slider {
    position: absolute; inset: 0;
    background: #D0D0D5; border-radius: 12px;
    transition: all 0.2s;
}
.toggle-slider::before {
    content: '';
    position: absolute; width: 18px; height: 18px;
    left: 3px; bottom: 3px;
    background: #fff; border-radius: 50%;
    transition: all 0.2s;
    box-shadow: 0 1px 3px rgba(0,0,0,0.15);
}
.toggle input:checked + .toggle-slider { background: #111; }
.toggle input:checked + .toggle-slider::before { transform: translateX(20px); }
.toggle.loading { opacity: 0.6; pointer-events: none; }
```

### Toggle Integration — Connect/Disconnect API

**⚠️ SECURITY NOTE: Never pass integration IDs through Python string interpolation for inline `onchange` handlers.** Python triple-quoted strings (`"""..."""`) consume `\'` → bare `'` breaks JS, and `\\'` → `\'` which JS reads as an escaped quote. Use `data-*` attributes + `el.dataset.id` instead.

```javascript
// CORRECT: uses el.dataset.id — no quoting hell
async function toggleIntegration(el) {
    var id = el.dataset.id;
    if (!id) return;
    var label = el.closest('.toggle');
    label.classList.add('loading');

    try {
        if (el.checked) {
            var r = await fetch('/api/integrations/' + id + '/connect', { method: 'POST' });
            var data = await r.json();
            if (data.redirect) window.open(data.redirect, '_blank');
        } else {
            await fetch('/api/integrations/' + id + '/disconnect', { method: 'POST' });
        }
        setTimeout(renderIntCards, 1000);  // Re-render with fresh status
    } catch(e) {
        el.checked = !el.checked;  // Revert on failure
    }
    label.classList.remove('loading');
}
```

### Card-Body Click Delegation

Clicking anywhere on the card body (icon, name, description area) triggers the toggle — the card feels like one clickable unit. Uses a single delegated listener on the parent container:

```javascript
// Attached after the page nav listener, scoped to int-card elements
document.getElementById('centerPanel').addEventListener('click', function(e) {
    var card = e.target.closest('.int-card');
    if (!card) return;

    // Don't trigger if the click was on the toggle itself (checkbox already handles it)
    if (e.target.closest('.toggle')) return;
    // Don't trigger on disabled/coming-soon cards
    if (card.classList.contains('coming-soon')) return;

    // Find the toggle checkbox inside the card and click it
    var toggle = card.querySelector('.toggle input[type="checkbox"]');
    if (toggle) {
        toggle.checked = !toggle.checked;
        // Dispatch change event so toggleIntegration fires
        toggle.dispatchEvent(new Event('change'));
    }
});
```

**Why this pattern works:**
- No inline onclick handlers needed for card body — the `int-card` class becomes the trigger surface
- `closest('.int-card')` handles clicks on any descendant within the card
- Excluding `.toggle` prevents double-triggering when the user clicks the actual toggle switch
- `dispatchEvent(new Event('change'))` fires the native `onchange` handler programmatically
- The card feels clickable without duplicating event logic

### Category Filtering

**⚠️ Escaping note:** When rendering filter pill onclick handlers from Python `"""` strings, `\'` gets eaten by Python. Use `&#39;` HTML entities instead:

```python
# CORRECT: HTML entities bypass Python string escaping
onclick="filterIntCat(&#39;all&#39;)"

# WRONG: Python eats the backslash, output becomes filterIntCat('all') which breaks single-quoted JS string
'onclick="filterIntCat(\\'all\\')"'
```

```javascript
var INT_CAT_FILTER = 'all';

function filterIntCat(cat) {
    INT_CAT_FILTER = cat;
    var pills = document.querySelectorAll('.int-cat-pill');
    for (var i = 0; i < pills.length; i++) {
        pills[i].classList.toggle('active', pills[i].dataset.cat === cat);
    }
    renderIntCards();
}
```

### Auto-Polling

```javascript
// Poll every 5 seconds while on the integrations page
setInterval(function() {
    var container = document.getElementById('intCardsContainer');
    if (container && container.innerHTML.length > 0) {
        renderIntCards();
    }
}, 5000);
```

## CSS Architecture for Integrations Page

Add all integration-specific CSS in the main `<style>` block alongside other dashboard styles. Key classes:

| Class | Purpose |
|-------|---------|
| `.int-search-wrap` | Wrapper for search input with icon |
| `.int-search-icon` | Absolute-positioned 🔍 icon |
| `.int-categories` | Flex row of filter pills |
| `.int-cat-pill` | Individual category filter button |
| `.int-cat-pill.active` | Active pill (black bg, white text) |
| `.int-category` | Section wrapper for one category |
| `.int-category-title` | Uppercase category heading |
| `.int-card` | Integration card (flex row) |
| `.int-card.coming-soon` | Greyed-out card |
| `.int-card-icon` | Colored icon square (44x44, rounded) |
| `.int-card-body` | Name + description (flex: 1) |
| `.int-card-actions` | Badge + toggle (flex-shrink: 0) |
| `.int-badge` | Status badge |
| `.int-badge.connected` | Green badge |
| `.int-empty` | No-results state |

## Pitfalls

- **Toggle state must revert on API failure** — If the connect/disconnect API errors, the checkbox should revert to its previous state. Always wrap in try/catch with `el.checked = !el.checked` in the catch block.
- **Search input fires renderIntCards on every keystroke** — The `oninput` handler is instant. For the ARA dashboard this is fine (< 12 integrations). For larger catalogs (50+ items), debounce the input at ~150ms.
- **Category pills must re-render on filter change** — `filterIntCat()` calls `renderIntCards()` which fetches fresh data from the API. Don't cache the integration list client-side if status changes are expected (e.g., WhatsApp connects while the page is open).
- **Auto-polling interval** — 5 seconds is aggressive. Reduce to 10-15s for production. The short interval is useful during development to catch connection state changes immediately.
- **Modular $ vs single var** — The frontend uses `var` (not `const`/`let`) for maximum browser compatibility with the embedded HTML string pattern. This is intentional — the code is embedded in a Python string and served to any browser.
