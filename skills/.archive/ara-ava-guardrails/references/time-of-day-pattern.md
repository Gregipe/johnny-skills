# Time-of-Day Pattern for System Prompts

## The Problem

LLMs default to "Good morning" regardless of actual time, because:
1. "Good morning" is over-represented in training data as the default greeting
2. AM/PM parsing requires a reasoning step the model skips for speed
3. Vague instructions ("Use time-appropriate greetings") don't override the training bias

## The Fix — Explicit Pre-Computed Field

Don't make the LLM parse AM/PM. Compute the time-of-day label server-side:

```python
IST = timezone(timedelta(hours=5, minutes=30))
now_ist = datetime.now(IST)
_hour = now_ist.hour
if 5 <= _hour < 12:
    _tod = "Morning"
elif 12 <= _hour < 17:
    _tod = "Afternoon"
elif 17 <= _hour < 21:
    _tod = "Evening"
else:
    _tod = "Night"
```

Inject into the system prompt as:

```
Current time: Friday, June 05, 2026 at 03:33 PM IST (UTC+5:30) — Time of day: Afternoon
```

The Tone section should reference the field by name:

```
Greet {owner_name} by name using the appropriate Time of day from the Context section 
(Morning / Afternoon / Evening / Night). E.g. "Good morning, Greg" in the morning, 
"Good afternoon, Greg" in the afternoon, etc.
```

## Applying to Other Categorical Decisions

This pattern generalizes. Whenever the LLM needs to pick from discrete options based on continuous data (time, ranges, scores, tiers), pre-compute the label:

| Raw data (bad) | Label (good) |
|---------------|-------------|
| `03:33 PM` | `Time of day: Afternoon` |
| `score: 85` | `Score tier: High` |
| `distance: 450km` | `Range: Long` |
| `age: 730 days` | `Age bucket: Old` |
| `temp: 38°C` | `Weather: Hot` |

The LLM does string matching between the label in context and the label in instructions — trivial, zero reasoning, zero errors.

## Pitfall — Example in Prompt Primes "Morning" as Default (June 15, 2026)

Even with a correct `Time of day: Evening` field AND explicit greeting instructions, Ava said "Morning, Greg" at 8 PM. Root cause: the base prompt had a single greeting example:

```
Greet by time of day... e.g. "Morning, {user_name}."
```

The LLM pattern-matched "greeting example → default to Morning" regardless of the `Time of day` field. The single example acted as behavioral primer.

**Fix:** Show BOTH morning and evening in the example, with explicit conditionals:

```
Greet by time of day... e.g. "Evening, {user_name}." if it's evening,
"Morning, {user_name}." if it's morning.
```

This prevents the LLM from treating "Morning" as the one and only greeting pattern. The conditional makes the LLM check the `Time of day` field before choosing.

**Also add a hard constraint in the Context section itself:**

```
Greeting rule: Use the Time of day above. Match your greeting.
NEVER say Good morning after noon, NEVER say Good evening before 5 PM.
```

The constraint sits directly after the `Time of day` field so the LLM cannot skip it.

## Verification

1. Send "good morning" / "hi" at different times of day
2. Check response starts with correct greeting ("Good afternoon" at 2 PM, "Good evening" at 7 PM)
3. If still defaults to morning, check: (a) the `Time of day` field is correct, (b) the example in the base prompt doesn't prime a single greeting, (c) the hard constraint is present in the Context section
4. Debug by querying the DB: check what context was actually sent to the LLM
