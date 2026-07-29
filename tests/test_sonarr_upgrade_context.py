import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_support import configure_test_environment

configure_test_environment()

from src.primary.apps.sonarr.upgrade import (
    _add_sonarr_search_context,
    _sonarr_search_reason,
)


class SonarrUpgradeContextTests(unittest.TestCase):
    def test_quality_cutoff_flag_produces_specific_search_reason(self):
        self.assertEqual(
            _sonarr_search_reason({"episodeFile": {"qualityCutoffNotMet": True}}),
            "Quality is below profile cutoff",
        )

    def test_cutoff_record_without_quality_flag_uses_truthful_generic_reason(self):
        self.assertEqual(
            _sonarr_search_reason({"qualityCutoffNotMet": False}),
            "Current file does not meet the Sonarr profile cutoff",
        )

    def test_search_context_does_not_modify_sonarr_api_object(self):
        episode_details = {"id": 42, "title": "The Episode"}

        enriched = _add_sonarr_search_context(
            episode_details,
            {"qualityCutoffNotMet": True},
        )

        self.assertNotIn("_neutarr_search_context", episode_details)
        self.assertEqual(
            enriched["_neutarr_search_context"],
            {"search_reason": "Quality is below profile cutoff"},
        )


if __name__ == "__main__":
    unittest.main()
