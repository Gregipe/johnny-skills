---
name: evidence-grounded-llm-pipelines
description: "Use when building sourced-evidence LLM pipelines."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [llm, pipelines, evidence, prospecting, structured-output]
    related_skills: [llm-api-safety]
---

# Evidence-Grounded LLM Pipelines

## When to Use

Building any tool where an LLM converts search/web evidence into structured, source-backed conclusions: prospecting radars, research digests, extraction tools, classification engines. (Canonical reference build: Hunar Prospect Radar, `~/hunar-prospect-radar`.)

## Core Principles

1. **"Not available" is a first-class output.** Never fill gaps with plausible values — Greg's hard rule is real data only, no fabrication. When evidence is inaccessible, say so and carry on with what exists.
2. **Every claim carries its source.** URL + short excerpt + source type + publication date + retrieval date + period (current/historical/uncertain). Users must be able to audit conclusions, not trust a score.
3. **Past is never present — and unverified never ranks.** Track a period on every extracted claim and classify employment/currency separately (verified current / likely current / unverified / former). A dated directory entry does not prove a title is current; a LinkedIn URL is not employment evidence. The ranked shortlist may contain ONLY `verified_current` and `likely_current` candidates — enforce this in code at finalize (a deterministic allowlist, not a prompt rule): `former` → excluded (`former_employee`) and `unverified` → excluded (`unverified_employment`), with the reason surfaced in the UI, no matter how high the fit score. Unverified candidates stay visible (excluded tab, re-analysis via pasted profile text) but are never presented as targets.
4. **Score and confidence are separate dimensions.** Relevance fit (0–100, weighted) and evidence confidence (high/medium/low) are shown side by side; high fit + low confidence must be flagged, never merged.
5. **Discovery favors recall, enrichment favors precision.** A broad cheap pass builds the pool; deep investigation (targeted follow-up searches per candidate) narrows to owners. Never filter a candidate out just because their title lacks target keywords — and never award high scores without functional-alignment evidence.

## Architecture That Works

- **Adapter interfaces for everything external** (search: Tavily/Brave/mock; LLM: one OpenAI-compatible client), selected by env var. Missing credential → clear setup error, never a silent mock in production.
- **SQLite local MVP** with a typed prepared-statement data layer (no ORM). Node ≥22.13 ships built-in `node:sqlite` — zero native-build pain; verify with a one-liner before committing to it.
- **Budget config per stage**: max queries per company, pool size, deep-candidate count, enrichment searches per candidate, ranked output, LLM max tokens, timeouts, cache TTL, deep-mode multiplier. Defaults bounded; LLM used only where semantic reasoning is required.
- **Job-based runs**: orchestrator writes progress per stage; per-company try/catch so one company failing never kills the run; final status completed/partial/failed. Searches that ran cleanly and found nothing = completed with zero candidates, NOT failed.
- **Centralized prompt module**: system prompts hold instructions only; all external text (user input, snippets, pasted profiles) goes into XML-tagged sections of the user message. Tuning the reasoning rules never touches pipeline logic.
- **Partial results are the norm**: record per-query search failures and LLM stage failures as warnings; the UI shows status and partial output when some sources fail. Wrap every per-item LLM call in try/catch inside the batch loop — a thrown error in one item must degrade to a warning, never abort the rest of the batch.

## Search Query Planning

- **Push LLM-generated queries first under a budget cap.** Deterministic rotations (term × alias, title × alias) consume the entire query budget before the hint loop at the end runs, so hints silently get nothing. Emit hint queries before the rotations, and drop low-value kinds (broad web, secondary-alias rotations) from standard depth instead of crowding them in.
- **Query with short brand aliases, never legal names.** "ANI Technologies Private Limited (Ola Cabs)" returns nothing — real content uses the brand. Build search aliases by filtering resolved names for length and characters (no parentheses, dots, or domain strings), sort shortest-first, and rotate at most two. The third alias is usually a distinguished-from entity the resolver leaked into the list ("Ola Consumer" in an Ola Cabs hunt).
- **Keyword pre-rank must never match terms against the person's name.** Someone literally named "Ola" (or a first-name/term collision) must not earn relevance; match only title, company, and source text.

## Structured LLM Output Rules

- Request `response_format: {type: "json_object"}` AND include the word "JSON" in the prompt — OpenAI-compatible APIs (DeepSeek included) reject json_object mode otherwise.
- Extract defensively: strip markdown fences, then slice from the first `{` to the last `}`. Never assume pure JSON.
- Validate with Zod. On failure retry ONCE with the validation errors fed back into the user prompt; a second failure is an honest recorded failure — the pipeline continues without that data.
- **Retry transient request-parse 400s.** OpenAI-compatible providers occasionally 400 with "Failed to parse the request body as JSON" on perfectly valid large payloads (server-side hiccup). Before treating a 400 as a content bug, reproduce the exact payload through the real code path (logging LLM stub) and round-trip it through JSON.stringify/JSON.parse locally; if clean, mark that 400 class retriable — a genuinely malformed body fails again on retry. If the round-trip fails, scan for backslash/hex escapes and lone surrogates at slice boundaries.
- **Fabrication guard**: a model-produced URL/ID is accepted only if its canonical form appears in the inputs the model saw. Reject-and-log everything else — models invent plausible slugs and citations.
- If sub-scores must sum to a total (weighted dimensions), verify and rescale on drift instead of trusting the stated total.
- **Enforce calibration rules in code, not in the prompt.** A prompt rule like "no functional alignment ⇒ score below 55" is a soft suggestion the model regularly violates — it extrapolates ownership from seniority and titles. After the LLM returns, apply the rule deterministically (e.g. token overlap between current claims and target terms; `score = min(score, 54)` when it fails) and append a gap note explaining the cap. Cap floors that feed a ranking must live where they cannot be ignored.

## Testing Strategy (Deterministic, No Network)

- **Mock search provider** (fixture handler keyed by query substring) + **scripted LLM** (resolver keyed by task, dispatching on content embedded in the user prompt, e.g. the slug/name). Tests exercise the REAL orchestration with both swapped — no API keys, no network.
- When you change query assembly or budget slices (e.g. `functional_terms.slice(0, 4)`), substring-keyed fixtures silently stop firing for terms pushed past the new slice. After any such change, run the E2E suite and verify every fixture's match term still falls inside the new slices; merge orphaned fixture results into a surviving query rather than widening a slice to serve a test.
- Encode the semantic failure cases as fixtures: wrong-entity employees (Ola Electric vs Ola Cabs), former employees, historical-vs-current confusion, generic titles vs explicit owners, inaccessible profile text, fabricated references, two same-name people.
- Validate real semantic quality separately with a live pilot run that writes full results to disk for manual top-N review; tune taxonomy/prompts from the false positives and re-run.

## Pitfalls

- Dedupe by canonical URL (regional hosts, query strings, case normalization), never by name alone — two same-name people are distinct candidates.
- An orchestrator helper that takes a getter as a parameter is a smell; in a language with module imports, call the data layer directly — stubbing a getter to an empty list silently breaks deterministic pre-ranking.
- Accumulate per-company stats in local counters, not the run-wide progress object, or multi-company runs report cumulative numbers for the first company.
- Keep deterministic logic (URL normalization, dedupe, keyword pre-rank) out of LLM calls — every semantic call is budget and latency.
- A candidate's evidence digest must exclude other people's profile URLs. Name-based follow-up searches routinely return other profiles (query pollution); feeding them as THIS candidate's evidence poisons extraction. Filter profile-type sources whose canonical URL differs from the candidate's canonical URL before building the digest.
- Embed the canonical identifier (canonical profile URL/slug) in every per-candidate prompt section (`<candidate>…`). Without it, the LLM — and any scripted test dispatcher that keys on the prompt — anchors on the first matching profile URL in the evidence block, which may be someone else's.

## Node/Next Toolchain Pitfalls (tsx + npm)

- tsx tests need `"type": "module"` in package.json. A Next.js project defaults to CJS, so tsx compiles `.ts` to CJS and top-level `await` crashes the entire test FILE at load (reported as a file-level failure with no subtests). Adding `"type": "module"` fixes it; Next 15 handles ESM configs fine.
- Type-only exports (`export interface`, `export type`) cannot be destructured from a dynamic `import()` — use a static `import type` for them; destructuring them as values is a compile error.
- Fix a vulnerable transitive dependency with an npm `overrides` entry pinning the patched version, not `npm audit fix --force` — force "fixes" by bumping the top-level package to a breaking major (e.g. postcss nested under next → next@16).
