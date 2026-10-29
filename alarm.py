#!/usr/bin/env python3
"""Multi-alarm command-line clock (v2).

Commands:
  add TIME [label]     TIME is HH:MM, HH:MM:SS (24-hour) or relative: +25m, +1h30m, +90s
                       e.g.  add 07:30 Wake up     add +25m Tea
  list                 show alarms with countdowns
  edit N TIME [label]  change alarm N's time (and label, if given)
  delete N             remove alarm number N (as shown by list)
  snooze [minutes]     re-arm the alarm(s) that just rang (default 5 minutes)
  help                 show commands
  quit                 exit
"""
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta

MAC_SOUND = "/System/Library/Sounds/Glass.aiff"
RELATIVE_RE = re.compile(r"^\+(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$")
TIME_ERROR = "Use HH:MM or HH:MM:SS (24-hour), or a relative time like +25m or +1h30m."

alarms = []      # list of {"time": datetime, "label": str}
last_fired = []  # alarms from the most recent ring, used by snooze
lock = threading.Lock()


def parse_time(text):
    """Parse an absolute (HH:MM[:SS]) or relative (+1h30m) time into a datetime."""
    now = datetime.now()

    match = RELATIVE_RE.match(text)
    if match and any(g is not None for g in match.groups()):
        hours, minutes, seconds = (int(g or 0) for g in match.groups())
        delta = timedelta(hours=hours, minutes=minutes, seconds=seconds)
        if delta.total_seconds() <= 0:
            raise ValueError("Duration must be greater than zero.")
        return (now + delta).replace(microsecond=0)

    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            parsed = datetime.strptime(text, fmt)
            break
        except ValueError:
            continue
    else:
        raise ValueError(TIME_ERROR)

    target = now.replace(hour=parsed.hour, minute=parsed.minute,
                         second=parsed.second, microsecond=0)
    if target <= now:  # already passed today -> tomorrow
        target += timedelta(days=1)
    return target


def format_delta(delta):
    total = max(int(delta.total_seconds()), 0)
    hours, rest = divmod(total, 3600)
    minutes, seconds = divmod(rest, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def play_sound():
    """Play one alert sound: afplay on macOS, winsound on Windows, else the bell."""
    try:
        if sys.platform == "darwin":
            subprocess.run(["afplay", MAC_SOUND], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        if sys.platform == "win32":
            import winsound
            winsound.Beep(1000, 500)
            return
    except Exception:
        pass  # fall back to the terminal bell below
    print("\a", end="", flush=True)


def ring(due):
    """Announce every due alarm, then play the sound."""
    print()
    for item in due:
        print(f"*** ALARM {item['time']:%H:%M:%S} - {item['label']} ***")
    print("(type 'snooze' to be reminded again)")
    for _ in range(5):
        play_sound()
        time.sleep(1)


def checker():
    """Background thread: fire any alarm whose time has arrived."""
    while True:
        now = datetime.now()
        with lock:
            due = [a for a in alarms if a["time"] <= now]
            for a in due:
                alarms.remove(a)
            if due:
                last_fired[:] = due
        if due:  # ring outside the lock so the prompt stays usable
            ring(due)
        time.sleep(1)


def cmd_add(args):
    if not args:
        print("Usage: add TIME [label]   (e.g. add 07:30 Wake up, add +25m Tea)")
        return
    try:
        when = parse_time(args[0])
    except ValueError as err:
        print(err)
        return
    label = " ".join(args[1:]) or "Alarm"
    with lock:
        alarms.append({"time": when, "label": label})
        alarms.sort(key=lambda a: a["time"])
    print(f"Set for {when:%a %H:%M:%S} (in {format_delta(when - datetime.now())}): {label}")


def cmd_list():
    with lock:
        if not alarms:
            print("No alarms set.")
            return
        now = datetime.now()
        for i, a in enumerate(alarms, 1):
            print(f"{i}) {a['time']:%H:%M:%S} \"{a['label']}\" (in {format_delta(a['time'] - now)})")


def cmd_delete(args):
    if not args or not args[0].isdigit():
        print("Usage: delete N  (use 'list' to see numbers)")
        return
    n = int(args[0])
    with lock:
        if not 1 <= n <= len(alarms):
            print(f"No alarm #{n}.")
            return
        removed = alarms.pop(n - 1)
    print(f"Deleted {removed['time']:%H:%M:%S} \"{removed['label']}\".")


def cmd_edit(args):
    if len(args) < 2 or not args[0].isdigit():
        print("Usage: edit N TIME [label]  (use 'list' to see numbers)")
        return
    n = int(args[0])
    try:
        when = parse_time(args[1])
    except ValueError as err:
        print(err)
        return
    new_label = " ".join(args[2:])
    with lock:
        if not 1 <= n <= len(alarms):
            print(f"No alarm #{n}.")
            return
        item = alarms[n - 1]
        item["time"] = when
        if new_label:
            item["label"] = new_label
        label = item["label"]
        alarms.sort(key=lambda a: a["time"])
    print(f"Updated: {when:%a %H:%M:%S} (in {format_delta(when - datetime.now())}) \"{label}\"")


def cmd_snooze(args):
    minutes = 5
    if args:
        if not args[0].isdigit() or int(args[0]) < 1:
            print("Usage: snooze [minutes]")
            return
        minutes = int(args[0])
    with lock:
        if not last_fired:
            print("Nothing to snooze.")
            return
        when = (datetime.now() + timedelta(minutes=minutes)).replace(microsecond=0)
        count = len(last_fired)
        for item in last_fired:
            alarms.append({"time": when, "label": item["label"]})
        last_fired.clear()
        alarms.sort(key=lambda a: a["time"])
    noun = "alarm" if count == 1 else "alarms"
    print(f"Snoozed {count} {noun} for {minutes} min (until {when:%H:%M:%S}).")


def main():
    threading.Thread(target=checker, daemon=True).start()
    print(__doc__)
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break
        if not line:
            continue
        cmd, *args = line.split()
        cmd = cmd.lower()
        if cmd == "add":
            cmd_add(args)
        elif cmd == "list":
            cmd_list()
        elif cmd == "edit":
            cmd_edit(args)
        elif cmd == "delete":
            cmd_delete(args)
        elif cmd == "snooze":
            cmd_snooze(args)
        elif cmd == "help":
            print(__doc__)
        elif cmd in ("quit", "exit"):
            print("Bye.")
            break
        else:
            print("Unknown command. Type 'help'.")


if __name__ == "__main__":
    main()
