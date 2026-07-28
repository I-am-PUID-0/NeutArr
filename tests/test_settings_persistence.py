import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_support import configure_test_environment

configure_test_environment()

from src.primary import settings_manager
from src.primary.web_server import app, handle_app_settings, save_general_settings


class SettingsPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.settings_file = Path(self.temp_directory.name) / "sonarr.json"
        self.path_patch = patch.dict(
            settings_manager.KNOWN_SETTINGS_FILES,
            {"sonarr": self.settings_file},
        )
        self.path_patch.start()
        settings_manager.clear_cache("sonarr")

    def tearDown(self):
        settings_manager.clear_cache("sonarr")
        self.path_patch.stop()
        self.temp_directory.cleanup()

    def test_failed_serialization_preserves_existing_settings(self):
        original_settings = {
            "instances": [
                {
                    "name": "Primary",
                    "api_url": "http://sonarr:8989",
                    "api_key": "existing-secret",
                }
            ]
        }
        self.settings_file.write_text(json.dumps(original_settings), encoding="utf-8")

        def fail_after_partial_write(data, file_handle, **kwargs):
            file_handle.write('{"truncated":')
            raise OSError("simulated write failure")

        with patch.object(settings_manager.json, "dump", side_effect=fail_after_partial_write):
            saved = settings_manager.save_settings("sonarr", {"instances": []})

        self.assertFalse(saved)
        self.assertEqual(json.loads(self.settings_file.read_text(encoding="utf-8")), original_settings)
        self.assertEqual(list(self.settings_file.parent.glob(".sonarr.json.*.tmp")), [])

    def test_successful_save_atomically_replaces_json_and_preserves_mode(self):
        self.settings_file.write_text('{"enabled": false}', encoding="utf-8")
        self.settings_file.chmod(0o640)
        updated_settings = {"enabled": True, "instances": []}

        self.assertTrue(settings_manager.save_settings("sonarr", updated_settings))

        self.assertEqual(json.loads(self.settings_file.read_text(encoding="utf-8")), updated_settings)
        self.assertEqual(stat.S_IMODE(self.settings_file.stat().st_mode), 0o640)
        self.assertTrue(self.settings_file.read_text(encoding="utf-8").endswith("\n"))

    def test_save_rejects_non_object_settings_without_replacing_file(self):
        self.settings_file.write_text('{"enabled": true}', encoding="utf-8")

        self.assertFalse(settings_manager.save_settings("sonarr", []))

        self.assertEqual(json.loads(self.settings_file.read_text(encoding="utf-8")), {"enabled": True})

    def test_failed_update_preserves_persisted_and_cached_settings(self):
        original_settings = {"enabled": True, "hourly_cap": 20}
        self.settings_file.write_text(json.dumps(original_settings), encoding="utf-8")
        settings_manager.load_settings("sonarr", use_cache=False)
        persisted_before_update = json.loads(self.settings_file.read_text(encoding="utf-8"))

        with patch.object(settings_manager, "_atomic_write_json", side_effect=OSError("simulated replace failure")):
            updated = settings_manager.update_settings(
                "sonarr",
                lambda settings: settings.update({"hourly_cap": 5}),
            )

        self.assertFalse(updated)
        self.assertEqual(json.loads(self.settings_file.read_text(encoding="utf-8")), persisted_before_update)
        self.assertEqual(settings_manager.load_settings("sonarr"), persisted_before_update)

    def test_general_settings_route_rejects_non_object_json(self):
        with app.test_request_context("/api/settings/general", method="POST", json=[]):
            response, status = save_general_settings()

        self.assertEqual(status, 400)
        self.assertEqual(response.get_json()["error"], "Settings must be a JSON object")

    def test_app_settings_route_rejects_non_object_json(self):
        with app.test_request_context("/api/settings/sonarr", method="POST", json=[]):
            response, status = handle_app_settings("sonarr")

        self.assertEqual(status, 400)
        self.assertEqual(response.get_json()["error"], "Settings must be a JSON object")


if __name__ == "__main__":
    unittest.main()
