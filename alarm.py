"""Core alarm data types."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class AlarmStatus(str, Enum):
    """Lifecycle states supported by an alarm."""

    SCHEDULED = "scheduled"
    RINGING = "ringing"
    DISMISSED = "dismissed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class Alarm:
    """An in-memory, one-time alarm.

    Lifecycle transitions are intentionally owned by :class:`AlarmManager`,
    rather than implemented as methods on this data model.
    """

    id: int
    scheduled_at: datetime
    label: str | None = None
    status: AlarmStatus = AlarmStatus.SCHEDULED
