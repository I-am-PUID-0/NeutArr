import datetime
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_support import configure_test_environment

configure_test_environment()

from src.primary import scheduler_engine


class SchedulerTimingTests(unittest.TestCase):
    def setUp(self):
        scheduler_engine.last_executed_actions.clear()

    def tearDown(self):
        scheduler_engine.last_executed_actions.clear()

    @staticmethod
    def schedule(hour=12, minute=0, days=None, enabled=True):
        return {
            "id": "timing-test",
            "time": {"hour": hour, "minute": minute},
            "days": [] if days is None else days,
            "action": "disable",
            "app": "sonarr-all",
            "enabled": enabled,
        }

    def test_schedule_runs_at_its_exact_time(self):
        current_time = datetime.datetime(2026, 7, 28, 12, 0, 0)

        self.assertTrue(
            scheduler_engine.should_execute_schedule(
                self.schedule(days=["tuesday"]),
                current_time=current_time,
            )
        )

    def test_schedule_runs_until_end_of_four_minute_window(self):
        current_time = datetime.datetime(2026, 7, 28, 12, 3, 59)

        self.assertTrue(
            scheduler_engine.should_execute_schedule(
                self.schedule(days=["tuesday"]),
                current_time=current_time,
            )
        )

    def test_schedule_stops_at_four_minutes(self):
        current_time = datetime.datetime(2026, 7, 28, 12, 4, 0)

        self.assertFalse(
            scheduler_engine.should_execute_schedule(
                self.schedule(days=["tuesday"]),
                current_time=current_time,
            )
        )

    def test_schedule_window_crosses_an_hour(self):
        current_time = datetime.datetime(2026, 7, 28, 7, 2, 59)

        self.assertTrue(
            scheduler_engine.should_execute_schedule(
                self.schedule(hour=6, minute=59, days=["tuesday"]),
                current_time=current_time,
            )
        )

    def test_schedule_window_crosses_midnight_using_scheduled_weekday(self):
        current_time = datetime.datetime(2026, 7, 28, 0, 1, 30)
        schedule = self.schedule(hour=23, minute=59, days=["monday"])

        self.assertTrue(
            scheduler_engine.should_execute_schedule(
                schedule,
                current_time=current_time,
            )
        )
        self.assertEqual(schedule["_scheduled_for"], datetime.datetime(2026, 7, 27, 23, 59))

    def test_midnight_rollover_does_not_use_the_new_weekday(self):
        current_time = datetime.datetime(2026, 7, 28, 0, 1, 30)

        self.assertFalse(
            scheduler_engine.should_execute_schedule(
                self.schedule(hour=23, minute=59, days=["tuesday"]),
                current_time=current_time,
            )
        )

    def test_schedule_does_not_run_before_its_time(self):
        current_time = datetime.datetime(2026, 7, 28, 11, 59, 59)

        self.assertFalse(
            scheduler_engine.should_execute_schedule(
                self.schedule(days=["tuesday"]),
                current_time=current_time,
            )
        )

    def test_disabled_schedule_does_not_run(self):
        current_time = datetime.datetime(2026, 7, 28, 12, 0, 0)

        self.assertFalse(
            scheduler_engine.should_execute_schedule(
                self.schedule(days=["tuesday"], enabled=False),
                current_time=current_time,
            )
        )

    def test_execution_tracking_uses_occurrence_date_after_midnight(self):
        action = self.schedule(hour=23, minute=59)
        monday_occurrence = datetime.datetime(2026, 7, 27, 23, 59)
        tuesday_occurrence = datetime.datetime(2026, 7, 28, 23, 59)

        with patch.object(scheduler_engine, "_update_scheduled_app_settings", return_value=True):
            self.assertTrue(scheduler_engine.execute_action(action, scheduled_for=monday_occurrence))
            self.assertTrue(scheduler_engine.execute_action(action, scheduled_for=tuesday_occurrence))

        self.assertIn("timing-test_2026-07-27", scheduler_engine.last_executed_actions)
        self.assertIn("timing-test_2026-07-28", scheduler_engine.last_executed_actions)


if __name__ == "__main__":
    unittest.main()
