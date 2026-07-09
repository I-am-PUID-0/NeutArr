import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "tests"))

from test_support import configure_test_environment

configure_test_environment()

from src.primary import settings_manager
from src.primary.auth import (
    DEFAULT_LOCAL_BYPASS_CIDRS,
    _is_local_ip,
    auth_config,
    normalize_local_bypass_cidrs,
    reset_bypass_caches,
)
from src.primary.web_server import app


class LocalBypassCidrTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()
        settings_manager.save_settings(
            "general",
            {
                "auth_mode": "login",
                "local_access_bypass": False,
                "proxy_auth_bypass": False,
                "local_bypass_cidrs": list(DEFAULT_LOCAL_BYPASS_CIDRS),
            },
        )
        reset_bypass_caches()

    def _api_headers(self):
        return {"X-Api-Key": auth_config.get_api_key()}

    def test_normalize_local_bypass_cidrs_accepts_text_and_deduplicates(self):
        cidrs = normalize_local_bypass_cidrs("10.55.0.0/16\n192.168.1.1/24, 10.55.0.0/16")

        self.assertEqual(cidrs, ["10.55.0.0/16", "192.168.1.0/24"])

    def test_normalize_local_bypass_cidrs_rejects_invalid_values(self):
        with self.assertRaisesRegex(ValueError, "Invalid CIDR range: not-a-cidr"):
            normalize_local_bypass_cidrs(["10.0.0.0/8", "not-a-cidr"])

    def test_general_settings_save_persists_valid_local_bypass_cidrs(self):
        response = self.client.post(
            "/api/settings/general",
            headers=self._api_headers(),
            json={
                "auth_mode": "local_bypass",
                "local_bypass_cidrs": "10.55.0.0/16\n192.168.50.10/32",
            },
        )

        self.assertEqual(response.status_code, 200)
        saved = settings_manager.load_settings("general", use_cache=False)
        self.assertTrue(saved["local_access_bypass"])
        self.assertFalse(saved["proxy_auth_bypass"])
        self.assertEqual(saved["local_bypass_cidrs"], ["10.55.0.0/16", "192.168.50.10/32"])

    def test_configured_local_bypass_cidrs_drive_ip_matching(self):
        settings_manager.save_settings(
            "general",
            {
                "auth_mode": "local_bypass",
                "local_access_bypass": True,
                "proxy_auth_bypass": False,
                "local_bypass_cidrs": ["10.55.0.0/16"],
            },
        )

        self.assertTrue(_is_local_ip("10.55.4.12"))
        self.assertFalse(_is_local_ip("192.168.1.12"))

    def test_general_settings_save_rejects_invalid_local_bypass_cidr(self):
        response = self.client.post(
            "/api/settings/general",
            headers=self._api_headers(),
            json={
                "auth_mode": "local_bypass",
                "local_bypass_cidrs": "10.0.0.0/8\nbad-range",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid CIDR range: bad-range", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
