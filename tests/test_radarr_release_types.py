import datetime
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from src.primary.apps.radarr.missing import movie_has_selected_release_date, normalize_release_types


class RadarrReleaseTypeTests(unittest.TestCase):
    def test_uses_legacy_single_release_type_when_array_is_absent(self):
        self.assertEqual(normalize_release_types({"release_type": "cinema"}), ["cinema"])

    def test_accepts_multiple_release_types_in_configured_order(self):
        settings = {"release_types": ["digital", "physical", "cinema"]}

        self.assertEqual(normalize_release_types(settings), ["digital", "physical", "cinema"])

    def test_accepts_comma_separated_release_type_strings(self):
        settings = {"release_types": "digital, physical, cinema"}

        self.assertEqual(normalize_release_types(settings), ["digital", "physical", "cinema"])

    def test_release_types_array_takes_precedence_over_legacy_release_type(self):
        settings = {"release_type": "physical", "release_types": ["digital"]}

        self.assertEqual(normalize_release_types(settings), ["digital"])

    def test_ignores_invalid_and_duplicate_release_types(self):
        settings = {"release_types": ["digital", "invalid", "digital", "physical"]}

        self.assertEqual(normalize_release_types(settings), ["digital", "physical"])

    def test_defaults_to_physical_when_no_valid_release_types_are_configured(self):
        self.assertEqual(normalize_release_types({"release_types": ["invalid"]}), ["physical"])

    def test_movie_is_eligible_when_any_selected_release_date_has_passed(self):
        now = datetime.datetime(2026, 5, 26, tzinfo=datetime.timezone.utc)
        movie = {
            "title": "Example Movie",
            "digitalRelease": "2026-05-01T00:00:00Z",
            "physicalRelease": "2026-06-01T00:00:00Z",
        }

        self.assertTrue(movie_has_selected_release_date(movie, ["digital", "physical"], now))

    def test_movie_is_not_eligible_when_selected_release_dates_are_future_or_missing(self):
        now = datetime.datetime(2026, 5, 26, tzinfo=datetime.timezone.utc)
        movie = {
            "title": "Example Movie",
            "digitalRelease": "2026-05-01T00:00:00Z",
            "physicalRelease": "2026-06-01T00:00:00Z",
        }

        self.assertFalse(movie_has_selected_release_date(movie, ["physical", "cinema"], now))

    def test_movie_is_eligible_when_cinema_is_the_only_past_selected_date(self):
        now = datetime.datetime(2026, 5, 26, tzinfo=datetime.timezone.utc)
        movie = {
            "title": "Example Movie",
            "inCinemas": "2026-05-01T00:00:00Z",
            "digitalRelease": "2026-06-01T00:00:00Z",
            "physicalRelease": "2026-07-01T00:00:00Z",
        }

        self.assertTrue(movie_has_selected_release_date(movie, ["cinema"], now))

    def test_movie_without_any_selected_release_dates_is_not_eligible(self):
        now = datetime.datetime(2026, 5, 26, tzinfo=datetime.timezone.utc)
        movie = {"title": "Example Movie", "digitalRelease": "2026-05-01T00:00:00Z"}

        self.assertFalse(movie_has_selected_release_date(movie, ["physical", "cinema"], now))

    def test_release_date_timezone_offsets_are_supported(self):
        now = datetime.datetime(2026, 5, 26, 12, 0, tzinfo=datetime.timezone.utc)
        movie = {"title": "Example Movie", "digitalRelease": "2026-05-26T08:00:00-04:00"}

        self.assertFalse(movie_has_selected_release_date(movie, ["digital"], now))

    def test_invalid_release_dates_are_ignored(self):
        now = datetime.datetime(2026, 5, 26, tzinfo=datetime.timezone.utc)
        movie = {
            "title": "Example Movie",
            "digitalRelease": "not-a-date",
            "physicalRelease": "2026-05-01T00:00:00Z",
        }

        self.assertTrue(movie_has_selected_release_date(movie, ["digital", "physical"], now))


if __name__ == "__main__":
    unittest.main()
