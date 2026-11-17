# Open-Weight Competitor Landscape (snapshot: Nov 2026)

Reference for when Greg asks about model comparisons or reopens the pool. Independent numbers from Artificial Analysis Intelligence Index **v5.0.1** (private datasets, agentic-heavy evals). v5 scores are NOT comparable to the older v4.x index — always use the latest v5 figure.

| Model | Weights / License | $ in/out per 1M | AA II v5.0.1 | Notes |
|---|---|---|---|---|
| **DeepSeek V4 Pro (max/xhigh)** | MIT | $0.66/$1.98 off-peak, ×2 peak | 23.1 | Current main model. Strong tool-calling proven in ARA loops, but weak independent knowledge reliability (AA-Omniscience negative — guesses when unsure). Vendor cards (GPQA 90.1, SWE-bench 80.6, TB2.1 87.9) are NOT replicated independently. |
| Kimi K3.1 Pro | public, custom license (commercial w/ restrictions) | $2.00/$10.00 | 46 | Open-weight intelligence leader; 2.8T/104B MoE; slow (~38 min per AA task); text+vision. |
| Qwen3.8 Max | announced; AA still lists API version as proprietary | $2.00/$6.00 | 34 | Very verbose; weights status in flux. |
| DeepSeek V4.1 Flash 1017 | MIT | $0.15/$0.60 off-peak, ×2 peak | 32.5 | Same vendor as Pro; **scores above Pro on v5 at ~1/4 price**; 552B/16B, ~173 tok/s, multimodal. Candidate for high-volume loops — side-by-side test on own workload before switching. |
| GLM-5.3 | custom license ($10B-revenue review clause) | $1.40/$4.40 | 32 | Delegation model. Slow + verbose. |
| GLM-5.3-Flash | MIT | $0.15/$0.50 | 28 | Best intelligence-per-dollar open weight; 320B/18B, multimodal. |

Long tail (input ~$0.1–0.5/M): MiMo-V2.6-Pro 30, Ling 3.1 Flash 29, MiniMax M3.1 Flash 29, Step 5 Preview 29, Mistral Large 4 26, Meta Muse Spark Open 25.

## Routing implications
- Factual/research-heavy work: prefer GLM-5.3 or GLM-5.3-Flash over V4 Pro (knowledge reliability). Keep V4 Pro for ARA agent loops — correctness-first policy still holds there.
- If output-price pressure ever appears: V4.1 Flash 1017 is the zero-lock-in same-vendor downgrade that still beats Pro on the independent index.

## DeepSeek API facts (verified Nov 2026)
- Model id `deepseek-v4-pro` is an alias serving the latest point release (0813); `/models` does not disclose the point release.
- Effort levels `low`/`high`/`max`, default `high`; `xhigh` = max. Same per-token rates at all effort levels — higher effort just burns more reasoning tokens billed at output rate.
- Cache discount ~97%; off-peak/peak split as in the table.

Sources: artificialanalysis.ai model pages (deepseek-v4-pro, glm-5-3, glm-5-3-flash, kimi-k3-1-pro, qwen3-8-max, open-source comparison), AA v5 announcement, DeepSeek API docs.
