# ICS Calendar File Generation

`ics_utils.py` generates `.ics` calendar files for meeting invitations sent via email.

## Usage

```python
from ics_utils import create_ics

ics_content = create_ics(
    lead_name="Gregory Ipe",
    meeting_details="2pm tomorrow - demo call",
    duration_minutes=60,
    organizer="Ava from Hunar.ai"
)
# Returns string containing .ics content
# Encode to bytes for email attachment: ics_content.encode("utf-8")
```

## Time Parsing

`_parse_meeting_time(details, now)` extracts the meeting time from natural language:

| Pattern | Example | Resolution |
|---------|---------|------------|
| `"tomorrow"` + time | "2pm tomorrow" | Next day at 14:00 |
| `"next week"` + time | "next week 3pm" | Next Monday at 15:00 |
| Time with am/pm | "Thursday 3pm", "2:30pm" | Parsed hour/minute |
| 24h format | "14:00" | Parsed directly |
| No time match | "Let's meet" | Defaults to next day 11am |

## Output Structure

```
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Hunar.ai//ARA//EN
METHOD:REQUEST
BEGIN:VEVENT
DTSTART:<YYYYMMDDTHHMMSS>
DTEND:<YYYYMMDDTHHMMSS>
DTSTAMP:<YYYYMMDDTHHMMSS>
UID:ara-meeting-<timestamp>-<hash>
SUMMARY:Meeting with <lead> - Hunar.ai
DESCRIPTION:Meeting with <lead>\n\n<details>
LOCATION:Virtual
BEGIN:VALARM
TRIGGER:-PT15M
ACTION:DISPLAY
DESCRIPTION:Reminder: Meeting with <lead>
END:VALARM
END:VEVENT
END:VCALENDAR
```

## Integration Points

- Called from `mark_meeting_booked` tool handler (~line 2470 in server.py)
- Called from `_detect_stage_changes` function (~line 4560 in server.py)
- Sends via `send_via_gmail_api()` with attachments parameter
