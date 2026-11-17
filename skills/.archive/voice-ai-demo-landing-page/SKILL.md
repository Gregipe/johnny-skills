---
name: voice-ai-demo-landing-page
description: "Re-brand a Hunar voice-AI demo landing page for a client."
version: 1.3.0
author: Greg Ipe
metadata:
  hermes:
    tags: [hunar, voice-ai, cloudflare-workers, demo, branding, react]
    category: deployment
---

# Voice-AI Demo Landing Page Skill

Hunar.ai client pitch demos are single-page apps where a visitor enters their name/number (plus optional fields), triggers a real Hunar voice-agent call to their own phone, and watches call progress live while results log to a Google Sheet. This skill covers the reference architecture and how to clone + re-brand an existing demo (e.g. Bajaj HF → Mondelez India) for a new client.

## When to Use

- Cloning an existing Hunar demo page for a new client / pitch
- Re-branding colors, logo, and copy on one of these pages
- Understanding or debugging the Worker proxy + Sheets logging layer

## Reference Architecture

Three real files + config:

- `public/index.html` — single-file React (CDN React 18 + Babel standalone, no build step). Three views: application form → call monitor → "About Hunar.ai".
- `src/index.js` — Cloudflare Worker. Proxies `/api/calls` (POST) and `/api/calls/:id` (GET) to the Hunar API with a server-side `X-API-Key`; `/api/log` (POST) appends a row to a Google Sheet via a service-account JWT; `/api/sheets/init` writes headers; everything else falls through to the `ASSETS` binding.
- `wrangler.jsonc` — worker `name`, assets binding, `nodejs_compat`.
- Secrets in `.dev.vars` (gitignored): `HUNAR_API_KEY`, `GOOGLE_SERVICE_ACCOUNT_JSON`.

See `references/hunar-api-and-sheet-logging.md` for the exact endpoints, JWT flow, and the 23-column sheet schema. See `references/hunar-agent-inspection.md` for how to inspect an agent's real identity (name / language / custom_variables) before writing copy or the `custom_data` payload. See `references/hunar-agent-update.md` for how to change an agent's `language`/`voice_persona` via PUT (full-payload requirement, OPTIONS discovery, test-call firing). See `references/cloudflare-deploy.md` for the production deploy — `wrangler login` OAuth gotchas, `secret put`, `deploy`, and read-only prod verification. See `references/mobile-responsive-inline-react.md` for making the single-file page responsive (the `isMobile` hook, the flex-leak pitfall, and DOM-measurement debugging).

## Prerequisites

- Node 22 + `npx` (wrangler runs via `npx wrangler dev` — no global install).
- The target client's agent UUID on Hunar's platform, or keep the previous UUID as a placeholder (see Pitfalls).
- Network for CDN React + the client's hotlinked logo.

## How to Re-brand (Procedure)

1. Clone full history: `git clone <existing-demo-repo> ~/<new-client>-voice-ai`.
2. Extract the client's real branding — see `references/brand-extraction.md`. Never guess colors; pull computed styles from their live site.
3. Decide the sidebar theme from the logo color: white logo → dark/purple sidebar; colored logo → light sidebar. Measure the logo's dominant pixel color before choosing.
4. Apply all string edits as ONE verified replacement script (see `references/verified-replacement-edit.md`), asserting each old-string count. Never hand-transcribe a ~36 KB single-file React page.
5. Keep the previous agent UUID with a `// TODO: swap id ...` comment; update the worker name in `wrangler.jsonc`.
6. Run `CI=1 npx --yes wrangler dev --port 8787` (background), then confirm it actually serves via `curl -s -o /dev/null -w '%{http_code}' localhost:8787` and `lsof -nP -iTCP:8787 -sTCP:LISTEN`. Do NOT wait for a "Ready on http" log line — see Pitfalls.
7. Leave `src/index.js` logging target (`SHEET_ID` / range) as-is until the real agent is wired up — note it for the switch.

## Inspect the Agent Before Copy / Payload

The agent UUID is only half the story — the agent's *declared config* decides the
copy, the language, and the exact `custom_data` keys. Inspect it read-only before
finalizing any of them:

```bash
KEY=$(grep '^HUNAR_API_KEY=' .dev.vars | cut -d= -f2- | tr -d '"')
curl -s https://api.voice.hunar.ai/external/v1/agents/<UUID>/ -H "X-API-Key: $KEY"
```

The response's `name`, `summary`, `language`, and `custom_variables` are the source
of truth (see `references/hunar-agent-inspection.md`). Concretely this session: the
cloned page said "consumer conversations" / Hinglish / three `custom_data` keys, but
the agent was `"BDE - Assessment"` — a Mondelez India *Sales Officer* recruitment
agent, `language: ENGLISH`, expecting `custom_variables: ["first_name"]` only. Copy,
`AGENT.lang` + badge + details strip + monitor fallback, and `custom_data` all had to
change to match.

## Update the Agent (language / persona)

A demo's call language is set on the **agent**, not the page — flipping the page's
`AGENT.lang`/badge/strip alone does nothing if the agent still says `ENGLISH`.
Update via `PUT /agents/{uuid}/` (full-payload required — see
`references/hunar-agent-update.md`), then sync the page copy to match. Concretely
this session: flipped the agent `language` ENGLISH→HINDI via GET→modify→PUT→verify,
then changed the page's badge, description, details strip, and monitor fallback to
Hindi. The About-Hunar page's "Hinglish/Tanglish" mentions are *platform capability*
claims, not this agent's language — leave them alone.

## Changing the Collected Fields

Each client may want a different field set (e.g. Mondelez trimmed Bajaj's name/mobile/city/loan → name/mobile only). A field is referenced in **seven** places in `index.html` — edit all of them or the page breaks silently:

1. `const[form,setForm]=useState({...})` — initial state
2. `handleLogin` validation (`if(!form.x || ...)return;`)
3. `formValid` gating the Continue button
4. `handleLogout` reset (`setForm({...})`)
5. `triggerCall` → `custom_data:{...}` — what the agent actually receives
6. the two `/api/log` bodies (`{...latest, city:..., loan_amount_lakhs:...}`)
7. the form `<select>`/`<input>` JSX + the details-strip array (`{[[\"🏙️\",\"City\",user.city],...]}`)

Also delete the now-unused `CITIES` / `LOAN_AMOUNTS` consts. `custom_data` should carry **exactly** the variables the Hunar agent's prompt expects — `callee_name` + `mobile_number` are always sent top-level regardless; everything else is custom. Flag that a removed field (e.g. `city`) will arrive empty if the agent prompt still references it.

## Mobile Responsiveness

These pages are block-layout on desktop; only the mobile top bar wants flex. Use a
`isMobile` state driven by a `matchMedia("(max-width: 768px)")` listener, and gate
**every** flex/flexDirection/alignItems/flexWrap behind `isMobile?...:"block"` — a
bare `display:"flex"` regresses desktop (nav buttons ballooned to 220px tall via
`flex:1` stretch; the logo block pushed its caption beside the wordmark and
flex-shrunk the image). Full pattern + the DOM-measurement debugging recipe in
`references/mobile-responsive-inline-react.md`.

## Deploy to Cloudflare (Production)

A pitch demo needs a shareable `*.workers.dev` URL (which also sidesteps localhost
browser quirks). Sequence: `npx --yes wrangler login` (NOT `CI=1` — it kills the
OAuth flow) → `printf '%s' "$KEY" | wrangler secret put HUNAR_API_KEY` →
`wrangler deploy` → verify with a read-only `GET /api/calls/bogus` that returns
Hunar's 422 (proves the bound secret authenticates). Full detail + the
`invalid_state` / truncated-URL gotcha in `references/cloudflare-deploy.md`.

## Static (no-backend) variant + Greg's hosting default

For calculators, teasers, or any page with **no API proxy and no Google-Sheets
logging**, shrink `src/index.js` to a pure asset passthrough (no `HUNAR_API_KEY`,
no service-account secrets):

```js
export default { async fetch(request, env) {
  try { return await env.ASSETS.fetch(request); }
  catch (e) { return new Response("Not found", { status: 404 }); }
} };
```

Keep only `public/` + `wrangler.jsonc` (assets binding). Deploys with the same
`npx --yes wrangler deploy`; verify readiness with `curl`/`lsof`, never a log line
(see Pitfalls).

**Hosting default for Greg:** prefer **Cloudflare Workers** for static sites.
`wrangler` is already OAuth-authed on Greg's machine (account `gregipe@gmail.com`),
so `npx --yes wrangler deploy` works with zero setup and yields
`https://<name>.gregipe-efb.workers.dev`. GitHub Pages (`gregipe.github.io`) is the
alternative but needs the `gh` CLI (not installed) **plus** a GitHub-registered SSH
key — treat as a follow-up, not the default path.

**Business-logic pages:** put all math in a separate ESM module (e.g. `public/calc.js`
exporting `compute()`) that `index.html` imports *and* a Node `test.mjs` imports
directly — verify the model reproduces known source numbers (e.g. the originating
spreadsheet) with `node test.mjs` before shipping. Catches arithmetic drift a visual
check misses.

**Hunar's own colors (for "neutral but Hunar-colored" pages):** see
`references/hunar-brand-palette.md` — primary `#006EDD`, light `#369BFF`, ink
`#121212`, canvas `#FAFAF9`. The logo is monochrome dark (`#15191e`), so derive the
accent from computed button/link styles, never the logo. `scripts/png_dominant_colors.py`
decodes a PNG's dominant colors in pure Python when PIL is missing or arch-mismatched.

## Quick Reference

| What | Where |
|------|-------|
| Hunar API base | `https://api.voice.hunar.ai/external/v1` |
| Agent identity | `const AGENT = {...}` in `index.html` |
| Worker name | `wrangler.jsonc` `name` |
| Log target | `SHEET_ID` + `SHEET_RANGE` in `src/index.js` |
| Secrets | `.dev.vars` (`HUNAR_API_KEY`, `GOOGLE_SERVICE_ACCOUNT_JSON`) |

## Pitfalls

- **Agent UUID is the critical dependency.** The page is inert without a live agent on Hunar. Keep the previous UUID as a clearly-marked placeholder and swap later.
- **Inspect the agent before trusting cloned copy.** `name` / `summary` / `language` / `custom_variables` from `GET /agents/{uuid}/` are the truth — a cloned page's copy and `custom_data` almost certainly describe the *previous* agent. Mismatch here produced wrong copy (consumer vs. recruitment), wrong language (Hinglish vs. English), and wrong payload (3 keys vs. `first_name` only).
- **"Load Failed" is never from the demo codebase.** It's Safari's network-error phrasing (browser `fetch` failed at the connection layer — server down or wrong port) or a Hunar-side message. Reproduce with `curl` against `/api/calls` and read the JSON error (401 = bad key, 422 = field validation) instead of guessing from the browser's red box. **If `curl` works but the browser still fails, drive the page in a real browser yourself** — `browser_navigate http://localhost:8787` → fill the form (`browser_type`) → click trigger (`browser_click`) → read `browser_console`. If it succeeds there with zero JS errors, the bug is client-side (stale cache or an extension), not the code. Confirm cache by checking whether the user's page still shows a *removed* field (e.g. City/Loan dropdowns) = old HTML; an incognito window bypasses cache and proves it.
- **In-place re-brand kills the old demo** if the previous client is still being shown the page. Clone to a new repo; keep both live.
- **Sheet schema should be generic, not agent-specific.** Bajaj's was hardcoded to its `result` fields. The Mondelez build switched to core call fields (Logged At, Call ID, Name, Number, Language, Status, Engagement, Duration, User Speech, Answered By, Call Ended By, Started At, Ended At, Recording URL) **plus one `Result JSON` column = `JSON.stringify(result)`** — this captures whatever the agent's `result_variables`/`result_schema` produce (e.g. the BDE assessment's 16 fields) with zero per-agent column maintenance. Also log **once** per call (wait for `result` to populate), not twice — the old 5-minute re-log duplicated rows.
- **Logo color determines sidebar color.** The Mondelez logo measured white (254,254,254) even though their brand is purple — so a purple sidebar worked. Always measure, don't assume.
- **`/api/debug-key` leaks part of the service-account private key** in the reference repo — remove before any non-demo deployment.
- **Open endpoints + no rate limit** — anyone with the URL can trigger calls. Fine for a pitch demo; flag before anything public.
- **`.wrangler/cache/wrangler-account.json` is committed** in the reference repo — gitignore `.wrangler/`.
- **Verified-replacement cascade bug** — when one replacement's target string appears inside another's target, applying the first makes the second report "NOT FOUND". Order broad replaces last, and skip (don't apply) any edit whose expected count mismatches. See `references/verified-replacement-edit.md`.
- **Renaming a color constant does not change its literal value.** `NAVY`→`PURPLE` / `ORANGE`→`ACCENT` renames every *reference* but leave the hex in `const ACCENT="#FF6700"` orphaned (old brand color still live). Update the hex too, then run the full color audit (see Verification).
- **`npx wrangler dev` runs silently.** First run can hang forever waiting on the npx "Ok to proceed?" install prompt (background processes have no stdin), and even once `workerd` is up the console may emit nothing while the server is fine. Always `npx --yes` (auto-accept) and verify readiness with `lsof` + `curl`, never by waiting for a log line.

## Verification

- `curl -s localhost:8787` returns HTML containing the new title and logo URL.
- `grep` the page for the old brand name / old color hexes — should return only intentional leftovers (e.g. the placeholder agent UUID).
- **Full color audit:** `curl -s localhost:8787/ | grep -oE '#[0-9A-Fa-f]{6}' | sort | uniq -c | sort -rn` — confirm only neutrals, semantic status colors (green/blue/amber/red pipeline states), and the new brand colors remain. Zero old-brand hexes (this is what catches the orphaned-color-value bug).
- Open `localhost:8787` and visually confirm sidebar, logo, and CTA colors.
