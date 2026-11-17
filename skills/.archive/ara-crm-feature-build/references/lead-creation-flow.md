# Lead Creation Flow — ARA Dashboard

End-to-end design and implementation of the Add Lead feature (manual + CSV import).

## Design Decisions (from user Q&A)

- **Button location**: Top-right of the Leads page central panel, next to search bar
- **Manual form**: Name (req) + Phone (req). Email, Company, Notes are optional
- **Assignee**: "Assign to Ava" checkbox defaults to checked for manual form. CSV leads are unassigned
- **CSV format**: Columns: name, phone, email, company, notes. Sample CSV downloadable
- **Duplicate detection**: Warn if phone or email matches existing lead. Show existing lead link. User can "Add anyway"
- **Domain blocklist**: Ignored for manual/CSV creation (only applies to auto-deal creation from email domain)
- **Search**: Free-text on name, phone, email, company. 250ms debounce
- **Created date**: Show in leads table. Already existed in DB model

## Files Modified

### server.py (backend)
- `LeadCreate` model: Added `notes` field
- `GET /api/leads/search?q=` — free-text search
- `GET /api/leads/check-duplicate?phone=&email=` — duplicate detection
- `GET /api/leads/sample-csv` — sample CSV download
- `POST /api/tenants/{id}/leads/upload-csv` — CSV import (multipart, File Upload)

### dashboard_template.py (frontend)
- CSS: ~100 lines of new styles (modal, form, dropzone, toolbar, duplicate warning, CSV result toast)
- `renderLeads()`: Replaced with toolbar (search + add button + count) + `renderLeadsTable()` helper
- `renderLeadsTable()`: Table with 5 columns (Name, Account, Source, Status, Created) + empty state
- `searchLeads()`: Debounced fetch to `/api/leads/search?q=`
- `showAddLeadModal()`: Creates modal with two tabs (Single Lead / Import CSV)
- `submitSingleLead()`: Validates fields, checks duplicates, creates via API
- `confirmAddLead()`: Skips duplicate check, proceeds with creation
- `createLeadAPI()`: POST to `/api/tenants/{id}/leads`
- `showLeadTab()`: Toggles between single and CSV tabs
- `downloadSampleCSV()`: Opens `/api/leads/sample-csv`
- `handleCSVFile()`: Shows file info in dropzone
- `uploadCSVLeads()`: Submits FormData with CSV file
- `clearCSVFile()`: Clears selected file
- drag-and-drop event listeners
- Event delegation: `switch-lead-tab`, `open-csv-file`, `download-sample-csv`
- File input change listener via `document.addEventListener('change', ...)`

## Escaping Bug Fixed

The modal's dropzone originally used inline onclick:
```javascript
onclick="document.getElementById('csvFileInput').click()"
```
This caused a JS syntax error because the single quotes around `csvFileInput` terminated the outer JS string literal. Fixed by using `data-action="open-csv-file"` with event delegation.

## Verification Steps

1. `node --check` on extracted script — JS compiles clean (0 errors)
2. Dashboard loads without console errors
3. Click Leads nav — shows search bar, Add Lead button, leads table with Created column
4. Click Add Lead — modal appears with two tabs
5. Submit empty form — validation errors appear on Name and Phone
6. Fill valid data — duplicate check runs, then lead is created
7. Enter duplicate phone — warning shown with Add Anyway button
8. Switch to CSV tab — dropzone visible
9. Upload CSV — leads created, success toast, refresh
10. Type in search — results filter with debounce