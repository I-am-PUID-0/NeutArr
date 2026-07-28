import json
import stat
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_support import configure_test_environment

configure_test_environment()

from src.primary import stateful_manager


class StatefulPersistenceTests(unittest.TestCase):
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

    def test_concurrent_processed_id_updates_preserve_every_id(self):
        instance_name = "Concurrent"
        state_file = stateful_manager.get_stateful_file_path("sonarr", instance_name)
        stateful_manager._atomic_write_json(
            state_file,
            {"processed_ids": [], "last_updated": 1},
        )
        media_ids = [str(media_id) for media_id in range(24)]
        original_json_load = json.load

        def delayed_json_load(file_handle):
            data = original_json_load(file_handle)
            time.sleep(0.005)
            return data

        with patch.object(stateful_manager.json, "load", side_effect=delayed_json_load):
            with ThreadPoolExecutor(max_workers=12) as executor:
                results = list(
                    executor.map(
                        lambda media_id: stateful_manager.add_processed_id(
                            "sonarr",
                            instance_name,
                            media_id,
                        ),
                        media_ids,
                    )
                )

        self.assertTrue(all(results))
        self.assertEqual(
            stateful_manager.get_processed_ids("sonarr", instance_name),
            set(media_ids),
        )

    def test_failed_atomic_write_preserves_existing_state_and_mode(self):
        instance_name = "Default"
        state_file = stateful_manager.get_stateful_file_path("sonarr", instance_name)
        original_state = {"processed_ids": ["existing"], "last_updated": 1}
        stateful_manager._atomic_write_json(state_file, original_state)
        state_file.chmod(0o640)

        def fail_after_partial_write(data, file_handle, **kwargs):
            file_handle.write('{"processed_ids": ["truncated"]')
            raise OSError("simulated write failure")

        with patch.object(stateful_manager.json, "dump", side_effect=fail_after_partial_write):
            self.assertFalse(
                stateful_manager.add_processed_id(
                    "sonarr",
                    instance_name,
                    "new",
                )
            )

        self.assertEqual(
            json.loads(state_file.read_text(encoding="utf-8")),
            original_state,
        )
        self.assertEqual(stat.S_IMODE(state_file.stat().st_mode), 0o640)
        self.assertEqual(list(state_file.parent.glob(f".{state_file.name}.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
