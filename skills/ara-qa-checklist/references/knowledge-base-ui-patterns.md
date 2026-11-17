# Toast Notification for Upload Feedback

When documents are uploaded, the UI must provide immediate visible feedback. A toast notification appears in the top-right corner:

```html
<div id="toast" style="position:fixed;top:20px;right:20px;background:#059669;color:white;padding:12px 20px;border-radius:10px;..."></div>
```

```javascript
function showToast(msg, ok) {
    var t = document.getElementById('toast');
    t.style.background = ok ? '#059669' : '#dc2626';  // green or red
    t.textContent = msg;
    t.style.display = 'block';
    t.style.opacity = '1';
    t.style.transform = 'translateY(0)';
    setTimeout(function() {
        t.style.opacity = '0';
        t.style.transform = 'translateY(-10px)';
        setTimeout(function() { t.style.display = 'none'; }, 300);
    }, 3000);
}
```

The toast is called on upload success/failure. It persists for 3 seconds then fades out.

# Event Delegation for Remove Buttons

**Do NOT use inline `onclick` with escaped quotes** inside Python triple-quoted strings. Python's string processing eats backslashes (`\\'` → `'`), breaking JS.

Instead, use event delegation with `data-*` attributes:

```javascript
// In render loop:
h += '<button class="kb-del" data-id="' + d.id + '" ...>Remove</button>';

// Once, after innerHTML assignment:
list.addEventListener('click', function(e) {
    var btn = e.target.closest('.kb-del');
    if (btn) deleteDocument(btn.getAttribute('data-id'));
});
```

This avoids ALL inline escaping issues. The click handler is attached once on the container, not per-button.

# Synthesis Section

Below the document list, show a green info box explaining how documents affect induction:

```html
<div id="kbStatus" style="background:#f0fdf4;border-radius:10px;...">
    <strong>✅ How this affects induction</strong>
    <p>The agent reads your uploaded documents and asks sharper questions based on what it already knows...</p>
</div>
```

Shown when docs.length > 0, hidden otherwise.

# Page Load Behavior

Documents must load on page load, not just on tab switch. Call `loadDocuments()` alongside `loadState()`:

```javascript
loadState();
loadDocuments();  // ← KB document list loads on every page refresh
```
