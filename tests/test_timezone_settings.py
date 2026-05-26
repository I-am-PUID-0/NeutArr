import os
import sys
import unittest
from pathlib import Path
from unittest.mock import mock_open, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_support import configure_test_environment

configure_test_environment()

from src.primary import settings_manager


class TimezoneSettingsTests(unittest.TestCase):
    def test_apply_timezone_succeeds_when_etc_localtime_is_not_writable(self):
        with (
            patch.object(settings_manager.os.path, "exists", return_value=True),
            patch.object(settings_manager.os.path, "lexists", return_value=True),
            patch.object(settings_manager.os, "remove", side_effect=PermissionError("denied")),
            patch.object(settings_manager.time_module, "tzset") as tzset,
        ):
            self.assertTrue(settings_manager.apply_timezone("America/New_York"))

        self.assertEqual(os.environ["TZ"], "America/New_York")
        tzset.assert_called_once()

    def test_apply_timezone_succeeds_when_etc_timezone_file_is_not_writable(self):
        with (
            patch.object(settings_manager.os.path, "exists", return_value=True),
            patch.object(settings_manager.os.path, "lexists", return_value=False),
            patch.object(settings_manager.os, "symlink"),
            patch("builtins.open", mock_open()) as mocked_open,
            patch.object(settings_manager.time_module, "tzset") as tzset,
        ):
            mocked_open.side_effect = PermissionError("denied")

            self.assertTrue(settings_manager.apply_timezone("America/Chicago"))

        self.assertEqual(os.environ["TZ"], "America/Chicago")
        tzset.assert_called_once()

    def test_apply_timezone_falls_back_to_utc_for_unknown_timezone(self):
        def exists(path):
            return path == "/usr/share/zoneinfo/UTC"

        with (
            patch.object(settings_manager.os.path, "exists", side_effect=exists),
            patch.object(settings_manager.os.path, "lexists", return_value=False),
            patch.object(settings_manager.os, "symlink"),
            patch("builtins.open", mock_open()),
            patch.object(settings_manager.time_module, "tzset"),
        ):
            self.assertTrue(settings_manager.apply_timezone("Not/AZone"))

        self.assertEqual(os.environ["TZ"], "UTC")


if __name__ == "__main__":
    unittest.main()
