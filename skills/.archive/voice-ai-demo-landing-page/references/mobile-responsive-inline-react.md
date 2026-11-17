# Mobile-Responsive Single-File React (inline styles, no build step)

These Hunar demo pages are one `public/index.html` with CDN React 18 + Babel
standalone — inline `style={{...}}` objects, no CSS file. Making them responsive
means a JS `isMobile` flag, not media queries.

## The `isMobile` hook

```js
const[isMobile,setIsMobile]=useState(false);
useEffect(()=>{
  const mq=window.matchMedia("(max-width: 768px)");
  const upd=()=>setIsMobile(mq.matches);
  upd();
  mq.addEventListener("change",upd);
  return()=>mq.removeEventListener("change",upd);
},[]);
```

Then conditionally branch every layout-relevant style, e.g.:

```js
// root: column on mobile, row on desktop; dvh on mobile (iOS URL-bar jump)
<div style={{display:"flex",flexDirection:isMobile?"column":"row",
             height:isMobile?"100dvh":"100vh",width:"100vw",overflow:"hidden"}}>

// sidebar -> compact top bar on mobile
<div style={{width:isMobile?"100%":260,minWidth:isMobile?0:260,
             background:PURPLE,display:"flex",
             flexDirection:isMobile?"row":"column",
             alignItems:isMobile?"center":"stretch",flexWrap:isMobile?"wrap":"nowrap"}}>
```

## The big pitfall: gate `display:"flex"` to mobile only

These pages were authored as **block** layout on desktop. The mobile top bar is
the only place that wants flex. Writing `display:"flex"` (or `flexDirection:"row"`)
*unconditionally* regresses desktop in two specific, easily-missed ways:

1. **Nav container made flex-row → buttons balloon to full height.**
   The `<nav>` has `flex:1` inside the sidebar column, so it has a definite
   height on desktop. When it became `display:flex;flexDirection:row`, its button
   children (default `align-items:stretch`, each `width:"100%"`) stretched to fill
   that fixed cross-size → buttons measured **220px tall** (vs ~42px). "The
   application box is now very big." Fix: `display:isMobile?"flex":"block"`.

2. **Logo block made flex → wordmark squished + caption moves beside it.**
   The logo `<div>` (img + "Powered by Hunar.ai" `<p>`) became `display:flex` with
   `alignItems:center`, so the `<p>` sat *beside* the `<img>` instead of below, and
   the `<img>` (width auto, flex-shrink default 1) got compressed → the Mondelez
   wordmark image looked "distorted". Fix: `display:isMobile?"flex":"block"`.

Rule of thumb: **every flex/flexDirection/alignItems/flexWrap added for the mobile
top bar gets `isMobile?...:"block"` (or the desktop original), never a bare `flex`.**

## Debugging layout regressions with the browser console (not vision)

The auxiliary vision model may refuse/fail to analyze a screenshot. DOM measurement
is deterministic and faster. In `browser_console` (expression):

```js
(() => {
  const purple = [...document.querySelectorAll('div')]
    .find(d => d.style.background === 'rgb(79, 33, 112)');   // sidebar
  const r = n => n ? {w: Math.round(n.getBoundingClientRect().width),
                      h: Math.round(n.getBoundingClientRect().height)} : null;
  const nav = purple.querySelector('nav');
  const btns = [...nav.querySelectorAll('button')].map(b => ({label:b.textContent.trim(), box:r(b)}));
  const img = purple.children[0].querySelector('img');
  const p = purple.children[0].querySelector('p');
  return JSON.stringify({
    sidebar: r(purple),
    navDisplay: getComputedStyle(nav).display,
    buttons: btns,                                              // watch h: ~220 = flex-leak bug
    logoBlockDisplay: getComputedStyle(purple.children[0]).display,
    poweredByBesideOrBelow: p.getBoundingClientRect().top >= img.getBoundingClientRect().bottom - 5 ? 'BELOW' : 'BESIDE',
    noHOverflow: document.documentElement.scrollWidth <= window.innerWidth,
  });
})()
```

**Image-distortion check** — confirm an `<img>` with `height` set and `width:auto`
is at its intrinsic ratio, not flex-shrunk:

```js
img.naturalWidth / img.naturalHeight          // aspect
Math.round(img.style.height.replace('px','') * img.naturalWidth / img.naturalHeight)
  === Math.round(img.getBoundingClientRect().width)   // true = undistorted
```

**Simulating a mobile viewport**: the browser tool's viewport is fixed; you can't
easily force `matchMedia('(max-width:768px)').matches` true after mount (the hook
captures the original `MediaQueryList`). Rely on: (a) the desktop path rendering
with zero JS errors (proves every ternary evaluates), and (b) the user's phone as
the true mobile check. Structural DOM measurement covers desktop regression risk.
