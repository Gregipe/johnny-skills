# Voice AI ROI / Break-even Model

The math behind the `voiceai-roi` calculator (Greg's client-facing tool). Verified against the
source Google Sheet `1cmryjAe1HyDNWHjTnaTT90O4kYsJqm4yPultz4fqHNw` (per-lead, scale-invariant —
lead volume cancels out of cost-per-conversion).

## Inputs

Customer Status Quo: `CPL` (₹/lead), `CTC` (₹/month), `hc` human connectivity on raw leads,
`hc2` call connectivity on AI-screened (warm) leads, `cr` human conversion on raw leads.
VoiceAI: `a` ₹/min, `t` AHT min, `ac` AI connectivity, `ae` engagement, `ad` disposition,
`f` productivity factor (multiplier on `cr` for pre-screened leads).

Fixed assumptions: 25 working days/month (`H = CTC/25`), human capacity 30 connected calls/day
(`CAP`).

## Formulas (per lead)

```
before:  conv = hc·cr            humanCost = hc/CAP·H       cpc = (CPL + humanCost)/conv
after:   e2e = ac·ae·ad·hc2·cr·f
         aiCost = ac·t·a         humanCost = (ac·ae·ad·hc2)/CAP·H
         cpcAfter = (CPL + aiCost + humanCost)/e2e
verdict: positive iff cpcAfter < cpcBefore
```

## Break-even (solve each lever individually, others at current values)

With `B = cpcBefore`:

```
ac* = CPL / [ B·ae·ad·hc2·cr·f − t·a − ae·ad·hc2·(H/CAP) ]
ae* = (CPL + ac·t·a) / [ ac·ad·hc2·(B·cr·f − H/CAP) ]
ad* = (CPL + ac·t·a) / [ ac·ae·hc2·(B·cr·f − H/CAP) ]
f*  = (CPL + ac·t·a + ac·ae·ad·hc2·(H/CAP)) / [ B·ac·ae·ad·hc2·cr ]
```

- Denominator ≤ 0 → that lever can never reach break-even alone (render as "not reachable").
- `req > 1` for a % lever → "above 100%, not achievable alone".
- `req ≤ current value` → "current value already clears it".

Combined benchmark (the number that decides it): required end-to-end conversion =
`(CPL + aiCost + humanCost) / B`; current = `e2e`; human-only = `hc·cr`.

## Verified baseline (sheet defaults: CPL 100, CTC 25k, hc=hc2=30%, cr=20%, a=3, t=1, ac=70%, ae=55%, ad=60%, f=3)

| Metric | Value |
|--------|-------|
| CPC before AI | ₹1,833.33 |
| CPC after AI | ₹2,511.06 (ROI-negative, +36.97%) |
| e2e before | 6.0% |
| e2e after | 4.158% |
| Required e2e to break even | 5.70% |
| Connectivity needed | 97.5% |
| Engagement needed | 76.0% |
| Disposition needed | 82.9% |
| Productivity needed | 4.11× |

## Key structural insight

Marketing CPL dominates spend (~96% of cost), so the AI path must convert *nearly as well as
the human-only path* to justify its added cost. The four AI levers are underdetermined against
one break-even equation — solving each individually (others held) plus showing the combined
end-to-end threshold is the clean way to present "what must the AI deliver".
