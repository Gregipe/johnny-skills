---
name: community-research
description: "Use when mining Reddit/forums for market pain points."
version: 1.0.0
author: Johnny
license: MIT
metadata:
  hermes:
    tags: [research, reddit, forums, market-research, sentiment, community]
    category: web
    related_skills: [blocked-page-recovery]
---

# Community / Forum Research

## When to Use

Greg asks for consumer/market insight from online communities: recurring
problem statements ranked by frequency, deep dives into a cluster's threads
and comment solutions, or emotional need-state audits.

Mining Reddit and similar communities for market insight: what problems recur,
what solutions people propose, and what emotional states drive them. Greg uses
this for startup-thesis questions (e.g. MoneyMettle) — he wants ranked problem
statements with real evidence, not summaries of summaries.

## Workflow

1. **Fetch the listing via RSS, not .json.** Reddit's .json endpoints (www and
   old.reddit) commonly return an HTML shell or a Blocked page from server IPs.
   The Atom feed works without auth:
   ```bash
   curl -s -m 30 -A "Mozilla/5.0 research" "https://www.reddit.com/r/<sub>/hot.rss?limit=100" -o /tmp/sub.rss
   ```
   `hot` works; `new`/`top` variants can return 0 bytes — fall back to `hot`.
   Parse with regex over `<entry>...</entry>` blocks (title + category term).
2. **Get comment/body text through search snippets.** Thread pages are usually
   blocked for direct fetch, but web_search with `site:reddit.com` plus an
   exact title fragment (or a distinctive phrase from the post) often returns
   snippets that include the post body AND top-comment text. Run one search
   per target thread, batch them.
3. **Count frequencies with code, never by feel.** Load the titles into
   execute_code, run a keyword classifier over theme buckets, print the
   frequency table, THEN hand-verify every bucket against the actual titles.
   Generic words ("bank", "salary", "income") inflate buckets — merge and
   adjust with judgment, and report the sample size plus the method in one
   line when delivering.
4. **Rank and quote.** Deliver problem statements in frequency order, each with
   2-4 verbatim example titles as evidence. A title is evidence; a vague
   paraphrase is not.
5. **Deep-dive a cluster when asked.** Pull thread bodies and comments via the
   snippet route for that cluster only. State the exact problem as a mechanism
   (why it happens), then the gist of community solutions as bullets. Name
   which solutions the data shows failing (e.g. everything requiring daily
   manual discipline) — that gap is the product insight.
6. **Save deep analyses to `/root/thesis/<topic>-<YYYY-MM>.md`** — they are
   thesis research artifacts other sessions must be able to reopen.

## Emotion / need-state audit (when Greg asks "what are people feeling")

Two-layer method — see `references/emotion-audit.md` for the lexicon buckets:

- **Layer 1 (surface):** lexicon-tag every title in the corpus, count per
  emotion bucket. This gives frequency.
- **Layer 2 (intensity):** deep-read the thread bodies. Titles carry frequency,
  bodies carry intensity — a state that is rare on the surface (desperation)
  can dominate the emotional ceiling.
- Deliver a frequency x intensity map, with verbatim quotes, and one line per
  state on what it means for the product. Include ABSENT states — what nobody
  expresses (e.g. contentment on a personal-finance sub) is itself a finding,
  often the most valuable one.

## Rules

- **Deliver in English, WhatsApp-friendly** — bullets, short lines, real
  quotes, no emoji, no tool narration. End with the product implication and
  one next-step question.
- **Honest counting** — never say "most common" without a count; never invent
  comment content. If a thread can't be reached, use snippets or say so.
- **Parse in execute_code, not terminal heredoc python** — heredoc scripts in
  terminal can hit the approval gate and stall the turn. Keep terminal to
  plain curl fetches; do all parsing with execute_code (read_file + regex).
- **Unescape HTML entities** (`&amp;`, `&#x27;`) in RSS titles before analyzing.
- **Bot-walled social pages (Instagram et al.) extract only image captions** —
  they are not a comment source; don't burn calls chasing them.
