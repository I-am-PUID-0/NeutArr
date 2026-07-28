import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_support import configure_test_environment

configure_test_environment()

from src.primary import settings_manager


class TimezoneSettingsTests(unittest.TestCase):
    def test_apply_timezone_updates_process_environment_and_clock(self):
        with (
            patch.object(settings_manager.os.path, "exists", return_value=True),
            patch.object(settings_manager.time_module, "tzset") as tzset,
        ):
            self.assertTrue(settings_manager.apply_timezone("America/New_York"))

        self.assertEqual(os.environ["TZ"], "America/New_York")
        tzset.assert_called_once()

    def test_apply_timezone_does_not_modify_system_timezone_files(self):
        with (
            patch.object(settings_manager.os.path, "exists", return_value=True),
            patch.object(settings_manager.time_module, "tzset") as tzset,
            patch.object(settings_manager.os, "remove") as remove,
            patch.object(settings_manager.os, "symlink") as symlink,
            patch("builtins.open") as open_file,
        ):
            self.assertTrue(settings_manager.apply_timezone("America/Chicago"))

        self.assertEqual(os.environ["TZ"], "America/Chicago")
        tzset.assert_called_once()
        remove.assert_not_called()
        symlink.assert_not_called()
        open_file.assert_not_called()

    def test_apply_timezone_falls_back_to_utc_for_unknown_timezone(self):
        def exists(path):
            return path == "/usr/share/zoneinfo/UTC"

        with (
            patch.object(settings_manager.os.path, "exists", side_effect=exists),
            patch.object(settings_manager.time_module, "tzset"),
        ):
            self.assertTrue(settings_manager.apply_timezone("Not/AZone"))

        self.assertEqual(os.environ["TZ"], "UTC")


if __name__ == "__main__":
    unittest.main()
