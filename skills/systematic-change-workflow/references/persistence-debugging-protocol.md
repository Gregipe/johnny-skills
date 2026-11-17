# ARA Persistence Debugging Protocol

Use when user reports: "I save data in the prompt builder, it says ✓ Saved, but on refresh it's gone."

## Step 1: Check localStorage vs in-memory

```javascript
// Directly from localStorage (bypasses getTemplate)
var raw = localStorage.getItem('ara_cadence_data');
var data = JSON.parse(raw);
var cold = data['cold'] || {};
var pp = cold.promptParts || {};
console.log('LS promptParts keys:', Object.keys(pp));
console.log('LS brandPersonality:', pp.brandPersonality ? pp.brandPersonality.personality : 'MISSING');

// In-memory (getTemplate may have been modified by rendering)
var t = getTemplate();
console.log('getTemplate promptParts keys:', t.promptParts ? Object.keys(t.promptParts) : 'MISSING');
console.log('getTemplate personality:', t.promptParts && t.promptParts.brandPersonality ? t.promptParts.brandPersonality.personality : 'MISSING');
```

If `LS promptParts keys: []` (empty) → Bug 7 (migrateToGlobalPromptParts wiped it)
If LS has data but getTemplate doesn't → some init code cleared it after load

## Step 2: Check raw JSON structure

Don't trust parsed API when the object is unexpectedly empty — inspect the raw string:

```javascript
var raw = localStorage.getItem('ara_cadence_data');
var idx = raw.indexOf('promptParts');
raw.substring(idx, idx + 200);
```

## Step 3: Verify JS function source matches expected fix

After restarting the server, the browser may still have cached JS:

```javascript
migrateToGlobalPromptParts.toString().includes('tmpl.promptParts = {}')
```
`true` = old code is running (browser cache or stale server)

Force a fresh load with `?cb=1` on the URL.

## Step 4: Instrument the save call

Monkey-patch to see what's actually being saved:

```javascript
var origSave = saveCurrentState;
saveCurrentState = function() {
  var t = getTemplate();
  console.log('SAVING: personality=' + t.promptParts.brandPersonality.personality);
  return origSave();
};
// Then click Save Changes
```

## Step 5: Verify DB independently of frontend

```bash
cd /Users/greg/ara && python3 -c "
from database import CadenceConfig, init_db
db = init_db()
cfg = db.query(CadenceConfig).filter(CadenceConfig.template_id == 'cold').first()
bp = cfg.config.get('promptParts', {}).get('brandPersonality', {}) if cfg else {}
print('Personality:', repr(bp.get('personality', '')))
db.close()
"
```

## Step 6: Verify server process freshness

```bash
echo "Server PID: $(pgrep -f 'venv/bin/python server.py$')"
echo "Start time: $(ps -p $(pgrep -f 'venv/bin/python server.py$') -o lstart=)"
echo "File modified: $(ls -l cadence_template.py | awk '{print $6, $7, $8}')"
```

If server started BEFORE the file was modified, restart.
