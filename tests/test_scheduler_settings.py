import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_support import configure_test_environment

configure_test_environment()

from src.primary import scheduler_engine, settings_manager


class SchedulerSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.settings_file = Path(self.temp_directory.name) / "sonarr.json"
        self.default_file = Path(self.temp_directory.name) / "sonarr.default.json"
        self.default_file.write_text("{}", encoding="utf-8")
        self.path_patch = patch.dict(
            settings_manager.KNOWN_SETTINGS_FILES,
            {"sonarr": self.settings_file},
        )
        self.default_patch = patch.dict(
            settings_manager.KNOWN_DEFAULT_CONFIG_FILES,
            {"sonarr": self.default_file},
        )
        self.path_patch.start()
        self.default_patch.start()
        settings_manager.clear_cache("sonarr")
        scheduler_engine.last_executed_actions.clear()
        scheduler_engine.execution_history.clear()

    def tearDown(self):
        scheduler_engine.last_executed_actions.clear()
        scheduler_engine.execution_history.clear()
        settings_manager.clear_cache("sonarr")
        self.default_patch.stop()
        self.path_patch.stop()
        self.temp_directory.cleanup()

    def write_settings(self, settings):
        self.settings_file.write_text(json.dumps(settings), encoding="utf-8")
        settings_manager.clear_cache("sonarr")

    def read_settings(self):
        return json.loads(self.settings_file.read_text(encoding="utf-8"))

    def test_disable_action_uses_atomic_settings_update_and_preserves_other_fields(self):
        self.write_settings(
            {
                "enabled": True,
                "api_key": "existing-secret",
                "instances": [
                    {"name": "Primary", "enabled": True},
                    {"name": "Secondary", "enabled": True},
                ],
            }
        )

        with patch.object(settings_manager, "update_settings", wraps=settings_manager.update_settings) as update:
            result = scheduler_engine.execute_action({"id": "disable-sonarr", "action": "disable", "app": "sonarr"})

        self.assertTrue(result)
        update.assert_called_once()
        persisted = self.read_settings()
        self.assertFalse(persisted["enabled"])
        self.assertEqual([instance["enabled"] for instance in persisted["instances"]], [False, False])
        self.assertEqual(persisted["api_key"], "existing-secret")

    def test_api_cap_action_changes_only_the_requested_setting(self):
        self.write_settings({"enabled": True, "hourly_cap": 20, "api_key": "existing-secret"})

        result = scheduler_engine.execute_action({"id": "limit-sonarr", "action": "api-5", "app": "sonarr"})

        self.assertTrue(result)
        self.assertEqual(
            self.read_settings(),
            {"enabled": True, "hourly_cap": 5, "api_key": "existing-secret"},
        )

    def test_unknown_or_path_like_app_target_is_rejected(self):
        self.write_settings({"enabled": True})

        result = scheduler_engine.execute_action({"id": "invalid-target", "action": "disable", "app": "../../outside"})

        self.assertFalse(result)
        self.assertEqual(self.read_settings(), {"enabled": True})
        self.assertEqual(scheduler_engine.execution_history[0]["status"], "error")

    def test_unknown_action_is_rejected_without_marking_it_executed(self):
        self.write_settings({"enabled": True})
        action = {"id": "unknown-action", "action": "erase", "app": "sonarr"}

        self.assertFalse(scheduler_engine.execute_action(action))

        self.assertEqual(self.read_settings(), {"enabled": True})
        self.assertEqual(scheduler_engine.last_executed_actions, {})
        self.assertEqual(scheduler_engine.execution_history[0]["status"], "error")


if __name__ == "__main__":
    unittest.main()
