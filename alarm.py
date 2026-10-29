#!/usr/bin/env python3
"""Multi-alarm command-line clock.
 
Commands:
  add HH:MM [label]      e.g.  add 07:30 Wake up
  add HH:MM:SS [label]   e.g.  add 14:05:30   (handy for quick tests)
  list                   show alarms with countdowns
  delete N               remove alarm number N (as shown by list)
  help                   show commands
  quit                   exit
"""
import threading
import time
from datetime import datetime, timedelta
 
alarms = []  # list of {"time": datetime, "label": str}
lock = threading.Lock()
 
 
def parse_time(text):
    """Parse HH:MM or HH:MM:SS (24-hour) into the next matching datetime."""
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            parsed = datetime.strptime(text, fmt)
            break
        except ValueError:
            continue
    else:
        raise ValueError("Time must be HH:MM or HH:MM:SS in 24-hour format.")
 
    now = datetime.now()
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
 
 
def ring(due):
    """Announce every due alarm, then beep."""
    print()
    for alarm in due:
        print(f"*** ALARM {alarm['time']:%H:%M:%S} - {alarm['label']} ***")
    for _ in range(5):
        print("\a", end="", flush=True)
        time.sleep(1)
 
 
def checker():
    """Background thread: fire any alarm whose time has arrived."""
    while True:
        now = datetime.now()
        with lock:
            due = [a for a in alarms if a["time"] <= now]
            for a in due:
                alarms.remove(a)
        if due:  # ring outside the lock so the prompt stays usable
            ring(due)
        time.sleep(1)
 
 
def cmd_add(args):
    if not args:
        print("Usage: add HH:MM [label]")
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
        elif cmd == "delete":
            cmd_delete(args)
        elif cmd == "help":
            print(__doc__)
        elif cmd in ("quit", "exit"):
            print("Bye.")
            break
        else:
            print("Unknown command. Type 'help'.")
 
 
if __name__ == "__main__":
    main()