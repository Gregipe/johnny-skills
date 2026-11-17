# Dashboard Mock Data Stripping Methodology

Methodology for stripping hardcoded/mock data from SPA dashboards while preserving UI structure.

## Principles

1. **Keep the shells** — stat cards, table headers, section titles, navigation items all stay. Only the VALUES change.
2. **Compute from API data** — replace `3` (hardcoded) with `leads.filter(l => l.stage === 'meeting_booked').length`
3. **Empty states > fake data** — when DB is empty, show "No items yet" instead of pre-populated rows
4. **Dynamic > static** — lead detail sections use real DB fields, not hardcoded "Head of Growth" / "51-200" / "SaaS"

## Common Mock Data Sources to Strip

### Stats Cards
```
❌ '<div class="stat-value">3</div>'              (hardcoded number)
✅ '<div class="stat-value">' + meetings + '</div>' (computed from API)
```

### Lists with Fake Names
```
❌ 'Rajesh Sharma — Budget discussion'
❌ 'Priya Patel — Proposal sent'
✅ Remove the section entirely or show empty state
```

### Hardcoded Percentages
```
❌ 'WhatsApp — 45%' / 'Calls — 30%' / 'Email — 25%'
✅ Remove pie chart entirely or compute from real channel data
```

### Lead Detail Page Fillers
```
❌ Company Size: 51-200, Industry: SaaS, Location: Bengaluru
❌ Title: Head of Growth, Timezone: Asia/Kolkata GMT+5:30
❌ AI Summary tags: [SaaS, Growth, Free Trial, High Intent]
✅ Show real `l.company`, `l.city`, `l.notes` from DB
✅ If null, show "—" or "No data yet"
```

### Chat Panel Mock Data
```
❌ Initial agent message: "I have reviewed your pipeline..."
❌ Suggestion chips: "[~] Give me a summary..."
✅ Leave suggestions empty array or generate from DB state
✅ Leave messages empty — start fresh each visit
```

### Timeline Events
```
❌ 4 hardcoded timeline entries (WhatsApp 10:24 AM, Voice Call yesterday, Email May 18, Meeting May 25)
✅ Render from real Conversation records: convs.map(c => ...)
✅ Empty state: "No conversation history yet"
```

## Verification Steps

After stripping, confirm clean:

```bash
# Check no known fake names remain in the template
grep -c "Rajesh\|Priya\|Ankit\|2h 30m\|Score: 87\|Head of Growth" dashboard_template.py
# Should return 0

# Check the page renders without JS errors
curl http://localhost:8766/dashboard | grep -c "Rajesh\|Error loading"
# Should return 0

# Verify lead detail with real data works
curl http://localhost:8766/api/leads/{some_real_id} | python -m json.tool
# Should show actual conversation timeline
```
