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

from src.primary import stateful_manager
from src.primary.instance_storage import (
    instance_storage_key,
    legacy_instance_storage_key,
)


class InstanceStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.stateful_directory = Path(self.temp_directory.name) / "stateful"
        self.path_patch = patch.object(
            stateful_manager,
            "STATEFUL_DIR",
            self.stateful_directory,
        )
        self.path_patch.start()

    def tearDown(self):
        self.path_patch.stop()
        self.temp_directory.cleanup()

    def test_storage_keys_distinguish_legacy_filename_collisions(self):
        first_name = "Primary-4K"
        second_name = "Primary_4K"

        self.assertEqual(
            legacy_instance_storage_key(first_name),
            legacy_instance_storage_key(second_name),
        )
        self.assertNotEqual(
            instance_storage_key(first_name),
            instance_storage_key(second_name),
        )
        self.assertEqual(instance_storage_key("Default"), "Default")

    def test_legacy_state_is_seeded_for_each_configured_collision(self):
        first_name = "Primary-4K"
        second_name = "Primary_4K"
        legacy_file = self.stateful_directory / "sonarr" / f"{legacy_instance_storage_key(first_name)}.json"
        legacy_file.parent.mkdir(parents=True)
        legacy_file.write_text(
            json.dumps({"processed_ids": ["100"], "last_updated": 1}),
            encoding="utf-8",
        )
        settings = {
            "instances": [
                {"name": first_name},
                {"name": second_name},
            ]
        }

        with patch.object(stateful_manager, "load_settings", return_value=settings):
            self.assertEqual(
                stateful_manager.get_processed_ids("sonarr", first_name),
                {"100"},
            )

        first_file = stateful_manager.get_stateful_file_path("sonarr", first_name)
        second_file = stateful_manager.get_stateful_file_path("sonarr", second_name)
        self.assertFalse(legacy_file.exists())
        self.assertTrue(first_file.exists())
        self.assertTrue(second_file.exists())

        self.assertTrue(stateful_manager.add_processed_id("sonarr", first_name, "200"))
        self.assertEqual(stateful_manager.get_processed_ids("sonarr", first_name), {"100", "200"})
        self.assertEqual(stateful_manager.get_processed_ids("sonarr", second_name), {"100"})


if __name__ == "__main__":
    unittest.main()
