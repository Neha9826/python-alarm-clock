"""Thread-safe in-memory alarm storage and lifecycle management."""

from dataclasses import replace
from datetime import datetime, timedelta, time
from threading import Lock
from typing import Callable

from alarm import Alarm, AlarmStatus
from time_utils import next_occurrence, parse_time


class AlarmError(Exception):
    """Base class for expected alarm-management errors."""


class AlarmNotFoundError(AlarmError):
    """Raised when an alarm ID does not exist."""


class InvalidAlarmStateError(AlarmError):
    """Raised when an operation is invalid for an alarm's current state."""


Clock = Callable[[], datetime]
SNOOZE_DURATION = timedelta(minutes=5)


class AlarmManager:
    """Own alarm records and serialize every lifecycle transition."""

    def __init__(self, clock: Clock | None = None) -> None:
        self._clock = clock if clock is not None else datetime.now
        self._alarms: dict[int, Alarm] = {}
        self._next_id = 1
        self._lock = Lock()

    def create_alarm(self, alarm_time: str | time, label: str | None = None) -> Alarm:
        """Create an alarm and return a snapshot of the stored record."""

        parsed_time = (
            parse_time(alarm_time)
            if isinstance(alarm_time, str)
            else alarm_time
        )
        scheduled_at = next_occurrence(parsed_time, self._clock())
        normalized_label = label.strip() if label and label.strip() else None

        with self._lock:
            alarm_id = self._next_id
            self._next_id += 1
            alarm = Alarm(
                id=alarm_id,
                scheduled_at=scheduled_at,
                label=normalized_label,
            )
            self._alarms[alarm_id] = alarm
            return replace(alarm)

    def list_alarms(self) -> tuple[Alarm, ...]:
        """Return snapshots of all alarms, ordered by ID."""

        with self._lock:
            return tuple(
                replace(self._alarms[alarm_id])
                for alarm_id in sorted(self._alarms)
            )

    def get_alarm(self, alarm_id: int) -> Alarm:
        """Return a snapshot of one alarm."""

        with self._lock:
            return replace(self._get_alarm_unlocked(alarm_id))

    def cancel_alarm(self, alarm_id: int) -> Alarm:
        """Cancel an alarm only while it is scheduled."""

        with self._lock:
            alarm = self._get_alarm_unlocked(alarm_id)
            if alarm.status is not AlarmStatus.SCHEDULED:
                raise InvalidAlarmStateError(
                    f"Alarm {alarm_id} can only be cancelled while scheduled; "
                    f"its current status is {alarm.status.value}."
                )
            alarm.status = AlarmStatus.CANCELLED
            return replace(alarm)

    def snooze_alarm(self, alarm_id: int) -> Alarm:
        """Move a ringing alarm five minutes forward, preserving its ID."""

        with self._lock:
            alarm = self._get_alarm_unlocked(alarm_id)
            if alarm.status is not AlarmStatus.RINGING:
                raise InvalidAlarmStateError(
                    f"Alarm {alarm_id} can only be snoozed while ringing; "
                    f"its current status is {alarm.status.value}."
                )
            alarm.scheduled_at = self._clock() + SNOOZE_DURATION
            alarm.status = AlarmStatus.SCHEDULED
            return replace(alarm)

    def dismiss_alarm(self, alarm_id: int) -> Alarm:
        """Dismiss an alarm only while it is ringing."""

        with self._lock:
            alarm = self._get_alarm_unlocked(alarm_id)
            if alarm.status is not AlarmStatus.RINGING:
                raise InvalidAlarmStateError(
                    f"Alarm {alarm_id} can only be dismissed while ringing; "
                    f"its current status is {alarm.status.value}."
                )
            alarm.status = AlarmStatus.DISMISSED
            return replace(alarm)

    def trigger_due_alarms(self, now: datetime | None = None) -> tuple[Alarm, ...]:
        """Atomically mark due alarms as ringing and return their snapshots.

        The caller is responsible for delivering notifications after this
        method returns. No external callback is invoked while the manager lock
        is held.
        """

        current_time = now if now is not None else self._clock()
        due: list[Alarm] = []

        with self._lock:
            for alarm in self._alarms.values():
                if (
                    alarm.status is AlarmStatus.SCHEDULED
                    and alarm.scheduled_at <= current_time
                ):
                    alarm.status = AlarmStatus.RINGING
                    due.append(replace(alarm))

        return tuple(due)

    def _get_alarm_unlocked(self, alarm_id: int) -> Alarm:
        try:
            return self._alarms[alarm_id]
        except KeyError as exc:
            raise AlarmNotFoundError(f"Alarm {alarm_id} was not found.") from exc
