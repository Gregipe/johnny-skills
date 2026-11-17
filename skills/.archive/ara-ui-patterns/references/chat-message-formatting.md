# Chat Message Formatting in ARA

Two separate code paths render chat messages. Both need identical treatment for line breaks, bold, and HTML safety.

## Dashboard Chat (`static/dashboard.js`)

**Function:** `addChatMsg(text, isUser)` at ~line 3075

```javascript
function addChatMsg(text, isUser) {
  var msgs = document.getElementById('chatMessages');
  var div = document.createElement('div');
  div.className = 'chat-msg ' + (isUser ? 'user' : 'agent');
  div.innerHTML = text.replace(/\n/g, '<br>').replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}
```

**Key rules:**
- Use `innerHTML`, NOT `textContent` — need `<br>` and `<strong>` rendering
- `\n` → `<br>` — explicit line breaks (don't rely on `white-space: pre-wrap`)
- `**text**` → `<strong>text</strong>` — markdown bold
- CSS: `.chat-msg` has `white-space: pre-wrap; max-width: 90%`
- User messages: `background:#111; color:#fff; align-self:flex-end`
- Agent messages: `background:#F0F0F2; color:#111; align-self:flex-start`

## Threads Page Chat (`threads_template.py`)

**Function:** `addMessage(role, content, time, scroll)` at ~line 580

```javascript
function addMessage(role, content, time, scroll) {
  var msgs = document.getElementById('chatMessages');
  var d = new Date(time);
  var timeStr = d.toLocaleTimeString(undefined, {hour:'2-digit', minute:'2-digit'});
  var div = document.createElement('div');
  div.className = 'chat-msg ' + role;
  div.innerHTML = (content || '').replace(/\n/g, '<br>').replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>') + '<div class="msg-time">' + timeStr + '</div>';
  msgs.appendChild(div);
  if (scroll) msgs.scrollTop = msgs.scrollHeight;
}
```

**Same rules as dashboard**, plus:
- Role-based classes: `user`, `assistant` (not `agent` like dashboard — `role` param is the DB value)
- Includes `.msg-time` div appended to each message

## Lead Profile Initial Message Format

When "Chat about [lead]" creates a new thread, the first user message uses structured emoji formatting:

```javascript
var msg = "📋 Lead: " + data.lead_name + " — " + (data.lead_company || "") + "\n" +
  "━━━━━━━━━━━━━━━━━━━━━━━━━━\n" +
  "• Name:    " + data.lead_name + "\n" +
  "• Company: " + (data.lead_company || "N/A") + "\n" +
  "• Phone:   " + (data.lead_phone || "N/A") + "\n" +
  "• Email:   " + (data.lead_email || "N/A") + "\n" +
  "• Source:  " + (data.lead_source || "N/A") + "\n" +
  "• Stage:   " + (data.lead_stage || "new") + "\n" +
  "• Notes:   " + (data.lead_notes || "None") + "\n" +
  "━━━━━━━━━━━━━━━━━━━━━━━━━━\n" +
  convText + "\n\n" +
  "Summarize this lead and their recent activity in 2-3 sentences."
```

Use actual `\n` (JavaScript newline), NOT `\\n` (literal backslash-n). Located in `static/dashboard.js` around line 2890 in the `start_lead_chat` callback.

## Cache-Busting

Every time you modify `static/dashboard.js`, bump the version in `dashboard_template.py`:

```html
<script src="/static/dashboard.js?v=N"></script>
_Cache-busting reminder: bump `v=N` in `dashboard_template.py` each time you modify `static/dashboard.js`. Current version as of May 27 = v=9._
```

Increment `v=N` with each change. Without this, the browser serves the cached version and fixes don't take effect.
