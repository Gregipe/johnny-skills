# Standalone Page Layout & Sidebar Consistency

ARA has two types of pages: **SPA pages** (inside the dashboard `/` route, swapped via `showPage()`) and **standalone pages** (separate routes: `/cadence`, `/threads`).

## The Rule

**All standalone pages must share the exact same sidebar as the dashboard SPA.** Every nav item, the same order, the same icons, the same click targets. The only difference: the active item is highlighted per page.

## Sidebar Template (copy-paste for new standalone pages)

```html
<div class="sidebar-nav">
  <div class="nav-item" onclick="window.location='/'"><span class="icon">🏠</span> Dashboard</div>
  <div class="nav-item" onclick="window.location='/leads'"><span class="icon">👤</span> Leads</div>
  <div class="nav-item" onclick="window.location='/'"><span class="icon">💰</span> Deals</div>
  <div class="nav-item active"><span class="icon">💬</span> Threads</div>  <!-- ← active per page -->
  <div class="nav-item" onclick="window.location='/cadence'"><span class="icon">📡</span> Outbound Cadence</div>
  <div class="nav-item" onclick="window.location='/dashboard#knowledge'"><span class="icon">📚</span> Knowledge</div>
  <div class="nav-item" onclick="window.location='/dashboard#induction'"><span class="icon">🧠</span> Induction</div>
  <div class="nav-item" onclick="window.location='/dashboard#integrations'"><span class="icon">🔌</span> Integrations</div>
</div>
```

All 8 items must be present. Do not add/remove items per page — the sidebar is global.

## Nav Link Convention

| Target type | Link pattern | Example |
|------------|-------------|---------|
| Dashboard SPA root | `window.location='/'` | Dashboard, Deals |
| Standalone page | `window.location='/pagename'` | Leads*, Threads, Cadence |
| SPA internal page (Knowledge, Induction, Integrations) | `window.location='/dashboard#pagename'` | Knowledge, Induction, Integrations |

*\*Leads route now redirects to `/` via server.py — use `window.location='/leads'` in sidebar for async navigation feel, the server redirects to dashboard.*

## CSS Setup for Standalone Pages

All standalone pages need these CSS blocks (same as dashboard):

```css
/* ── Sidebar (ARA light gray) ── */
.sidebar{width:240px;min-width:240px;background:#F5F5F7;display:flex;flex-direction:column;border-right:1px solid #E5E5E7;height:100vh}
.sidebar-header{padding:20px 16px 12px;border-bottom:1px solid #E5E5E7;display:flex;align-items:center;gap:12px}
.sidebar-logo{width:36px;height:36px;background:#111111;border-radius:10px;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;color:white;flex-shrink:0}
.sidebar-title{font-size:13px;font-weight:600;line-height:1.3}
.sidebar-title span{font-weight:400;color:#6E6E73;font-size:11px}
.sidebar-nav{padding:12px 8px;flex:1}
.nav-item{display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:8px;font-size:13px;font-weight:500;color:#111111;cursor:pointer;transition:all .15s;text-decoration:none}
.nav-item:hover{background:#E8E8ED}
.nav-item.active{background:#E0E0E5;color:#111111;font-weight:600}
.nav-item .icon{font-size:16px;width:20px;text-align:center;flex-shrink:0}
```

## App Container

The layout structure for all standalone pages:

```html
<div class="app">
  <div class="sidebar">...</div>
  <div class="center">...</div>       <!-- or chat-panel if two-panel layout -->
  <div class="chat-panel">...</div>   <!-- only if Ava chat needed -->
</div>
```

`.app` is always `display:flex; height:100vh`.

## Ava Chat Panel on Standalone Pages

When a standalone page includes the Ava chat panel (like Threads), it must match the dashboard's chat panel exactly:

- **Gear icon** (`⚙️`) with `onclick="toggleAvaSettings()"` — same settings panel (tone, auto-assign, daily touches, localStorage)
- **Suggestions chips** — same 3 (Summarize, Next action, Last activity)
- **Input** — `placeholder="Coach Ava, ask a question..."`, `sendMsg()` on Enter
- **Send button** — `→`, disabled when no thread selected
- **Context bar** — `#threadContext` above messages, shows thread summary

Copy the full Ava settings JS functions (`toggleAvaSettings`, `loadAvaSettings`, `saveAvaSettings`) — they're identical across pages.

## Pitfalls

- **Missing nav items** — Most common mistake: forgetting Knowledge, Induction, or Integrations. Every standalone page must have all 8 nav items.
- **SPA links on standalone pages** — Can't use `showPage('knowledge')` from a standalone page — those functions only exist in the dashboard SPA. Use hash routing (`/dashboard#knowledge`) instead.
- **Different sidebar CSS** — The standalone page sidebar CSS must match the dashboard sidebar exactly. Slight differences in padding, gap, font-size, or colors are immediately visible.
- **Hash route timeout** — The dashboard's hash routing polls for 5s max. If the dashboard takes longer to load, the hash route silently fails. Consider increasing the timeout or adding a loading message.
- **Active nav item** — Only ONE nav item should have `class="nav-item active"` per page. On the threads page, Threads is active. On the cadence page, Outbound Cadence is active. Don't add the active class to any other item.
- **`/leads` redirect** — The standalone `/leads` page was replaced with a redirect to `/`. The sidebar nav for Leads should use `window.location='/leads'` which triggers the redirect to dashboard. This feels instant to the user.
