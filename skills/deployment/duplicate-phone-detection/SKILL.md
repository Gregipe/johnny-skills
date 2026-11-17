---
name: duplicate-phone-detection
category: deployment
description: create_lead automatically detects duplicate phone/email and returns DUPLICATE_PHONE error before saving
---

# Duplicate Phone Detection

`create_lead` in execute_tool has built-in duplicate detection. Before creating a lead, it checks if the phone number or email already exists in the DB. If found, it returns `ToolResult.fail("create_lead", "DUPLICATE_PHONE", ...)` with `params={"existing": existing_lead_name}`.

The error code `DUPLICATE_PHONE` has recovery template:
```
"That phone/email is already on file for {existing}. Update {existing} instead, or create anyway?"
```

## LLM Prompt

The `create_lead` tool description in the system prompt needs to mention this behavior for the LLM to know about it:

```
**create_lead** — Create new lead. Args: {"name": "...", "phone": "...", "company": "...", "email": "...", "notes": "...", "lead_source": "..."}
```

Should become:
```
**create_lead** — Create new lead. Args: {"name": "...", "phone": "...", "company": "...", "email": "...", "notes": "...", "lead_source": "..."}
- Automatically checks phone and email for duplicates. If a match is found, returns DUPLICATE_PHONE error.
```

## Testing

Test by calling create_lead with a phone that belongs to an existing lead. Expect:
- `result.ok == False`
- `result.error.code == "DUPLICATE_PHONE"`
- `result.error.params["existing"] == existing_lead.name`
