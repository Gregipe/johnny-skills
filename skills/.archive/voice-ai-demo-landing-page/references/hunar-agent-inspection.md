# Hunar Agent Inspection (read-only)

The page's copy, language, and `custom_data` payload must match the agent — and the
agent's *declared* config is the source of truth, not whatever you cloned from a
previous demo. Inspect the agent BEFORE finalizing any of them. Every call below is
read-only: no call is placed, nothing is billed.

## Endpoints

`HUNAR_BASE = https://api.voice.hunar.ai/external/v1`
Auth header: `X-API-Key: <HUNAR_API_KEY>`

| Call | Returns |
|------|---------|
| `GET /agents/` | `{"count": N, "next": "...?page=2", "results":[...]}` — paginated list of every agent on the org |
| `GET /agents/{uuid}/` | one agent: `id, status, name, language, custom_variables, custom_variable_values, summary, logo, voice_persona` |

```bash
KEY=$(grep '^HUNAR_API_KEY=' .dev.vars | cut -d= -f2- | tr -d '"')
curl -s https://api.voice.hunar.ai/external/v1/agents/<UUID>/ -H "X-API-Key: $KEY"
```

## What each field means for the page

- `name` + `summary` → what the agent actually does. (This session: `"BDE - Assessment"`
  = Mondelez India *Sales Officer* recruitment assessment — not "consumer conversations"
  as the cloned copy assumed.)
- `language` → set the page's `AGENT.lang`, the badge, the details-strip value, the
  `desc`, AND the monitor-page fallback (`callData?.language || "..."`). Do NOT assume
  Hinglish — this agent was `ENGLISH`.
- `custom_variables` (array) → the EXACT keys to send in `custom_data`. Send only these
  (this session: `["first_name"]`). `callee_name` and `mobile_number` are always sent
  top-level and are NOT custom variables.
- `custom_variable_values` → sample/placeholder value per variable (e.g. `{"first_name": "Ananya"}`).
- `status` → `ACTIVE` means it can take calls.

## Call-API error shapes

- `401 {"success": false, "message": "Invalid API key", "details": []}` — wrong/missing key.
- `422 {"success": false, "message": "Validation Failed for fields: <f>", "details":[{"field_name","error_msg"}]}`
  — a field failed validation, e.g. `mobile_number: Invalid phone number: 0000000000`
  (Indian 10-digit, 6–9 prefix), or `call_id: invalid character ...`. Call IDs are
  numeric — don't probe `GET /calls/<uuid-ish-placeholder>`; the 422 still proves the
  key authenticated (past the 401).

## Diagnosing "trigger shows Load Failed"

"Load Failed" is not a string anywhere in the demo codebase. It is either (a) Safari's
network-error phrasing — the browser `fetch` failed at the connection layer (server
down / wrong port), or (b) a Hunar-side message. Reproduce with `curl` directly against
`/api/calls` and read the JSON error — that pinpoints key-vs-agent-vs-number instantly,
instead of guessing from the browser's red box.
