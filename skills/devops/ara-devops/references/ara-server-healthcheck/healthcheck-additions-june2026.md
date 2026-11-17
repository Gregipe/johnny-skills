# Post-Restart Verification Additions (June 2026)

## Run test_baileys_init.py
```bash
python3 /opt/ara/tests/test_baileys_init.py
```
Validates all BaileysWA instance attributes. Catches __init__ regressions that break Ava chat.

## Verify sidecar document endpoint
```bash
curl -s -X POST http://localhost:8767/send-document \
  -H 'Content-Type: application/json' \
  -d '{"phone":"919582549236","filePath":"/tmp/nonexistent.pdf"}'
# Should return: {"ok":false,"error":"File not found: /tmp/nonexistent.pdf"}
# NOT: Cannot POST /send-document (means endpoint missing)
```

## Verify sidecar connected
```bash
curl -s http://localhost:8767/status | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get("connected"))'
# Should return: True
```

## Verify owner guard
```python
from whatsapp_sidecar_client import BaileysWA
wa = BaileysWA()
assert wa._owner_phone == "919582549236"
assert hasattr(wa, 'send_to_owner')
assert hasattr(wa, 'mark_unread_owner')
assert hasattr(wa, 'send_document')
```

## Clean test residue
After running test suite, verify no REGRESSION actions remain:
```sql
SELECT count(*) FROM action_items WHERE title LIKE '%REGRESSION%';
```
