# Prompt-Audit: Anti-Hallucination Pattern

## The Bug
The `EXTRACT_SKILLS_PROMPT` in `document_skills.py` contained a format example:
```json
{"category": "guardrail", "key": "pricing_tiers", "value": "<=10000 min: Rs 4/min, 10001-20000: Rs 3.5/min, >20000: Rs 3/min"}
```

The LLM copied this example verbatim when extracting skills from hunar.ai — a website that has NO pricing. The prompt primed the model to invent pricing data.

## The Fix (4 layers)

### Layer 1: Remove priming examples
Replace specific format examples with generic placeholders:
```json
// Before: primes the LLM to output specific fake data
{"category": "guardrail", "key": "pricing_tiers", "value": "<=10000 min: Rs 4/min..."}

// After: generic, forces the LLM to use actual document content
{"category": "guardrail", "key": "another_key", "value": "Another exact quote — leave empty if not in document"}
```

### Layer 2: Forbid extrapolation in instructions
```
// Before
"Extract ALL specific, actionable pieces of information from this document."

// After
"Extract ONLY facts explicitly stated in the document above. DO NOT invent, extrapolate, or guess. Leave categories empty if not present."
```

### Layer 3: Temperature → 0
```
temperature=0.1 → temperature=0  // removes ALL creative freedom
```

### Layer 4: Verification gate (code, not deployed in this session)
Post-extraction: grep each skill value against the source document text. If <25% of meaningful words appear in the source, discard the skill and log a HALLUCINATION warning.

## Audit Checklist
Before deploying ANY extraction prompt:
1. [ ] Format examples use generic placeholders, NOT real-looking data
2. [ ] Instructions explicitly forbid extrapolation
3. [ ] Category descriptions say "X IF present" not "X"
4. [ ] temperature=0 for deterministic extraction
5. [ ] After first run: verify 5 random extracted skills against raw document text
