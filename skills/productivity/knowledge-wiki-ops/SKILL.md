---
name: knowledge-wiki-ops
description: "Use when Greg sends an article, link, or document to read."
version: 1.0.0
author: Johnny
license: MIT
metadata:
  hermes:
    tags: [knowledge, wiki, reading, thesis, research]
    category: productivity
---

# Knowledge Wiki Ops — Greg's Personal Knowledge Base

Greg's knowledge wiki lives at `/root/thesis/wiki`. It follows the LLM Wiki pattern (Karpathy): an AI-maintained, interlinked set of markdown pages that compounds — the substrate for his standing rule that Johnny connects the dots across his reading instead of collating links (see user-interaction-style, standing-rules reference).

## When to Use

- Greg sends an article, essay, link, PDF, or voice note about something he's reading
- He asks how a new piece connects to earlier ones, or what it means for his thesis
- He asks about his reading history / idea map / thesis

## Structure (authoritative schema: /root/thesis/wiki/WIKI.md — read it when in doubt)

- `raw/` — immutable source digests with a provenance header (url, title, author, date-sent, sent-by). One file per source.
- `sources/<slug>.md` — one page per source: thesis, dated key claims, data points, entities mentioned, connections.
- `concepts/<slug>.md` — one page per idea/frame: definition, provenance, why it matters to Greg, cross-references, contradiction notes.
- `entities/<slug>.md` — one page per durable thing (company, person, model): what, why it matters, dated facts, cross-references.
- `explorations/<slug>.md` — substantial syntheses/answers Greg asked for, filed for reuse.
- `index.md` — every page listed + Last touched date. Must be updated on every ingest.

## Ingest Workflow (every time Greg sends something to read)

1. Save the source digest into `raw/` with provenance header (URL, title, author, date-sent).
2. Write `sources/<slug>.md`: thesis + key claims WITH DATES + data points + entities + connections.
3. Create/update every `concepts/` and `entities/` page the source touches. Cross-link both ways.
4. Flag contradictions: when a new dated fact conflicts with an existing page, keep the newer fact and mark the older page "superseded by <source> (date)". Contradiction-flagging is what makes the wiki more than notes.
5. Update `index.md` (add new pages, bump Last touched).
6. Reply to Greg with connections to his existing map — never a summary round-up (standing rule).

## Query Workflow

Answer from wiki pages first, cite the pages, and file substantial new syntheses into `explorations/` so they are reusable.

## Lint

A cron job ("Wiki weekly lint", Fridays ~5:30 PM IST) already runs the lint pass automatically: contradictions, stale claims, orphan pages, broken links; it fixes the mechanical issues itself and reports to Greg. Do NOT create a duplicate cron — if the job is missing, recreate it with schedule `0 12 * * 5`, deliver origin.

## Pitfalls

- **Stale-write guard:** write_file refuses to overwrite a file the current session hasn't read. When updating `index.md` (touched on every ingest), read_file it first, then write the merged content.
- **Update, don't append:** pages are the working brain, not an archive. Extend the existing source/concept/entity page when the topic recurs; don't create a parallel page or a per-session file.
- **Dated claims only:** every claim in wiki pages carries a source page reference and a date — undated claims go stale silently.
- **Secrets stay out:** redact Greg's personal identifiers, phone numbers, and financial details from raw/ and page files before writing.
- **Language:** wiki content and replies are in English (Greg corrected Hinglish on WhatsApp).
- **Filenames:** lowercase, hyphenated slugs. Never `<date>-<incident>.md` outside raw/.
