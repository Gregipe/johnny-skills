# Testing Ava at Scale: Background Job Pattern

When testing Ava's agent chat endpoint, the LLM round-trip takes 60-120 seconds. Direct SSH + curl + pipe-to-python times out because the pipe blocks waiting for the SSH connection. Use this pattern instead:

## Pattern: Background Curl → File → Read

```bash
# 1. Fire the request in background, write to temp file
ssh root@46.224.132.99 \
  'curl -s -o /tmp/ava_test_N.json -w "%{http_code}" \
   -X POST http://localhost:8766/api/agent/chat/3e736242 \
   -H "Content-Type: application/json" \
   -d "{\"message\":\"...query...\",\"thread_id\":\"test-xxx\",\"channel\":\"whatsapp\"}" &'

# 2. Wait for LLM to respond
sleep 90

# 3. Read the output file
ssh root@46.224.132.99 'cat /tmp/ava_test_N.json'
```

## Parsing Results

```bash
# Check HTTP status + file size first
ssh root@46.224.132.99 'wc -c /tmp/ava_test_N.json'

# Tools called
ssh root@46.224.132.99 'python3 -c "
import json
with open(\"/tmp/ava_test_N.json\") as f: d=json.load(f)
tr=d.get(\"tool_results\",\"\")
if tr:
    tools=json.loads(tr) if isinstance(tr,str) else tr
    for t in tools:
        print(f\"  {t.get(\"tool\",\"?\")} | {str(t.get(\"summary\",\"\"))[:100]}\")
"'

# Response text
ssh root@46.224.132.99 'python3 -c "
import json
with open(\"/tmp/ava_test_N.json\") as f: d=json.load(f)
print(d.get(\"response\",\"NONE\")[:2000])
"'
```

## Running Multiple Tests in Parallel

```bash
# Fire all requests simultaneously
ssh root@46.224.132.99 \
  'curl -s -o /tmp/ava_test_1.json ... &' && \
ssh root@46.224.132.99 \
  'curl -s -o /tmp/ava_test_2.json ... &' && \
ssh root@46.224.132.99 \
  'curl -s -o /tmp/ava_test_3.json ... &'

# Wait once for all
sleep 120

# Read all results
ssh root@46.224.132.99 'cat /tmp/ava_test_1.json'
ssh root@46.224.132.99 'cat /tmp/ava_test_2.json'
ssh root@46.224.132.99 'cat /tmp/ava_test_3.json'
```

## Pitfalls

- **Don't pipe** `curl | python3` — the SSH pipe blocks after curl finishes, timer runs out before python3 reads stdin
- **Don't use `curl ... &` from execute_code** — timeout applies to the whole script, not just the foreground commands
- **Use `-o` not `>`** with background curl — `>` can truncate before data arrives
- **Check `-w '%{http_code}'`** — a 500 means a server crash, not a behavior issue
- **Files are tiny (<100 bytes) but HTTP 200** — the query was fast (CHITCHAT or CAPABILITY, no tools called)
- **Files are 5-15KB** — multiple tools were called, check `tool_results` structure
