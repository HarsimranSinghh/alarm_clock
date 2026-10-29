"""Tests for alarm.py. Run with:  python -m unittest test_alarm -v
(also works with pytest)."""
import io
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from unittest import mock

import alarm

FIXED_NOW = datetime(2026, 1, 15, 12, 0, 0)  # Thursday, noon


class FakeDatetime(datetime):
    """datetime whose now() is frozen, so tests don't depend on the clock."""

    @classmethod
    def now(cls, tz=None):
        return FIXED_NOW


class StopLoop(Exception):
    """Raised from a patched time.sleep to break out of checker()'s loop."""


def run(func, *args):
    """Call func and return everything it printed."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        func(*args)
    return buf.getvalue()


class AlarmTestCase(unittest.TestCase):
    def setUp(self):
        alarm.alarms.clear()
        alarm.last_fired.clear()
        patcher = mock.patch.object(alarm, "datetime", FakeDatetime)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(alarm.alarms.clear)
        self.addCleanup(alarm.last_fired.clear)


class TestParseTime(AlarmTestCase):
    def test_future_time_is_today(self):
        self.assertEqual(alarm.parse_time("13:30"), datetime(2026, 1, 15, 13, 30, 0))

    def test_past_time_rolls_to_tomorrow(self):
        self.assertEqual(alarm.parse_time("07:30"), datetime(2026, 1, 16, 7, 30, 0))

    def test_exact_current_time_rolls_to_tomorrow(self):
        self.assertEqual(alarm.parse_time("12:00"), datetime(2026, 1, 16, 12, 0, 0))

    def test_seconds_format(self):
        self.assertEqual(alarm.parse_time("12:00:30"), datetime(2026, 1, 15, 12, 0, 30))

    def test_midnight(self):
        self.assertEqual(alarm.parse_time("00:00"), datetime(2026, 1, 16, 0, 0, 0))

    def test_invalid_inputs(self):
        for bad in ["99:99", "25:00", "7pm", "abc", "", "12", "12:60"]:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    alarm.parse_time(bad)


class TestFormatDelta(unittest.TestCase):
    def test_seconds_only(self):
        self.assertEqual(alarm.format_delta(timedelta(seconds=45)), "45s")

    def test_minutes_and_seconds(self):
        self.assertEqual(alarm.format_delta(timedelta(minutes=5, seconds=10)), "5m 10s")

    def test_hours_and_minutes(self):
        self.assertEqual(alarm.format_delta(timedelta(hours=6, minutes=42, seconds=59)), "6h 42m")

    def test_negative_clamped_to_zero(self):
        self.assertEqual(alarm.format_delta(timedelta(seconds=-5)), "0s")


class TestAdd(AlarmTestCase):
    def test_add_with_label(self):
        out = run(alarm.cmd_add, ["13:00", "Take", "pizza", "out"])
        self.assertEqual(len(alarm.alarms), 1)
        self.assertEqual(alarm.alarms[0]["label"], "Take pizza out")
        self.assertIn("Take pizza out", out)

    def test_add_default_label(self):
        run(alarm.cmd_add, ["13:00"])
        self.assertEqual(alarm.alarms[0]["label"], "Alarm")

    def test_add_without_args_prints_usage(self):
        out = run(alarm.cmd_add, [])
        self.assertIn("Usage", out)
        self.assertEqual(alarm.alarms, [])

    def test_add_bad_time_not_stored(self):
        out = run(alarm.cmd_add, ["99:99"])
        self.assertIn("HH:MM", out)
        self.assertEqual(alarm.alarms, [])

    def test_alarms_kept_sorted(self):
        run(alarm.cmd_add, ["15:00", "late"])
        run(alarm.cmd_add, ["13:00", "early"])
        run(alarm.cmd_add, ["14:00", "middle"])
        self.assertEqual([a["label"] for a in alarm.alarms], ["early", "middle", "late"])


class TestList(AlarmTestCase):
    def test_empty(self):
        self.assertIn("No alarms", run(alarm.cmd_list))

    def test_numbered_with_countdown(self):
        run(alarm.cmd_add, ["13:00", "A"])
        run(alarm.cmd_add, ["14:30", "B"])
        out = run(alarm.cmd_list)
        self.assertIn('1) 13:00:00 "A" (in 1h 0m)', out)
        self.assertIn('2) 14:30:00 "B" (in 2h 30m)', out)


class TestDelete(AlarmTestCase):
    def setUp(self):
        super().setUp()
        run(alarm.cmd_add, ["13:00", "A"])
        run(alarm.cmd_add, ["14:00", "B"])
        run(alarm.cmd_add, ["15:00", "C"])

    def test_delete_middle(self):
        out = run(alarm.cmd_delete, ["2"])
        self.assertIn("Deleted", out)
        self.assertEqual([a["label"] for a in alarm.alarms], ["A", "C"])

    def test_delete_out_of_range(self):
        for n in ["0", "4", "99"]:
            with self.subTest(n=n):
                self.assertIn("No alarm", run(alarm.cmd_delete, [n]))
        self.assertEqual(len(alarm.alarms), 3)

    def test_delete_non_number_or_missing(self):
        for args in ([], ["abc"], ["-1"]):
            with self.subTest(args=args):
                self.assertIn("Usage", run(alarm.cmd_delete, args))
        self.assertEqual(len(alarm.alarms), 3)


class TestChecker(AlarmTestCase):
    def run_one_tick(self):
        """Run checker() for exactly one loop iteration; return ring() mock."""
        with mock.patch.object(alarm, "ring") as fake_ring, \
                mock.patch.object(alarm.time, "sleep", side_effect=StopLoop):
            with self.assertRaises(StopLoop):
                alarm.checker()
        return fake_ring

    def test_due_alarm_fires_and_is_removed(self):
        alarm.alarms.append({"time": FIXED_NOW - timedelta(seconds=1), "label": "due"})
        fake_ring = self.run_one_tick()
        fake_ring.assert_called_once()
        self.assertEqual(alarm.alarms, [])

    def test_future_alarm_does_not_fire(self):
        alarm.alarms.append({"time": FIXED_NOW + timedelta(minutes=5), "label": "later"})
        fake_ring = self.run_one_tick()
        fake_ring.assert_not_called()
        self.assertEqual(len(alarm.alarms), 1)

    def test_two_alarms_same_second_both_fire(self):
        alarm.alarms.append({"time": FIXED_NOW, "label": "one"})
        alarm.alarms.append({"time": FIXED_NOW, "label": "two"})
        fake_ring = self.run_one_tick()
        fake_ring.assert_called_once()
        due = fake_ring.call_args[0][0]
        self.assertEqual({a["label"] for a in due}, {"one", "two"})
        self.assertEqual(alarm.alarms, [])

    def test_only_due_alarms_removed(self):
        alarm.alarms.append({"time": FIXED_NOW - timedelta(seconds=1), "label": "due"})
        alarm.alarms.append({"time": FIXED_NOW + timedelta(hours=1), "label": "later"})
        self.run_one_tick()
        self.assertEqual([a["label"] for a in alarm.alarms], ["later"])


class TestRing(unittest.TestCase):
    def test_ring_prints_each_label_and_plays_sound_five_times(self):
        due = [
            {"time": FIXED_NOW, "label": "one"},
            {"time": FIXED_NOW, "label": "two"},
        ]
        with mock.patch.object(alarm.time, "sleep"), \
                mock.patch.object(alarm, "play_sound") as fake_sound:
            out = run(alarm.ring, due)
        self.assertIn("one", out)
        self.assertIn("two", out)
        self.assertIn("snooze", out)
        self.assertEqual(fake_sound.call_count, 5)


class TestPlaySound(unittest.TestCase):
    def test_other_platforms_use_terminal_bell(self):
        with mock.patch.object(alarm.sys, "platform", "linux"):
            self.assertEqual(run(alarm.play_sound), "\a")

    def test_macos_uses_afplay(self):
        with mock.patch.object(alarm.sys, "platform", "darwin"), \
                mock.patch.object(alarm.subprocess, "run") as fake_run:
            out = run(alarm.play_sound)
        self.assertEqual(fake_run.call_args[0][0], ["afplay", alarm.MAC_SOUND])
        self.assertEqual(out, "")  # no bell when afplay works

    def test_macos_falls_back_to_bell_if_afplay_fails(self):
        with mock.patch.object(alarm.sys, "platform", "darwin"), \
                mock.patch.object(alarm.subprocess, "run", side_effect=FileNotFoundError):
            self.assertEqual(run(alarm.play_sound), "\a")

    def test_windows_uses_winsound(self):
        fake_winsound = mock.Mock()
        with mock.patch.object(alarm.sys, "platform", "win32"), \
                mock.patch.dict("sys.modules", {"winsound": fake_winsound}):
            out = run(alarm.play_sound)
        fake_winsound.Beep.assert_called_once_with(1000, 500)
        self.assertEqual(out, "")


class TestRelativeTime(AlarmTestCase):
    def test_minutes(self):
        self.assertEqual(alarm.parse_time("+25m"), datetime(2026, 1, 15, 12, 25, 0))

    def test_hours_and_minutes(self):
        self.assertEqual(alarm.parse_time("+1h30m"), datetime(2026, 1, 15, 13, 30, 0))

    def test_seconds(self):
        self.assertEqual(alarm.parse_time("+90s"), datetime(2026, 1, 15, 12, 1, 30))

    def test_hours_only(self):
        self.assertEqual(alarm.parse_time("+2h"), datetime(2026, 1, 15, 14, 0, 0))

    def test_crosses_midnight(self):
        self.assertEqual(alarm.parse_time("+13h"), datetime(2026, 1, 16, 1, 0, 0))

    def test_invalid_relative(self):
        for bad in ["+", "+m", "+5x", "+1m1h", "+-5m", "5m"]:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    alarm.parse_time(bad)

    def test_zero_duration_rejected(self):
        for bad in ["+0m", "+0s", "+0h0m"]:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    alarm.parse_time(bad)

    def test_add_with_relative_time(self):
        out = run(alarm.cmd_add, ["+25m", "Tea"])
        self.assertEqual(alarm.alarms[0]["time"], datetime(2026, 1, 15, 12, 25, 0))
        self.assertEqual(alarm.alarms[0]["label"], "Tea")
        self.assertIn("in 25m 0s", out)


class TestEdit(AlarmTestCase):
    def setUp(self):
        super().setUp()
        run(alarm.cmd_add, ["13:00", "A"])
        run(alarm.cmd_add, ["14:00", "B"])

    def test_edit_time_keeps_label(self):
        out = run(alarm.cmd_edit, ["1", "15:00"])
        self.assertIn("Updated", out)
        self.assertEqual(alarm.alarms[1]["time"], datetime(2026, 1, 15, 15, 0, 0))
        self.assertEqual(alarm.alarms[1]["label"], "A")

    def test_edit_time_and_label(self):
        run(alarm.cmd_edit, ["2", "+10m", "New", "label"])
        self.assertEqual(alarm.alarms[0]["time"], datetime(2026, 1, 15, 12, 10, 0))
        self.assertEqual(alarm.alarms[0]["label"], "New label")

    def test_edit_resorts_list(self):
        run(alarm.cmd_edit, ["1", "16:00"])
        self.assertEqual([a["label"] for a in alarm.alarms], ["B", "A"])

    def test_edit_bad_number(self):
        for n in ["0", "3", "99"]:
            with self.subTest(n=n):
                self.assertIn("No alarm", run(alarm.cmd_edit, [n, "15:00"]))

    def test_edit_bad_time_changes_nothing(self):
        out = run(alarm.cmd_edit, ["1", "99:99"])
        self.assertIn("HH:MM", out)
        self.assertEqual(alarm.alarms[0]["time"], datetime(2026, 1, 15, 13, 0, 0))

    def test_edit_usage(self):
        for args in ([], ["1"], ["abc", "15:00"]):
            with self.subTest(args=args):
                self.assertIn("Usage", run(alarm.cmd_edit, args))


class TestSnooze(AlarmTestCase):
    def test_nothing_to_snooze(self):
        self.assertIn("Nothing to snooze", run(alarm.cmd_snooze, []))
        self.assertEqual(alarm.alarms, [])

    def test_snooze_rearms_with_default_five_minutes(self):
        alarm.last_fired.append({"time": FIXED_NOW, "label": "Wake up"})
        out = run(alarm.cmd_snooze, [])
        self.assertIn("Snoozed 1 alarm for 5 min", out)
        self.assertEqual(alarm.alarms, [{"time": datetime(2026, 1, 15, 12, 5, 0), "label": "Wake up"}])
        self.assertEqual(alarm.last_fired, [])

    def test_snooze_custom_minutes(self):
        alarm.last_fired.append({"time": FIXED_NOW, "label": "X"})
        run(alarm.cmd_snooze, ["10"])
        self.assertEqual(alarm.alarms[0]["time"], datetime(2026, 1, 15, 12, 10, 0))

    def test_snooze_multiple_alarms(self):
        alarm.last_fired.extend([
            {"time": FIXED_NOW, "label": "one"},
            {"time": FIXED_NOW, "label": "two"},
        ])
        out = run(alarm.cmd_snooze, [])
        self.assertIn("Snoozed 2 alarms", out)
        self.assertEqual({a["label"] for a in alarm.alarms}, {"one", "two"})

    def test_cannot_snooze_twice_for_one_ring(self):
        alarm.last_fired.append({"time": FIXED_NOW, "label": "X"})
        run(alarm.cmd_snooze, [])
        self.assertIn("Nothing to snooze", run(alarm.cmd_snooze, []))
        self.assertEqual(len(alarm.alarms), 1)

    def test_invalid_minutes(self):
        alarm.last_fired.append({"time": FIXED_NOW, "label": "X"})
        for bad in ["0", "abc", "-5"]:
            with self.subTest(bad=bad):
                self.assertIn("Usage", run(alarm.cmd_snooze, [bad]))
        self.assertEqual(alarm.alarms, [])
        self.assertEqual(len(alarm.last_fired), 1)

    def test_checker_records_fired_alarms_for_snooze(self):
        alarm.alarms.append({"time": FIXED_NOW - timedelta(seconds=1), "label": "due"})
        with mock.patch.object(alarm, "ring"), \
                mock.patch.object(alarm.time, "sleep", side_effect=StopLoop):
            with self.assertRaises(StopLoop):
                alarm.checker()
        run(alarm.cmd_snooze, [])
        self.assertEqual([a["label"] for a in alarm.alarms], ["due"])
        self.assertEqual(alarm.alarms[0]["time"], datetime(2026, 1, 15, 12, 5, 0))


if __name__ == "__main__":
    unittest.main()
