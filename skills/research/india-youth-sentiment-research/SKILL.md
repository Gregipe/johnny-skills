---
name: india-youth-sentiment-research
description: "Use when researching Indian youth sentiment on Reddit/Quora."
version: 1.0.0
author: Johnny (Chief of Staff)
license: MIT
---

# India Youth Sentiment Research

Purpose: understand what young Indians are feeling about careers, money, education, and life — for Greg's LinkedIn content and India-startup thesis.

## When to Use

- Greg asks where/how to gauge Indian youth opinion (Reddit, Quora, social)
- Content research for LinkedIn, startup thesis, or market-pulse work on India
- Any request to summarize an r/India-related thread

## Channel reality (Nov 2026)

Reddit India is the live signal: the 18–30, urban, English-speaking cohort moved here (India subs roughly tripled in traffic while Quora hit multi-year lows). Quora is a legacy archive, not a live pulse — its youth-facing content is heavily polluted with AI-generated answers and spam. Use Quora for pre-2023 high-quality answers on specific career questions and for secondary dips; follow Quora *Topics* (Life in India, Indian Students, Higher Education in India, Careers), not Spaces — most Spaces are dormant.

## Subreddit map (verified active Nov 2026)

Careers & education (biggest anxiety cluster):
| Sub | Signal |
|---|---|
| r/developersIndia | Richest single source: fresher hiring freezes, AI-displacement fear, salary threads |
| r/IndiaCareers | General career advice; "is studying abroad still worth it" debates |
| r/Indian_Academia | Stream/college choice, exam-path decisions |
| r/Indians_StudyAbroad | Study-abroad dream vs debt calculus |
| r/indianmedschool, r/UPSC | Aspirant burnout, "is it still worth it" threads |

Money:
| Sub | Signal |
|---|---|
| r/personalfinanceindia | Salary-saving-investing from 20-somethings; "survive on 30K in Bangalore" genre |
| r/IndiaFinance | Younger/poorer money crowd — debt, loan apps, frozen accounts; grew ~15x while personalfinanceindia shrank ~2x (2024-26) |
| r/IndianStreetBets | Retail F&O culture, loss porn — behavioral read on Gen Z risk appetite |
| r/CreditCardsIndia | Card-optimization consumerism, rewards hacking |
| r/IndiaInvestments, r/FIRE_Ind | Long-term investing, early-retirement ambition |

General life & sentiment:
| Sub | Signal |
|---|---|
| r/AskIndia | Highest-volume open questions: marriage, moving abroad, life choices |
| r/IndianTeenagers | Rawest Gen Z: loneliness, parental pressure, dating, identity |
| r/Arrangedmarriage | Family/money/life-expectation dynamics (salary filters, property questions) |
| r/TwoXIndia | Women's view: careers vs marriage, safety, workplace |
| r/indiasocial | Casual everyday chatter |
| r/bangalore, r/mumbai, r/delhi | Cost-of-living, rent, layoff angst — city-specific |

Maintained directories: r/IndiaTrending/wiki/indiansubs and r/india/wiki/related_subreddits.

## Reading method

- Sort by Top (this month/week), then read the comments — consensus and fights are the signal, not the posts.
- Count recurring complaint themes, not individual posts: fresher hiring, AI job fear, rent, F&O losses, study-abroad debt, marriage pressure. Frequency = theme.
- Verify a sub is alive by recency of its top posts, not subscriber counts.
- Bias rule: Reddit India = English-speaking, urban, male-skewed, tech-heavy. It does NOT represent rural/tier-3 youth — that cohort lives on Instagram Reels, YouTube comments, WhatsApp groups. Label Reddit-sourced claims as "urban educated youth voice" and triangulate before using them in a thesis or post.

## Access & honesty rules

Reddit blocks most automated access paths; the working playbook is in `references/reddit-quora-access.md`. When a thread's comments can't be retrieved: summarize ONLY what was actually retrieved, state plainly what was unreachable, and offer alternatives (user pastes comments from their logged-in app, or retry after indexing). Never invent what commenters said — fabricated comment content is a hard trust-break with Greg.

## Multi-year trend analysis

When Greg asks to analyze a sub/theme "the same way" across years, this is the shape he expects — build it in without being asked:

1. **Same calendar window every year** ("same period for consistency"), cap 1000 posts/year, and REPORT each corpus's actual covered date range — per-year density differences are themselves a finding (a sub that fills 1000 posts in 4 days vs 32 days is a signal).
2. **Probe both archives before fetching** (limit=100 sample); arctic-shift is the workhorse for 2024-2026. Mechanics in `references/reddit-quora-access.md`. Save corpora as JSON in cache/scratch so re-analyses never refetch.
3. **Buckets:** multi-label regex on title+selftext, IDENTICAL across every year and sub (deltas are meaningless otherwise). Taxonomy sets in `references/analysis-taxonomies.md`. Report per-theme %, micro word-counts, and sample titles. ≥2pp = signal.
4. **Corpus sanity check before trusting a mid-year dip:** avg selftext length per year (a year of much shorter posts depresses every bucket — a universal V-shape across all themes is an artifact, not sentiment) + duplicate/automod-thread titles.
5. **Validation chain (Greg will ask for it — run it up front):** a surprising delta is not a finding until a second window (e.g. H1 vs H2) and a two-year-back baseline agree. Classify each theme: monotonic structural / spike→plateau / spike→reversion.
6. **Deliverable:** per-year table with deltas → "intensifying vs relaxing" verdicts → the meta-story of the tone shift → bias caveat (urban/English/male/tech-heavy).
7. **Problem deep-dive:** filter all posts in the theme, sub-cluster into concrete problem statements with real title quotes, then mine the best threads' COMMENTS (comments API in the access file) for the solutions people suggest, quoting real comment text. Never fabricate.

## Findings library (completed analyses, Nov 2026)

Baseline multi-year studies — reuse their tables instead of re-deriving; re-run only for NEW windows:
- `references/careers-3y-trend-2024-2026.md` — r/IndiaCareers 3-year buckets, validation-chain verdicts (structural vs spike), referral/AI/laid-off micros.
- `references/personalfinance-3y-trend-2024-2026.md` — r/personalfinanceindia + r/IndiaFinance 3-year buckets, the two-Indias split, 8 debt problem statements. Warns about the 2025 verbosity artifact.
- `references/emi-deep-dive-2024-2026.md` — EMI>income deep-dive: 2-year arc, why-amplifying drivers, solutions clustered from 935 comments, one-line thesis.
- `scripts/corpus_fetch.py` — reusable fetcher (arctic pagination, pullpush probe, comments API) + the hard-won pitfalls (no q param, dense-subs cover only last days, verbosity check).

## Standing deliverable

A weekly "India Youth Pulse" digest (top threads + comment themes from ~10 of these subs) fits Greg's goals. Offer it, or set it up as a server cron job, when this topic comes up.
