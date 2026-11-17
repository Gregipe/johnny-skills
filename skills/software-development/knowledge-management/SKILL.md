---
name: knowledge-management
description: Knowledge management for AI agents — conversational induction/onboarding flows and document-based knowledge extraction. Covers structured knowledge extraction from LLM conversations, document parsing, source provenance, and the knowledge bridge to agent prompts.
---

# Knowledge Management for AI Agents

This skill covers how to build systems that extract, store, and deliver knowledge to AI agents — both through conversational onboarding (induction) and document ingestion.

## Two Knowledge Sources

| Source | Method | Documentation |
|--------|--------|---------------|
| **Conversational** | Induction/onboarding chat with user | See "Induction Design" below |
| **Document-based** | PDF/DOCX/PPT parsing + LLM extraction | See "Document Extraction" below |

## Induction Design

> **Content absorbed from `conversational-induction-design`.**

Design systems where an AI agent inducts a user through a structured conversation — extracting knowledge, building a skills database, and configuring behavior.

### Core Philosophy

**Induction must feel like a conversation, NOT a form.** One question, one answer, one follow-up. A dump of 7 questions gets 7 shallow answers; 7 sequential questions get 7 deep answers.

### Module-Based Structure

Break induction into **4-6 modules** that correspond to logical knowledge domains:
- Account Setup — admin, industry, language, personality
- Proposition — what, segments, value props
- GTM Learnings — channels, objections, wins/losses
- Inbound Setup — lead sources, CRM, follow-up
- Policy & Guardrails — pricing, discounts, compliance

### The Knowledge Bridge

**Most common failure:** Data collected in induction is never used by the agent.

```
Induction → Skill table (collect & store ✓)
                    ↓
            Agent system prompt
           (inject & use — MISSING ✗)
```

**Both injection points must be wired:**
1. Agent Chat — skills_context injected into system prompt
2. Scheduled Message Generation — skills used in auto-generated outbound messages

### One Question At A Time

**The #1 rule:** The LLM must ask EXACTLY ONE question per response.

**Four layers that must align:**
1. System prompt — explicit rule at top
2. Dynamic runtime instructions — server code injection
3. Conversation history — override old multi-question patterns
4. Frontend — auto-send to API, never hardcode welcome message

### Knowledge-Aware Start

When documents are uploaded BEFORE induction, the agent should acknowledge existing knowledge:
- "From your website, I can see you serve X, Y, Z..."
- "Let me confirm and go deeper on X"
- "I couldn't find pricing info — can you tell me?"

## Document Knowledge Extraction

> **Content absorbed from `document-knowledge-extraction`.**

Extract structured knowledge from uploaded documents using an LLM, and persist with source provenance.

### Core Pipeline

```
Upload → Parse → LLM Extract → Persist with Source → Present Result
```

### Document Parsing

| Format | Library | Code |
|--------|---------|------|
| PDF | `PyMuPDF` (`fitz`) | `doc = fitz.open(path)` |
| DOCX | `python-docx` | `doc = Document(path)` |
| PPTX | `python-pptx` | `prs = Presentation(path)` |
| TXT | Built-in | `open(path).read()` |

### LLM Extraction Categories

- `proposition` — Value proposition, positioning
- `gtm_learnings` — Channel insights, objection patterns
- `inbound` — Lead handling, CRM info
- `guardrail` — Policy rules, pricing limits
- `messaging_win` — Proven messaging patterns
- `segment_signal` — Segment-specific behavior

### Source Provenance (Critical)

Every knowledge entry MUST be tagged with its source:
- `source = "induction"` — From onboarding conversation
- `source = "document"` — From uploaded PDFs/websites
- `source = "conversation"` — From daily agent interactions

This enables filtering and auditing.

### Hallucination Defense

Three-layer defense:
1. **Prompt hardening** — "Do NOT invent, extrapolate, or guess"
2. **Temperature=0** — Eliminate creative variance
3. **Verification gate** — Grep skill values against raw source text

### Chunked Extraction

Don't truncate documents — split into windows and extract from each:
- 6000-char windows
- One LLM call per chunk
- Deduplicate skills by key

## Common Patterns

### Skills Dashboard

Display knowledge with source badges:
- 💬 Induction (green)
- 📄 Document (blue)  
- 🔄 Conversation (amber)

### Prompt Injection

Skills must be injected into agent system prompts:
```
## What You Know About This Tenant
### proposition
- logistics_segment: For logistics companies...
- pricing_tier: ₹4/min up to 10K mins
```

### Induction → Document Bridge

When documents are uploaded during induction:
1. Parse document
2. Extract skills via LLM
3. Add to Skills table
4. Acknowledge in chat response

## References

### From conversational-induction-design
- `references/ara-induction-implementation.md` — Full implementation
- `references/one-question-at-a-time-fix.md` — Multi-question fix
- `references/induction-document-upload.md` — Document upload flow

### From document-knowledge-extraction
- `references/ara-document-to-skills-implementation.md` — ARA-specific implementation
- `scripts/verify_skills.py` — Hallucination verification

## Pitfalls

### Document Text Truncation
Historical truncation at 6000 chars lost 80% of content. Use chunked extraction.

### Format Example Hallucination
LLM copies prompt examples instead of actual document content. Remove specific examples from prompts.

### Pre-Loaded Knowledge Not Acknowledged
Without explicit instruction, agent ignores pre-loaded documents and asks generic questions.

### Hardcoded Welcome Message
Frontend hardcoded messages bypass the API — agent never runs, knowledge base ignored.

### Fresh Start Gate
Use `hist_count == 0` (conversation logs), not `covered_count == 0` (document skills) — documents ≠ induction.
