# render_results Synthesis Gap (STRATEGIC/DIAGNOSTIC)

**Symptom**: Ava correctly classifies a STRATEGIC or DIAGNOSTIC query. She calls the right inspection tools (pipeline summary, query_database, read_system_logs, web_search). All tools return OK with rich data. But the user-facing response is just "✅ N action(s) completed" instead of actual analysis and synthesis.

**Example**:
- User: "Where should I get my next leads? Analyze my pipeline."
- Ava calls: get_pipeline_summary → query_leads → web_search (9 tools, all OK)
- Response: "✅ 9 action(s) completed"
- Expected: Pipeline analysis → gaps identified → 3 target companies with rationale

**Root cause**: The observe loop (`agent_chat` ~line 5858-5876) executes all tool calls and passes results to `render_results()`. The `render_results` function produces a confirmation summary ("✅ N action(s) completed") which becomes the `_resp_text`. This text is stored as the assistant response AND returned to the user. The LLM never gets a chance to synthesize the tool outputs into a narrative analysis — the confirmation overwrites the synthesis.

**Why this only affects STRATEGIC/DIAGNOSTIC**:

| Query type | Expected | render_results output | Match? |
|-----------|----------|----------------------|--------|
| CHITCHAT | "Morning!" | (no tools called) | ✅ |
| SIMPLE_QUESTION | Raw data from 1 tool | "✅ Get Action Items: ..." | ✅ (tool output IS the answer) |
| CAPABILITY | Direct answer | (no tools called) | ✅ |
| ACTION | Confirmation of execution | "✅ action(s) completed" | ✅ |
| **STRATEGIC** | Synthesized analysis | "✅ 9 action(s) completed" | ❌ |
| **DIAGNOSTIC** | Evidence-based diagnosis | "✅ 9 action(s) completed" | ❌ |

**Detection**: When testing STRATEGIC or DIAGNOSTIC queries:
```bash
curl -s -X POST http://localhost:8766/api/agent/chat/{tenant_id} \
  -H 'Content-Type: application/json' \
  -d '{"message":"...strategic query...","thread_id":"test-xxx","channel":"whatsapp"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['response'][:500])"
```
If response is "✅ N action(s) completed" for a non-ACTION query, this bug is present. Check `tool_results` to verify correct tools were called — the classification is working, the synthesis is broken.

**The `tool_results` JSON will show correct tool execution** — this is NOT a classification bug, it's a response-delivery bug.

**Fix (implemented June 16, 2026):** One-line change in agent_chat at ~line 6262:

```python
# BEFORE (line 6262):
return {"response": response, "thread_id": thread_id, "tool_results": _tool_results_json}

# AFTER:
return {"response": final_response_text or response, "thread_id": thread_id, "tool_results": _tool_results_json}
```

The observe loop already captures the LLM's synthesis in `_loop_out["final_text"]` (line 5716). The LLM produces analysis text alongside its tool calls — but `agent_chat` was extracting `final_response_text` at line 6189 and then THROWING IT AWAY, returning `render_results` output (`response`) instead.

**Verification (tested live June 16, 2026):**

| Query | Before | After |
|-------|--------|-------|
| "Where should I get my next leads?" | "✅ 9 action(s) completed" (30 chars) | Full segment analysis, gap ID, 3 targets with rationale (2,193 chars) |
| "Is the scheduler running?" | "✅ 9 action(s) completed" | "check_health: ok, read_system_logs: ok, query_database: ok..." (LLM text delivered) |

The LLM was always producing analysis — it was just being discarded at the final return statement.

**Also related:** `query_database` tool needed SQLAlchemy `text()` wrapper (line 5042):
```python
# BEFORE:
result_proxy = db.execute(sql)

# AFTER:
from sqlalchemy import text as _sql_text
result_proxy = db.execute(_sql_text(sql))
```

Without this, all `query_database` calls failed silently with "Textual SQL expression should be explicitly declared as text()".
