Multi-Alarm CLI

A small command-line alarm clock written in Python. Set several alarms, list them with countdowns, delete the ones you don't need, and get a message plus a terminal beep when they go off.

No dependencies, no website, no database. Python 3.8+ and the standard library only.

Quick start
python alarm.py

Then type commands at the > prompt:

> add 07:30 Wake up
Set for Fri 07:30:00 (in 6h 42m): Wake up
> add 13:15 Take pizza out
> list
1) 07:30:00 "Wake up" (in 6h 42m)
2) 13:15:00 "Take pizza out" (in 12h 27m)
> delete 2
Deleted 13:15:00 "Take pizza out".
> quit
Commands
Command	Description
add HH:MM [label]	Add an alarm (24-hour time). Label is optional.
add HH:MM:SS [label]	Same, with seconds. Handy for quick testing.
list	Show all alarms, sorted by time, with a countdown.
delete N	Remove alarm number N as shown by list.
help	Show the command list.
quit / exit	Exit. Ctrl+C also works.
How it behaves
Time format: 24-hour only (07:30, 18:45). 12-hour AM/PM is not supported.
Time already passed today: the alarm is set for the same time tomorrow.
Same-second alarms: if two alarms are due at once, both are announced together.
Ringing: each due alarm prints *** ALARM HH:MM:SS - label ***, then the terminal bell sounds 5 times. Fired alarms are removed from the list.
Storage: alarms live in memory only and are lost when you quit.
Try it quickly

Set an alarm a few seconds ahead instead of waiting for a real time. If it is currently 14:05:00:

> add 14:05:10 Test
Sound

The alarm uses the terminal bell (\a), which depends on your terminal settings and can be silent or quiet. If you can't hear it, add a platform sound inside ring() in alarm.py:

macOS: os.system("afplay /System/Library/Sounds/Glass.aiff") (add import os)
Windows: winsound.Beep(1000, 500) (add import winsound)
Tests
python -m unittest test_alarm -v

The suite has 25 tests covering time parsing, the tomorrow rollover, add/list/delete, the background checker, and ringing. The clock is frozen during tests, so results don't depend on the time of day, and the suite runs in milliseconds. pytest test_alarm.py also works if you have pytest installed.

Project layout
alarm.py        # the app
test_alarm.py   # unit tests
README.md       # this file
How it works
Alarms are stored in a plain list of dicts: {"time": datetime, "label": str}.
A background daemon thread checks the list every second and fires any alarm whose time has arrived.
A threading.Lock protects the list so adding or deleting at the prompt can't clash with the checker.
The main thread runs the command prompt.
Known limitations
Alarms are not saved between runs.
No recurring or weekday alarms, snooze, or custom sound files.
A ring message can print in the middle of text you are typing.
While an alarm is ringing (about 5 seconds), the checker is paused, so another alarm due in that window fires a few seconds late.
The list numbering can shift if an alarm fires between running list and delete, so re-run list if unsure.
Ideas for next steps
Snooze (press Enter to repeat in 5 minutes)
Relative alarms such as add +25m
Saving alarms to a JSON file
Recurring alarms