---
name: llm-comparison-tools
description: "Build tools that compare LLMs head-to-head (debate chambers, evaluation arenas, side-by-side test harnesses). Covers multi-model orchestration, split-screen UIs, turn-by-turn context management, adjudication/ judging."
version: 1.1.0
author: John (Hermes for Greg)
license: MIT
---

# LLM Comparison Tools

Build interactive tools that pit two (or more) LLMs against each other in structured comparison. The canonical example is the Debate Chamber — two models debate a motion turn by turn with a third model as judge.

## When to Use This

- User wants to compare two models on the same task
- User wants to see how different models argue the same position
- User wants to build a side-by-side LLM comparison UI
- Any task involving two+ model calls with structured back-and-forth

## Architecture Pattern

### Core Flow (Model-vs-Model)

```
User Motion → Model A (FOR) → Model B (AGAINST) → Turn Manager (context accumulator) → Model A (rebuttal) → ...
                                                                                                      ↓
                                                                                             Adjudicator Model (judge)
```

### Player Types: User-as-Debater

Each debate slot (FOR and AGAINST) can be occupied by either an LLM or a human ("User"). Track this with booleans in the session:

```python
session = {
    "for_is_user": True/False,      # Is the user playing FOR?
    "against_is_user": True/False,  # Is the user playing AGAINST?
    "for_key": str | None,          # None if user is on this side
    "against_key": str | None,      # None if user is on this side
}
```

When it's the user's turn:
1. Frontend calls `/next` → backend returns `{type: "user_input_required", side: "FOR", stage_label: "Opening Statement"}`
2. Frontend shows a textarea + "Submit Argument" button
3. User types argument, submits via `POST /submit-user-turn` with `{content: str}`
4. Backend appends to history, advances `stage_index`
5. Frontend renders the user's argument as a card (speaker="You", grey header)
6. "Generate Next Argument" button reappears for the next turn

**Constraints:**
- Both sides cannot be User at the same time — at least one LLM required
- User turns cannot be regenerated (no `/regenerate` for user-submitted content)
- Simulate mode is disabled when user is a player

### Key Design Decisions

1. **API abstraction layer**: Wrap each model behind a uniform async function. Gregory's setup has:
   - **DeepSeek**: OpenAI-compatible API (`https://api.deepseek.com/v1/chat/completions`)
   - **MiniMax**: Anthropic-compatible API (`https://api.minimax.io/anthropic/v1/messages`)
   - See `references/api-providers.md` for exact endpoint URLs, model IDs, and auth format

2. **Context accumulation**: Each turn appends to a shared `history` list. Pass the FULL history to each subsequent call — models need to see the opponent's arguments to respond properly.

3. **Adjudication**: Use a third model or the same model for judging. The judge prompt should be impartial and structured — summary, evaluation criteria, winner declaration.

## UI pattern: Split-screen (FOR / AGAINST) with independent scroll columns. Two aesthetic options exist:

   - **Dark courtroom** (original): Red/teal/gold accents on dark background, gavel icon, theatrical banners — good for one-shot live debates
   - **Light iOS** (updated): White cards, soft gray backgrounds, blue/red accent colors, SF-style typography, minimal — better for reading-focused turn-by-turn consumption

   Use a loading overlay with per-round progress so the user doesn't stare at an empty screen during API calls. For turn-by-turn (step mode), use a subtle card-based loading indicator instead — no overlay.

## Handling Incomplete / Truncated LLM Responses

**Problem:** LLM API calls can silently return truncated content — hitting `max_tokens`, timing out during generation, or dropping mid-response due to network blips. In a comparison/debate tool, a half-generated argument rendered to the user is worse than no argument: it wastes their time, breaks the flow, and there's no way to recover the specific turn.

**Three-Layer Protection:**

```
Layer 1: Completeness Validation (backend) — reject truncated output immediately
Layer 2: Auto-Retry (backend) — regenerate up to 2 more times transparently
Layer 3: Manual Retry (frontend) — if still incomplete, let user click "Retry" to redo that specific turn
```

### Layer 1: Completeness Heuristics (`is_argument_complete()`)

After every LLM call, run a heuristic check before accepting the response:

```python
def is_argument_complete(content: str) -> bool:
    """Check if an LLM-generated response appears complete (not truncated)."""
    if not content or not content.strip():
        return False
    text = content.strip()

    # Error or empty responses
    if text.startswith("[Error:") or text.startswith("[Empty"):
        return False

    # Must have meaningful content
    if len(text) < 50:
        return False

    # Strong completion signal: ends with sentence-ending punctuation
    last_char = text[-1]
    if last_char in '.!?':
        return True

    # Ends with quotes after punctuation (e.g. .")
    stripped = text.rstrip('\'"\u201d\u201c')
    if stripped and stripped[-1] in '.!?':
        return True

    # Strong truncation signals
    if text.endswith(',') or text.endswith(';'):
        return False
    if text.endswith('..') or text.endswith('...') or text.endswith('…'):
        return False

    # Ends with a hanging conjunction/preposition — almost certainly cut off
    import re
    tokens = re.findall(r'\b\w+\b', text)
    if tokens and tokens[-1].lower() in (
        'and', 'but', 'or', 'for', 'nor', 'yet', 'so',
        'the', 'a', 'an', 'to', 'with', 'because',
        'that', 'this', 'these', 'those', 'which',
        'while', 'although', 'since', 'until',
    ):
        return False

    # Unmatched code block — truncated mid-code
    if text.count('```') % 2 != 0:
        return False

    # Ends with a letter/digit and no closing punctuation — likely truncated
    if last_char.isalpha() or last_char.isdigit():
        return False

    return True
```

**Heuristic rules (in priority order):**
- **Hard reject**: Error responses, empty strings, content under 50 chars
- **Strong complete**: Ends with `.`, `!`, `?` (including after closing quotes)
- **Strong truncated**: Ends with `,`, `;`, `..`, `...`, `…` (trailing off)
- **Hanging word**: Last word is a conjunction/preposition/article — model was mid-sentence
- **Broken markdown**: Unmatched triple backtick count
- **No punctuation**: Ends on a letter/digit without closing punctuation — model hit `max_tokens`

### Layer 2: Auto-Retry with Backoff

Wrap the LLM call in a retry loop:

```python
async def call_llm_with_retry(model_key, system_prompt, user_prompt, max_retries=2):
    for attempt in range(max_retries + 1):
        content = await call_llm(model_key, system_prompt, user_prompt)
        if is_argument_complete(content):
            return (content, attempt > 0, attempt)
        if attempt < max_retries:
            await asyncio.sleep(1)  # brief backoff
    # Exhausted retries — return best effort (frontend will show retry button)
    return (content, True, max_retries)
```

Returns `(content, was_retried, retry_count)`. Each response carries a `complete` boolean and `retry_count` integer so the frontend knows the state.

### Layer 3: Regenerate Endpoint (Manual Retry)

Add an endpoint that regenerates the LAST turn only, overwriting it in-place rather than advancing the stage:

```
POST /api/chamber/{session_id}/regenerate → Regenerates the last turn
```

**Key behavior:**
1. Determines which stage the last turn belongs to (via `turn_number`)
2. Builds the prompt using history UP TO (not including) the failed turn — so the model gets fresh context without seeing its own truncated output
3. Calls the LLM with retry and completeness validation
4. **Overwrites** the last entry in both `history[]` and `turns[]` — does NOT append
5. Does NOT advance `stage_index` — the state machine stays where it is
6. Returns the replaced turn data to the frontend for in-place DOM swap

**Do NOT advance `stage_index` after regeneration** — the stage was already advanced when the turn was first generated. Regeneration replaces content at the same stage.

### Frontend Fail-Safe UI

The `complete` flag from every API response controls the button state:

| `complete` | `is_last_debate_turn` | Button shown | Action |
|-----------|----------------------|--------------|--------|
| `true` | `false` | "Generate Next Argument →" (blue) | Calls `/next` |
| `true` | `true` | "Adjudicate Debate ⚖️" (blue) | Calls `/next` |
| `false` | any | "Retry Incomplete Argument 🔄" (orange) | Calls `/regenerate` |

**Visual feedback for incomplete turns:**
- Turn badge shows `⚠️ Incomplete` in orange instead of the stage label
- Orange warning banner inside the card: "This argument appears incomplete. Click 'Retry' to regenerate."
- Retry button is orange (`#fff5e6` background, `#e65100` text/outline) — visually distinct from the blue primary button

**In-place card replacement:**
- When `/regenerate` returns a new turn, find the last `.turn-card` matching that side (FOR left column, AGAINST right column)
- Fade out (200ms opacity transition), swap innerHTML, fade back in
- Scroll to the card so the user sees the replacement
- Animations prevent jarring visual jumps

## Delivery Mode: Batch vs Step-by-Step

Two architecture patterns exist:

| Mode | API | Pattern | Use When | UX |
|------|------|---------|----------|-----|
| **Batch** | `POST /api/chamber/{id}/simulate` | Generates all remaining turns + adjudication in one backend loop, returns `{turns: [...], adjudication: {...}}` | User wants instant results, both sides are models | Loading overlay with per-turn progress text, frontend renders all cards with staggered 100ms entrance animations after response arrives |
| **Step-by-Step** | `POST /api/chamber/init` → 1st turn → `POST /api/chamber/{id}/next` → remaining turns one at a time | User wants to read each argument before seeing the next | Single loading card per turn, "Generate Next Argument" button, no overlay. When user is a player, textarea input replaces the button at their turns |

### Step-by-Step API Pattern

```
POST /api/chamber/init                     → Returns { session_id, turn(1st) }
POST /api/chamber/{id}/next                → Returns { turn } or { type: "adjudication" }
POST /api/chamber/{id}/submit-user-turn    → Accept user's typed argument for their turn
POST /api/chamber/{id}/simulate            → Batch-generated all remaining turns + adjudication
POST /api/chamber/{id}/regenerate          → Regenerates the last turn in-place
GET  /api/chamber/{id}/status              → Returns full session state
```

- `/init`: Creates a session and generates the first turn (auto-validates for completeness). Accepts a `model_for` or `model_against` value of `"user"` for user-as-debater mode.
- `/next`: Generates the next turn with FULL debate history as context, auto-validates + auto-retries. Returns `{type: "user_input_required"}` when the current turn belongs to the human debater.
- `/submit-user-turn`: Accepts `{content: str}` for user's typed argument when it's the human's turn. Validates current stage is user's, appends to history, advances stage_index. Body: `{content: "User's argument text here"}`.
- `/simulate`: Generates ALL remaining LLM turns + adjudication in a single call. Only works when both sides are models (not user). Returns `{type: "simulation", turns: [...], adjudication: {...}}`. Use this for batch mode — frontend renders all turns with staggered entrance animations.
- `/regenerate`: Re-runs the LAST turn's prompt (without the truncated response in history), overwrites in-place. Only used when a turn comes back with `complete: false` after auto-retry is exhausted. Cannot regenerate user-submitted turns.
- `/status`: Returns everything (turns, adjudication, current stage, models used)

Each `next` call generates the subsequent turn with the FULL debate history passed as context. Turns are NOT pre-computed — they're generated on-demand so each model sees the opponent's actual arguments before responding.

Every turn response includes:
| Field | Type | Description |
|-------|------|-------------|
| `content` | string | The generated argument |
| `complete` | boolean | `true` if passed completeness heuristics |
| `retry_count` | int | How many retries were attempted (0 = first try) |

### Opening Statement Independence

For the FIRST opening statements (both sides), append an instruction to the system prompt:
> "Do NOT reference or respond to any opposing arguments yet — simply build the best possible case for your position."

This prevents Model B's opening from reading like a rebuttal to Model A. Rebuttal rounds restore the "respond directly to the opponent" instruction.

## Prompt Engineering for Structured Debates

### System Prompt Structure

Each side gets a system prompt that defines:
- Their role ("skilled debater arguing FOR/AGAINST the motion")
- Mandate ("cite specific, verifiable examples")
- Constraints ("200-350 words", "keep it sharp")
- Rebuttal rule ("directly address the opponent's previous argument, quote and counter")

### Turn Distinction

Each API call needs a stage-specific instruction appended to the user message:

| Stage | Instruction Key |
|-------|----------------|
| Opening | "Present your opening arguments with specific examples." |
| Rebuttal | "Respond directly to [opponent]'s last arguments. Quote their specific claims and counter with evidence." |
| Closing | "Summarize your strongest points and explain why your side wins." |

### Adjudicator Prompt

The judge should evaluate on:
- Quality of evidence and examples
- Logical consistency
- How well each side addressed counter-arguments
- Persuasiveness

## Round Structure

For a full debate with opening + 3 rounds:

1. Model A: Opening Statement (FOR)
2. Model B: Opening Statement (AGAINST)
3. Model A: Rebuttal — addresses B's opening point by point
4. Model B: Rebuttal — addresses A's opening point by point
5. Model A: Second Rebuttal — counters B's first rebuttal
6. Model B: Second Rebuttal — counters A's first rebuttal
7. Model A: Closing Statement
8. Model B: Closing Statement
9. Adjudicator: Final verdict

## Available Reference Implementations

- `references/debate-chamber/` — Full working debate app (Python FastAPI + HTML/CSS UI)
  - `debate_server.py` — Backend with all API integration
  - `templates/index.html` — Split-screen iOS-style UI
  - Run with: `cd ~/Documents/debate_app && /Users/greg/.hermes/hermes-agent/venv/bin/python3.11 debate_server.py`
  - Open: `http://127.0.0.1:8765`
  - **Deployment note**: The app is auto-started via a launchd service (`com.greg.chamber` in `~/Library/LaunchAgents/`). There are TWO code locations — the working copy at `~/Documents/debate_app/` AND the launchd copy at `~/Library/Application Support/chamber/`. Both must be updated and the launch agent reloaded (`launchctl bootout gui/$(id -u)/com.greg.chamber && launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.greg.chamber.plist`). The launchd plist must use a Python that has httpx installed (Hermes venv Python, NOT system /usr/bin/python3).

## Pitfalls

- **Don't use the same model for BOTH sides AND as judge** — the judge may show bias toward its own output. Use a different model or the same model with a distinct system prompt.
- **API rate limits**: MiniMax has a tight RPM limit. Space calls 1-2 seconds apart if needed, or use the higher-throughput model variants. Error `status_code: 1002` = rate limit exceeded.
- **Context window**: Each turn adds to the prompt. For 8-turn debates, total prompt can reach 4K-6K tokens. Stay within model context limits.
- **Timeouts**: Each API call takes 10-30 seconds. Total debate time: 2-5 minutes. Show loading progress per round, not a spinning wheel.
- **Model availability**: DeepSeek models are listed at `https://api.deepseek.com/v1/models`. Available: `deepseek-v4-flash`, `deepseek-v4-pro`. MiniMax models use Anthropic API format at `https://api.minimax.io/anthropic/v1`.
- **Opening statements sounding like rebuttals**: If no independence guard is added to the prompt, Model B's opening will respond to Model A's opening instead of making its own case. Always add "Do NOT reference or respond to any opposing arguments yet" for opening stages.
- **System Python may not have httpx**: `/usr/bin/python3` on macOS 3.9+ often lacks httpx/fastapi/uvicorn. Always use the Hermes venv Python or a venv with dependencies installed. Run with `cd ~/Documents/debate_app && /Users/greg/.hermes/hermes-agent/venv/bin/python3.11 debate_server.py`.
- **Launchd auto-restart**: The chamber app has a launchd agent that auto-starts on boot and auto-restarts on crash. You must `launchctl bootout gui/$(id -u)/com.greg.chamber` before deploying new code, update BOTH code copies (`~/Documents/debate_app/` and `~/Library/Application Support/chamber/`), then re-bootstrap. If you only edit one copy, the old version will keep running.
- **MiniMax thinking blocks**: MiniMax responses include `thinking` blocks (reasoning) interleaved with `text` blocks. Always iterate `content[]` to extract only `type: "text"` blocks. Not doing so results in blank replies.
- **LLM responses can truncate silently**: Models hit `max_tokens`, time out, or drop mid-sentence. Always run `is_argument_complete()` on every response before accepting it. Without this check, the UI renders half-generated arguments with no way to recover the specific turn. See the "Handling Incomplete / Truncated Responses" section above.
- **Regenerate replaces history, don't advance stage**: When implementing a regenerate endpoint, the last turn's content overwrites in-place — `stage_index` stays unchanged. Appending instead of replacing creates duplicate entries and breaks the turn counter.

## Verification

After building a comparison tool:
1. Test with a simple motion (e.g., "AI will replace more jobs than it creates") — both models should generate distinct, coherent arguments
2. Verify rebuttals explicitly reference the opponent's claims (not generic responses)
3. Check the adjudicator actually picks a winner with justification
4. Confirm the UI shows turns in order with clear side/round labels
