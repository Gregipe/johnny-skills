# Induction Module Routing & LLM Prompt Design (Updated May 2026)

## Session Breakthroughs from Greg's ARA Induction Session

### Rule: Module "Continue" vs "Start" Based on History Count

**When creating a new session for an existing tenant**, check conversation history count to decide whether the LLM should "Continue" or "Start":

```python
# Before: always "Start" — causes re-asking of already-answered questions
module_instruction = "Start with Module X..."

# After: check if there's conversation history
hist_count = db.query(CoachingLog).filter(
    CoachingLog.tenant_id == tenant_id,
    CoachingLog.feedback_type.in_(["induction_chat", "induction_chat_response"])
).count()

if hist_count >= 2:  # at least one user + one assistant turn
    module_instruction = "Continue where you left off in Module X..."
else:
    module_instruction = "Start with Module X..."
```

**Threshold:** `hist_count >= 2` means at least one user message and one assistant response. That's enough to consider the conversation "in progress" even if no skills were saved for the current module yet.

**Without this check:** Every server restart causes the LLM to start the module from scratch, re-asking the first question even though the user already answered it.

### Rule: LLM Must Emit Save Blocks BEFORE Conversational Text

LLMs frequently narrate "I've saved that" without emitting the actual `===SAVE_SKILL===` block. The fix is a prominent instruction near the END of the system prompt:

```
## MANDATORY SKILL SAVING — READ THIS FIRST
For every specific fact the customer shares, you MUST begin your response
with a ===SAVE_SKILL=== block BEFORE any conversational text.

If you narrate "I've saved that" without the block, nothing is saved.
Your response MUST start with ===SAVE_SKILL=== when the customer provides
a specific, useful fact.
```

Key design choices:
- **Position:** Near the end of the prompt (not buried in a bullet list mid-prompt)
- **Explicit format:** "Your response MUST start with ===SAVE_SKILL==="
- **Concrete example:** Use realistic data (inbound category, actual channel names)
- **Negative feedback:** "If you narrate without the block, nothing is saved"
- **No conflicting instructions:** Remove any ambiguous "you can save" language from earlier sections

### Rule: Contradiction Detection

Between-module contradiction is a first-class requirement. Add as an explicit rule:

```
## FLAG CONTRADICTIONS IMMEDIATELY
Cross-reference every new answer against everything the customer has already
told you. If anything seems inconsistent — different target segments,
conflicting channel performance, different pricing — flag it right away.
Say: "Earlier you mentioned X, but now you're saying Y — can you help me
understand which is correct?"
```

### Category Naming Consistency

**Critical:** The category name used in `===SAVE_SKILL===` blocks MUST match the category name in the backend's `get_induction_state()` categories dict. A mismatch (e.g., LLM saves with `gtm_learnings` but state checker looks for `gtm_learning`) means skills are saved but invisible — the module shows 0 skills despite 19+ being in the DB.

Check all THREE layers for consistency:
1. **Backend:** `categories` dict in `get_induction_state()`
2. **LLM prompt:** The example in the save block instruction
3. **Frontend:** `MODULES` array, `data-tab` attributes, `MODULE_NAMES` keys

### Conversation History Replay

For proper session continuity after restart:

```python
# 1. Only replay logs that have proper user/assistant pairs
# Skip old "induction" type logs (one-sided, no assistant responses)
recent_logs = db.query(CoachingLog).filter(
    CoachingLog.tenant_id == tenant_id,
    CoachingLog.feedback_type.in_(["induction_chat", "induction_chat_response"])
).order_by(CoachingLog.id.desc()).limit(8).all()
recent_logs.reverse()

# 2. Map feedback_type to role correctly
for log in recent_logs:
    role = "user"
    if log.feedback_type == "induction_chat_response":
        role = "assistant"
    messages.append({"role": role, "content": log.feedback})
```

### Dictation Accumulation Fix

For browser-native STT: the `fullTranscript` (or `dictationText`) variable MUST be at module scope, not inside the `getUserMedia` callback. If it's inside the callback, it resets to `''` every time recognition restarts (silence timeout, error, or re-click) — losing all accumulated speech.

```javascript
var dictationText = '';  // module scope — survives restarts

recognition.onresult = function(e) {
    var interim = '';
    for (var i = e.resultIndex; i < e.results.length; i++) {
        var r = e.results[i];
        if (r.isFinal) {
            dictationText += r[0].transcript + ' ';
        } else {
            interim = r[0].transcript;
        }
    }
    inp.value = dictationText + interim;
};
```

### CSS Specificity for Mic Button

`.input-inner button` (0,1,1) overrides `.mic-btn` (0,1,0). Always use `.input-inner .mic-btn` (0,2,1) for custom buttons inside the input area. Otherwise the mic button inherits the Send button's blue background and becomes a blue blob.
