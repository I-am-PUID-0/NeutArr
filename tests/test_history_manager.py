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

from src.primary import history_manager


class HistoryManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.history_directory = Path(self.temp_directory.name) / "history"
        self.path_patch = patch.object(
            history_manager,
            "HISTORY_BASE_PATH",
            self.history_directory,
        )
        self.path_patch.start()

    def tearDown(self):
        self.path_patch.stop()
        self.temp_directory.cleanup()

    def test_rename_preserves_history_when_names_share_a_safe_filename(self):
        old_name = "Primary-4K"
        new_name = "Primary_4K"
        history_file = history_manager.get_history_file_path("sonarr", old_name)
        self.assertEqual(
            history_file,
            history_manager.get_history_file_path("sonarr", new_name),
        )

        history_file.parent.mkdir(parents=True)
        history_file.write_text(
            json.dumps(
                [
                    {"id": 1, "date_time": 10, "instance_name": old_name},
                    {"id": 2, "date_time": 20, "instance_name": new_name},
                ]
            ),
            encoding="utf-8",
        )

        self.assertTrue(
            history_manager.handle_instance_rename(
                "sonarr",
                old_name,
                new_name,
            )
        )

        self.assertTrue(history_file.exists())
        entries = json.loads(history_file.read_text(encoding="utf-8"))
        self.assertEqual([entry["instance_name"] for entry in entries], [new_name, new_name])


if __name__ == "__main__":
    unittest.main()
