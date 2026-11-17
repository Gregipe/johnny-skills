# Structured LLM Fields Pattern — Predictable AI Output

**Session:** May 2026 — ARA Cadence Builder  
**Applies to:** Any UI where an LLM generates text from user-defined inputs (email previews, call scripts, landing pages, proposals)

## The Problem

A single "Objective" text box forces the LLM to guess what the user wants in each section of the output. This causes unpredictable results requiring repetitive regenerate cycles.

User feedback: *"The drafts are not exactly what I want — I don't want to keep iterating with the LLM inference."*

## The Pattern: Fields → LLM Fills Language

Instead of one input for the whole output, break the output into named slots. The user writes WHAT each slot should contain. The LLM writes the language around it.

```
BEFORE (unpredictable):              AFTER (predictable):
┌──────────────────────────────┐    ┌──────────────────────────────┐
│ Warm intro + value hook      │    │ Opening: [Reference their   │
│ — establish credibility      │    │           expansion/growth] │
│ and spark curiosity          │    │ Value:   [Voice AI handles  │
│                              │    │           screening auto]   │
│  → LLM invents structure     │    │ CTA:     [Worth 2 min?]     │
│  → often misses the point    │    └──────────────────────────────┘
└──────────────────────────────┘             │
                                             │ LLM fills language:
                                             ▼
                                   "Hey Rajesh 👋 I saw Acme..."
```

## Channel-Specific Field Schemas

Each channel defines which fields it needs. The UI renders the right fields based on the channel selection.

```javascript
var STEP_FIELDS = {
  whatsapp: [
    {key:'opening', label:'Opening', placeholder:'Hook / personalization'},
    {key:'value', label:'Value', placeholder:'Core value proposition'},
    {key:'cta', label:'CTA', placeholder:'Call to action'}
  ],
  email: [
    {key:'subject', label:'Subject', placeholder:'Email subject line'},
    {key:'opening', label:'Opening', placeholder:'First paragraph'},
    {key:'body', label:'Body', placeholder:'Value prop / details'},
    {key:'cta', label:'CTA', placeholder:'Call to action'}
  ],
  call: [
    {key:'greeting', label:'Greeting', placeholder:'Context / opener'},
    {key:'value', label:'Value', placeholder:'Why call now'},
    {key:'question', label:'Question', placeholder:'Key discovery question'},
    {key:'cta', label:'CTA', placeholder:'Closing ask'}
  ],
  sms: [
    {key:'hook', label:'Hook', placeholder:'One-line value'},
    {key:'cta', label:'CTA', placeholder:'Next step'}
  ]
};
```

## Backend: Field-to-Prompt Mapping

The backend system prompt maps each field key to a human-readable instruction. The LLM sees exactly what to put where.

```python
field_mapping = {
    "subject": "Subject line: ",
    "opening": "Opening/hook: ",
    "body": "Body/content: ",
    "value": "Value proposition: ",
    "greeting": "Greeting: ",
    "question": "Key question: ",
    "cta": "Call to action: ",
    "hook": "Hook/message: "
}

# Build field instructions
field_text = "Field-by-field content to include:\n"
for k, v in fields.items():
    if v:
        label = field_mapping.get(k, k + ": ")
        field_text += f"  {label}{v}\n"
```

The system prompt includes `{field_text}` right before the channel guidelines.

## Migration from Flat to Structured

When upgrading from `desc` (single string) to `fields` (object), migrate existing data on load:

```javascript
// On load, detect old format and convert
step.desc = step.fields ? undefined : step.desc;  // old path
if (!step.fields) {
    step.fields = defaultFields(step.channel);
    if (step.desc) {
        var firstKey = Object.keys(step.fields)[0];
        if (firstKey) step.fields[firstKey] = step.desc;
    }
}
```

Also ensure new steps are created with empty fields:

```javascript
function addStep(channel) {
    t.steps.push({
        channel: channel,
        day: 0,
        delay: 0,
        desc: '',
        fields: defaultFields(channel)  // ← critical
    });
}
```

## When to Use This Pattern

Use structured fields instead of a single prompt/objective box when:
- The output has clearly identifiable sections (subject, body, CTA, etc.)
- The user expressed frustration with LLM iteration
- You need the LLM output to follow a predictable structure every time
- Different channels/platforms require different output structures

Don't use this pattern when:
- A single input is truly sufficient (editing one thing that maps to one output slot)
- The user explicitly wants the LLM to "figure out the best structure"
