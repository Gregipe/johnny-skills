# SVG Channel Icons — ARA Production UI Pattern

When rendering channel chips or step-row channel indicators in production UI, use colored icon wraps with inline SVGs. Emoji are acceptable for mockups and rapid prototypes only — always swap to SVGs before shipping.

## Icon Wrap Pattern

Each channel gets a colored rounded-square background with a white SVG inside:

```css
.ch-icon-wrap {
  width: 24px; height: 24px; border-radius: 6px;
  display: inline-flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.ch-icon-wrap.whatsapp { background: #25D366; }
.ch-icon-wrap.email { background: #3B82F6; }
.ch-icon-wrap.call { background: #6366F1; }
.ch-icon-wrap.sms { background: #9CA3AF; }
.ch-icon-wrap svg { width: 14px; height: 14px; fill: white; }
```

For channel chips (larger, pill-shaped buttons):
```css
.channel-chip .ch-icon-wrap { width: 18px; height: 18px; border-radius: 5px; }
.channel-chip .ch-icon-wrap svg { width: 12px; height: 12px; }
```

For step rows (inline, next to channel name):
```css
.step-row .step-channel { display: flex; align-items: center; gap: 6px; }
.step-row .step-channel .ch-icon-wrap { width: 24px; height: 24px; border-radius: 6px; }
.step-row .step-channel .ch-icon-wrap svg { width: 14px; height: 14px; }
.step-row .step-channel .ch-name { font-size: 12px; font-weight: 500; color: #111111; }
```

## SVG Strings (16x16 viewBox)

### WhatsApp (green circle with white phone receiver)
```html
<svg viewBox="0 0 16 16"><path d="M8 1C4.1 1 1 4.1 1 8c0 1.5.5 2.9 1.4 4L2 14l2.1-.6c1.1.6 2.4 1 3.9 1 3.9 0 7-3.1 7-7s-3.1-7-7-7zm3.5 10.1c-.1.4-.6.8-1.1.9-.5.1-1 .2-2-.3-1.2-.6-2.3-1.7-3-3-.3-.6-.3-1.1-.2-1.4.1-.2.2-.3.4-.4h.4c.1 0 .3 0 .4.3l.5 1.2c0 .1 0 .2-.1.3l-.3.4c-.1.1-.1.2 0 .3.3.6.8 1.1 1.3 1.4.1.1.2.1.3 0l.4-.3c.1-.1.3-.1.4-.1s.3.1.5.2l1.1.5c.1.1.2.2.2.3z" fill="white"/></svg>
```

### Email (blue envelope)
```html
<svg viewBox="0 0 16 16"><rect x="2" y="3.5" width="12" height="9" rx="1.5" fill="none" stroke="white" stroke-width="1.2"/><path d="M2 5l6 4.5L14 5" fill="none" stroke="white" stroke-width="1.2"/></svg>
```

### Call (indigo phone handset)
```html
<svg viewBox="0 0 16 16"><path d="M3.5 2.5c0-.6.4-1 1-1h1c.5 0 .9.4 1 1 0 0 .5 3 2 4.5s4.5 2 4.5 2c.6.1 1 .5 1 1v1c0 .6-.4 1-1 1C9.5 12 6 11 4.5 9.5S3 5.5 3.5 2.5z" fill="none" stroke="white" stroke-width="1.2"/></svg>
```

### SMS (gray chat bubble)
```html
<svg viewBox="0 0 16 16"><path d="M2 3h12a1 1 0 011 1v7a1 1 0 01-1 1H5l-3 2V4a1 1 0 011-1z" fill="none" stroke="white" stroke-width="1.2"/></svg>
```

## Usage in HTML (channel chips)

```html
<div class="channel-chip" draggable="true" data-channel="whatsapp">
  <span class="ch-icon-wrap whatsapp">
    <svg viewBox="0 0 16 16"><path d="M8 1C4.1..." fill="white"/></svg>
  </span>
  WhatsApp
</div>
```

## Usage in JavaScript (step row rendering)

Define a `CHANNEL_ICONS` object so you can reference icons by channel name:

```javascript
var CHANNEL_ICONS = {
  whatsapp: '<span class="ch-icon-wrap whatsapp"><svg viewBox="0 0 16 16"><path d="M8 1C4.1..." fill="white"/></svg></span>',
  email: '<span class="ch-icon-wrap email"><svg viewBox="0 0 16 16">...</svg></span>',
  call: '<span class="ch-icon-wrap call"><svg viewBox="0 0 16 16">...</svg></span>',
  sms: '<span class="ch-icon-wrap sms"><svg viewBox="0 0 16 16">...</svg></span>'
};

// In step row:
div.innerHTML = '<div class="step-channel">' + (CHANNEL_ICONS[step.channel] || '') + '<span class="ch-name">' + name + '</span></div>';
```

## Anti-patterns

- Don't use emoji (💬 📧 📞 ✉️) for channel icons in production UI — Greg will flag them as "ugly"
- Don't use inline SVG stroke colors other than white — the colored background wrap supplies the brand color
- Don't mix icon sizes — chips use 18px wraps, step rows use 24px wraps
