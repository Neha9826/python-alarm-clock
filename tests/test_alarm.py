"""Tests for the alarm data model."""

import unittest
from datetime import datetime

from alarm import Alarm, AlarmStatus


class AlarmModelTests(unittest.TestCase):
    def test_default_status_and_label(self) -> None:
        scheduled_at = datetime(2026, 10, 31, 8, 30)
        alarm = Alarm(id=1, scheduled_at=scheduled_at)

        self.assertEqual(alarm.id, 1)
        self.assertEqual(alarm.scheduled_at, scheduled_at)
        self.assertIsNone(alarm.label)
        self.assertIs(alarm.status, AlarmStatus.SCHEDULED)

    def test_custom_label_and_status(self) -> None:
        scheduled_at = datetime(2026, 10, 31, 8, 30)
        alarm = Alarm(
            id=42,
            scheduled_at=scheduled_at,
            label="Morning meeting",
            status=AlarmStatus.RINGING,
        )

        self.assertEqual(alarm.label, "Morning meeting")
        self.assertIs(alarm.status, AlarmStatus.RINGING)
        self.assertEqual(alarm.scheduled_at, scheduled_at)

    def test_lifecycle_enum_values(self) -> None:
        self.assertEqual(
            {status.value for status in AlarmStatus},
            {"scheduled", "ringing", "dismissed", "cancelled"},
        )


if __name__ == "__main__":
    unittest.main()
