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
        self.eros_settings_file = Path(self.temp_directory.name) / "eros.json"
        self.default_file = Path(self.temp_directory.name) / "sonarr.default.json"
        self.eros_default_file = Path(self.temp_directory.name) / "eros.default.json"
        self.default_file.write_text("{}", encoding="utf-8")
        self.eros_default_file.write_text("{}", encoding="utf-8")
        self.path_patch = patch.dict(
            settings_manager.KNOWN_SETTINGS_FILES,
            {
                "sonarr": self.settings_file,
                "eros": self.eros_settings_file,
            },
        )
        self.default_patch = patch.dict(
            settings_manager.KNOWN_DEFAULT_CONFIG_FILES,
            {
                "sonarr": self.default_file,
                "eros": self.eros_default_file,
            },
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
            result = scheduler_engine.execute_action({"id": "disable-sonarr", "action": "disable", "app": "sonarr-all"})

        self.assertTrue(result)
        update.assert_called_once()
        persisted = self.read_settings()
        self.assertFalse(persisted["enabled"])
        self.assertEqual([instance["enabled"] for instance in persisted["instances"]], [False, False])
        self.assertEqual(persisted["api_key"], "existing-secret")

    def test_instance_target_changes_only_the_selected_instance(self):
        self.write_settings(
            {
                "enabled": True,
                "instances": [
                    {"name": "Primary", "enabled": True},
                    {"name": "Secondary", "enabled": True},
                ],
            }
        )

        result = scheduler_engine.execute_action({"id": "disable-secondary", "action": "disable", "app": "sonarr-1"})

        self.assertTrue(result)
        persisted = self.read_settings()
        self.assertTrue(persisted["enabled"])
        self.assertEqual([instance["enabled"] for instance in persisted["instances"]], [True, False])

    def test_whisparr_v3_target_updates_eros_settings(self):
        self.eros_settings_file.write_text(
            json.dumps({"enabled": True, "instances": [{"name": "Eros", "enabled": True}]}),
            encoding="utf-8",
        )
        settings_manager.clear_cache("eros")

        result = scheduler_engine.execute_action({"id": "disable-eros", "action": "disable", "app": "whisparr-v3"})

        self.assertTrue(result)
        persisted = json.loads(self.eros_settings_file.read_text(encoding="utf-8"))
        self.assertFalse(persisted["enabled"])
        self.assertFalse(persisted["instances"][0]["enabled"])

    def test_api_cap_action_changes_only_the_requested_setting(self):
        self.write_settings({"enabled": True, "hourly_cap": 20, "api_key": "existing-secret"})

        result = scheduler_engine.execute_action({"id": "limit-sonarr", "action": "api-5", "app": "sonarr-all"})

        self.assertTrue(result)
        self.assertEqual(
            self.read_settings(),
            {"enabled": True, "hourly_cap": 5, "api_key": "existing-secret"},
        )

    def test_current_ui_targets_resolve_to_the_expected_config(self):
        expected_targets = {
            "global": ("global", None),
            "sonarr-all": ("sonarr", None),
            "radarr-all": ("radarr", None),
            "lidarr-all": ("lidarr", None),
            "readarr-all": ("readarr", None),
            "whisparr-v2": ("whisparr", None),
            "whisparr-v3": ("eros", None),
        }

        for target, expected in expected_targets.items():
            with self.subTest(target=target):
                self.assertEqual(scheduler_engine._resolve_schedule_target(target), expected)

    def test_non_string_target_is_rejected(self):
        self.write_settings({"enabled": True})

        result = scheduler_engine.execute_action(
            {"id": "invalid-target-type", "action": "disable", "app": ["sonarr-all"]}
        )

        self.assertFalse(result)
        self.assertEqual(self.read_settings(), {"enabled": True})

    def test_unknown_or_path_like_app_target_is_rejected(self):
        self.write_settings({"enabled": True})

        result = scheduler_engine.execute_action({"id": "invalid-target", "action": "disable", "app": "../../outside"})

        self.assertFalse(result)
        self.assertEqual(self.read_settings(), {"enabled": True})
        self.assertEqual(scheduler_engine.execution_history[0]["status"], "error")

    def test_missing_app_settings_do_not_report_success_or_suppress_retry(self):
        action = {
            "id": "missing-sonarr",
            "action": "disable",
            "app": "sonarr-all",
        }

        result = scheduler_engine.execute_action(action)

        self.assertFalse(result)
        self.assertFalse(self.settings_file.exists())
        self.assertEqual(scheduler_engine.last_executed_actions, {})
        self.assertEqual(scheduler_engine.execution_history[0]["status"], "error")
        self.assertIn("Error disabling sonarr-all", scheduler_engine.execution_history[0]["message"])

    def test_global_action_fails_when_no_app_settings_exist(self):
        missing_settings = Path(self.temp_directory.name) / "missing"
        action = {
            "id": "missing-global",
            "action": "disable",
            "app": "global",
        }

        with patch.object(
            settings_manager,
            "get_settings_file_path",
            side_effect=lambda app_type: missing_settings / f"{app_type}.json",
        ):
            result = scheduler_engine.execute_action(action)

        self.assertFalse(result)
        self.assertEqual(scheduler_engine.last_executed_actions, {})
        self.assertEqual(scheduler_engine.execution_history[0]["status"], "error")
        self.assertIn("Error disabling global", scheduler_engine.execution_history[0]["message"])

    def test_global_action_updates_configured_apps_and_skips_unconfigured_apps(self):
        self.write_settings({"enabled": True})
        missing_settings = Path(self.temp_directory.name) / "missing"
        action = {
            "id": "partial-global",
            "action": "disable",
            "app": "global",
        }

        with patch.object(
            settings_manager,
            "get_settings_file_path",
            side_effect=lambda app_type: (
                self.settings_file if app_type == "sonarr" else missing_settings / f"{app_type}.json"
            ),
        ):
            result = scheduler_engine.execute_action(action)

        self.assertTrue(result)
        self.assertFalse(self.read_settings()["enabled"])
        self.assertEqual(scheduler_engine.execution_history[0]["status"], "success")

    def test_unknown_action_is_rejected_without_marking_it_executed(self):
        self.write_settings({"enabled": True})
        action = {"id": "unknown-action", "action": "erase", "app": "sonarr"}

        self.assertFalse(scheduler_engine.execute_action(action))

        self.assertEqual(self.read_settings(), {"enabled": True})
        self.assertEqual(scheduler_engine.last_executed_actions, {})
        self.assertEqual(scheduler_engine.execution_history[0]["status"], "error")

    def test_scheduler_check_does_not_suppress_retry_after_failed_action(self):
        action = {
            "id": "retry-action",
            "action": "disable",
            "app": "sonarr-all",
            "time": {"hour": 12, "minute": 0},
            "days": ["monday"],
            "enabled": True,
        }

        with (
            patch.object(scheduler_engine.os.path, "exists", return_value=True),
            patch.object(scheduler_engine.os.path, "getsize", return_value=100),
            patch.object(scheduler_engine, "load_schedule", return_value={"sonarr": [action]}),
            patch.object(scheduler_engine, "should_execute_schedule", return_value=True),
            patch.object(scheduler_engine, "execute_action", return_value=False),
        ):
            scheduler_engine.check_and_execute_schedules()

        self.assertNotIn("retry-action", scheduler_engine.last_executed_actions)


if __name__ == "__main__":
    unittest.main()
