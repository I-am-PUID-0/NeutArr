import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_support import configure_test_environment

configure_test_environment()

from src.primary.apps.swaparr.handler import is_enabled_for_app, is_enabled_for_app_instance


class SwaparrPerInstanceSettingsTests(unittest.TestCase):
    def test_missing_app_enabled_defaults_to_disabled(self):
        self.assertFalse(is_enabled_for_app("sonarr", {"enabled": True}))

    def test_malformed_app_enabled_defaults_to_disabled(self):
        self.assertFalse(is_enabled_for_app("radarr", {"enabled": True, "app_enabled": ["radarr"]}))

    def test_missing_specific_app_key_defaults_to_disabled(self):
        settings = {"enabled": True, "app_enabled": {"sonarr": True}}

        self.assertFalse(is_enabled_for_app("radarr", settings))

    def test_false_value_disables_specific_app(self):
        settings = {"enabled": True, "app_enabled": {"lidarr": False}}

        self.assertFalse(is_enabled_for_app("lidarr", settings))

    def test_true_value_enables_specific_app(self):
        settings = {"enabled": True, "app_enabled": {"readarr": True}}

        self.assertTrue(is_enabled_for_app("readarr", settings))

    def test_instance_toggle_can_disable_one_instance_without_disabling_the_app_type(self):
        settings = {
            "enabled": True,
            "app_enabled": {"sonarr": True},
            "app_instances": {"sonarr": {"Default": True, "Instance 2": False}},
        }

        self.assertTrue(is_enabled_for_app_instance("sonarr", {"instance_name": "Default"}, settings))
        self.assertFalse(is_enabled_for_app_instance("sonarr", {"instance_name": "Instance 2"}, settings))

    def test_missing_instance_toggle_defaults_to_disabled_even_when_app_type_is_enabled(self):
        settings = {"enabled": True, "app_enabled": {"radarr": True}, "app_instances": {"radarr": {}}}

        self.assertFalse(is_enabled_for_app_instance("radarr", {"instance_name": "Default"}, settings))

    def test_app_type_disable_still_disables_all_instances_for_legacy_configs(self):
        settings = {"enabled": True, "app_enabled": {"lidarr": False}}

        self.assertFalse(is_enabled_for_app_instance("lidarr", {"instance_name": "Default"}, settings))

    def test_malformed_instance_toggle_defaults_to_disabled(self):
        settings = {"enabled": True, "app_enabled": {"sonarr": True}, "app_instances": ["Default"]}

        self.assertFalse(is_enabled_for_app_instance("sonarr", {"instance_name": "Default"}, settings))


if __name__ == "__main__":
    unittest.main()
