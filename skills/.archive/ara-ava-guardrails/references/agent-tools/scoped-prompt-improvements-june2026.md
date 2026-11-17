# Scoped Prompt Improvements — June 2026

Five prompt changes were scoped and analyzed but NOT built. They address the core gap: Ava pattern-matches keywords to tools instead of reasoning about intent.

## A. Message Classification (new section before tool rules)
| Type | Trigger | Response |
|------|---------|----------|
| CAPABILITY | "can you...", "would you be able to..." | Explain system limits. Zero tools. |
| DIAGNOSTIC | "why did...", "what happened..." | Reason from context. Tools only if you need data. |
| HYPOTHETICAL | "if I...", "what if..." | Answer conceptually. Don't search for things that aren't there. |
| DIRECTIVE | "send X", "create Y" | Execute per tool-calling rules. |
| CONVERSATIONAL | "hey", "thanks" | Respond naturally. No tools. |

## B. Replace Rule #6: "Understand, then act"
Current: "Do, don't investigate first."
Replace with: "Classify the message before touching a tool. Directive → call it. Diagnostic → reason first. Capability/Hypothetical → answer directly."

## C. Strategic confirmation proposals
When there's ambiguity in choices, explain WHY: "I found two decks — Hunar Self Serve and Voice AI White Paper. I'll attach Voice AI unless you meant the other. Shall I send?"

## D. Capability self-awareness (new section)
Short list: CAN (email with PDF attachments, WhatsApp, search KB, CRUD, web search, reminders, cron). CANNOT (receive files via chat, create integrations, modify system config, access inbox).

## E. Tool description hygiene
- list_documents: Add "If none, tell user to upload via dashboard."
- get_lead_detail: Add "Do NOT call as preamble before an action."
- send_email: Add "If no document matches the requested filename, tell user instead of guessing."

## Status
Scoped and discussed with Greg. Not yet built. These changes are pure prompt/SKILL.md changes — no server.py modifications needed.
