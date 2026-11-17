# Chat Suggestion Chips — Capability-Driven Pattern

## Pattern

Chat suggestion chips bridge what the agent CAN do and what the USER SEES. After adding new tools, the suggestions endpoint must be updated so users immediately discover the new capability.

## Implementation

The `/api/agent/suggestions/{tenant_id}` endpoint (in server.py) returns clickable chips shown on new chat load.

### Contextual suggestions (per-lead/deal)
```python
# Lead-specific: based on stage
for l in leads[:3]:
    if stage_hint in ("new", "reached_out"):
        suggestions.append(f"Send a WhatsApp to {name}{context}")
    elif stage_hint in ("engaged", "qualified"):
        suggestions.append(f"Move {name} to the next stage{context}")

# Deal-based: news search
for d in deals[:2]:
    suggestions.append(f"Search the latest news about {org}")
```

### General capability suggestions (always shown)
Add chips for every major tool category:
```python
suggestions.append("Give me a summary of today's activity")       # → get_summary
suggestions.append("Remind me to call Greg at 2PM on Monday")     # → set_reminder
suggestions.append("What's happening with the Swiggy deal?")      # → get_lead_detail
suggestions.append("Save this learning: mid-market pricing is ₹15/min") # → save_learning
suggestions.append("Search knowledge base for pricing info")       # → search_knowledge_base
suggestions.append("Schedule a follow-up to Rajesh in 2 hours")   # → schedule_message
suggestions.append("Show me all leads in pipeline")               # → search_leads
suggestions.append("What's my pipeline overview?")                 # → get_pipeline_summary
suggestions.append("Search the web for AI voice agent trends")    # → web_search
```

## Key Rules

1. **Every tool category gets at least one suggestion chip** — if you add tools but don't update suggestions, users won't discover them
2. **Natural language only** — chips are plain text, not tool names. The LLM maps user text to tools
3. **De-duplicate** — use a `seen = set()` to prevent duplicates when multiple leads trigger similar suggestions
4. **Clear on first message** — frontend hides suggestions when the user sends their first message (`document.getElementById('chatSuggestionChips').style.display = 'none'`)
