# Updating a Hunar Agent via API (PUT)

The Hunar external API can *update* agents, not just inspect them — useful when a
demo's language or persona needs to change without touching the Hunar console.

## Discover which methods an endpoint allows

`OPTIONS` returns an `Allow` header listing the verbs an endpoint accepts:

```bash
curl -s -X OPTIONS https://api.voice.hunar.ai/external/v1/agents/<UUID>/ \
  -H "X-API-Key: $KEY" -i | grep -i '^allow:'
# agents/{id}/ -> GET, PUT
# calls/       -> GET, POST   (no per-call language override — agent config governs)
```

## PUT semantics (the non-obvious part)

A **partial** PUT is rejected. Changing `voice_persona` or `language` triggers
server-side validation requiring the FULL agent payload:

```
PUT {"language":"HINDI"}
-> 422 "Validation Failed for fields: non_field_error"
   "When updating 'voice_persona' or 'language', all fields are required.
    Missing: name, objective, voice_persona, persona_name, agent_prompt,
    introduction, result_prompt, result_schema"
```

Safe pattern — GET the whole object, flip the one field, PUT it back, verify:

```python
agent = GET /agents/{uuid}/        # full object incl. agent_prompt, result_schema, ...
agent["language"] = "HINDI"        # or "ENGLISH"
PUT /agents/{uuid}/  body=agent    # 200 -> returns updated object
GET /agents/{uuid}/                # confirm the field actually changed (fresh GET)
```

`GET /agents/{uuid}/` returns every field you must echo back:
`agent_code, agent_prompt, conclusion, created_at, custom_variable_values,
custom_variables, id, introduction, language, logo, name, objective,
persona_name, required_variables, result_prompt, result_schema, result_variables,
silence_response, status, summary, voice_name, voice_persona`.

## `language` values

Observed valid values: `ENGLISH` and `HINDI`. The agent's `summary` may claim
"English or Hindi" while `language` is pinned to one — `language` is the field
that actually decides the call language, so trust it over prose.

## Firing a test call (useful for isolating client-vs-server bugs)

```bash
curl -s -X POST https://api.voice.hunar.ai/external/v1/calls/ \
  -H "X-API-Key: $KEY" -H 'Content-Type: application/json' \
  -d '{"agent_id":"<uuid>","mobile_number":"<10-digit>","callee_name":"Full Name","custom_data":{"first_name":"..."}}'
```

- Auth is `X-API-Key: <key>` (NOT `Authorization: Bearer`).
- 200 -> `{"id","request_id","status":"NOT_STARTED","from_phone_number","guardrails":{"allowed_days","earliest_call_time","last_call_time"}}`. Status then polls `NOT_STARTED -> IN_PROGRESS -> terminal` via `GET /calls/{id}`.
- 401 `{"message":"Invalid API key"}` = bad/placeholder key.
- 422 `{"message":"mobile_number: Invalid phone number: ..."}` = number fails validation (use a real 10-digit number starting 6-9).
- `call_id` in `GET /calls/{id}` is validated; a random string returns 422 "invalid character".
