# Auto-Growing Textarea in Flex Layout

Implementing a `<textarea>` that grows vertically as the user types, inside a flex container with fixed-height siblings (icon buttons).

## The Problem

An `<input type="text">` is inherently single-line — it cannot wrap or grow. Switching to `<textarea>` introduces flex layout conflicts:

- `display: flex; align-items: center` on the parent container forces the textarea's height to match the tallest sibling (the fixed 32px buttons)
- CSS `height` property is overridden by the flex layout's computed height
- `el.style.height = el.scrollHeight + 'px'` in JS has no visible effect because flex wins

## The Fix

### HTML

```html
<textarea placeholder="Type here..." id="chatInput"
  onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendMsg();}"
  oninput="autoGrowChatInput(this)" rows="1"></textarea>
```

- `rows="1"` — initial single-line height
- `Enter` submits (prevented via `event.preventDefault()` so no newline is inserted)
- `Shift+Enter` inserts a newline (bypasses the submit)
- `oninput="autoGrowChatInput(this)"` — fires on every keystroke and paste

### CSS

```css
.chat-input-wrap {
  display: flex;
  align-items: center;   /* centers buttons vertically */
  gap: 8px;
}

/* Shared: input + textarea get the same base styles */
.chat-input-wrap input,
.chat-input-wrap textarea {
  border: none;
  background: transparent;
  font-size: 13px;
  font-family: inherit;
  color: #111111;
  outline: none;
}

/* Textarea-specific: prevent flex from controlling height */
.chat-input-wrap textarea {
  resize: none;
  min-height: 20px;
  max-height: 50vh;          /* cap before it fills the screen */
  padding: 0;
  line-height: 1.5;
  overflow-y: auto;          /* scroll when content exceeds max-height */
  white-space: pre-wrap;     /* preserve whitespace, wrap normally */
  word-wrap: break-word;     /* break long words/URLs */
  width: 100%;
  box-sizing: border-box;
  align-self: flex-start;    /* ← CRITICAL: prevents flex from stretching height */
  flex-grow: 1;              /* fills horizontal space */
}
```

**Key CSS rules:**
1. `align-self: flex-start` — overrides the flex parent's `align-items: center` for this item only. Flex no longer controls the textarea's height.
2. `flex-grow: 1` — ensures the textarea fills the remaining horizontal width (since `flex: 1` was removed to avoid height conflicts).
3. `box-sizing: border-box` + `width: 100%` — reliable width calculation.

### JavaScript — The `cssText` Approach

Setting individual `el.style.height` properties in a flex context can silently fail — flex can override inline `height` because of the way style resolution works in multi-layer flex containers. The most reliable approach is to use `el.style.cssText` which resets ALL inline styles at once:

```javascript
function autoGrowChatInput(el) {
  el.style.cssText = 'height:auto;overflow:hidden';  // reset everything at once
  var h = el.scrollHeight;                            // read true content height
  var maxH = Math.round(window.innerHeight * 0.5);    // 50% of viewport height

  if (h > maxH) {
    el.style.cssText = 'height:' + maxH + 'px;overflow-y:auto';  // cap + scroll
  } else {
    el.style.cssText = 'height:' + Math.max(20, h) + 'px;overflow:hidden';  // fit content
  }
}
```

**Why `cssText` is essential:** In a flex context (`display: flex; align-items: center`), setting `el.style.height = 'auto'` then `el.style.height = sh + 'px'` can produce no visible effect because:
- The browser's style resolution may block intermediate reflows between the two property sets
- Flex layout's `align-items: center` may override the inline `height` if `align-self` isn't set correctly
- Using `cssText` forces the element to evaluate all style rules at once, breaking through flex's override

**The `overflow: hidden` pitfall:** When a textarea has `overflow: hidden` (or any overflow state), the browser may clip `scrollHeight` to the visible area when the element has an explicit `height` set. The sequence matters:
1. First set `cssText = 'height:auto;overflow:hidden'` — this resets the height to auto (letting the content determine size) while keeping overflow hidden
2. Now `scrollHeight` reflects the TRUE content height, not the clipped height
3. Then set the final height based on true content

**Why NOT `height: '0px'` first:** Setting height to `'0px'` before reading scrollHeight can return a value that's too small when overflow is hidden, because the browser doesn't expand the content beyond zero height. Always reset to `'auto'` first (via `cssText`), THEN read scrollHeight.

### Max-height handled in JS, not CSS

The max-height limit (50% of viewport) is enforced in JavaScript, not via CSS `max-height`. This avoids the `max-height` vs inline `height` CSS priority conflict — `max-height` always overrides inline `height`, so if the CSS says `max-height: 50vh` and JS says `height: 2000px`, the element stays at 50vh. By handling the cap in JS, the CSS can be simpler with no max-height:

```css
.chat-input-wrap textarea {
  /* no max-height — JS handles it */
  min-height: 20px;
}
```

### Send handler (reset on submit) — use cssText

```javascript
function sendMsg() {
  var inp = document.getElementById('chatInput');
  var text = inp.value.trim();
  if (!text) return;
  inp.value = '';
  inp.style.cssText = 'height:20px;overflow:hidden';
  sendChatMsg(text);
}
```

Use `cssText` here too for the same reason: `inp.style.height = '20px'` alone might not take effect if flex is fighting it. `cssText` resets ALL inline styles in one shot.

## Pitfalls

- **Browser caching** — CSS and JS changes to static files served by FastAPI's `StaticFiles` mount are aggressively cached. Bump `?v=N` on the `<script>` tag after every deployment. Without it, users see the old `<input>` behavior despite the server having the new code.
- **`rows="1"` is not a CSS property** — it's an HTML attribute that sets the initial number of visible text lines. Without it, the textarea defaults to 2 rows in most browsers.
- **Flex `align-items: center` vs `align-self: flex-start`** — The parent uses `align-items: center` to vertically center the icon buttons. The textarea needs `align-self: flex-start` to escape this. Without it, the textarea is forced to the button height (32px) and never grows.
- **`overflow-y: auto` on a textarea** — adds a scrollbar when content exceeds `max-height`. Without `overflow-y: auto`, content continues to grow past `max-height` (hidden overflow in some browsers) or clips without indication.
- **Sibling subagent conflicts** — When multiple agent sessions modify the same file concurrently (common during deployment), `file was modified by sibling subagent` warnings appear. Always re-read the file before writing if this warning fires.
