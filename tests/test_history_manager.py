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
from src.primary.utils.history_utils import build_media_details


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

    def test_failed_history_write_preserves_existing_document_and_mode(self):
        instance_name = "Primary"
        history_file = history_manager.get_history_file_path("sonarr", instance_name)
        history_file.parent.mkdir(parents=True)
        original_entries = [
            {
                "id": 1,
                "date_time": 10,
                "instance_name": instance_name,
                "processed_info": "Existing",
            }
        ]
        history_file.write_text(json.dumps(original_entries), encoding="utf-8")
        history_file.chmod(0o640)

        def fail_after_partial_write(_entries, destination, **_kwargs):
            destination.write('{"partial":')
            raise OSError("simulated interrupted write")

        with patch.object(history_manager.json, "dump", side_effect=fail_after_partial_write):
            result = history_manager.add_history_entry(
                "sonarr",
                {"name": "New", "instance_name": instance_name, "id": 2},
            )

        self.assertIsNone(result)
        self.assertEqual(json.loads(history_file.read_text(encoding="utf-8")), original_entries)
        self.assertEqual(history_file.stat().st_mode & 0o777, 0o640)
        self.assertEqual(list(history_file.parent.glob(f".{history_file.name}.*.tmp")), [])

    def test_add_history_entry_preserves_app_specific_details(self):
        details = {
            "media_type": "Movie",
            "studio": "Example Studio",
            "monitored": False,
        }

        entry = history_manager.add_history_entry(
            "radarr",
            {
                "name": "Example Movie (2026)",
                "instance_name": "Movies",
                "id": 42,
                "details": details,
            },
        )

        self.assertEqual(entry["details"], details)
        stored_entry = json.loads(
            history_manager.get_history_file_path("radarr", "Movies").read_text(encoding="utf-8")
        )[0]
        self.assertEqual(stored_entry["details"], details)

    def test_media_detail_snapshot_uses_an_allowlist(self):
        details = build_media_details(
            "radarr",
            {
                "title": "Example Movie",
                "originalTitle": "Original Example",
                "year": 2026,
                "monitored": False,
                "studio": "Example Studio",
                "genres": ["Drama", "Science Fiction"],
                "movieFile": {
                    "quality": {"quality": {"name": "Bluray-1080p"}},
                    "customFormatScore": 0,
                    "path": "/private/media/movie.mkv",
                },
                "_neutarr_search_context": {
                    "custom_format_target_score": 100,
                    "search_reason": "Custom format score 0 is below target 100",
                },
                "path": "/private/media",
                "apiKey": "must-not-be-captured",
                "overview": "A deliberately long plot summary.",
            },
        )

        self.assertEqual(details["quality"], "Bluray-1080p")
        self.assertEqual(details["custom_format_score"], 0)
        self.assertEqual(details["custom_format_target_score"], 100)
        self.assertEqual(details["search_reason"], "Custom format score 0 is below target 100")
        self.assertFalse(details["monitored"])
        self.assertNotIn("path", details)
        self.assertNotIn("api_key", details)
        self.assertNotIn("overview", details)

    def test_sonarr_detail_snapshot_includes_episode_and_series_context(self):
        details = build_media_details(
            "sonarr",
            {
                "title": "The Episode",
                "seasonNumber": 2,
                "episodeNumber": 4,
                "airDate": "2026-07-28",
                "hasFile": False,
                "episodeFile": {
                    "quality": {"quality": {"name": "WEBDL-1080p"}},
                    "customFormatScore": 125,
                    "qualityCutoffNotMet": True,
                },
                "_neutarr_search_context": {
                    "search_reason": "Quality is below profile cutoff",
                },
                "series": {
                    "title": "Example Series",
                    "year": 2024,
                    "network": "Example Network",
                },
            },
        )

        self.assertEqual(details["series"], "Example Series")
        self.assertEqual(details["episode_title"], "The Episode")
        self.assertEqual(details["season"], 2)
        self.assertEqual(details["episode"], 4)
        self.assertFalse(details["file_available"])
        self.assertEqual(details["quality"], "WEBDL-1080p")
        self.assertEqual(details["custom_format_score"], 125)
        self.assertEqual(
            details["search_reason"],
            "Quality is below profile cutoff",
        )

    def test_sonarr_detail_snapshot_does_not_invent_search_reason(self):
        details = build_media_details(
            "sonarr",
            {
                "title": "The Episode",
                "episodeFile": {
                    "customFormatScore": 0,
                    "qualityCutoffNotMet": False,
                },
            },
        )

        self.assertEqual(details["custom_format_score"], 0)
        self.assertNotIn("search_reason", details)

    def test_add_refuses_to_replace_wholly_malformed_history(self):
        instance_name = "Primary"
        history_file = history_manager.get_history_file_path("radarr", instance_name)
        history_file.parent.mkdir(parents=True)
        malformed_document = '{"incomplete":'
        history_file.write_text(malformed_document, encoding="utf-8")

        result = history_manager.add_history_entry(
            "radarr",
            {"name": "New", "instance_name": instance_name, "id": 2},
        )

        self.assertIsNone(result)
        self.assertEqual(history_file.read_text(encoding="utf-8"), malformed_document)

    def test_get_history_skips_bad_records_without_hiding_valid_entries(self):
        history_file = history_manager.get_history_file_path("lidarr", "Primary")
        history_file.parent.mkdir(parents=True)
        history_file.write_text(
            json.dumps(
                [
                    {
                        "id": 1,
                        "date_time": 10,
                        "instance_name": "Primary",
                        "processed_info": "Older",
                    },
                    {
                        "id": 2,
                        "date_time": "20",
                        "instance_name": "Primary",
                        "processed_info": 123,
                    },
                    "not an object",
                    {"id": 3, "instance_name": "Primary"},
                    {"id": 4, "date_time": "invalid", "instance_name": "Primary"},
                ]
            ),
            encoding="utf-8",
        )

        result = history_manager.get_history("lidarr")

        self.assertEqual(result["total_entries"], 2)
        self.assertEqual([entry["id"] for entry in result["entries"]], [2, 1])
        self.assertEqual(result["entries"][0]["date_time"], 20)

        search_result = history_manager.get_history("lidarr", search_query="123")
        self.assertEqual(search_result["total_entries"], 1)
        self.assertEqual(search_result["entries"][0]["id"], 2)

    def test_untrusted_app_type_cannot_select_a_history_directory(self):
        outside_directory = Path(self.temp_directory.name) / "outside"

        with self.assertRaises(ValueError):
            history_manager.get_history_file_path("../outside", "Primary")

        self.assertFalse(outside_directory.exists())
        self.assertEqual(history_manager.get_history("../outside")["entries"], [])
        self.assertFalse(history_manager.clear_history("../outside"))

    def test_instance_name_with_path_separators_remains_app_scoped(self):
        history_file = history_manager.get_history_file_path(
            "sonarr",
            "../../outside/Primary",
        )
        app_directory = (self.history_directory / "sonarr").resolve()

        self.assertEqual(history_file.parent, app_directory)
        self.assertTrue(history_file.name.endswith(".json"))
        self.assertNotIn("/", history_file.name)

    def test_symlinked_app_directory_cannot_escape_history_root(self):
        outside_directory = Path(self.temp_directory.name) / "outside"
        outside_directory.mkdir()
        self.history_directory.mkdir()
        (self.history_directory / "radarr").symlink_to(
            outside_directory,
            target_is_directory=True,
        )

        self.assertFalse(history_manager.ensure_history_dir())
        with self.assertRaises(ValueError):
            history_manager.get_history_file_path("radarr", "Primary")
        self.assertEqual(list(outside_directory.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
