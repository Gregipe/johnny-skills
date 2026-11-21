# Accessing Reddit & Quora Threads

## Reddit

Reddit serves a "You've been blocked by network security" 403 to most automated paths: direct curl on www/old/api, `.json` endpoints, and browsers on datacenter IPs. Redlib mirror instances are mostly shut down or sit behind Anubis/go-away proof-of-work that denies datacenter IPs outright. Fresh threads (<24h) are rarely in archive.org/archive.ph.

Working order of attempts:
1. **web_extract on the www.reddit.com thread URL** (Exa backend). This has succeeded where every other path was blocked; it returns post title + body, and sometimes comment text. On timeout, retry once — old.reddit URLs often time out while www succeeds.
2. **pullpush.io archive API** for older threads: `GET https://api.pullpush.io/reddit/search/comment/?link_id=<id>` and `GET .../search/submission/?ids=<id>`. The endpoint responds with valid JSON; coverage lags publication, so a <48h-old thread may return empty data — that means "not indexed yet," not "no comments." Retry a day later.
3. **Stop when 1 and 2 come back empty** for a fresh thread. Do not burn more turns cycling mirrors (they deny fast) — summarize the verified post body, state that the comment thread was unreachable and why, and offer alternatives: Greg opens the link in his logged-in Reddit app and pastes comments back, or you retry after the thread is indexed.

## Bulk archive research (subreddit trend analysis)

- **arctic-shift** (`https://arctic-shift.photon-reddit.com/api/posts/search`) covers the Indian subs for 2024/2025/2026 (r/IndiaCareers, r/personalfinanceindia, r/IndiaFinance, r/developersIndia, r/CreditCardsIndia, r/FIREIndia, r/indiasocial): params `subreddit`, `after`, `before` (ISO dates or epoch), `limit` (max 100), `sort=desc`. It has NO full-text search (`q` param returns 400) — do keyword filtering locally on fetched corpora. Pagination is FLAKY — advance a cursor by the last item's `created_utc`, dedupe by id, and on an empty page step the cursor back/forward 3600s and keep going; never trust a single-page count (2025 windows can look empty with naive after/before probes even though data exists).
- **pullpush.io coverage is spotty by sub**: it had r/IndiaCareers only from 2026-09-12 onward and nothing at all for r/personalfinanceindia, r/IndiaFinance or r/developersIndia. Probe both archives with a limit=100 sample before planning a fetch; arctic-shift is the default for 2024-2026 work.
- Corpus density is itself a signal: r/IndiaCareers grew from ~900 posts/month (Sep-Oct 2024) to ~1000 posts per ~2 weeks (2026). State archive + window + n per corpus in every trend deliverable.
- **A 1000-post cap covers wildly different date ranges per sub**: r/developersIndia fills it in ~4 days, r/personalfinanceindia in 15-32. For dense subs the window fetch can never reach historical periods — find threads via web_search `site:reddit.com/r/<sub> <keywords>`, take the post id from the URL, and mine comments directly (below).
- **Comment mining: `GET https://arctic-shift.photon-reddit.com/api/comments/search?link_id=t3_<post_id>&limit=100`** works even when a sub's post history is unreachable; rank locally by `score`. Some threads return 0 comments (archive gaps) — report that as an honest empty, don't cycle mirrors.
- **Corpus-verbosity check before trusting mid-year numbers**: a year whose posts average much shorter selftexts (e.g. ~260 vs ~440 chars) depresses EVERY keyword bucket — a universal V-shape across all themes is a corpus artifact, not sentiment. Also count duplicate/automod-thread titles (weekly/daily discussion threads inflate N without matching any theme).
- **execute_code batching**: one 1000-post arctic walk takes 40-90s; more than ~5 fetches in one cell hits the 300s timeout and kills the kernel. Split into ≤4-5 fetches per cell, and glob the scratch dir for already-saved corpora before re-fetching — files written before a timeout survive.
- Bucket taxonomies (career, money, debt sub-clusters, EMI-stress filter, advice clusters) live in `references/analysis-taxonomies.md` — multi-label regex on title+selftext, identical across every year/sub. ≥2pp deltas between same-window corpora are signal; below that, noise.

## Honesty rule (non-negotiable)

When only part of a thread is retrievable, summarize ONLY what was retrieved and label the rest as unreachable. Never fabricate commenter claims to make a summary look complete — that is the #1 trust-breaker with Greg.
