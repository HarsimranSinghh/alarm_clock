Multi-Alarm CLI (v2)

A small command-line alarm clock written in Python. Set several alarms, use quick timers like +25m, edit or delete them, snooze when they ring, and get a message plus a sound when they go off.

No dependencies, no website, no database. Python 3.8+ and the standard library only.

Quick start
python alarm.py

Then type commands at the > prompt:

> add 07:30 Wake up
Set for Fri 07:30:00 (in 6h 42m): Wake up
> add +25m Tea
Set for Thu 14:30:12 (in 25m 0s): Tea
> list
1) 14:30:12 "Tea" (in 24m 51s)
2) 07:30:00 "Wake up" (in 6h 42m)
> edit 1 +10m Tea is ready
> delete 2
> quit
Commands
Command	Description
add TIME [label]	Add an alarm. TIME can be absolute or relative (see below). Label is optional.
list	Show all alarms, sorted by time, with a countdown.
edit N TIME [label]	Change alarm N's time. The label is kept unless you give a new one.
delete N	Remove alarm number N as shown by list.
snooze [minutes]	Re-arm the alarm(s) that just rang. Default is 5 minutes.
help	Show the command list.
quit / exit	Exit. Ctrl+C also works.
Time formats
Format	Example	Meaning
HH:MM	07:30	24-hour clock time
HH:MM:SS	14:05:30	Same, with seconds (handy for testing)
+Xh, +Xm, +Xs (combinable)	+25m, +1h30m, +90s	That long from now

Units must be in the order hours, minutes, seconds (+1h30m works, +30m1h does not). 12-hour AM/PM is not supported.

How it behaves
Time already passed today: an absolute time such as 07:30 is set for tomorrow. Relative times always count forward from now.
Ringing: each due alarm prints *** ALARM HH:MM:SS - label ***, then a sound plays 5 times. Fired alarms are removed from the list.
Snooze: type snooze (or snooze 10) after an alarm rings. It re-adds the alarm(s) from the most recent ring, with the same labels, that many minutes from now. It only applies to the latest ring, and only once per ring.
Same-second alarms: if two alarms are due at once, both are announced together and snoozed together.
Storage: alarms live in memory only and are lost when you quit.
Sound
Platform	Sound
macOS	afplay with the system Glass sound
Windows	winsound.Beep (1000 Hz, 0.5 s)
Linux / other	Terminal bell (\a)

If the platform sound fails (for example afplay is missing), it falls back to the terminal bell. The bell depends on your terminal settings and can be quiet or silent.

Tests
python -m unittest test_alarm -v

The suite has 50 tests covering time parsing (absolute and relative), the tomorrow rollover, add/list/edit/delete/snooze, the background checker, ringing, and the sound selection per platform. The clock is frozen during tests, so results don't depend on the time of day, and the suite runs in milliseconds. pytest test_alarm.py also works if you have pytest installed.

Project layout
alarm.py        # the app
test_alarm.py   # unit tests
README.md       # this file
How it works
Alarms are stored in a plain list of dicts: {"time": datetime, "label": str}.
A background daemon thread checks the list every second and fires any alarm whose time has arrived. It records what fired so snooze can re-arm it.
A threading.Lock protects the lists so commands at the prompt can't clash with the checker.
The main thread runs the command prompt.
Known limitations
Alarms are not saved between runs.
No recurring or weekday alarms.
A ring message can print in the middle of text you are typing.
While an alarm is ringing (about 5 seconds), the checker is paused, so another alarm due in that window fires a few seconds late.
The list numbering can shift if an alarm fires between running list and delete/edit, so re-run list if unsure.
The sound playback is not covered by automated tests on real hardware, so check it on your own OS.
Ideas for next steps
Save and load alarms from a JSON file
Recurring alarms (--repeat weekdays)
Enable/disable alarms without deleting them
12-hour AM/PM input
