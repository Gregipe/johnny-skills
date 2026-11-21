# Analysis Taxonomies

Reusable multi-label regex bucket sets for youth-sentiment corpora. Invariants: match on lowercased `title + " " + selftext`; posts may hit multiple buckets (percentages sum >100%); use IDENTICAL sets across every year/sub in a comparison; ≥2pp deltas are signal.

## Career issues (IndiaCareers, developersIndia)

- fresher_job_hunt: `\bfresher`, `\bunemployed`, `\bjobless`, `job hunt`, `looking for (a |any |some )?(job|work|internship)`, `no (job|offer|call|response)`, `not getting`, `reject`, `unable to (find|get|land|secure)`, `desperat`
- interview_ghosting: `\binterview`, `\bghost`, `\bshortlist`, `\brecruiter`, `\bassessment`, `online test`, `\baptitude`, `panel round`, `coding round`, `no (call|response|reply|update)`
- salary_offer: `\bsalary`, `\bctc`, `\blpa\b`, `\bpackage`, `offer letter`, `job offer`, `\bnegotiat`, `\blowball`, `\bappraisal`, `\bhike\b`, `\bincrement`, `\bstipend`, `\bbond\b`
- layoffs_pip: `\blaid off`, `\blayoff`, `\bfired`, `\bterminat`, `lost (my |the |a )?job`, `job loss`, `\bpip\b`, `on bench`, `\bbenched`
- toxic_workplace: `\btoxic`, `\bmanager\b`, `\bboss\b`, `\bburnout`, `\boverwork`, `\bresign`, `\bquit`, `notice period`, `office politics`, `\bexploit`, `\bmicromanag`, `work culture`
- ai_fear: `\bai\b`, `\bautomation`, `\bchatgpt`, `\bllm`, `\bagentic`, `replace`, `future proof`, `\bobsolete`
- career_switch: `\bswitch`, `\btransition`, `\bpivot`, `career change`, `change (my |the |my )?(career|domain|field)`, `different (domain|field|role)`, `\bupskill`, `\breskill`
- study_abroad: `\babroad`, `\bmasters`, `\bms\b`, `\busa\b`, `\bgermany`, `\bcanada`, `\bvisa\b`, `\bforeign`, `\bmigrat`, `\binternational`
- govt_jobs: `\bssc\b`, `\bupsc`, `\bgovernment`, `\bgovt`, `\bpsu\b`, `bank po`, `\brailway`, `\bias\b`, `group a`, `group b`, `\bcgl\b`, `scientist b`
- education_degree: `\bbtech`, `\bmba\b`, `\bmtech`, `\bphd`, `\bcollege`, `tier[- ]?3`, `\biit\b`, `\bnit\b`, `\bdegree\b`, `\bcse\b`, `\bece\b`, `\bcat\b`, `\bgate\b`, `\bjee\b`, `drop year`, `class (10|11|12)`, `\bcampus`, `\bstudent`
- startup_freelance: `\bstartup`, `\bfounder`, `\bbusiness\b`, `\bfreelanc`, `side (gig|hustle|income)`, `\byoutube`, `passive income`, `own (business|agency|firm)`, `\bentrepreneur`
- mental_health: `\bdepress`, `\banxi`, `\bstress`, `\bhopeless`, `\bsuicid`, `\bcrying`, `giving up`, `\bexhaust`, `\bfrustrat`, `mental health`, `\bregret`, `feeling (very )?lost`
- referrals_networking: `\breferral`, `\blinkedin`, `\bnetwork`, `\bconnection`
- work_life: `\bwfh\b`, `\bremote\b`, `\bhybrid\b`, `work[- ]life`, `\bworkload`, `\bonsite`
- age_pressure: `\b25m\b`, `\b26m\b`, `\b27m\b`, `\b28m\b`, `\b30`, `too late`, `worth it`, `career gap`, `\bgap\b`
- sector_choice: `confused between`, `which (one|is better|job|career|path|option|field|domain)`, `should i (choose|do|take|pursue|join|study|go)`, `career path`, `which field`, `which domain`, `break into`, `how (do|to) (i )?(get|start|break|enter)`

## Money issues (personalfinanceindia, IndiaFinance)

- debt_loans: `personal loan`, `home loan`, `education loan`, `student loan`, `car loan`, `\bloan\b`, `\bemi\b`, `\bdebt\b`, `\brepay`, `\bdefault`, `borrow`
- credit_cards: `credit card`, `\bcc\b`, `card bill`, `card due`, `\bcibil\b`, `credit score`, `limit enhancement`, `lounge access`, `cashback`
- investing: `\bsip\b`, `mutual fund`, `index fund`, `\bportfolio`, `\binvest`, `allocation`, `lump ?sum`, `\belss\b`, `\bppf\b`, `\bnps\b`, `\bepf\b`, `\basset`
- trading_fno: `\bfno\b`, `\boptions?\b`, `\bfutures\b`, `intraday`, `\btrading`, `\bnifty\b`, `stock market`, `share market`, `\bstocks?\b`, `equity`, `swing trade`
- crypto: `\bcrypto`, `\bbitcoin`, `\bbtc\b`, `\beth\b`, `\bethereum`, `\bcoin\b`
- savings_emergency: `emergency fund`, `\bsaving`, `\bcorpus\b`, `net worth`, `fixed deposit`, `\bfd\b`, `liquid fund`, `rainy day`
- salary_income: `\bsalary`, `in[- ]hand`, `take home`, `\bincome\b`, `\bpackage\b`, `\bincrement`, `\bhike\b`, `\bbonus\b`, `\bappraisal`, `\bctc\b`
- budget_expenses: `\bbudget`, `\bexpense`, `\bspending`, `cost of living`, `\brent\b`, `\bgrocer`, `monthly (expense|budget)`, `lifestyle inflation`, `\bafford`
- housing: `buy (a |the )?(home|flat|house|property)`, `house purchase`, `\bproperty\b`, `real estate`, `rent vs buy`, `down ?payment`, `\bhome loan`, `\bbuilder\b`, `under construction`
- marriage_wedding: `\bmarriage\b`, `\bwedding\b`, `\bshaadi\b`, `\bdowry\b`
- family_dependents: `\bparents?\b`, `\bfather\b`, `\bmother\b`, `\bfamily\b`, `\bdependent`, `\bsibling`, `medical bill`, `\bhospital`, `\bsurgery`, `\btreatment`, `\bdisease`
- insurance: `\binsurance\b`, `term plan`, `health (insurance|cover)`, `\bpremium\b`, `\blic\b`, `\bmediclaim`, `\bpolicy\b`
- taxes: `\btax\b`, `\bitr\b`, `income tax`, `\btds\b`, `\b80c\b`, `\b80d\b`, `\bhra\b`, `capital gains`, `\bgst\b`, `tax notice`
- fire_retirement: `\bfire\b`, `\bretire`, `\bpension`, `financial independence`, `\b45x\b`, `early retirement`, `retirement corpus`
- scams_fraud: `\bscam`, `\bfraud`, `\bponzi`, `\bcyber`, `\bphishing`, `upi fraud`, `fake app`, `recovery agent`, `cheat`
- gold: `\bgold\b`, `\bsgb\b`, `sovereign`
- side_income: `side (hustle|income|gig)`, `passive income`, `\bfreelanc`, `\bgig\b`, `second income`, `extra income`, `make money`
- jobloss_finance: `\blaid off`, `job loss`, `\bunemployed`, `\bseverance`, `no income`, `lost (my |the )?job`, `\bfired`
- mental_financial: `\bdepress`, `\banxi`, `\bstress`, `\bhopeless`, `\bpanic`, `\bscared`, `lost everything`, `\btrapped`, `\bregret`, `crying`, `\bsuicid`
- nri_foreign: `\bnri\b`, `\babroad\b`, `foreign (income|currency)`, `\busd\b`, `\bremittance`, `moving (abroad|to)`, `ms abroad`, `\bmasters\b`, `\busa\b`, `\bcanada\b`, `\bdubai\b`, `\bvisa\b`
- banking_ops: `\bbank\b`, `\bsbi\b`, `\bhdfc\b`, `\bicici\b`, `\baxis\b`, `\bkotak\b`, `\baccount\b`, `\bdeposit\b`, `\bkyc\b`, `\bupi\b`, `\brbi\b`, `neft`, `imps`, `\bcheque`

## Debt sub-clusters (problem statements within debt)

Run on the subset of posts matching debt_loans/credit_cards to extract concrete problem statements:

- education loan burden: `education loan`, `student loan`, `study loan`, `80e`
- home loan / EMI strain: `home loan`, `housing loan`, `mortgage`, `\bemi\b`, `overdue`, `missed payment`, `can'?t (pay|afford)`
- emergency loan: `emergency`, `urgent`, `medical`, `\bhospital`, `\bsurgery`, `treatment`
- loan apps / NBFC: `loan app`, `\bmoneyview\b`, `\bslice\b`, `\bnavi\b`, `kreditbee`, `\bnbfc\b`, `instant loan`, `\bfibe\b`, `\bdmi finance`
- parents/family debt: `parents?.{0,30}(loan|debt|borrow)`, `father.{0,30}(loan|debt)`, `family (debt|loan)`, `second loan`, `inherited`
- credit card debt: `credit card.{0,30}(debt|due|bill|outstanding)`, `card (debt|due)`, `minimum due`, `revolving`
- cibil / credit score damage: `\bcibil\b`, `credit score`, `score (dropped|down)`
- debt-free / repayment strategy: `debt[- ]free`, `get out of debt`, `pay (off|it off)`, `clear.{0,20}(loan|debt)`, `become debt`
- guarantor / co-signer trap: `\bguarantor\b`, `co[- ]sign`, `took (a )?loan.{0,25}(my|her|his) name`, `loan.{0,20}(my|her|his) name`
- fraud / fake loans: `fake loan`, `loan.{0,15}(fraud|scam)`, `scam.{0,20}loan`, `loan apps.{0,20}(loot|harass)`, `ponzi`
- debt trap / multiple loans: `another loan`, `loan to pay`, `refinanc`, `balance transfer`, `debt (cycle|trap)`, `multiple (loans|debt)`
- foreclosure / penalties / lien: `foreclose`, `foreclosure`, `prepayment`, `penalty.{0,20}loan`, `\blien\b`

## EMI-stress deep-dive filter

Cross-cutting filter for the "EMI > income" problem, applied across all subs:

- EMIX: `\bemi\b|installment|loan (repay|payment)|mortgage|home loan|car loan|personal loan`
- SHOCK (income side): `laid off|layoff|\bfired\b|\bterminated|unemployed|jobless|job loss|lost (my |the |his |her )?job|salary (cut|reduced|flat|stagnant|freeze)|pay cut|no (increment|salary|job)|on bench|\bbenched|notice period|recession`
- STRESS (mental side): `can'?t (pay|afford|sleep|handle|take|breathe)|unable to (pay|afford)|struggl|anxi|stress|depress|panic|trapped|hopeless|bankrupt|suicid|drown|burden|tension|\bfear\b|nightmare|scared|insomnia|regret|ruin|mental (health|peace|pressure)|sleepless|helpless`
- "shock" posts = EMIX + SHOCK; "mental" posts = EMIX + STRESS.

## Advice/solution clusters (mined from thread comments)

Use on comment bodies fetched via arctic-shift's comments API to answer "what solutions do people suggest":

- negotiate/restructure with bank: `talk (to|with) (the )?bank`, `moratorium`, `restructur`, `negotiat`, `increase.{0,20}tenure`, `lower.{0,20}emi`
- debt consolidation / balance transfer: `consolidat`, `balance transfer`, `single emi`, `take[- ]over`, `refinanc`
- emergency fund / EMI buffer: `emergency fund`, `emi fund`, `6 months`, `3-6 months`, `12 months.{0,30}(emi|expense)`, `buffer`
- sell asset / downsize: `sell (the |your )?(house|flat|home|car|property|asset)`, `liquidat`, `downsize`
- prepay / close loans: `prepay`, `foreclose`, `close.{0,20}loan`, `part payment`, `pay (off|down).{0,20}(loan|debt|principal)`
- pause SIPs/investments: `stop sip`, `pause sip`, `sip.{0,20}(stop|pause|hold)`, `investments.{0,20}(later|stop|pause)`
- cut lifestyle / move back: `move.{0,20}(back|home|with parents)`, `lifestyle.{0,20}(cut|change|reduce)`, `cut (down )?(on )?expense`, `downgrade`
- loan/term insurance: `term (insurance|plan|cover)`, `loan (insurance|protection|cover)`, `insurance.{0,20}(loan|emi|cover)`
- legal / settlement / insolvency: `settlement`, `one[- ]time`, `ots\b`, `sarfaesi`, `insolvenc`, `bankrupt`, `ombudsman`
- PF / savings withdrawal: `\bpf\b`, `epf`, `provident`
- gig / second income / upskill: `freelanc`, `\bgig\b`, `side.{0,15}(income|hustle|job)`, `upskill`, `second (income|job)`, `switch.{0,20}job`
- avoid EMI forever / rent don't buy: `never.{0,30}emi`, `no emi`, `avoid.{0,20}(emi|loan)`, `rent.{0,30}(instead|don'?t buy|vs)`
