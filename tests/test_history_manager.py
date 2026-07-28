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
from src.primary.instance_storage import legacy_instance_storage_key


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

    def test_colliding_instance_names_use_distinct_history_files(self):
        old_name = "Primary-4K"
        new_name = "Primary_4K"

        history_manager.add_history_entry(
            "sonarr",
            {"name": "First", "instance_name": old_name, "id": 1},
        )
        history_manager.add_history_entry(
            "sonarr",
            {"name": "Second", "instance_name": new_name, "id": 2},
        )

        old_file = history_manager.get_history_file_path("sonarr", old_name)
        new_file = history_manager.get_history_file_path("sonarr", new_name)
        self.assertNotEqual(old_file, new_file)
        self.assertEqual(
            json.loads(old_file.read_text(encoding="utf-8"))[0]["instance_name"],
            old_name,
        )
        self.assertEqual(
            json.loads(new_file.read_text(encoding="utf-8"))[0]["instance_name"],
            new_name,
        )

    def test_rename_splits_and_preserves_a_legacy_collision_file(self):
        old_name = "Primary-4K"
        new_name = "Primary_4K"
        legacy_file = self.history_directory / "sonarr" / f"{legacy_instance_storage_key(old_name)}.json"
        legacy_file.parent.mkdir(parents=True)
        legacy_file.write_text(
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

        old_file = history_manager.get_history_file_path("sonarr", old_name)
        new_file = history_manager.get_history_file_path("sonarr", new_name)
        self.assertFalse(legacy_file.exists())
        self.assertFalse(old_file.exists())
        self.assertTrue(new_file.exists())
        entries = json.loads(new_file.read_text(encoding="utf-8"))
        self.assertEqual([entry["instance_name"] for entry in entries], [new_name, new_name])


if __name__ == "__main__":
    unittest.main()
