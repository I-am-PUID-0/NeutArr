import json
import stat
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_support import configure_test_environment

configure_test_environment()

from src.primary import scheduler_engine
from src.primary.routes.scheduler_routes import save_schedules
from src.primary.web_server import app


class SchedulerPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.schedule_file = Path(self.temp_directory.name) / "scheduler" / "schedule.json"
        self.file_patch = patch.object(scheduler_engine, "SCHEDULE_FILE", str(self.schedule_file))
        self.file_patch.start()

    def tearDown(self):
        self.file_patch.stop()
        self.temp_directory.cleanup()

    @staticmethod
    def schedule(schedule_id="schedule-1", **overrides):
        schedule = {
            "id": schedule_id,
            "time": {"hour": 12, "minute": 30},
            "days": ["monday", "friday"],
            "action": "disable",
            "app": "sonarr-all",
            "enabled": True,
        }
        schedule.update(overrides)
        return schedule

    def write_existing(self, data):
        self.schedule_file.parent.mkdir(parents=True, exist_ok=True)
        self.schedule_file.write_text(json.dumps(data), encoding="utf-8")

    def read_persisted(self):
        return json.loads(self.schedule_file.read_text(encoding="utf-8"))

    def test_successful_save_atomically_replaces_file_and_preserves_mode(self):
        self.write_existing({"global": []})
        self.schedule_file.chmod(0o640)

        normalized = scheduler_engine.save_schedule({"sonarr": [self.schedule()]})

        self.assertEqual(self.read_persisted(), normalized)
        self.assertEqual(set(normalized), set(scheduler_engine.SCHEDULE_GROUPS))
        self.assertEqual(stat.S_IMODE(self.schedule_file.stat().st_mode), 0o640)
        self.assertTrue(self.schedule_file.read_text(encoding="utf-8").endswith("\n"))

    def test_failed_serialization_preserves_existing_schedule(self):
        original_schedule = {"global": [self.schedule(app="global")]}
        self.write_existing(original_schedule)

        def fail_after_partial_write(data, file_handle, **kwargs):
            file_handle.write('{"truncated":')
            raise OSError("simulated write failure")

        with patch.object(scheduler_engine.json, "dump", side_effect=fail_after_partial_write):
            with self.assertRaises(OSError):
                scheduler_engine.save_schedule({"sonarr": [self.schedule()]})

        self.assertEqual(self.read_persisted(), original_schedule)
        self.assertEqual(list(self.schedule_file.parent.glob(".schedule.json.*.tmp")), [])

    def test_invalid_api_payload_is_rejected_without_replacing_file(self):
        original_schedule = {"global": [self.schedule(app="global")]}
        self.write_existing(original_schedule)
        invalid_schedule = {"sonarr": [self.schedule(action="delete-everything")]}

        with app.test_request_context("/api/scheduler/save", method="POST", json=invalid_schedule):
            response, status = save_schedules()

        self.assertEqual(status, 400)
        self.assertEqual(response.get_json()["error"], "Schedule data is invalid")
        self.assertEqual(self.read_persisted(), original_schedule)

    def test_empty_api_payload_is_rejected_without_replacing_file(self):
        original_schedule = {"global": [self.schedule(app="global")]}
        self.write_existing(original_schedule)

        with app.test_request_context("/api/scheduler/save", method="POST", json={}):
            response, status = save_schedules()

        self.assertEqual(status, 400)
        self.assertEqual(response.get_json()["error"], "Schedule data is invalid")
        self.assertEqual(self.read_persisted(), original_schedule)

    def test_validation_exception_detail_is_not_returned(self):
        exception_detail = "private scheduler validation detail"

        with (
            app.test_request_context("/api/scheduler/save", method="POST", json={"global": []}),
            patch(
                "src.primary.routes.scheduler_routes.save_schedule",
                side_effect=scheduler_engine.ScheduleValidationError(exception_detail),
            ),
        ):
            response, status = save_schedules()

        self.assertEqual(status, 400)
        self.assertEqual(response.get_json()["error"], "Schedule data is invalid")
        self.assertNotIn(exception_detail, response.get_json()["error"])

    def test_duplicate_ids_are_rejected_across_groups(self):
        duplicate_id = "duplicate"
        schedule_data = {
            "global": [self.schedule(duplicate_id, app="global")],
            "sonarr": [self.schedule(duplicate_id)],
        }

        with self.assertRaisesRegex(scheduler_engine.ScheduleValidationError, "id must be unique"):
            scheduler_engine.save_schedule(schedule_data)

        self.assertFalse(self.schedule_file.exists())

    def test_legacy_time_and_abbreviated_days_are_normalized(self):
        normalized = scheduler_engine.save_schedule(
            {
                "sonarr": [
                    self.schedule(
                        time="08:05",
                        days=["Mon", "WED", "monday"],
                        action="pause",
                    )
                ]
            }
        )

        schedule = normalized["sonarr"][0]
        self.assertEqual(schedule["time"], {"hour": 8, "minute": 5})
        self.assertEqual(schedule["days"], ["monday", "wednesday"])
        self.assertEqual(schedule["action"], "pause")

    def test_invalid_existing_file_is_backed_up_before_repair(self):
        self.schedule_file.parent.mkdir(parents=True, exist_ok=True)
        invalid_content = '{"sonarr": ['
        self.schedule_file.write_text(invalid_content, encoding="utf-8")

        loaded = scheduler_engine.load_schedule()

        self.assertEqual(loaded, scheduler_engine._empty_schedule())
        self.assertEqual(self.read_persisted(), scheduler_engine._empty_schedule())
        backups = list(self.schedule_file.parent.glob("schedule.json.backup.*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), invalid_content)

    def test_concurrent_saves_leave_one_complete_valid_document(self):
        payloads = [
            {"sonarr": [self.schedule(f"schedule-{index}", time={"hour": index, "minute": 0})]} for index in range(12)
        ]

        with ThreadPoolExecutor(max_workers=6) as executor:
            list(executor.map(scheduler_engine.save_schedule, payloads))

        persisted = self.read_persisted()
        scheduler_engine.validate_schedule_data(persisted)
        persisted_ids = {entry["id"] for entries in persisted.values() for entry in entries}
        self.assertEqual(len(persisted_ids), 1)
        self.assertIn(next(iter(persisted_ids)), {f"schedule-{index}" for index in range(12)})
        self.assertEqual(list(self.schedule_file.parent.glob(".schedule.json.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
