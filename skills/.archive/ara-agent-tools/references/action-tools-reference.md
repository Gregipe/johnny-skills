# Action Tools Reference (May 2026)

Six new tools Ava can call during conversations to enforce decisions on the backend.
All follow the [TOOL_CALL: {json}] format. Most require user confirmation except `add_skill`.

## 1. create_action_item

Creates a personal action item / reminder for the human team.

```python
# Handler (execute_tool):
elif tool_name == 'create_action_item':
    title = args.get('title', '')
    description = args.get('description', '')
    lead_name = args.get('lead_name', '')
    priority = args.get('priority', 'normal')  # low, normal, high, critical
    if not title:
        return "Error: 'title' is required"
    from database import ActionItem
    lead = resolve_lead(lead_name, db) if lead_name else None
    action = ActionItem(
        tenant_id=tenant_id,
        action_type='review_lead' if lead else 'note',
        title=title,
        description=f"[{priority}] {description or title}",
        ref_type='lead' if lead else None,
        ref_id=lead.id if lead else None,
        status='open',
    )
    db.add(action)
    db.commit()
    return f"📋 Action item created: [{priority}] {title}"
```

**DB Model:** `ActionItem` — note it uses `action_type`, `ref_type`, `ref_id`, NOT `lead_id` or `priority` or `source` column. Priority is embedded in the description string.

**Confirmation:** YES (data-modifying)

## 2. update_lead_stage

Moves a lead through its pipeline stage with an optional reason.

```python
elif tool_name == 'update_lead_stage':
    lead_name = args.get('lead_name', '')
    new_stage = args.get('stage', '')
    reason = args.get('reason', '')
    if not lead_name or not new_stage:
        return "Error: 'lead_name' and 'stage' are required"
    valid = ('new', 'reached_out', 'engaged', 'qualified', 'meeting_booked',
             'dormant', 'closed_won', 'closed_lost', 'lost')
    if new_stage not in valid:
        return f"Error: stage must be one of {', '.join(valid)}"
    lead = resolve_lead(lead_name, db)
    old = lead.stage
    lead.stage = new_stage
    lead.updated_at = utcnow()
    db.commit()
    msg = f"Stage: {old} → {new_stage}"
    if reason:
        msg += f" — {reason}"
    return f"✅ {lead.name}: {msg}"
```

**Valid stages:** `new`, `reached_out`, `engaged`, `qualified`, `meeting_booked`, `dormant`, `closed_won`, `closed_lost`, `lost`

**Auto-confirmation triggers:** Direct command verbs like "move Gregory to engaged" bypass the "Shall I proceed?" gate.

**Confirmation:** YES (data-modifying — changes lead state)

## 3. schedule_follow_up

Schedules a future follow-up action for a lead with a purpose and optional message template.

```python
elif tool_name == 'schedule_follow_up':
    lead_name = args.get('lead_name', '')
    purpose = args.get('purpose', '')
    channel = args.get('channel', 'auto')  # auto, email, whatsapp, call
    delay_hours = int(args.get('delay_hours', 48))
    message_template = args.get('message_template', '')
    if not lead_name or not purpose:
        return "Error: 'lead_name' and 'purpose' are required"
    lead = resolve_lead(lead_name, db)
    scheduled_at = utcnow() + timedelta(hours=delay_hours)
    from database import ScheduledAction
    action = ScheduledAction(
        tenant_id=tenant_id, lead_id=lead.id, action_type='follow_up',
        status='pending', scheduled_at=scheduled_at,
        payload={'purpose': purpose, 'channel': channel,
                 'lead_stage': lead.stage,
                 'message_template': message_template or ''},
        channel=channel if channel != 'auto' else 'whatsapp',
    )
    db.add(action)
    db.commit()
    # Returns IST time for human-readable display
    return f"📅 Follow-up for {lead.name} at ... Purpose: {purpose}"
```

**Scheduler handling:** The existing scheduler daemon polls `ScheduledAction` every 30s. `follow_up` is a new `action_type` — the scheduler needs to know how to handle it (typically send a WhatsApp with the message_template or a generic check-in).

**Confirmation:** YES (schedules an action)

## 4. add_skill (Autonomous — No Confirmation)

Saves a new learning/skill from a conversation. This is the **only** data-modifying tool that does NOT require user confirmation.

```python
elif tool_name == 'add_skill':
    category = args.get('category', '')
    key = args.get('key', '')
    value = args.get('value', '')
    segment = args.get('segment', '')
    if not category or not key or not value:
        return "Error: 'category', 'key', and 'value' are required"
    from database import Skill
    skill = Skill(tenant_id=tenant_id, category=category, key=key,
                  value=value, source='conversation', confidence=1.0,
                  evidence_count=1)
    db.add(skill)
    db.commit()
    tag = f" [{segment}]" if segment else ''
    return f"🧠 Skill saved{tag}: [{category}] {key}"
```

**Why autonomous:** Conversation learnings are enrichment/observation — the human doesn't need to review each one individually. If a pattern turns out wrong, a single "delete that skill" command fixes it.

**Valid categories:** `proposition`, `gtm_learning`, `guardrail`, `objection_pattern`, `messaging_win`, `segment_signal`, `timing_pattern`

**Wiring:** The tool name is **omitted from `_DATA_MODIFYING_TOOLS`** so the confirmation gate (`needs_confirmation = tool_names & data_modifying_tools`) skips it. The system prompt's `IMPORTANT` rule lists `add_skill` under the read-only section.

**Confirmation:** NO (autonomous enrichment)

## 5. escalate_to_human

Flags something urgent for Greg's attention with priority level. Creates BOTH an ActionItem AND a LearningNotification.

```python
elif tool_name == 'escalate_to_human':
    title = args.get('title', '')
    message = args.get('message', '')
    lead_name = args.get('lead_name', '')
    urgency = args.get('urgency', 'normal')  # normal, high, critical
    if not title or not message:
        return "Error: 'title' and 'message' are required"
    from database import ActionItem, LearningNotification
    lead = resolve_lead(lead_name, db) if lead_name else None
    action = ActionItem(tenant_id=tenant_id, action_type='escalate',
        title=title, description=f"[{urgency}] {message}",
        ref_type='lead' if lead else None,
        ref_id=lead.id if lead else None, status='open')
    db.add(action)
    note = LearningNotification(tenant_id=tenant_id, notif_type='escalation',
        title=f"🚨 Escalation: {title}", message=message)
    db.add(note)
    db.commit()
    return f"🚨 Escalated: [{urgency}] {title}"
```

**DB Models:**
- `ActionItem` uses: `action_type`, `title`, `description`, `ref_type`, `ref_id`, `status` — NOT `lead_id`, `priority`, `source`, `due_at`
- `LearningNotification` uses: `notif_type` (NOT `notification_type`), `title`, `message` — NO `source` column

**Confirmation:** YES (flags require human attention)

## 6. log_insight

Logs a structured insight about a conversation exchange to the AvaInsight table.

```python
elif tool_name == 'log_insight':
    lead_name = args.get('lead_name', '')
    insight_type = args.get('insight_type', '')  # sentiment, objection, signal, win, pattern
    summary = args.get('summary', '')
    details = args.get('details', '')
    if not lead_name or not insight_type or not summary:
        return "Error: 'lead_name', 'insight_type', and 'summary' are required"
    lead = resolve_lead(lead_name, db)
    from database import Conversation, AvaInsight
    last_conv = db.query(Conversation).filter(
        Conversation.lead_id == lead.id
    ).order_by(Conversation.created_at.desc()).first()
    insight = AvaInsight(tenant_id=tenant_id, lead_id=lead.id,
        conversation_id=last_conv.id if last_conv else None,
        insight_type=insight_type, key=summary[:120],
        value=details or summary, source='ava')
    db.add(insight)
    db.commit()
    return f"💡 Insight logged: [{insight_type}] {summary[:80]}"
```

**DB Model:** `AvaInsight` uses: `insight_type` (NOT `signal_type`), `key`, `value`, `source`, `confidence` — NOT `summary`, `details`

**Confirmation:** YES (writes to the insights journal)

## Integration Checklist

When adding a new action tool (or modifying an existing one), audit all of:

1. **Handler** — `elif tool_name == 'my_tool':` block in `execute_tool()`
2. **System prompt definition** — Numbered entry in the tool schema section
3. **Example** — `[TOOL_CALL: {...}]` example in the examples section
4. **Confirmation gate** — Add/remove from `_DATA_MODIFYING_TOOLS` set
5. **Confirmation prompt text** — The `IMPORTANT: Before outputting [TOOL_CALL:]` rule line — update both the data-modifying and read-only lists
6. **Autonomous exception** — If the tool is enrichment-only (like `add_skill`), omit from `_DATA_MODIFYING_TOOLS` and add to the read-only list in the confirmation prompt text

## See Also

- `ara-agent-tools/SKILL.md` — Main tool-calling architecture
- `ara-agent-tools/references/action-agent-7-layer-expansion.md` — Full tool expansion architecture
- `ara-agent-tools/references/tool-handler-safety-rules.md` — DateTime parsing, NOT NULL constraints, commit-failure cascades
- `ara-ava-guardrails/SKILL.md` — Ava's personality boundaries and prompt injection protection
- `server.py` — `execute_tool()` function at ~line 3090

## Note: `create_action` (distinct from `create_action_item`)

A separate tool handler at `server.py:3471` for voice-note-initiated actions. Has two known pitfalls:
- `due_at` must be parsed from string to datetime (see tool-handler-safety-rules.md §1)
- `action_type` must be set explicitly — column is NOT NULL (see tool-handler-safety-rules.md §2)
