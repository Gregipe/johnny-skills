---
name: static-web-tools
description: "Build and ship single-file static web tools to Cloudflare."
version: 1.0.0
author: Johnny
license: MIT
metadata:
  hermes:
    tags: [static, cloudflare-workers, calculator, microsite, deploy, hunar]
    category: deployment
    related_skills: [voice-ai-demo-landing-page]
---

# Static Web Tools Skill

Build and ship small, single-file, no-backend web tools (ROI calculators, microsites,
landing pages) for Greg to a public Cloudflare Workers URL. No build step, no framework —
vanilla HTML/CSS/JS in one `index.html`, pure logic split into a testable ESM module.

This is the *static* sibling of `voice-ai-demo-landing-page` (which is the API-backed,
call-triggering demo variant). Both share the Cloudflare Workers static-assets deploy path.

## When to Use

- Greg asks for a public calculator, estimator, or microsite ("a simple URL where people can…").
- Any single-page tool whose only dependency is client-side JS (no secrets, no server).
- Branding or re-branding one of these pages in Hunar colors.

## Prerequisites

- Node 22 + `npx` (wrangler runs via `npx --yes wrangler …` — no global install).
- A Cloudflare account already OAuth-authenticated via wrangler on Greg's machine
  (see `references/hunar-brand.md` for the account). Verify with `npx --yes wrangler whoami`.
- **Do not assume `gh`/git push works** — `gh` is not installed and the local SSH key is not
  registered on GitHub. Cloudflare Workers is the zero-auth deploy path for Greg's public tools.

## Quick Reference

| What | Where |
|------|-------|
| Project shape | `public/index.html` + `public/<name>.js` (ESM logic) + `src/index.js` (passthrough worker) + `wrangler.jsonc` |
| Deploy | `cd <dir> && npx --yes wrangler deploy` → prints `https://<name>.gregipe-efb.workers.dev` |
| Local test | `npx --yes wrangler dev --port 8787` (background) → `lsof -nP -iTCP:8787 -sTCP:LISTEN` + `curl` |
| Math verification | `node test.mjs` against `public/<name>.js` exports (before wiring UI) |
| Hunar brand | `#006EDD` primary, `#369BFF` light, `#121212` ink, `#FAFAF9` canvas (see `references/hunar-brand.md`) |
| Break-even model | formulas + verified baseline in `references/roi-break-even-model.md` |

## Procedure

1. **Separate logic from UI.** Put the pure math in `public/<name>.js` as ESM
   (`export function compute(inputs)` + `export const inr/pct/mult` formatters). The page
   imports it as `<script type="module">`. This is what makes the math unit-testable in Node.
2. **Unit-test the math before touching the UI.** Write `test.mjs` that imports the module and
   asserts the known-good numbers (e.g. reproduce the source spreadsheet exactly) plus edge
   cases (divide-by-zero guards, degenerate-but-valid inputs). Run `node test.mjs`. Fix the
   math here — it is far cheaper than debugging rendered numbers in the browser.
3. **Build `public/index.html`** with the 4-file Cloudflare shape:
   - `wrangler.jsonc`: `name`, `compatibility_date`, `main: src/index.js`, `assets: { directory: "public", binding: "ASSETS" }`, `compatibility_flags: ["nodejs_compat"]`.
   - `src/index.js`: `export default { async fetch(req, env) { try { return await env.ASSETS.fetch(req); } catch { return new Response("Not found", { status: 404 }); } } }`.
4. **Verify locally in a real browser.** `npx --yes wrangler dev --port 8787` in the background,
   confirm it serves with `lsof` + `curl -o /dev/null -w '%{http_code}'`, then
   `browser_navigate http://localhost:8787/` and use `browser_console` to assert the computed
   DOM values (`document.getElementById('o-before').textContent`) and `js_errors: []`. Test one
   interactivity flip (change an input, assert the verdict/target changes, restore).
5. **Deploy.** `npx --yes wrangler deploy`, then `curl` the live URL (200 + expected text) and
   `browser_navigate` the live URL to confirm the module loads over the network.
6. **Commit** locally (`git init && git add -A && git -c user.name=… -c user.email=… commit`).
   No remote — flag to Greg if he wants a GitHub mirror (needs auth setup).

## Pitfalls

- **`npx wrangler dev` runs silently.** First run can hang on the npx install prompt and even
  once up the console may print nothing. Always `npx --yes`, verify readiness with `lsof` +
  `curl`, never wait for a log line.
- **`&` in a shell heredoc trips the backgrounding guard.** Bitwise ops (`x & 255`) or any
  bare `&` in an inline `python3 - <<'EOF'` is rejected as backgrounding. Write the script to
  a file (`write_file`) and run `python3 file` — see `scripts/logo_palette.py`.
- **`gh` is not set up.** `gh: command not found` and SSH `Permission denied (publickey)` are
  the *current* state on Greg's machine. Route public micro-tools to Cloudflare Workers
  (wrangler OAuth already works) instead of GitHub Pages.
- **Framer sites return neutral computed styles.** `hunar.ai` `getComputedStyle` on buttons/
  headings yields browser-default blue and neutrals — the real brand color is in the logo PNG,
  which is an 8-bit colormap. Decode it with `scripts/logo_palette.py` (PIL is often broken on
  this box due to an arm64/x86_64 mismatch).
- **Public Google Sheets export via curl.** Append `/export?format=csv&gid=0` to the sheet URL.
  Non-existent gids return HTML (not CSV) — check `file`/first bytes before parsing.
- **Single-file edits: patch, don't hand-transcribe.** When restructuring a large `index.html`,
  do targeted `patch` operations on unique anchors (IDs) rather than rewriting the whole file —
  a full rewrite risks silently dropping a section.
- **Vision fallback may not attach screenshots** in some sessions; rely on `browser_console`
  DOM assertions for verification, not `browser_vision`/`vision_analyze` descriptions.

## Verification

- `node test.mjs` → all checks pass (sheet reproduction + lever sensitivity + edge cases).
- `browser_console` (no expression) → `js_errors: []`.
- Live `curl` → 200 + page contains the expected section headings and computed values.
