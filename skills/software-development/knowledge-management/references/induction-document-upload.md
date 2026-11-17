# Induction Document Upload — Implementation Details

## Files Modified

### server.py
- **parse_document()** (line ~75) — Already existed for PDF/DOCX/PPTX/TXT parsing using PyMuPDF, python-docx, python-pptx
- **New endpoint**: `POST /api/induction/{tenant_id}/upload` (after line ~2877)
  - Accepts multipart file upload
  - Calls `parse_document()` to extract text
  - Saves to Document table + raw file to UPLOAD_DIR
  - Calls `extract_skills_from_document()` from document_skills.py
  - Generates Ava's conversational response via LLM
  - Runs `_run_induction_on_doc()` for contradiction checking against existing docs

### document_skills.py (new file)
- `EXTRACT_SKILLS_PROMPT` — structured extraction prompt template
- `extract_skills_from_document(doc, tenant_id, db)` — core function:
  - Validates minimum content length (50 chars)
  - Calls LLM with extraction prompt (truncated to 6000 chars)
  - Parses JSON array response
  - Upserts into Skill table by key (deduplicates)
  - Returns list of saved skill keys like `["guardrail/pricing_tier_starter", "proposition/company_offering"]`

### induction_template.py (chat UI)
- Hidden file input: `<input type="file" id="fileInput" accept=".pdf,.docx,.doc,.pptx,.txt">`
- Attachment button reusing `.mic-btn` class styling:
  ```html
  <button onclick="document.getElementById('fileInput').click()" class="mic-btn" title="Attach document">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
      <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
    </svg>
  </button>
  ```
- `uploadFile()` JS function — uploads via FormData to /api/induction/{TENANT}/upload
- 10MB size limit, shows typing indicator, handles errors gracefully

## Skills Context Injection into Scheduled Messages

### The Broken Loop
- `_generate_step_message()` (line ~2480) built its own system prompt from template config only
- Induction skills never reached automated email/WhatsApp generation
- Skills were visible in agent chat (coaching interface) but not in outbound messages

### The Fix
- `_execute_action()` (line ~6091) now queries Skill table before calling `_generate_step_message()`
- Skills are categorized by category (proposition, gtm_learnings, inbound, guardrail, etc.)
- Formatted as `[category]\n  - key: value (truncated to 300 chars)\n  - ...`
- Passed as `skills_context` parameter to `_generate_step_message()`
- Injected as `## What You Know About This Business (from induction)` section in the generation prompt

### Order of Operations in _execute_action()
1. Load cadence config from DB
2. Load recent conversation history for the lead
3. Query Skill table for TENANT_ID, organized by category
4. Call `_generate_step_message()` with skills_context
5. Send via WhatsApp or email based on channel

## Test Results

16 skills extracted from a pricing text file:
- `pricing_tier_starter`: Starter tier up to 10,000 min at Rs 4/min
- `pricing_tier_growth`: 10,001 to 20,000 min at Rs 3.5/min
- `company_offering`: Hunar.ai uses voice-to-voice AI
- `tat_reduction_proven`: 50% reduction proven at Rebel Foods and Flipkart
- `multilingual_support`: Hindi, English, Hinglish, Bengali, Tamil
- `soc2_compliance`: All plans include SOC 2 compliance
- And 11 more across guardrail, proposition, and segment_signal categories

## Pitfalls Encountered

1. **Response format for skill summary** — Initial implementation tried to format each extracted skill into the LLM prompt for Ava's response. This caused Ava to say "extraction came back empty" even when 16 skills were saved. Fix: use category counts instead of individual skill names in the LLM response prompt.

2. **extract_skills_from_document in a different file** — Import from `document_skills` module works, but the contradiction check `_run_induction_on_doc` is in server.py. The upload endpoint had to import from itself: `from server import _run_induction_on_doc`.

3. **Only one injection point was wired** — The original induction data was injected into the agent chat prompt but NOT into `_generate_step_message()`. This meant the coaching interface worked but scheduled outbound messages were still blind.
