import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_support import configure_test_environment

configure_test_environment()

from src.primary.apps.radarr.api import (
    _build_quality_profile_map,
    _get_movie_file_custom_format_score,
    _is_radarr_upgrade_candidate,
    get_cutoff_unmet_movies,
)


def make_profile(min_format_score=0, cutoff_format_score=0):
    return {
        "id": 1,
        "cutoff": 20,
        "minFormatScore": min_format_score,
        "cutoffFormatScore": cutoff_format_score,
        "items": [
            {"quality": {"id": 10, "name": "HD-720p"}},
            {"quality": {"id": 20, "name": "HD-1080p"}},
        ],
        "formatItems": [
            {"format": {"id": 100, "name": "Preferred"}, "score": 50},
            {"format": {"id": 200, "name": "Avoid"}, "score": -100},
        ],
    }


def make_movie(quality_id=20, custom_format_score=0):
    return {
        "id": 123,
        "title": "Example Movie",
        "monitored": True,
        "hasFile": True,
        "qualityProfileId": 1,
        "movieFile": {
            "quality": {"quality": {"id": quality_id}},
            "customFormatScore": custom_format_score,
        },
    }


class RadarrUpgradeCandidateTests(unittest.TestCase):
    def test_quality_cutoff_unmet_movie_is_upgrade_candidate(self):
        profile = _build_quality_profile_map([make_profile()])[1]
        movie = make_movie(quality_id=10, custom_format_score=0)

        self.assertTrue(_is_radarr_upgrade_candidate(movie, profile))

    def test_quality_met_but_custom_format_score_below_cutoff_is_upgrade_candidate(self):
        profile = _build_quality_profile_map([make_profile(cutoff_format_score=100)])[1]
        movie = make_movie(quality_id=20, custom_format_score=-50)

        self.assertTrue(_is_radarr_upgrade_candidate(movie, profile))

    def test_quality_met_but_custom_format_score_below_minimum_is_upgrade_candidate(self):
        profile = _build_quality_profile_map([make_profile(min_format_score=0)])[1]
        movie = make_movie(quality_id=20, custom_format_score=-10)

        self.assertTrue(_is_radarr_upgrade_candidate(movie, profile))

    def test_quality_and_custom_format_targets_met_is_not_upgrade_candidate(self):
        profile = _build_quality_profile_map([make_profile(min_format_score=0, cutoff_format_score=100)])[1]
        movie = make_movie(quality_id=20, custom_format_score=100)

        self.assertFalse(_is_radarr_upgrade_candidate(movie, profile))

    def test_custom_format_score_can_be_calculated_from_matched_formats(self):
        profile = _build_quality_profile_map([make_profile()])[1]
        movie = make_movie(quality_id=20)
        movie["movieFile"].pop("customFormatScore")
        movie["movieFile"]["customFormats"] = [{"id": 100}, {"id": 200}]

        self.assertEqual(_get_movie_file_custom_format_score(movie, profile), -50)

    def test_quality_profile_accepts_scalar_custom_format_id(self):
        profile = make_profile()
        profile["formatItems"] = [
            {"format": 100, "score": 50},
            {"format": 200, "score": -100},
        ]
        profile_info = _build_quality_profile_map([profile])[1]
        movie = make_movie(quality_id=20)
        movie["movieFile"].pop("customFormatScore")
        movie["movieFile"]["customFormats"] = [{"id": 100}, {"id": 200}]

        self.assertEqual(_get_movie_file_custom_format_score(movie, profile_info), -50)

    def test_quality_profile_accepts_format_id_without_nested_format(self):
        profile = make_profile()
        profile["formatItems"] = [
            {"formatId": 100, "score": 50},
            {"formatId": 200, "score": -100},
        ]
        profile_info = _build_quality_profile_map([profile])[1]
        movie = make_movie(quality_id=20)
        movie["movieFile"].pop("customFormatScore")
        movie["movieFile"]["customFormats"] = [{"id": 100}, {"id": 200}]

        self.assertEqual(_get_movie_file_custom_format_score(movie, profile_info), -50)

    def test_cutoff_check_fetches_movie_file_detail_when_movie_payload_omits_custom_score(self):
        movie = make_movie(quality_id=20)
        movie["movieFile"] = {"id": 456, "quality": {"quality": {"id": 20}}}
        profile = make_profile(cutoff_format_score=100)
        requested_endpoints = []

        def fake_arr_request(api_url, api_key, api_timeout, endpoint, method="GET", data=None):
            requested_endpoints.append(endpoint)
            if endpoint == "movie":
                return [movie]
            if endpoint == "qualityprofile":
                return [profile]
            if endpoint == "moviefile/456":
                return {"id": 456, "customFormatScore": -50}
            return None

        with patch("src.primary.apps.radarr.api.arr_request", side_effect=fake_arr_request):
            candidates = get_cutoff_unmet_movies("http://radarr.example", "apikey", 120, monitored_only=True)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["movieFile"]["customFormatScore"], -50)
        self.assertIn("moviefile/456", requested_endpoints)

    def test_cutoff_check_can_calculate_score_from_detailed_movie_file_formats(self):
        movie = make_movie(quality_id=20)
        movie["movieFile"] = {"id": 456, "quality": {"quality": {"id": 20}}}
        profile = make_profile()

        def fake_arr_request(api_url, api_key, api_timeout, endpoint, method="GET", data=None):
            if endpoint == "movie":
                return [movie]
            if endpoint == "qualityprofile":
                return [profile]
            if endpoint == "moviefile/456":
                return {"id": 456, "customFormats": [{"id": 100}, {"id": 200}]}
            return None

        with patch("src.primary.apps.radarr.api.arr_request", side_effect=fake_arr_request):
            candidates = get_cutoff_unmet_movies("http://radarr.example", "apikey", 120, monitored_only=True)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(
            _get_movie_file_custom_format_score(candidates[0], _build_quality_profile_map([profile])[1]), -50
        )

    def test_cutoff_check_does_not_fetch_movie_file_detail_when_movie_payload_has_custom_score(self):
        movie = make_movie(quality_id=20, custom_format_score=-50)
        movie["movieFile"]["id"] = 456
        profile = make_profile(cutoff_format_score=100)
        requested_endpoints = []

        def fake_arr_request(api_url, api_key, api_timeout, endpoint, method="GET", data=None):
            requested_endpoints.append(endpoint)
            if endpoint == "movie":
                return [movie]
            if endpoint == "qualityprofile":
                return [profile]
            if endpoint == "moviefile/456":
                self.fail("moviefile detail should not be fetched when /movie includes customFormatScore")
            return None

        with patch("src.primary.apps.radarr.api.arr_request", side_effect=fake_arr_request):
            candidates = get_cutoff_unmet_movies("http://radarr.example", "apikey", 120, monitored_only=True)

        self.assertEqual(len(candidates), 1)
        self.assertNotIn("moviefile/456", requested_endpoints)


if __name__ == "__main__":
    unittest.main()
