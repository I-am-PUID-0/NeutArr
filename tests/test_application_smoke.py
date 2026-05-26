import json
import os
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))

from test_support import configure_test_environment

_TEST_CONFIG = configure_test_environment()

from src.primary.web_server import app


class ApplicationSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config.update(TESTING=True)
        cls.client = app.test_client()

    def test_health_endpoint_returns_core_service_payload(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok", "service": "neutarr"})

    def test_ping_alias_uses_same_health_contract(self):
        response = self.client.get("/ping")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok", "service": "neutarr"})

    def test_version_endpoint_returns_plain_text_version(self):
        response = self.client.get("/api/version")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.text.strip())
        self.assertIn("text/plain", response.headers.get("Content-Type", ""))

    def test_auth_status_is_public_and_exposes_expected_shape(self):
        response = self.client.get("/api/auth/status")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        for key in [
            "has_users",
            "instance_storage_key",
            "proxy_auth_bypass",
            "local_access_bypass",
            "setup_skipped",
            "auth_enabled",
        ]:
            self.assertIn(key, payload)

    def test_home_page_redirects_until_setup_is_completed_then_renders_shell(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/setup", response.headers.get("Location", ""))

        setup_response = self.client.post(
            "/api/auth/setup",
            json={
                "username": "tester",
                "password": "StrongPassword123!",
                "confirm_password": "StrongPassword123!",
            },
        )
        self.assertEqual(setup_response.status_code, 201)

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"NeutArr", response.data)

    def test_default_config_files_are_valid_json_objects(self):
        defaults_dir = _REPO_ROOT / "src" / "primary" / "default_configs"
        config_files = sorted(defaults_dir.glob("*.json"))

        self.assertGreater(len(config_files), 0)
        for config_file in config_files:
            with self.subTest(config=config_file.name):
                payload = json.loads(config_file.read_text())
                self.assertIsInstance(payload, dict)

    def test_required_frontend_assets_exist(self):
        for asset in [
            _REPO_ROOT / "frontend" / "templates" / "index.html",
            _REPO_ROOT / "frontend" / "static" / "js" / "new-main.js",
            _REPO_ROOT / "frontend" / "static" / "js" / "settings_forms.js",
            _REPO_ROOT / "frontend" / "static" / "css" / "new-style.css",
        ]:
            with self.subTest(asset=asset.name):
                self.assertTrue(asset.is_file())


if __name__ == "__main__":
    unittest.main()
