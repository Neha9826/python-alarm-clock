"""Interactive command-line interface for the alarm clock."""

import shlex
import sys
from threading import Lock
from typing import Callable, TextIO

from alarm import Alarm
from alarm_manager import AlarmError, AlarmManager


InputFunction = Callable[[], str]


class AlarmCLI:
    """Read commands and coordinate application-controlled terminal output.

    Notifications are written directly by the scheduler callback, so they do
    not depend on the blocking input operation returning. Standard ``input``
    cannot reliably redraw a partially typed line on every terminal; the
    notification and a fresh prompt are still printed immediately.
    """

    def __init__(
        self,
        alarm_manager: AlarmManager,
        output_lock: Lock | None = None,
        input_function: InputFunction = input,
        output_stream: TextIO | None = None,
    ) -> None:
        self._alarm_manager = alarm_manager
        self._output_lock = output_lock if output_lock is not None else Lock()
        self._input = input_function
        self._output = output_stream if output_stream is not None else sys.stdout

    def run(self) -> None:
        """Run the command loop until exit or end-of-input."""

        self._write("Type 'help' to see available commands.")
        while True:
            self._write("alarm> ", end="")
            try:
                raw_command = self._input()
            except EOFError:
                self._write("\nInput closed. Exiting.")
                return

            try:
                should_continue = self.execute(raw_command)
            except (AlarmError, ValueError) as exc:
                self._write(f"Error: {exc}")
                continue

            if not should_continue:
                self._write("Goodbye.")
                return

    def execute(self, raw_command: str) -> bool:
        """Execute one command; return ``False`` when the CLI should exit."""

        try:
            parts = shlex.split(raw_command)
        except ValueError as exc:
            raise ValueError(f"Could not parse command: {exc}") from exc

        if not parts:
            return True

        command = parts[0].lower()
        args = parts[1:]

        if command == "help":
            self._require_arg_count(command, args, 0)
            self._show_help()
        elif command == "set":
            if len(args) < 1:
                raise ValueError("Usage: set HH:MM [label]")
            label = " ".join(args[1:]) or None
            alarm = self._alarm_manager.create_alarm(args[0], label)
            self._write(
                f"Created alarm #{alarm.id} for {alarm.scheduled_at:%Y-%m-%d %H:%M}"
                + (f" — {alarm.label}" if alarm.label else "")
                + "."
            )
        elif command == "list":
            self._require_arg_count(command, args, 0)
            self._show_alarms()
        elif command == "cancel":
            self._require_arg_count(command, args, 1)
            alarm = self._alarm_manager.cancel_alarm(self._parse_id(args[0]))
            self._write(f"Alarm #{alarm.id} cancelled.")
        elif command == "snooze":
            self._require_arg_count(command, args, 1)
            alarm = self._alarm_manager.snooze_alarm(self._parse_id(args[0]))
            self._write(
                f"Alarm #{alarm.id} snoozed until {alarm.scheduled_at:%Y-%m-%d %H:%M}."
            )
        elif command == "dismiss":
            self._require_arg_count(command, args, 1)
            alarm = self._alarm_manager.dismiss_alarm(self._parse_id(args[0]))
            self._write(f"Alarm #{alarm.id} dismissed.")
        elif command == "exit":
            self._require_arg_count(command, args, 0)
            return False
        else:
            raise ValueError(f"Unknown command '{command}'. Type 'help' for commands.")

        return True

    def notify_alarm(self, alarm: Alarm) -> None:
        """Print a ringing notification from the scheduler thread."""

        label = f" — {alarm.label}" if alarm.label else ""
        with self._output_lock:
            self._output.write("\a\n")
            self._output.write(
                f"[ALARM] Alarm #{alarm.id} is ringing{label}. "
                f"Use 'snooze {alarm.id}' or 'dismiss {alarm.id}'.\n"
            )
            self._output.write("alarm> ")
            self._output.flush()

    def write_message(self, message: str) -> None:
        """Write an application message using the shared output lock."""

        self._write(message)

    def _show_alarms(self) -> None:
        alarms = self._alarm_manager.list_alarms()
        if not alarms:
            self._write("No alarms have been created.")
            return

        self._write("ID  Scheduled             Status      Label")
        self._write("--  -------------------   ----------  ----------------")
        for alarm in alarms:
            label = alarm.label or "-"
            self._write(
                f"{alarm.id:<3} {alarm.scheduled_at:%Y-%m-%d %H:%M:%S}   "
                f"{alarm.status.value:<10}  {label}"
            )

    def _show_help(self) -> None:
        self._write("Commands:")
        self._write(
            "  set HH:MM [label]  Create a one-time alarm (24-hour local time)."
        )
        self._write("  list               List all alarms and their statuses.")
        self._write("  cancel ID          Cancel an alarm that is still scheduled.")
        self._write("  snooze ID          Snooze a ringing alarm for five minutes.")
        self._write("  dismiss ID         Dismiss a ringing alarm.")
        self._write("  help               Show this help message.")
        self._write("  exit               Shut down the application.")

    def _write(self, message: str, end: str = "\n") -> None:
        with self._output_lock:
            self._output.write(message + end)
            self._output.flush()

    @staticmethod
    def _parse_id(value: str) -> int:
        try:
            alarm_id = int(value)
        except ValueError as exc:
            raise ValueError("Alarm ID must be an integer.") from exc
        if alarm_id <= 0:
            raise ValueError("Alarm ID must be a positive integer.")
        return alarm_id

    @staticmethod
    def _require_arg_count(command: str, args: list[str], expected: int) -> None:
        if len(args) != expected:
            if command in {"cancel", "snooze", "dismiss"}:
                usage = f"Usage: {command} ID"
            else:
                usage = f"Usage: {command}"
            raise ValueError(usage)
