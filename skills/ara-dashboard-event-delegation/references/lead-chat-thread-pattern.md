# Lead Chat Thread Pattern

When clicking "Start AI Chat" on a lead detail page, the flow creates a dedicated thread and injects lead context into the first message.

## Backend: POST /api/leads/{lead_id}/chat

Creates a `ChatThread` with `title=f"Chat about {lead.name}"` and `thread_type="lead"`.

Returns:
- `thread_id`, `lead_name`, `lead_company`, `lead_phone`, `lead_email`
- `lead_source`, `lead_stage`, `lead_notes`
- `conversations` array: past interactions (`channel`, `direction`, `content`, `created_at`)

## Frontend: startLeadChat(leadId)

```javascript
async function startLeadChat(leadId) {
  try {
    // 1. POST to create thread (NOT GET — endpoint is @app.post)
    var r = await fetch('/api/leads/' + leadId + '/chat', {method: 'POST'});
    if (!r.ok) return;
    var data = await r.json();

    // 2. Clear current chat
    activeThreadId = null;
    clearStoredThread();
    document.getElementById('chatMessages').innerHTML = '';
    document.getElementById('chatSuggestions').innerHTML = '';

    // 3. Set new thread
    activeThreadId = data.thread_id;
    setStoredThread(data.thread_id);

    // 4. Inject lead context into first message
    var convText = data.conversations?.length > 0
      ? 'Past interactions:\n' + data.conversations.map(c => 
          `[${c.channel} ${c.direction}] ${c.content.substring(0,200)} (${c.created_at.substring(0,10)})`
        ).join('\n')
      : 'No past interactions yet.';

    var msg = `Chat about ${data.lead_name}\n\n` +
      `I want to discuss this lead. Profile:\n` +
      `Name: ${data.lead_name}\nCompany: ${data.lead_company || 'N/A'}\n` +
      `Phone: ${data.lead_phone || 'N/A'}\nEmail: ${data.lead_email || 'N/A'}\n` +
      `Source: ${data.lead_source || 'N/A'}\nStage: ${data.lead_stage || 'new'}\n` +
      `Notes: ${data.lead_notes || 'None'}\n\n` +
      convText + '\n\n' +
      `Please introduce yourself and briefly summarize this lead in 2-3 sentences.`;

    // 5. Show in chat panel
    addChatMsg(msg, true);
    showTyping();
    var r2 = await fetch('/api/agent/chat/' + TENANT, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: msg, thread_id: data.thread_id})
    });
    var resp = await r2.json();
    hideTyping();
    if (resp.response) addChatMsg(resp.response, false);
  } catch(e) {
    hideTyping();
    addChatMsg('Sorry, I encountered an error starting this chat.', false);
  }
}
```

## Key Requirements

1. **POST not GET** — The backend endpoint uses `@app.post`, but `fetch(url)` defaults to GET. Always specify `{method: 'POST'}`.

2. **Event delegation** — The "Start AI Chat" button uses `data-action="start-lead-chat"` and `data-lead-id="{{id}}"`, not inline onclick. Register in the document-level delegation handler:
   ```javascript
   if (action === 'start-lead-chat' && t.dataset.leadId) { 
     startLeadChat(t.dataset.leadId); 
     return; 
   }
   ```

3. **Thread title** — The backend creates the thread with `title=f"Chat about {lead.name}"`. The frontend message starts with `Chat about {leadName}` to match.

4. **\n escaping in Python """...""" strings** — Every `\n` in the JS code above must be `\\\\n` in the Python source to survive the triple-quoted string parser. See `../SKILL.md` for the full escaping reference.

5. **Hidden method for `startLeadChat`** — Since the ARA button is dynamically rendered into `innerHTML`, the event delegation on the `document` catches clicks. The handler uses `t.dataset.leadId` which is the `data-lead-id` attribute on the button element.
