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
        patcher = mock.patch.object(alarm, "datetime", FakeDatetime)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(alarm.alarms.clear)
 
 
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
    def test_ring_prints_each_label_and_beeps(self):
        due = [
            {"time": FIXED_NOW, "label": "one"},
            {"time": FIXED_NOW, "label": "two"},
        ]
        with mock.patch.object(alarm.time, "sleep"):
            out = run(alarm.ring, due)
        self.assertIn("one", out)
        self.assertIn("two", out)
        self.assertEqual(out.count("\a"), 5)
 
 
if __name__ == "__main__":
    unittest.main()