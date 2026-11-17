# Accessing Reddit & Quora Threads

## Reddit

Reddit serves a "You've been blocked by network security" 403 to most automated paths: direct curl on www/old/api, `.json` endpoints, and browsers on datacenter IPs. Redlib mirror instances are mostly shut down or sit behind Anubis/go-away proof-of-work that denies datacenter IPs outright. Fresh threads (<24h) are rarely in archive.org/archive.ph.

Working order of attempts:
1. **web_extract on the www.reddit.com thread URL** (Exa backend). This has succeeded where every other path was blocked; it returns post title + body, and sometimes comment text. On timeout, retry once — old.reddit URLs often time out while www succeeds.
2. **pullpush.io archive API** for older threads: `GET https://api.pullpush.io/reddit/search/comment/?link_id=<id>` and `GET .../search/submission/?ids=<id>`. The endpoint responds with valid JSON; coverage lags publication, so a <48h-old thread may return empty data — that means "not indexed yet," not "no comments." Retry a day later.
3. **Stop when 1 and 2 come back empty** for a fresh thread. Do not burn more turns cycling mirrors (they deny fast) — summarize the verified post body, state that the comment thread was unreachable and why, and offer alternatives: Greg opens the link in his logged-in Reddit app and pastes comments back, or you retry after the thread is indexed.

## Bulk archive research (subreddit trend analysis)

- **arctic-shift** (`https://arctic-shift.photon-reddit.com/api/posts/search`) is the archive that has r/IndiaCareers data for 2024/2025/2026: params `subreddit`, `after`, `before` (ISO dates or epoch), `limit` (max 100), `sort=desc`. Pagination is FLAKY — advance a cursor by the last item's `created_utc`, dedupe by id, and on an empty page step the cursor back/forward 3600s and keep going; never trust a single-page count (2025 windows can look empty with naive after/before probes even though data exists).
- **pullpush.io has NO pre-2026 coverage for r/IndiaCareers** (its archive starts ~2026-09-12). Any year-ago or multi-year comparison on that sub must use arctic-shift for the older years.
- Corpus density is itself a signal: r/IndiaCareers grew from ~900 posts/month (Sep-Oct 2024) to ~1000 posts per ~2 weeks (2026). State archive + window + n per corpus in every trend deliverable.
- Reusable buckets for career-issue clustering (multi-label regex on title+selftext): fresher_job_hunt, interview_ghosting, salary_offer, layoffs_pip, toxic_workplace, ai_fear, career_switch, study_abroad, govt_jobs, education_degree, startup_freelance, mental_health, referrals_networking, work_life, age_pressure, sector_choice. ≥2pp deltas between same-window corpora are signal; below that, noise.

## Honesty rule (non-negotiable)

When only part of a thread is retrievable, summarize ONLY what was retrieved and label the rest as unreachable. Never fabricate commenter claims to make a summary look complete — that is the #1 trust-breaker with Greg.
