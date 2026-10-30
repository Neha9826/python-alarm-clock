"""Background scheduler for due alarm notifications."""

from threading import Event, Lock, Thread, current_thread
from typing import Callable

from alarm import Alarm
from alarm_manager import AlarmManager


NotificationCallback = Callable[[Alarm], None]


class AlarmScheduler:
    """Poll the manager and notify immediately when an alarm starts ringing.

    The manager performs the atomic state transition. This class invokes the
    supplied callback only after that manager method has released its lock.
    """

    def __init__(
        self,
        alarm_manager: AlarmManager,
        notification_callback: NotificationCallback,
        poll_interval: float = 0.25,
    ) -> None:
        if poll_interval <= 0:
            raise ValueError("poll_interval must be greater than zero.")

        self._alarm_manager = alarm_manager
        self._notification_callback = notification_callback
        self._poll_interval = poll_interval
        self._stop_event = Event()
        self._state_lock = Lock()
        self._thread: Thread | None = None

    @property
    def is_running(self) -> bool:
        """Whether the scheduler worker thread is currently alive."""

        with self._state_lock:
            return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Start the worker; repeated calls while running are harmless."""

        with self._state_lock:
            if self._thread is not None and self._thread.is_alive():
                return

            self._stop_event.clear()
            self._thread = Thread(
                target=self._run,
                name="alarm-scheduler",
                daemon=True,
            )
            self._thread.start()

    def stop(self, timeout: float | None = 5.0) -> None:
        """Request shutdown and join the worker thread.

        A timeout raises ``TimeoutError`` instead of silently leaving a worker
        running. ``None`` waits without a timeout.
        """

        with self._state_lock:
            thread = self._thread
            self._stop_event.set()

        if thread is None or thread is current_thread():
            return

        thread.join(timeout=timeout)
        if thread.is_alive():
            raise TimeoutError("Alarm scheduler did not stop before the timeout.")

    def _run(self) -> None:
        while not self._stop_event.is_set():
            due_alarms = self._alarm_manager.trigger_due_alarms()
            for alarm in due_alarms:
                self._notification_callback(alarm)
            self._stop_event.wait(self._poll_interval)
