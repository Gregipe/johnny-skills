---
name: moneymettle
description: Use when working on MoneyMettle, Greg's card net-value app.
---

# MoneyMettle

Greg's personal project: **net-value transparency for Indian middle-income credit-card users** — estimates, never promises. One-pager philosophy: categories ≠ payment route ≠ MCC ≠ EMI status; unknown stays unknown; route-sensitive rules fall back to a *disclosed* POS likely-case simulation; no invented numbers.

## Location & stack

- Repo: `~/Personal/Moneymettle/moneymettle` (pasted zip, **no .git** — check `git status` fails; don't assume history)
- Polsia Next.js 16 template (App Router, React 19, Tailwind 4, Prisma 6, Vitest 3, Biome, Playwright)
- No `.env`/`AGENTS.md`/`.github` in the paste; `SKIP_ENV_VALIDATION=1` for local build/dev
- Read `.polsia/ownership.json` before editing — Polsia template splits framework_owned vs user_owned

## Pipeline files (read these first for any statement work)

| Stage | File |
|---|---|
| Upload/validate | `src/lib/business/statement-input.ts` |
| CSV/PDF parse + evidence | `src/lib/business/statement-analysis.ts` (1230 lines, core) |
| PDF text layer | `src/lib/business/statement-pdf.ts` |
| Category summary | `src/lib/business/statement-aggregation.ts` |
| Reviewer memory | `src/lib/business/merchant-review-memory.ts` (localStorage, 500 cap) |
| Handoff (Zod v7) | `src/lib/business/compare/statement-import.ts` |
| Rule matching | `src/lib/business/compare/statement-bucket-assignment.ts`, `term-conditions.ts` |
| Estimates | `src/lib/business/compare/statement-estimator.ts`, `calculation.ts` |
| Cycle reward valuation | `src/lib/business/compare/statement-reward-valuation.ts` |
| Card identity from heading | `src/lib/business/compare/card-heading-match.ts` |
| Card data (3 cards) | `src/lib/business/compare/cards.ts` (Axis ACE, HDFC Millennia, SBI Cashback) |
| Pages | `src/app/(custom)/{spend-summary,compare,card-terms}/page.tsx`; UI in `src/components/custom/money-mettle/` |

## Commands (MUST run with NODE_ENV=development or unset — see trap)

```bash
cd ~/Personal/Moneymettle/moneymettle
NODE_ENV=development npm install --include=dev   # install
NODE_ENV=development npm run test                # 36 files / 333 tests, ~7s
NODE_ENV=development npm run typecheck           # clean
env -u NODE_ENV SKIP_ENV_VALIDATION=1 npm run build  # build (unset NODE_ENV — next sets it)
NODE_ENV=development npm run lint                # 22 pre-existing cosmetic errors, all lint:fix-able
```

## NODE_ENV trap (critical)

The Mac shell has `NODE_ENV=production` exported. Consequences:
- `npm install` silently **skips devDependencies** → `prisma generate` fails (exit 127), tests can't run. Fix: `NODE_ENV=development npm install --include=dev`.
- Vitest under production NODE_ENV loads React's production build, which **strips `act`** and externalizes node builtins → `act is not a function`, `resolve is not a function` failures. Fix: `NODE_ENV=development npm run test`.
- `next build` with NODE_ENV **forced to development** crashes prerendering `/_global-error` (`useContext` of null). Fix: `env -u NODE_ENV` so Next sets it to production itself.

## Local hosting (Oct 2026)

- Postgres 16 via Homebrew: `arch -arm64 brew install postgresql@16` (the TUI shell runs under Rosetta — brew installs FAIL without the `arch -arm64` prefix; `arch` reports i386). Service: `brew services start postgresql@16`. DB: `moneymettle`, owner greg, trust auth on localhost.
- `.env.local` (created, not in paste): `DATABASE_URL="postgresql://greg@localhost:5432/moneymettle"`. Prisma CLI skips .env loading via prisma.config.ts, so export DATABASE_URL in the shell for CLI commands.
- Schema: `npx prisma db push` (multi-file prisma/schema). 8 tables. Seed runs at boot via instrumentation.ts → seed.ts (idempotent upserts of cardTermsSeedData).
- App: production build + `npm run start` on http://localhost:3000. Verified live: /health 200, /api/card-terms serves 3 cards from DB, /spend-summary and /compare render.

## Product direction (Greg, Oct 20 2026)

Expanded beyond the 3-card tool: (1) catalog of ALL publicly available Indian credit cards, scraped by a recurring cron (issuer sites + aggregators like PaisaBazaar/BankBazaar) with diff-checks and review-gated promotion — NOT runtime scraping; (2) dual ingestion: credit-card statements (incl. password-protected PDFs — prompt for password, unlock client-side) + UPI app statements (same classification pipeline); (3) delta simulation: customer's current-card rewards vs each catalog card, annualized with caps/fees/GST, ranked best/2nd/3rd + switch verdict; UPI spend simulated as additional card spend; (4) evidence tier relaxed: inferred categories participate with disclosed labeling (Greg approved 6b). Merchant-alias normalization layer approved. Local OCR (tesseract installed) + ollama available on the Mac for local extraction.

## Issuer category suffixes (Axis statement format, fixed Oct 2026)

Axis embeds the bank's category in each row's description: `MERCHANT,MUMBAI FOOD PRODUCTS`, `MERCHANT, REF# 77013232 UTILITIES`. Fix in `statement-analysis.ts::splitIssuerCategorySuffix` + `statement-pdf.ts`:
- Split at LAST comma; if tail ends with a known issuer token (longest-first list `ISSUER_CATEGORY_SUFFIX_TOKENS`), use it as `categoryValue` → statement-level evidence; merchant = text before comma.
- `MISCELLANEOUS` suffix → review + inferred suggestion (keeps evidence discipline); curated merchant identity (e.g. OpenAI billed as RETAIL STORES) beats the issuer bucket; EMI rows never inherit the suffix category.
- PDF parser also excludes summary/totals lines (second date or `amount Dr/Cr` inside the description) — previously parsed as phantom spends.
- DCC MARKUP / GST / EMI PRINCIPAL rows → 'Fees & interest' via categoryFromText; 'payment received' → transaction type outstanding_balance_payment.
- Real-statement result: 23 unclassified → 7 (3 are BBPS payment-received credits, 2 are ₹2 LinkedIn, 1 PayPal DeepSeek misc, 1 TATA PLAY with suggestion).
- Scratch diagnostic: `tests/unit/scratch-statement-debug.test.ts` parses `~/Personal/Moneymettle/samples/Credit Card Statement - Unlocked.pdf` (Axis ATLAS) — use it to re-measure accuracy after parser changes.

## Curated merchant dictionary (merchant-level ground truth, Oct 2026)

- Data: `src/lib/business/merchant-dictionary.json` (entries: canonicalName, patterns, category, detail). Loader: `src/lib/business/merchant-dictionary.ts` → `curatedMerchantLookup(value)` (normalized prefix match, truncation-safe).
- New `CategoryEvidence` tier: `'curated'` — outranks the issuer bucket ONLY when they disagree; real MCC stays strongest; when curated agrees with the statement bucket, the stronger `statement` evidence is kept. Review edits (`reviewer`) still applied post-hoc win overall.
- Wired through: `createStatementTransaction` (statement-analysis.ts), Zod handoff v7 enum (statement-import.ts), UI labels ('merchant dictionary') in savings-calculator.tsx + statement-review.tsx, bucket-assignment disclosure message — curated does NOT qualify as issuer evidence for category-level card terms.
- Greg's seeded ground truth: Divine Icecream → Food & dining; PayPal → Subscriptions; MSGAURAV/M S GAURAV SWEETS → Food & dining; Joshh Powai → Groceries.

## Local LLM enrichment pipeline (review-gated, Oct 2026)

- `tests/unit/scratch-enrich-merchants.test.ts` — opt-in via `RUN_ENRICHMENT=1` (defaults to skip; ~5 min of CPU inference). Batches distinct un-curated merchants from the real statement to local Ollama (llama3.2:3b), writes proposals to `scripts/enrichment-proposals.json`. NOTHING auto-applies to the dictionary — Greg reviews, then approved entries are merged into merchant-dictionary.json.
- Ollama on this Mac: GUI server on 11434 crashes with `llama runner terminated` (Metal backend failure on macOS 26.3). Workaround: CPU-only server `OLLAMA_NUM_GPU=0 OLLAMA_HOST=127.0.0.1:11435 ollama serve` — the shell runs under Rosetta so spawn it plain (arch -arm64 + GPU still fails; a newer Ollama update zip sits in ~/Library/Caches/ollama/updates but is not applied).
- llama3.2:3b returns `{"results": [...]}` (not a bare array) — parser must unwrap `raw.results`. Prompt must forbid citing sources in rationale (model invents "official website confirms" lines). The 3B model ALSO emits bare single objects and comma/newline-concatenated `{...}` streams, so the parser scans the raw text for balanced-brace fragments and parses each independently; batch size 5 + `num_predict: 1024` + "return one entry for EVERY merchant" reduces early stopping. Even so, a 3B local model returns partial coverage (~25%) and marginal proposals — the curated dictionary (human ground truth) is the real fix; the LLM layer is a weak assist. Consider a stronger model (or cloud) only if proposal quality matters.

## Known state (Oct 2026)

- Tests: 342 passed + 1 skipped (enrichment opt-in), typecheck clean, build green (all 14 routes).
- Lint: 22 errors pre-existing in paste — formatting/import-sort across 10 test files + 2 non-null assertions (`tests/unit/compare-calculation.test.ts:185`, `tests/unit/statement-analysis.test.ts:44`).
- Greg's rule from the one-pager: completed tasks aren't proof of live behavior — inspect current source and tests before trusting anything.
