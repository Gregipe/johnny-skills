# LIC policy documents — anatomy and analysis flags

## Anatomy of an LIC life-insurance policy bond

- **Cover letter** (pages 1–2, Hindi + English): free-look notice (15 days from receipt of document), servicing branch address, policyholder address.
- **Schedule** ("Part A contd.", page ~3): every key value. Labels and values sit in separate text layers — use the two-pass extraction (plain + `extraction_mode="layout"`) and map values to fields by position.
- **Part B** definitions. **Part C** benefits (death, survival, maturity, participation in profits). **Part D** servicing conditions (forfeiture/paid-up, revival, loan, surrender, termination, free look). **Part E** usually "Not Applicable". **Part F** other terms (assignment, nomination, suicide clause, taxes, claim documents). **Part G** statutory provisions (Section 45 incontestability) + grievance redressal (branch → IRDAI toll-free 155255 / 18004254732, igms.irda.gov.in, Insurance Ombudsman).
- **Annexures 1–3**: full text of Insurance Act 1938 S.38 (assignment), S.39 (nomination), S.45. **Annexures 4–5**: guaranteed surrender value factor tables — often rendered as images, so they extract empty.
- **Last page**: multiple-nominee details table (name / age / relationship / percentage) — frequently a table that does not extract as text.

## Schedule field map (jumbled-token mapping)

Policy no · commencement date · plan + UIN · policy term (e.g. 66 yrs = whole life to age 100) · premium paying term (PPT) · basic sum assured · instalment premium + mode (Yly/Hly/Qly/Mly) · due day of month · last premium due · maturity date · DOB + age (admitted?) · rider rows (name / UIN / sum assured / premium / last premium due / termination) · nominee (+ appointee if minor, beneficiary) · proposal no + date · issuance date · branch office · agency code + agent phone.

## Flag checklist — surface all that apply, money and timing first

- **Premium due vs today's date**; grace = 1 calendar month (yearly/half-yearly/quarterly) or 15 days (monthly). State whether the policy is inside grace.
- **Thresholds crossed**: paid-up and surrender eligible after 3 full years' premiums; loan eligible after 3 full years (up to 90% of surrender value in-force, 80% paid-up); no surrender value on riders.
- **Jeevan Umang specifics**: survival benefit = 8% of basic SA per year starting at end of PPT, for life until maturity; death benefit = max(10× annualized premium, basic SA, maturity SA) + vested bonuses + final additional bonus, floor 105% of premiums paid; maturity (age 100) = SA + bonuses; with-profit reversionary bonuses declared annually during PPT.
- **Rider expiry = end of PPT** (e.g. ADDB accidental cover) — flag the cover dropping off and the re-cover decision point.
- **Suicide clause**: within 12 months of risk commencement or revival, only 80% of premiums paid.
- **Section 45**: after 3 years the policy is incontestable except for fraud.
- **Nominee/beneficiary correctness** — verify against the user's intent, including the multiple-nominee percentage split.
- **Taxes**: GST charged extra on premiums. Benefit tax treatment (80C/10(10D)) is NOT stated in the document — don't over-claim; only note what the document itself says.
