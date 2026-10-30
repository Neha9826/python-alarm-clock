"""Application entry point."""

from threading import Lock

from alarm_manager import AlarmManager
from cli import AlarmCLI
from scheduler import AlarmScheduler


def main() -> None:
    """Initialize the application and guarantee scheduler shutdown."""

    output_lock = Lock()
    alarm_manager = AlarmManager()
    cli = AlarmCLI(alarm_manager, output_lock=output_lock)
    scheduler = AlarmScheduler(alarm_manager, cli.notify_alarm)

    try:
        scheduler.start()
        cli.run()
    except KeyboardInterrupt:
        cli.write_message("\nInterrupted. Shutting down.")
    finally:
        scheduler.stop()


if __name__ == "__main__":
    main()
