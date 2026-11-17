# Brand Extraction (programmatic, no guessing)

How to pull a client's exact colors, logo, and fonts from their live site so a re-brand is faithful rather than "close enough".

## 1. Computed styles via `browser_console`

`web_extract` gives copy but not color. Use `browser_navigate` to the client's site, then `browser_console` with a `getComputedStyle` scan. Example that found Mondelez's brand:

```js
(() => {
  const out = {};
  const el = document.querySelector('header') || document.querySelector('nav') || document.body;
  const cs = getComputedStyle(el);
  out.headerBg = cs.backgroundColor;
  out.headerColor = cs.color;
  // dominant purple-ish colors (b > r+30 && b > g+10)
  const purples = new Set();
  document.querySelectorAll('*').forEach(el => {
    ['color','backgroundColor','borderColor'].forEach(p => {
      const m = getComputedStyle(el)[p].match(/rgb\(\s*(\d+),\s*(\d+),\s*(\d+)/);
      if (m) { const [r,g,b]=[m[1],m[2],m[3]].map(Number); if (b>100 && b>r+30 && b>g+10) purples.add(getComputedStyle(el)[p]); }
    });
  });
  out.purpleColors = [...purples].slice(0,12);
  const logo = document.querySelector('header img, nav img, [class*="logo"] img, a img');
  out.logoSrc = logo ? logo.src : null;
  const fonts = new Set();
  document.querySelectorAll('h1,h2,h3,body').forEach(el => fonts.add(getComputedStyle(el).fontFamily.split(',')[0]));
  out.fonts = [...fonts].slice(0,8);
  const link = document.querySelector('a');
  out.linkColor = link ? getComputedStyle(link).color : null;
  return JSON.stringify(out, null, 1);
})()
```

Mondelez result: purple `rgb(79, 33, 112)` = `#4F2170`, link color identical, fonts Calibri / "MDLZ BITE TYPE", logo hosted on Contentful.

## 2. Logo pixel color (decides sidebar theme)

The logo image is often a white or colored wordmark. Measure its visible-pixel mean before choosing light vs dark sidebar. Use `sips` to convert, then parse BMP with stdlib `struct` — no PIL dependency (PIL on this Mac had an arm64/x86_64 arch mismatch, so avoid it):

```bash
curl -sL -o /tmp/logo.png "<logo URL>"
sips -s format png /tmp/logo.png --out /tmp/logo-conv.png >/dev/null 2>&1
sips -s format bmp /tmp/logo-conv.png --out /tmp/logo.bmp >/dev/null 2>&1
```

```python
import struct
data = open('/tmp/logo.bmp','rb').read()
off = struct.unpack('<I', data[10:14])[0]
w = struct.unpack('<i', data[18:22])[0]
h = struct.unpack('<i', data[22:26])[0]
bpp = struct.unpack('<H', data[28:30])[0]
abs_h = abs(h); rs=gs=bs=n=0
row_size = ((bpp*w + 31)//32)*4
for y in range(abs_h):
    base = off + y*row_size
    for x in range(w):
        p = data[base + x*(bpp//8): base + x*(bpp//8) + (bpp//8)]
        b,g,r = p[0],p[1],p[2]; a = p[3] if bpp==32 else 255
        if a > 100: rs+=r; gs+=g; bs+=b; n+=1
print('mean RGB:', (rs//n, gs//n, bs//n))
print('DARK logo' if (rs+gs+bs)//n < 450 else 'LIGHT logo')
```

Rule of thumb: mean < 450 → dark/colored logo (use a light sidebar); ≥ 450 → white logo (use a dark sidebar). Mondelez's logo measured (254,254,254) — white — so a purple sidebar was correct despite the purple brand.
