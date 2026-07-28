import datetime
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_support import configure_test_environment

configure_test_environment()

from src.primary import stats_manager


class FixedDateTime(datetime.datetime):
    current = datetime.datetime(2026, 7, 28, 12, 0, 30)

    @classmethod
    def now(cls, tz=None):
        if tz is not None:
            return cls.current.replace(tzinfo=tz)
        return cls.current


class StatsPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.stats_directory = Path(self.temp_directory.name) / "tally"
        self.stats_directory.mkdir()
        self.patchers = [
            patch.object(stats_manager, "STATS_DIR", str(self.stats_directory)),
            patch.object(stats_manager, "STATS_FILE", str(self.stats_directory / "media_stats.json")),
            patch.object(stats_manager, "HOURLY_CAP_FILE", str(self.stats_directory / "hourly_cap.json")),
        ]
        for path_patcher in self.patchers:
            path_patcher.start()
        self.original_last_hour_checked = stats_manager.last_hour_checked
        stats_manager.last_hour_checked = None

    def tearDown(self):
        stats_manager.last_hour_checked = self.original_last_hour_checked
        for path_patcher in reversed(self.patchers):
            path_patcher.stop()
        self.temp_directory.cleanup()

    def test_concurrent_top_of_hour_checks_reset_only_once(self):
        thread_count = 12
        barrier = threading.Barrier(thread_count)
        results = []
        results_lock = threading.Lock()

        def check_reset():
            barrier.wait()
            result = stats_manager.check_hourly_reset()
            with results_lock:
                results.append(result)

        with (
            patch.object(stats_manager.datetime, "datetime", FixedDateTime),
            patch.object(stats_manager, "save_hourly_caps", return_value=True) as save_caps,
        ):
            threads = [threading.Thread(target=check_reset) for _ in range(thread_count)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=2)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(save_caps.call_count, 1)
        self.assertEqual(results.count(True), 1)
        self.assertEqual(results.count(False), thread_count - 1)
        self.assertEqual(stats_manager.last_hour_checked, "2026-07-28T12")

    def test_same_clock_hour_on_next_day_is_a_new_reset_period(self):
        stats_manager.last_hour_checked = "2026-07-27T12"

        with (
            patch.object(stats_manager.datetime, "datetime", FixedDateTime),
            patch.object(stats_manager, "save_hourly_caps", return_value=True) as save_caps,
        ):
            self.assertTrue(stats_manager.check_hourly_reset())

        save_caps.assert_called_once()
        self.assertEqual(stats_manager.last_hour_checked, "2026-07-28T12")

    def test_failed_reset_preserves_existing_caps_permissions_and_marker(self):
        cap_file = Path(stats_manager.HOURLY_CAP_FILE)
        original_caps = stats_manager.get_default_hourly_caps()
        original_caps["sonarr"]["api_hits"] = 7
        cap_file.write_text(json.dumps(original_caps), encoding="utf-8")
        cap_file.chmod(0o640)
        stats_manager.last_hour_checked = "previous-period"

        def fail_after_partial_write(_data, destination, **_kwargs):
            destination.write('{"partial":')
            raise OSError("simulated interrupted write")

        with patch.object(stats_manager.json, "dump", side_effect=fail_after_partial_write):
            self.assertFalse(stats_manager.reset_hourly_caps())

        self.assertEqual(json.loads(cap_file.read_text(encoding="utf-8")), original_caps)
        self.assertEqual(cap_file.stat().st_mode & 0o777, 0o640)
        self.assertEqual(stats_manager.last_hour_checked, "previous-period")
        self.assertEqual(list(cap_file.parent.glob(f".{cap_file.name}.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
