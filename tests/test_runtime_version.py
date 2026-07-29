import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.primary.utils import version


class RuntimeVersionTests(unittest.TestCase):
    def test_project_version_is_used_without_runtime_marker(self):
        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(version, "_get_project_version", return_value="1.11.0"),
        ):
            self.assertEqual(version.get_runtime_version(), "1.11.0")

    def test_matching_release_runtime_marker_is_preserved(self):
        with (
            patch.dict("os.environ", {"NEUTARR_VERSION": "1.11.0"}, clear=True),
            patch.object(version, "_get_project_version", return_value="1.11.0"),
        ):
            self.assertEqual(version.get_runtime_version(), "1.11.0")

    def test_matching_dev_runtime_marker_is_preserved(self):
        with (
            patch.dict("os.environ", {"NEUTARR_VERSION": "1.11.0-dev.12"}, clear=True),
            patch.object(version, "_get_project_version", return_value="1.11.0"),
        ):
            self.assertEqual(version.get_runtime_version(), "1.11.0-dev.12")

    def test_stale_semantic_runtime_marker_does_not_override_bundled_source(self):
        with (
            patch.dict("os.environ", {"NEUTARR_VERSION": "1.8.0"}, clear=True),
            patch.object(version, "_get_project_version", return_value="1.11.0"),
        ):
            self.assertEqual(version.get_runtime_version(), "1.11.0")

    def test_dumb_branch_marker_is_preserved(self):
        with (
            patch.dict("os.environ", {"NEUTARR_VERSION": "dev-a1b2c3d4"}, clear=True),
            patch.object(version, "_get_project_version", return_value="1.11.0"),
        ):
            self.assertEqual(version.get_runtime_version(), "dev-a1b2c3d4")

    def test_runtime_marker_is_used_when_project_metadata_is_unavailable(self):
        with (
            patch.dict("os.environ", {"NEUTARR_VERSION": "1.8.0"}, clear=True),
            patch.object(version, "_get_project_version", return_value=""),
        ):
            self.assertEqual(version.get_runtime_version(), "1.8.0")

    def test_fallback_is_used_when_no_version_source_is_available(self):
        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(version, "_get_project_version", return_value=""),
        ):
            self.assertEqual(version.get_runtime_version(), version.FALLBACK_VERSION)


if __name__ == "__main__":
    unittest.main()
