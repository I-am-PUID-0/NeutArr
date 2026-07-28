import json
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_support import configure_test_environment

configure_test_environment()

from src.primary.apps.swaparr import handler


class SwaparrPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.state_directory = Path(self.temp_directory.name) / "swaparr"
        self.path_patch = patch.object(
            handler,
            "SWAPARR_STATE_DIR",
            str(self.state_directory),
        )
        self.path_patch.start()

    def tearDown(self):
        self.path_patch.stop()
        with handler.swaparr_state_locks_guard:
            handler.swaparr_state_locks.clear()
        self.temp_directory.cleanup()

    def test_colliding_instance_names_keep_independent_strikes(self):
        settings = {
            "enabled": True,
            "max_strikes": 3,
            "max_download_time": "2h",
            "ignore_above_size": "25GB",
            "remove_from_client": True,
            "dry_run": True,
            "app_enabled": {"sonarr": True},
            "app_instances": {
                "sonarr": {
                    "Primary-4K": True,
                    "Primary_4K": True,
                }
            },
        }

        def queue_for_instance(_app_name, api_url, _api_key, _api_timeout):
            return [
                {
                    "id": 1,
                    "name": api_url,
                    "size": 1,
                    "status": "downloading",
                    "eta": 0,
                    "error_message": "",
                }
            ]

        with patch.object(handler, "get_queue_items", side_effect=queue_for_instance):
            handler.process_stalled_downloads(
                "sonarr",
                {
                    "instance_name": "Primary-4K",
                    "api_url": "https://first.example.invalid",
                    "api_key": "first-key",
                },
                settings,
            )
            handler.process_stalled_downloads(
                "sonarr",
                {
                    "instance_name": "Primary_4K",
                    "api_url": "https://second.example.invalid",
                    "api_key": "second-key",
                },
                settings,
            )

        first_file = handler._get_state_file("sonarr", "Primary-4K", "strikes.json")
        second_file = handler._get_state_file("sonarr", "Primary_4K", "strikes.json")
        self.assertNotEqual(first_file, second_file)

        first_state = json.loads(first_file.read_text(encoding="utf-8"))
        second_state = json.loads(second_file.read_text(encoding="utf-8"))
        self.assertEqual(first_state["1"]["strikes"], 1)
        self.assertEqual(second_state["1"]["strikes"], 1)
        self.assertEqual(first_state["1"]["name"], "https://first.example.invalid")
        self.assertEqual(second_state["1"]["name"], "https://second.example.invalid")

    def test_failed_write_preserves_existing_state_and_permissions(self):
        state_file = handler._get_state_file("radarr", "Primary", "strikes.json")
        original_state = {"1": {"strikes": 1}}
        state_file.write_text(json.dumps(original_state), encoding="utf-8")
        state_file.chmod(0o640)

        def fail_after_partial_write(_data, destination, **_kwargs):
            destination.write('{"partial":')
            raise OSError("simulated interrupted write")

        with patch.object(handler.json, "dump", side_effect=fail_after_partial_write):
            saved = handler.save_strike_data(
                "radarr",
                {"1": {"strikes": 2}},
                "Primary",
            )

        self.assertFalse(saved)
        self.assertEqual(json.loads(state_file.read_text(encoding="utf-8")), original_state)
        self.assertEqual(state_file.stat().st_mode & 0o777, 0o640)
        self.assertEqual(list(state_file.parent.glob(f".{state_file.name}.*.tmp")), [])

    def test_malformed_state_is_preserved_and_stops_processing(self):
        state_file = handler._get_state_file("lidarr", "Primary", "strikes.json")
        malformed_document = '{"incomplete":'
        state_file.write_text(malformed_document, encoding="utf-8")
        settings = {
            "enabled": True,
            "app_enabled": {"lidarr": True},
            "app_instances": {"lidarr": {"Primary": True}},
        }

        with patch.object(handler, "get_queue_items") as get_queue:
            handler.process_stalled_downloads(
                "lidarr",
                {
                    "instance_name": "Primary",
                    "api_url": "https://lidarr.example.invalid",
                    "api_key": "lidarr-key",
                },
                settings,
            )

        get_queue.assert_not_called()
        self.assertEqual(state_file.read_text(encoding="utf-8"), malformed_document)

    def test_single_instance_migrates_legacy_app_state(self):
        legacy_file = self.state_directory / "readarr" / "strikes.json"
        legacy_file.parent.mkdir(parents=True)
        legacy_state = {"1": {"strikes": 2}}
        legacy_file.write_text(json.dumps(legacy_state), encoding="utf-8")

        loaded_state = handler.load_strike_data(
            "readarr",
            "Primary",
            allow_legacy_migration=True,
        )

        instance_file = handler._get_state_file("readarr", "Primary", "strikes.json")
        self.assertEqual(loaded_state, legacy_state)
        self.assertFalse(legacy_file.exists())
        self.assertEqual(json.loads(instance_file.read_text(encoding="utf-8")), legacy_state)

    def test_zulu_removed_timestamp_is_compatible_with_current_utc_time(self):
        instance_name = "Primary"
        item = {
            "id": 1,
            "name": "Stalled download",
            "size": 1,
            "status": "downloading",
            "eta": 0,
            "error_message": "",
        }
        item_hash = handler.generate_item_hash(item)
        removed_time = (handler._utc_now() - timedelta(days=1)).isoformat().replace("+00:00", "Z")
        handler.save_removed_items(
            "whisparr",
            {
                item_hash: {
                    "name": item["name"],
                    "size": item["size"],
                    "removed_time": removed_time,
                }
            },
            instance_name,
        )
        settings = {
            "enabled": True,
            "dry_run": True,
            "app_enabled": {"whisparr": True},
            "app_instances": {"whisparr": {instance_name: True}},
        }

        with patch.object(handler, "get_queue_items", return_value=[item]):
            handler.process_stalled_downloads(
                "whisparr",
                {
                    "instance_name": instance_name,
                    "api_url": "https://whisparr.example.invalid",
                    "api_key": "whisparr-key",
                },
                settings,
            )

        removed_items = handler.load_removed_items("whisparr", instance_name)
        self.assertIn(item_hash, removed_items)


if __name__ == "__main__":
    unittest.main()
