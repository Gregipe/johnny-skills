# Search-Before-Asking Rule (2026-06-29)

**Correction signal**: Greg saying "Search for it and get it" or "you do have
the API key — search for it" means you asked for something he already provided
instead of checking existing sources first.

## Rule

Before asking Greg for any credential, API key, file path, or configuration
value, exhaust these sources in order:

1. **Current profile's .env and config.yaml**
   - `~/.hermes/profiles/<profile>/.env`
   - `~/.hermes/profiles/<profile>/config.yaml`

2. **Default profile**
   - `~/.hermes/.env`
   - `~/.hermes/config.yaml`

3. **Session history** — `session_search` for past sessions where the key was set
   - Look for provider names: "GLM", "zai", "openai", etc.
   - Look for key variable names: "GLM_API_KEY", "API_KEY"

4. **Project files** — `.env`, `config.yaml`, or credential files in the working directory

Only ask when all four sources come up empty. When you do find the value,
confirm with a masked preview: `GLM_API_KEY=399d...CVV ✓`.

**Real example**: Greg asked to switch TA to GLM 5.2. Johnny asked "What's
your API key?" — but the key was already in `~/.hermes/profiles/johnny/.env`
(set in session `20260627_183357_cdb26c` on June 27). Greg had to say
"Search for it and get it." The key was `GLM_API_KEY` in the profile's
.env — not commented out, not in a different file.

## Discovery Pattern

```python
# Don't ask — search first
from hermes_tools import search_files

# 1. Check profile .env
search_files(pattern="GLM_API_KEY|ZAI_API_KEY", target="content",
             path="~/.hermes/profiles/johnny/", file_glob=".env*")

# 2. Check default .env
search_files(pattern="GLM_API_KEY|ZAI_API_KEY", target="content",
             path="~/.hermes/", file_glob=".env*")

# 3. Search past sessions
session_search(query="GLM_API_KEY api key", limit=5)

# Only after all three: ask Greg
```

## Why This Matters

Greg provides credentials exactly once and expects them to persist. Asking
again signals to Greg that the system is forgetful or careless. This erodes
trust in the agent's competence. The cost of searching (seconds) is zero
compared to the cost of asking Greg to re-provide something he already gave.
