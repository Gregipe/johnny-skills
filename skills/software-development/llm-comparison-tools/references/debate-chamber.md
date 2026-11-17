# LLM Debate Chamber (Chamber)

A split-screen debate arena where two LLMs argue FOR and AGAINST a motion, turn by turn, with an adjudicator delivering a final verdict. Built for Gregory's local setup at `/Users/greg/Documents/debate_app/`.

## Location

```
/Users/greg/Documents/debate_app/
├── debate_server.py      # FastAPI backend (session-based, step-by-step)
└── templates/
    └── index.html         # Light iOS-aesthetic UI
```

## Quick Start

```bash
cd /Users/greg/Documents/debate_app && /usr/bin/python3 debate_server.py
# Open: http://127.0.0.1:8765
```

## How It Works

### Backend (debate_server.py)

FastAPI server on port 8765. Step-by-step session-based pattern.

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Serves the HTML UI |
| `/api/models` | GET | Returns available models |
| `/api/chamber/init` | POST | Creates session, generates 1st turn (FOR opening) |
| `/api/chamber/{id}/next` | POST | Generates + returns the next turn or adjudication |
| `/api/chamber/{id}/status` | GET | Returns full session state |

### Step-by-Step Flow

1. User submits motion + model selections via `/api/chamber/init`
2. Backend generates only the first turn (FOR opening), returns it with `session_id`
3. User reads the turn, clicks "Generate Next Argument"
4. Frontend calls `/api/chamber/{id}/next` — backend generates the next turn with FULL debate history as context
5. Repeat until all 8 turns + adjudication are done
6. Turns are NOT pre-computed — each is generated on-demand so each model sees the opponent's actual arguments

### Debate Flow (9 stages)

| # | Stage | Side | UI Button Label |
|---|-------|------|-----------------|
| 1 | Opening Statement | FOR | Generate Next Argument → |
| 2 | Opening Statement | AGAINST | Generate Next Argument → |
| 3 | Rebuttal — Round 1 | FOR | Generate Next Argument → |
| 4 | Rebuttal — Round 1 | AGAINST | Generate Next Argument → |
| 5 | Rebuttal — Round 2 | FOR | Generate Next Argument → |
| 6 | Rebuttal — Round 2 | AGAINST | Generate Next Argument → |
| 7 | Closing Statement | FOR | Generate Next Argument → |
| 8 | Closing Statement | AGAINST | Deliver Verdict ⚖️ |
| 9 | Adjudication | Judge | (auto) |

### Opening Statement Independence

FOR and AGAINST openings are independent — neither side references the other. The prompt instruction:
> "Do NOT reference or respond to any opposing arguments yet — simply build the best possible case for your position."

Rebuttal rounds restore "respond directly to the opponent's arguments" instruction.

### UI Features (Light iOS Theme)

- White cards on light gray background
- Apple SF-style typography (Inter font)
- Header: "Chamber" with Latin quote
- FOR turns: red accent, light red header
- AGAINST turns: blue accent, light blue header
- Adjudication: gold accent card
- Sticky header with backdrop blur
- Fade-up animations on each turn card
- Mobile-responsive (single column on small screens)
- No loading overlay — subtle spinner card per turn
