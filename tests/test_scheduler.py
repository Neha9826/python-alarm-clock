"""Tests for scheduler threading, notification, and shutdown."""

import threading
import unittest
from datetime import datetime
from io import StringIO

from alarm_manager import AlarmManager
from cli import AlarmCLI
from scheduler import AlarmScheduler


class SchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 10, 30, 9, 0)
        self.manager = AlarmManager(clock=lambda: self.now)

    def test_background_thread_notifies_immediately_for_due_alarm(self) -> None:
        alarm = self.manager.create_alarm("09:00", "Immediate")
        notified = threading.Event()
        received = []

        def callback(item) -> None:
            received.append(item)
            notified.set()

        scheduler = AlarmScheduler(self.manager, callback, poll_interval=0.01)
        try:
            scheduler.start()
            self.assertTrue(notified.wait(timeout=2))
        finally:
            scheduler.stop(timeout=2)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].id, alarm.id)
        self.assertFalse(scheduler.is_running)

    def test_scheduler_does_not_duplicate_notification_across_cycles(self) -> None:
        alarm = self.manager.create_alarm("09:00")
        notified = threading.Event()
        second_cycle = threading.Event()
        callback_count = 0
        cycle_count = 0
        count_lock = threading.Lock()
        original_trigger = self.manager.trigger_due_alarms

        def tracked_trigger_due_alarms(*args, **kwargs):
            nonlocal cycle_count
            result = original_trigger(*args, **kwargs)
            with count_lock:
                cycle_count += 1
                if cycle_count >= 2:
                    second_cycle.set()
            return result

        self.manager.trigger_due_alarms = (  # type: ignore[method-assign]
            tracked_trigger_due_alarms
        )

        def callback(item) -> None:
            nonlocal callback_count
            with count_lock:
                callback_count += 1
            notified.set()

        scheduler = AlarmScheduler(self.manager, callback, poll_interval=0.01)
        try:
            scheduler.start()
            self.assertTrue(notified.wait(timeout=2))
            self.assertTrue(second_cycle.wait(timeout=2))
        finally:
            scheduler.stop(timeout=2)

        self.assertEqual(callback_count, 1)
        self.assertEqual(self.manager.get_alarm(alarm.id).status.value, "ringing")

    def test_scheduler_stops_and_joins_worker_thread(self) -> None:
        self.manager.create_alarm("10:00")
        scheduler = AlarmScheduler(self.manager, lambda _alarm: None, poll_interval=1)

        scheduler.start()
        self.assertTrue(scheduler.is_running)
        scheduler.stop(timeout=2)

        self.assertFalse(scheduler.is_running)

    def test_repeated_start_does_not_create_duplicate_workers(self) -> None:
        scheduler = AlarmScheduler(self.manager, lambda _alarm: None, poll_interval=0.5)
        scheduler.start()
        first_thread = scheduler._thread
        scheduler.start()
        try:
            self.assertIs(scheduler._thread, first_thread)
        finally:
            scheduler.stop(timeout=2)

    def test_callback_runs_after_manager_lock_is_released(self) -> None:
        self.manager.create_alarm("09:00")
        callback_completed = threading.Event()
        lock_was_available: list[bool] = []

        def callback(_alarm) -> None:
            acquired = self.manager._lock.acquire(blocking=False)
            lock_was_available.append(acquired)
            if acquired:
                self.manager._lock.release()
            callback_completed.set()

        scheduler = AlarmScheduler(self.manager, callback, poll_interval=0.01)
        try:
            scheduler.start()
            self.assertTrue(callback_completed.wait(timeout=2))
        finally:
            scheduler.stop(timeout=2)

        self.assertEqual(lock_was_available, [True])


    def test_notification_is_printed_while_cli_input_is_blocked(self) -> None:
        self.manager.create_alarm("09:00", "While typing")
        input_started = threading.Event()
        allow_input_to_finish = threading.Event()
        notification_delivered = threading.Event()
        output = StringIO()

        def blocking_input() -> str:
            input_started.set()
            if not allow_input_to_finish.wait(timeout=2):
                raise TimeoutError("Test input was not released.")
            return "exit"

        cli = AlarmCLI(
            self.manager,
            input_function=blocking_input,
            output_stream=output,
        )

        def notify(alarm) -> None:
            cli.notify_alarm(alarm)
            notification_delivered.set()

        scheduler = AlarmScheduler(self.manager, notify, poll_interval=0.01)
        cli_thread = threading.Thread(target=cli.run)
        try:
            cli_thread.start()
            self.assertTrue(input_started.wait(timeout=2))
            scheduler.start()
            self.assertTrue(notification_delivered.wait(timeout=2))
            self.assertIn("[ALARM] Alarm #1 is ringing", output.getvalue())
        finally:
            allow_input_to_finish.set()
            cli_thread.join(timeout=2)
            scheduler.stop(timeout=2)

        self.assertFalse(cli_thread.is_alive())

    def test_non_positive_poll_interval_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AlarmScheduler(self.manager, lambda _alarm: None, poll_interval=0)


if __name__ == "__main__":
    unittest.main()
