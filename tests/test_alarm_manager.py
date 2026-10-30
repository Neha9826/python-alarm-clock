"""Tests for alarm storage, lifecycle rules, and concurrency."""

import threading
import unittest
from datetime import datetime

from alarm import AlarmStatus
from alarm_manager import (
    AlarmManager,
    AlarmNotFoundError,
    InvalidAlarmStateError,
)


class MutableClock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def __call__(self) -> datetime:
        return self.current


class AlarmManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 10, 30, 9, 0)
        self.clock = MutableClock(self.now)
        self.manager = AlarmManager(clock=self.clock)

    def test_create_multiple_alarms_with_unique_ids(self) -> None:
        first = self.manager.create_alarm("10:00", "Stand-up")
        second = self.manager.create_alarm("11:00", "Review")

        self.assertEqual(first.id, 1)
        self.assertEqual(second.id, 2)
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(first.label, "Stand-up")
        self.assertEqual(second.label, "Review")

    def test_blank_label_is_normalized_to_none(self) -> None:
        alarm = self.manager.create_alarm("10:00", "   ")
        self.assertIsNone(alarm.label)

    def test_list_returns_all_alarms_and_current_statuses(self) -> None:
        first = self.manager.create_alarm("10:00")
        second = self.manager.create_alarm("11:00")
        self.manager.cancel_alarm(first.id)

        alarms = self.manager.list_alarms()
        self.assertEqual([alarm.id for alarm in alarms], [1, 2])
        self.assertIs(alarms[0].status, AlarmStatus.CANCELLED)
        self.assertIs(alarms[1].status, AlarmStatus.SCHEDULED)
        self.assertEqual(second.id, alarms[1].id)

    def test_list_returns_snapshots_not_mutable_internal_records(self) -> None:
        alarm = self.manager.create_alarm("10:00")
        snapshot = self.manager.list_alarms()[0]
        snapshot.status = AlarmStatus.DISMISSED

        self.assertIs(self.manager.get_alarm(alarm.id).status, AlarmStatus.SCHEDULED)

    def test_cancel_pending_alarm(self) -> None:
        alarm = self.manager.create_alarm("10:00")
        cancelled = self.manager.cancel_alarm(alarm.id)
        self.assertIs(cancelled.status, AlarmStatus.CANCELLED)

    def test_cannot_cancel_ringing_alarm(self) -> None:
        alarm = self.manager.create_alarm("09:00")
        self.manager.trigger_due_alarms()
        with self.assertRaises(InvalidAlarmStateError):
            self.manager.cancel_alarm(alarm.id)

    def test_cannot_cancel_terminal_alarm(self) -> None:
        alarm = self.manager.create_alarm("10:00")
        self.manager.cancel_alarm(alarm.id)
        with self.assertRaises(InvalidAlarmStateError):
            self.manager.cancel_alarm(alarm.id)

    def test_unknown_alarm_id_raises_not_found(self) -> None:
        with self.assertRaises(AlarmNotFoundError):
            self.manager.cancel_alarm(999)
        with self.assertRaises(AlarmNotFoundError):
            self.manager.get_alarm(999)

    def test_snooze_ringing_alarm_for_exactly_five_minutes(self) -> None:
        alarm = self.manager.create_alarm("09:00")
        self.manager.trigger_due_alarms()
        self.clock.current = datetime(2026, 10, 30, 9, 2, 15)

        snoozed = self.manager.snooze_alarm(alarm.id)
        self.assertEqual(snoozed.id, alarm.id)
        self.assertEqual(
            snoozed.scheduled_at,
            datetime(2026, 10, 30, 9, 7, 15),
        )
        self.assertIs(snoozed.status, AlarmStatus.SCHEDULED)

    def test_snooze_requires_ringing_state(self) -> None:
        alarm = self.manager.create_alarm("10:00")
        with self.assertRaises(InvalidAlarmStateError):
            self.manager.snooze_alarm(alarm.id)

    def test_dismiss_ringing_alarm(self) -> None:
        alarm = self.manager.create_alarm("09:00")
        self.manager.trigger_due_alarms()
        dismissed = self.manager.dismiss_alarm(alarm.id)
        self.assertIs(dismissed.status, AlarmStatus.DISMISSED)

    def test_dismiss_requires_ringing_state(self) -> None:
        alarm = self.manager.create_alarm("10:00")
        with self.assertRaises(InvalidAlarmStateError):
            self.manager.dismiss_alarm(alarm.id)

    def test_due_alarm_transitions_to_ringing_exactly_once(self) -> None:
        alarm = self.manager.create_alarm("09:00")

        first_result = self.manager.trigger_due_alarms()
        second_result = self.manager.trigger_due_alarms()

        self.assertEqual([item.id for item in first_result], [alarm.id])
        self.assertEqual(second_result, ())
        self.assertIs(self.manager.get_alarm(alarm.id).status, AlarmStatus.RINGING)

    def test_alarm_is_not_due_before_scheduled_datetime(self) -> None:
        alarm = self.manager.create_alarm("10:00")
        results = self.manager.trigger_due_alarms(
            now=datetime(2026, 10, 30, 9, 59, 59)
        )
        self.assertEqual(results, ())
        self.assertIs(self.manager.get_alarm(alarm.id).status, AlarmStatus.SCHEDULED)

    def test_cancelled_alarm_is_not_triggered(self) -> None:
        alarm = self.manager.create_alarm("10:00")
        self.manager.cancel_alarm(alarm.id)
        results = self.manager.trigger_due_alarms(
            now=datetime(2026, 10, 30, 12, 0)
        )
        self.assertEqual(results, ())

    def test_snoozed_alarm_can_ring_again_with_same_id(self) -> None:
        alarm = self.manager.create_alarm("09:00")
        first_ring = self.manager.trigger_due_alarms()
        self.assertEqual(first_ring[0].id, alarm.id)

        self.clock.current = datetime(2026, 10, 30, 9, 1)
        snoozed = self.manager.snooze_alarm(alarm.id)
        second_ring = self.manager.trigger_due_alarms(
            now=snoozed.scheduled_at
        )

        self.assertEqual(len(second_ring), 1)
        self.assertEqual(second_ring[0].id, alarm.id)
        self.assertIs(second_ring[0].status, AlarmStatus.RINGING)

    def test_concurrent_due_checks_trigger_alarm_only_once(self) -> None:
        alarm = self.manager.create_alarm("09:00")
        worker_count = 16
        barrier = threading.Barrier(worker_count)
        results: list[tuple] = []
        results_lock = threading.Lock()
        errors: list[BaseException] = []

        def check_due() -> None:
            try:
                barrier.wait(timeout=2)
                result = self.manager.trigger_due_alarms()
                with results_lock:
                    results.append(result)
            except BaseException as exc:  # surfaced in the test thread
                with results_lock:
                    errors.append(exc)

        workers = [threading.Thread(target=check_due) for _ in range(worker_count)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=3)

        self.assertFalse(any(worker.is_alive() for worker in workers))
        self.assertEqual(errors, [])
        triggered_ids = [item.id for result in results for item in result]
        self.assertEqual(triggered_ids, [alarm.id])

    def test_race_between_cancel_and_due_check_has_one_valid_outcome(self) -> None:
        alarm = self.manager.create_alarm("10:00")
        barrier = threading.Barrier(2)
        outcomes: list[str] = []
        outcomes_lock = threading.Lock()

        def cancel() -> None:
            barrier.wait(timeout=2)
            try:
                result = self.manager.cancel_alarm(alarm.id)
                outcome = result.status.value
            except InvalidAlarmStateError:
                outcome = "cancel-rejected"
            with outcomes_lock:
                outcomes.append(outcome)

        def trigger() -> None:
            barrier.wait(timeout=2)
            result = self.manager.trigger_due_alarms(
                now=datetime(2026, 10, 30, 10, 0)
            )
            outcome = result[0].status.value if result else "not-triggered"
            with outcomes_lock:
                outcomes.append(outcome)

        workers = [threading.Thread(target=cancel), threading.Thread(target=trigger)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=3)

        self.assertFalse(any(worker.is_alive() for worker in workers))
        final_status = self.manager.get_alarm(alarm.id).status
        self.assertIn(final_status, {AlarmStatus.CANCELLED, AlarmStatus.RINGING})
        if final_status is AlarmStatus.CANCELLED:
            self.assertIn("not-triggered", outcomes)
        else:
            self.assertIn("cancel-rejected", outcomes)


if __name__ == "__main__":
    unittest.main()
