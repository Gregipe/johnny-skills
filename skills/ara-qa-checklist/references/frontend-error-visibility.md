# Frontend Error Visibility — ARA Dashboard

## The Silent `catch(e) {}` Antipattern

### How It Breaks

```javascript
// BROKEN: error swallowed silently, user sees nothing
async function deleteKnowledgeDoc(docId) {
  try {
    await fetch('/api/knowledge/3e736242/' + docId, { method: 'DELETE' });
    loadKnowledgeList();
  } catch(e) {}  // ← SWALLOWED
}
```

When the API returns 400/500, or the network fails, or `loadKnowledgeList` throws — the user clicks the delete button, sees the confirm dialog, clicks OK, and **nothing happens**. No error, no feedback, no refresh. The UI just sits there.

### The Fix

```javascript
// FIXED: error surfaced to user
async function deleteKnowledgeDoc(docId) {
  try {
    await fetch('/api/knowledge/3e736242/' + docId, { method: 'DELETE' });
    loadKnowledgeList();
  } catch(e) {
    console.error(e);
    alert('Delete failed: ' + e.message);
  }
}
```

### QA Checklist Item

Before deploying any dashboard.js change, grep for `catch(e) {}`:
```bash
grep -n 'catch(e) {}' /opt/ara/static/dashboard.js
```
Every hit is a bug — there is no legitimate use of an empty catch block in user-facing code. Fix each one to at minimum `console.error(e)`.

### Real Example

**Symptom:** "The X button on knowledge base items does nothing. A popup appears saying 'Remove this website from the learning list' but clicking OK doesn't delete it."

**Root cause:** `deleteWebsiteDoc()` caught API errors with `catch(e) {}` — the DELETE endpoint returned 400 because the document's `source_type` didn't match `"website"`, the error was swallowed, and `loadKnowledgeList()` was never called.

**Fix:** Added `console.error(e); alert('Delete failed: ' + e.message);` to the catch block, revealing the underlying API error so it could be diagnosed.
