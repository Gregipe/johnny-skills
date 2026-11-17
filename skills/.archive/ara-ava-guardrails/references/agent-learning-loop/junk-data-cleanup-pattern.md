# Junk Data Cleanup — Learning Tables (June 2026)

## Problem
The learnings dashboard showed absurd numbers: 273 insights, 171 patterns, 177 pending review, 1% average confidence. All were machine-generated noise from auto-classification pipelines.

## Audit Results
- `ava_insights`: 273 rows — all from 3 batch runs (May 28-June 4). 153/273 had valueless keys ("none", "unknown", "unclear", "neutral", "non-committal"). All were auto-classification tags like "sentiment: neutral", "language: english", "objection: none".
- `learning_notifications`: 60 rows — 47 action_failed (Gregory Ipe retry loops), 4 action_reminder (noise), 4 new_skill (word-frequency false positives), 3 synthesis_ready, 1 action_scheduled, 1 escalation test.
- `skills`: 177 rows — 66 were machine chaff (proposition 33, gtm_learnings 21, inbound 11, learned_patterns 1). 111 were legitimate coaching-derived patterns.

## Cleanup Executed
- Deleted all 60 `learning_notifications`
- Deleted all 273 `ava_insights`
- Deleted 66 junk skills (proposition, gtm_learnings, inbound, learned_patterns)
- Kept 111 coaching-derived skills (messaging_win, objection_pattern, segment_signal, timing_pattern, coaching_general, guardrail, learning_summary)

## Why Confidence Was 1%
175/177 skills had `confidence=0.0`. The `_promote_insights_to_skills` pipeline extracts patterns from insights but doesn't carry confidence over — all auto-promoted skills get confidence=0.0. The 2 non-zero skills were manually created.

## Remaining Issue
The 111 kept skills still have confidence=0.0. The confidence scoring was never wired up for the auto-promotion pipeline. Dashboard will still show ~1% average confidence even after cleanup, because the kept skills all have confidence=0.0.
