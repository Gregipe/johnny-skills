# Emotion / Need-State Audit — Lexicon Buckets

Regex buckets for Layer-1 surface tagging of community titles. Tune keywords
to the domain; counts are a first pass, hand-verification decides.

```python
states = {
 'anxiety_fear':   r'scared|afraid|worry|panic|anxious|fear|stress',
 'despair':        r'lost|depress|hopeless|no purpose|drowning|exhausted|tired of|screwed',
 'uncertainty':    r'clueless|confused|doubt|help|advice|should i|how do i|what to do|unable to|genuinely|clarify',
 'guilt_shame':    r'obsess|careful with money|suffering|guilt|ashamed',
 'hope_aspire':    r'start|begin|journey|future|dream|fire|retire|grow|build|reach|goal|track',
 'comparison':     r'others|everyone|people earning|lifestyle of|net worth',
 'family_strain':  r'parent|father|mother|son|wife|family|inherit|wedding|abuse',
 'security_seek':  r'enough|emergency|stability|safe|secure|insurance',
}
```

## Reading the output

- Frequency = title counts. Intensity = deep read of bodies ("mentally
exhausted", "haven't slept in 4 days" — one body can outweigh ten titles).
- High-engagement signal: upvote counts on emotionally loaded threads show
  collective resonance beyond what a count of occurrences suggests.
- The absent state: check what NOBODY posts. On r/personalfinanceindia,
  contentment is missing — even success posts ask "what can we do better".
  The missing terminal state is a positioning gap.
- Brand implication: pick ONE brand emotion that serves all found states
  (e.g. calm competence for finance), and list the emotional job each state
  needs from the product (certainty / progress / rescue-without-judgment /
  neutral arbitration / permission).
