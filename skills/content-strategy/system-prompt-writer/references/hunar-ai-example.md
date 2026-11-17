# Hunar.ai — Reference Example

This document shows the complete system prompt generated for Hunar.ai using the system-prompt-writer skill and the `POST /api/cadence/generate-prompt` backend endpoint.

## Process

1. Tenant config provides: name="Hunar.ai", industry="recruitment", segments=["Staffing", "Logistics", "BFSI", "QSR/Retail", "Tech/SaaS"]
2. Induction docs provide: capabilities (voice AI, multilingual screening, etc.), case studies (Swiggy, logistics deployments, etc.), customer names
3. Backend endpoint assembles 13 sections from `prompt_templates.json` (inherited) + induction data (per-tenant)
4. Saves `systemPrompt` (14,935 chars) + `promptParts` to all 3 cadence templates

## Per-Section Breakdown (Quality Benchmark)

| # | Section | Chars | Source | Notes |
|---|---------|-------|--------|-------|
| 1 | Objective | 1,092 | Per-tenant | Tenant name, ICP, target roles |
| 2 | Brand Voice | 662 | Inherited | Style anchor — same for all |
| 3 | Sector Context | 1,669 | Per-tenant | Capabilities, positioning, themes |
| 4 | Security & Guardrails | 2,644 | Inherited | Full injection defense + 3 subsections |
| 5 | WhatsApp | 2,026 | Inherited | Anatomy + sequence rules |
| 6 | Email | 2,379 | Inherited | Subject + body + sequence rules |
| 7 | Call | 1,087 | Inherited | Structure + tone + voicemail |
| 8 | Lead Context Awareness | 468 | Inherited | Adaptation rules |
| 9 | Industry Contextualization | 3,740 | Per-tenant | 5 industry segments with pains + hooks |
| 10 | FOMO & Curiosity | 647 | Inherited | Strategic tension |
| 11 | Message Structure | 674 | Inherited | CTA rules |
| 12 | Sequence Evolution | 650 | Inherited | Touch progression |
| 13 | Communication Rules | 1,372 | Inherited | Do/don't, clarify rules, dedup guardrail |

**Total: ~17,110 chars** (varies slightly per tenant depending on segment count)

## Output Quality Standards

- **Sector Case Studies:** 4 detailed deployments with metrics (80% connection rate, 3X improvement, etc.) — never one-liners
- **Security:** Full injection prevention + 3 populated sub-sections (Restricted Claims with 5 boundary types, Escalation with 6 scenarios, FAQ with 8 Q&A pairs)
- **Sequences: Behavioral stages only** — Opening → Build → Sharpen → Close/Reframe. NO T+ time delays. Timing belongs in step selector.
- **Industry segments:** Each segment has 3-5 core pains, messaging posture, and 3 example hooks — operational realism, no marketing fluff
- **Channel docs:** Each has full message anatomy, behavioral sequence rules, and comprehensive don'ts

## What NOT to Do

- ❌ Leave sector case studies as one-liners — must be specific deployments with metrics
- ❌ Omit sub-sections of Security (restricted claims, escalation, FAQs must all be filled)
- ❌ Embed T+ time delays in prompt text — timing belongs in the step selector
- ❌ Save to systemPrompt without updating promptParts (or vice versa)
- ❌ Forget to clear localStorage after DB writes — hard refresh required
- ❌ Generic industry text where tenant has specific segments — use the detailed templates
- ❌ Shallow induction = shallow prompt. If docs are thin, ask for more during induction.
