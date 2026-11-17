# Scraping X/Twitter timelines without login + large-corpus topic analysis

Verified 2026-09-22 on @newonpolsia (827 posts). Reusable for "what are people
building on X / market-demand read" style research.

## Mirror landscape (try in this order)

| Target | Status (Sept 2026) |
|---|---|
| `x.com/<handle>` direct | Login wall / HTTP error — no anonymous timeline |
| `xcancel.com` | **Suspended** — X Corp cease & desist, Sept 2026 |
| `sotwe.com`, `lightbrd.com`, TwitterWebViewer | Cloudflare bot-block (empty / challenge) |
| `nitter.net` | connection refused |
| `nitter.poast.org` | DNS dead |
| `nitter.privacyredirect.com` | HTTP/2 error |
| **`tweetviewer.com/<handle>`** | **WORKED** — profile loads, has a "Load more posts" button |

## Extraction recipe

1. `browser_navigate` to `tweetviewer.com/<handle>`.
2. `browser_snapshot` first to find the right selectors / the "Load more" button.
3. Use `browser_console` with an **async JS loop**: click "Load more", pull tweet
   text out of the DOM, dedupe by exact text, repeat until the feed stops loading.
4. Append each batch to a JSONL file via `terminal` (one JSON per line:
   `{"date","text","likes","rts"}`). Strip newlines from text before writing.
5. Dedupe by text (grep the file or keep a set in the loop). Pause ~2–3 s between
   loads to dodge rate limits.

## Caveats (these bite during analysis)

- **Relative timestamps only** ("19s", "5m") → every tweet collapses to the same
  day. No time-series / trend-over-time analysis is possible.
- **No engagement counts** exposed → all `likes`/`rts` = 0. "Top 1000" means
  "most recent N the viewer keeps loading", NOT top-by-engagement.
- **Deep history may be unreachable** — the viewer's "Load more" can stall at a
  few hundred; that's your practical ceiling, not a bug.
- **Verify quality before analyzing**: assert total count, unique-text count,
  avg text length, a script-based language split (Unicode range heuristics:
  `\u0900-\u097F` → hindi, `ñáéíóú¿¡` → es, `ãõç` → pt, etc.), and eyeball the
  first ~10 rows. Catches empty/duplicate/garbled dumps early.

## Large-corpus topical categorization (parallel fan-out)

For ~500–1000+ posts, don't stuff them all into your own context:

1. Split into ~275-item chunk files (plain text, one post per line).
2. Dispatch N **parallel `delegate_task` subagents** (file toolset only — they just
   `read_file` their chunk). Each returns a compact taxonomy:
   `### Topic (count) — 2-sentence description — Examples: A, B, C`.
   Constrain them to assign **every** post to exactly one topic (counts must sum
   to the chunk size) and to return **verbatim** product/brand names (no invention).
3. Synthesize the N reports into one merged taxonomy + the "demand read."

This keeps your context lean (subagent summaries, not 800 raw posts) while the
verbatim-example requirement keeps it grounded. Tune the prompt with the platform
context (what Polsia/etc. is) so subagents frame categories around *demand*, not
just features.
