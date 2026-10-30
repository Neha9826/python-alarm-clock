"""Strict time parsing and next-occurrence calculations."""

import re
from datetime import datetime, time, timedelta

_TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def parse_time(value: str) -> time:
    """Parse a strict 24-hour ``HH:MM`` value.

    Values must be zero-padded and contain exactly two digits for both the
    hour and minute. Seconds and surrounding whitespace are not accepted.
    """

    if not isinstance(value, str) or not _TIME_PATTERN.fullmatch(value):
        raise ValueError("Time must use the 24-hour HH:MM format (for example, 09:05).")

    hour, minute = (int(part) for part in value.split(":"))
    return time(hour=hour, minute=minute)


def next_occurrence(alarm_time: str | time, now: datetime) -> datetime:
    """Return the next local datetime matching ``alarm_time``.

    A time earlier than the current hour/minute is scheduled for the following
    day. A request matching the current hour/minute remains due immediately,
    even if seconds have elapsed since the start of that minute.
    The supplied ``now`` value makes the calculation deterministic in tests.
    """

    parsed_time = parse_time(alarm_time) if isinstance(alarm_time, str) else alarm_time
    if not isinstance(parsed_time, time):
        raise TypeError("alarm_time must be an HH:MM string or datetime.time value.")
    if not isinstance(now, datetime):
        raise TypeError("now must be a datetime value.")

    occurrence = datetime.combine(now.date(), parsed_time, tzinfo=now.tzinfo)
    same_requested_minute = (
        parsed_time.second == 0
        and parsed_time.microsecond == 0
        and occurrence.hour == now.hour
        and occurrence.minute == now.minute
    )
    if occurrence < now and not same_requested_minute:
        occurrence += timedelta(days=1)
    return occurrence
