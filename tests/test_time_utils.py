"""Tests for strict time parsing and occurrence calculations."""

import unittest
from datetime import datetime, time

from time_utils import next_occurrence, parse_time


class ParseTimeTests(unittest.TestCase):
    def test_valid_zero_padded_24_hour_times(self) -> None:
        self.assertEqual(parse_time("00:00"), time(0, 0))
        self.assertEqual(parse_time("09:05"), time(9, 5))
        self.assertEqual(parse_time("23:59"), time(23, 59))

    def test_invalid_hours_and_minutes_are_rejected(self) -> None:
        for value in ("24:00", "99:00", "12:60", "12:99", "-1:00"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_time(value)

    def test_empty_and_malformed_values_are_rejected(self) -> None:
        for value in ("", " ", "9:05", "09:5", "09.05", "09:05:00", " 09:05", "09:05 "):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_time(value)

    def test_non_string_input_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_time(None)  # type: ignore[arg-type]


class NextOccurrenceTests(unittest.TestCase):
    def test_future_alarm_uses_current_date(self) -> None:
        now = datetime(2026, 10, 30, 10, 15)
        self.assertEqual(
            next_occurrence("11:30", now),
            datetime(2026, 10, 30, 11, 30),
        )

    def test_past_alarm_rolls_over_to_tomorrow(self) -> None:
        now = datetime(2026, 10, 30, 11, 30)
        self.assertEqual(
            next_occurrence("10:00", now),
            datetime(2026, 10, 31, 10, 0),
        )

    def test_exact_current_time_is_not_moved_to_tomorrow(self) -> None:
        now = datetime(2026, 10, 30, 11, 30)
        self.assertEqual(next_occurrence("11:30", now), now)

    def test_current_hour_and_minute_triggers_even_after_seconds_advance(self) -> None:
        now = datetime(2026, 10, 30, 11, 30, 47)
        self.assertEqual(
            next_occurrence("11:30", now),
            datetime(2026, 10, 30, 11, 30),
        )

    def test_midnight_rollover(self) -> None:
        now = datetime(2026, 10, 30, 23, 59)
        self.assertEqual(
            next_occurrence("00:00", now),
            datetime(2026, 10, 31, 0, 0),
        )

    def test_time_object_is_supported(self) -> None:
        now = datetime(2026, 10, 30, 7, 0)
        self.assertEqual(
            next_occurrence(time(8, 0), now),
            datetime(2026, 10, 30, 8, 0),
        )

    def test_timezone_information_is_preserved(self) -> None:
        from datetime import timezone, timedelta

        zone = timezone(timedelta(hours=5, minutes=30))
        now = datetime(2026, 10, 30, 23, 30, tzinfo=zone)
        result = next_occurrence("00:15", now)
        self.assertEqual(result, datetime(2026, 10, 31, 0, 15, tzinfo=zone))


if __name__ == "__main__":
    unittest.main()
