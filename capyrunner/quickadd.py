"""Parse quick-add text like:
    "Call Jason in 30m"        -> due in 30 minutes
    "Deploy LMS in 2h"         -> due in 2 hours
    "Standup @9:30"            -> today 09:30 (tomorrow if already past)
    "Send report tomorrow @14" -> tomorrow 14:00
    "Review plugin tomorrow"   -> tomorrow 09:00
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

_IN = re.compile(r"\s+in\s+(\d+)\s*(m|min|mins|minutes?|h|hr|hrs|hours?|d|days?)\b", re.I)
_AT = re.compile(r"\s*@\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", re.I)
_TOMORROW = re.compile(r"\s+tomorrow\b", re.I)


def parse(text: str, now: datetime | None = None) -> tuple[str, str | None]:
    now = now or datetime.now()
    title = " " + text.strip()
    due: datetime | None = None

    m = _IN.search(title)
    if m:
        n, unit = int(m.group(1)), m.group(2).lower()
        delta = timedelta(minutes=n) if unit.startswith("m") else \
            timedelta(hours=n) if unit.startswith("h") else timedelta(days=n)
        due = now + delta
        title = title[:m.start()] + title[m.end():]

    tomorrow = bool(_TOMORROW.search(title))
    title = _TOMORROW.sub("", title)

    m = _AT.search(title)
    if m:
        h, mi, ap = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").lower()
        if ap == "pm" and h < 12:
            h += 12
        if ap == "am" and h == 12:
            h = 0
        if 0 <= h < 24 and 0 <= mi < 60:
            base = now + timedelta(days=1) if tomorrow else now
            due = base.replace(hour=h, minute=mi, second=0, microsecond=0)
            if not tomorrow and due <= now:
                due += timedelta(days=1)
            title = title[:m.start()] + title[m.end():]
    elif tomorrow and due is None:
        due = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)

    title = " ".join(title.split()) or text.strip()
    return title, due.replace(microsecond=0).isoformat() if due else None
