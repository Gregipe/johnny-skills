---
name: financial-statement-analysis
description: "Use when Greg shares a bank/UPI/card statement PDF."
version: 1.0.0
author: Johnny
license: MIT
metadata:
  hermes:
    tags: [finance, upi, statements, analysis, moneymettle, pdf]
    category: productivity
    related_skills: [pdf]
---

# Financial Statement Analysis (Leak Audit)

## When to Use

Greg sends a GPay/bank/card statement PDF — with or without a message. Run the
leak audit and reply with the analysis.

Greg shares GPay/bank/card statement PDFs (often with no message — the implied
ask is "show me where my money goes"). This is the MoneyMettle leak-audit
pipeline: parse, categorize, verify, deliver.

## Workflow

1. **Extract text with read_file.** The read_file tool auto-extracts a PDF's
   text layer. Do NOT read the PDF binary inside execute_code — it is not
   UTF-8 and throws UnicodeDecodeError. If there is no text layer (scanned
   statement), use the pdf skill's OCR path.
2. **Parse transactions.** Regex over the extracted lines for
   `Paid to <party> ... |₹<amount>|` and `Received from <party>` blocks.
   GPay statements split large amounts across lines in extraction
   ("₹1,00,00 0" = 100000, "₹46,231.8 8" = 46231.88, "₹15,857.7 6" =
   15857.76) — merge adjacent digit fragments before summing. Normalize
   Indian comma format (`1,00,000`) before arithmetic.
3. **Categorize via a merchant keyword map**, not an LLM guess: normalize
   payee names (case, known variants), then bucket — credit-card bill
   payments, family names, grocery, utilities, fitness, subscriptions,
   church, pharmacy, one-offs. Aggregate: category share %, monthly trend,
   top-N payments, recurring merchants (>= 3 hits).
4. **Verify the total before reporting.** Sum of parsed rows must match the
   statement's stated total. A gap means a missed row — find it first
   (a single missed ₹400 row is a reconciliation error, not noise).
5. **Deliver the leak audit:** headline in/out totals → biggest category with
   its % → the black-box flag: credit-card bill payments dominate and HIDE
   the real spend; the inner answer lives in the card statement — request it
   ("send the Axis statement and we'll close the black box") → ranked visible
   categories → large one-off payments listed for Greg to NAME (never guess
   who a person is) → monthly trend → one meta-line tying the finding to the
   thesis. Save to `/root/thesis/` when thesis-related.

## Rules

- **Screenshots of transactions: vision_analyze may not see images in this
  environment (returns text-only).** When Greg sends a transaction
  screenshot instead of a PDF, delegate to a subagent with the image passed
  in `images` (OCR tools available in the subagent) rather than relying on
  vision_analyze.
- **Never speculate identities.** A payee name like "Forma Fisica" gets its
  semantic reading ("physical form" — fitness brand) and a provisional
  category, but the person/business is Greg's to confirm.
- **Merchant lookups rarely resolve local proprietorships** — the reliable
  paths are the payment app's transaction detail screen (registered merchant
  name, VPA, category) and the bank's debit SMS. Web search is a supplement,
  not the answer.
- **Amount + time shape is signal:** a lump sum on a weekday morning reads as
  a membership/package payment, not a single session — say so as inference.
- **Deliver in English, WhatsApp-friendly**, no emoji, no tool narration,
  short lines (see user-interaction-style skill).
