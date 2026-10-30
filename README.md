# Python CLI Alarm Clock

A lightweight, dependency-free command-line alarm clock built with Python's standard library.

The application supports multiple one-time alarms, thread-safe alarm lifecycle management, five-minute snoozing, and background notifications that appear even while the CLI is waiting for user input.

The project emphasizes correctness, concurrency safety, maintainability, and testability without introducing unnecessary dependencies or infrastructure.

## Features

- Create multiple one-time alarms using strict 24-hour `HH:MM` input.
- Assign every alarm a unique, increasing integer ID.
- Support optional labels for identifying alarms.
- List alarms with their scheduled datetime and current status.
- Cancel alarms that are still scheduled.
- Trigger due alarms automatically through a background scheduler thread.
- Display alarm notifications without requiring the user to press Enter.
- Emit a terminal bell when an alarm starts ringing.
- Snooze ringing alarms for five minutes while preserving their original IDs.
- Dismiss ringing alarms.
- Handle exact-current-time scheduling and next-day rollover.
- Validate command input and reject invalid lifecycle operations.
- Shut down the scheduler cleanly on `exit`, end-of-input, or Ctrl+C.
- Keep alarm state in memory without requiring a database or external service.

## Technology Stack

| Component | Technology |
|---|---|
| Language | Python 3.10+ |
| Application | Command-line interface |
| Concurrency | Python threading |
| Synchronization | `threading.Lock`, `threading.Event` |
| Data model | Dataclasses and Enum |
| Automated testing | `unittest` |
| Dependencies | Python standard library only |

No third-party packages are required.

## Architecture

The application follows a modular architecture with clearly separated responsibilities.

| Module | Responsibility |
|---|---|
| `alarm.py` | Defines the `Alarm` dataclass and `AlarmStatus` enum. Contains alarm data without owning lifecycle transitions. |
| `time_utils.py` | Handles strict time parsing and calculates the next alarm occurrence using an injected datetime. |
| `alarm_manager.py` | Owns in-memory alarm storage, ID generation, lifecycle validation, due-alarm detection, and thread-safe state transitions. |
| `scheduler.py` | Runs the background scheduler thread, detects due alarms, invokes notification callbacks, and handles shutdown. |
| `cli.py` | Implements command parsing, input validation, user-facing messages, and synchronized terminal output. |
| `main.py` | Initializes application components, connects the scheduler callback, starts the application, and guarantees scheduler shutdown. |

### Project Structure

```text
python-alarm-clock/
├── main.py
├── alarm.py
├── alarm_manager.py
├── scheduler.py
├── time_utils.py
├── cli.py
├── README.md
├── requirements.txt
├── .gitignore
└── tests/
    ├── __init__.py
    ├── test_alarm.py
    ├── test_time_utils.py
    ├── test_alarm_manager.py
    └── test_scheduler.py
```

## Alarm Lifecycle

Each alarm follows a controlled lifecycle managed by `AlarmManager`.

```text
                    due
SCHEDULED ──────────────────> RINGING
     │                           │
     │ cancel                    ├── dismiss ──> DISMISSED
     │                           │
     ▼                           └── snooze ───> SCHEDULED
 CANCELLED                                      (5 minutes later)
```

The following transition rules are enforced:

- Only `SCHEDULED` alarms can be cancelled.
- Only `RINGING` alarms can be snoozed or dismissed.
- Snoozing preserves the original alarm ID.
- Snoozing schedules the next occurrence five minutes after the snooze operation.
- Dismissed and cancelled alarms remain in the in-memory list as terminal records.
- An alarm cannot be triggered more than once for the same scheduled occurrence.

## Concurrency and Notification Design

A background scheduler is used to ensure alarms can trigger independently of the interactive CLI.

### Background scheduler

- The scheduler runs in a dedicated background thread.
- It checks for due alarms immediately on startup and then at a configurable polling interval (250 milliseconds by default).
- A `threading.Event` coordinates scheduler shutdown.
- The worker thread is joined during shutdown.

### Thread-safe alarm management

`AlarmManager` protects its internal alarm state and lifecycle transitions using `threading.Lock`.

When an alarm becomes due:

1. The scheduler asks `AlarmManager` to identify due alarms.
2. The manager atomically transitions eligible alarms from `SCHEDULED` to `RINGING`.
3. Alarm notification information is returned to the scheduler.
4. The manager lock is released before notification callbacks execute.
5. The scheduler invokes the notification callback.

This prevents duplicate triggering and avoids executing external callbacks while holding the manager lock.

### Notifications during blocking input

The notification callback writes directly to the terminal from the background scheduler thread.

A shared output lock coordinates application-controlled terminal writes between the CLI and notification callback.

This allows alarm notifications to appear while the main thread is blocked inside `input()`, without requiring the user to press Enter.

**Terminal limitation:** Python's standard `input()` does not provide portable control over terminal line editing or prompt redraw. Notifications are displayed immediately, but partially typed input may not be preserved or redrawn perfectly across all terminals.

## Scheduling Behaviour

Alarms use the machine's local system time.

| Scenario | Behaviour |
|---|---|
| Entered time is later than the current time | Scheduled for today |
| Entered time is earlier than the current time | Scheduled for tomorrow |
| Entered hour and minute match the current hour and minute | Eligible to trigger immediately |
| Alarm is snoozed | Rescheduled five minutes after the snooze operation |

Time calculations use an injected datetime where appropriate, allowing deterministic testing without relying on real-world waiting periods.

## Requirements

- Python 3.10 or later.
- A terminal capable of running a standard Python CLI.
- No third-party packages.

## Installation and Setup

Clone the repository:

```bash
git clone https://github.com/Neha9826/python-alarm-clock.git
cd python-alarm-clock
```

Optionally create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Activate it on macOS or Linux:

```bash
source .venv/bin/activate
```

No dependency installation is necessary because the application uses only the Python standard library.

## Running the Application

From the project root:

```bash
python main.py
```

On systems where the Python executable is named `python3`:

```bash
python3 main.py
```

The application starts an interactive command prompt:

```text
Type 'help' to see available commands.
alarm>
```

## CLI Commands

| Command | Example | Description |
|---|---|---|
| `set HH:MM [label]` | `set 07:30 Morning walk` | Create a one-time alarm. |
| `list` | `list` | Display all alarms and their statuses. |
| `cancel ID` | `cancel 1` | Cancel an alarm that is still scheduled. |
| `snooze ID` | `snooze 1` | Snooze a ringing alarm for five minutes. |
| `dismiss ID` | `dismiss 1` | Dismiss a ringing alarm. |
| `help` | `help` | Display available commands. |
| `exit` | `exit` | Shut down the application. |

Labels can contain spaces.

### Example Session

```text
Type 'help' to see available commands.
alarm> set 07:30 Morning walk
Created alarm #1 for 2026-10-31 07:30 — Morning walk.

alarm> list
ID  Scheduled             Status      Label
--  -------------------   ----------  ----------------
1   2026-10-31 07:30:00   scheduled   Morning walk

alarm> cancel 1
Alarm #1 cancelled.

alarm> list
ID  Scheduled             Status      Label
--  -------------------   ----------  ----------------
1   2026-10-31 07:30:00   cancelled   Morning walk

alarm> exit
Goodbye.
```

When an alarm becomes due, the terminal bell is emitted once for that ringing occurrence, and a notification message is displayed with instructions to snooze or dismiss it.

## Automated Testing

The project uses Python's built-in `unittest` framework.

Run the complete test suite from the project root:

```bash
python -m unittest discover -s tests -v
```

Alternatively:

```bash
python3 -m unittest discover -s tests -v
```

### Test Coverage

The automated test suite covers:

**Alarm model**
- Default values and lifecycle status.
- Custom labels and scheduled datetime.
- Lifecycle enum values.

**Time utilities**
- Valid and invalid 24-hour time input.
- Empty and malformed input.
- Future and past alarm scheduling.
- Exact-current-time scheduling.
- Midnight rollover.
- Timezone information preservation.

**Alarm manager**
- Multiple alarms and unique IDs.
- Alarm listing and state snapshots.
- Cancellation and lifecycle validation.
- Snoozing and dismissing.
- ID preservation after snoozing.
- Duplicate-trigger prevention.
- Concurrent state transitions and cancellation races.

**Scheduler**
- Background execution and immediate notifications.
- Notification delivery while CLI input is blocked.
- Callback execution outside the manager lock.
- Duplicate worker and notification prevention.
- Graceful worker shutdown.

### Verification

The complete test suite was executed locally.

```text
----------------------------------------------------------------------
Ran 39 tests in 0.048s

OK
```

Python compilation was also verified successfully using:

```bash
python -m compileall -q .
```

## Design Decisions and Trade-offs

- **One-time alarms:** Recurring alarms are outside the current scope.
- **In-memory storage:** Avoids database and persistence complexity. Alarm state is lost when the application exits.
- **Local system time:** Keeps scheduling straightforward without exposing timezone configuration through the CLI.
- **Background polling:** A 250 ms polling interval provides a simple and understandable scheduling mechanism for this application.
- **Atomic state transitions:** Centralizing lifecycle management in `AlarmManager` prevents competing operations from creating inconsistent states.
- **Callbacks outside locks:** Prevents notification handling from unnecessarily holding the manager's synchronization lock.
- **Standard-library implementation:** Avoids external dependencies and keeps setup minimal.
- **Deterministic testing:** Injected time values and synchronization primitives reduce dependence on real-time delays.

The polling approach introduces a small trigger delay. It is not intended to provide real-time scheduling guarantees.

## Known Limitations

- Alarms are not persisted between application sessions.
- Only one-time alarms are supported.
- Scheduling follows the host machine's local system clock.
- Manual system clock changes and daylight-saving transitions are subject to the platform's local datetime behaviour.
- The terminal bell may be disabled or ignored by the terminal or operating system.
- Partially typed input may not redraw perfectly after a background notification.
- The scheduler polling interval introduces a small delay before an alarm is detected.

## Future Improvements

Potential extensions include:

- Persistent alarm storage.
- Recurring alarms.
- Configurable snooze durations.
- Improved terminal input handling.
- Configurable scheduler polling intervals.
- Additional integration testing across operating systems.

These improvements are intentionally outside the current implementation scope.

## Author

**Neha Pattnayak**

GitHub: [github.com/Neha9826](https://github.com/Neha9826)

---

*Built as a Python CLI engineering assessment project, with an emphasis on modular design, concurrency safety, deterministic testing, and practical engineering trade-offs.*