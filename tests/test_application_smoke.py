import json
import os
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))

from test_support import configure_test_environment

_TEST_CONFIG = configure_test_environment()

from src.primary import auth as auth_module
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
            "setup_token_required",
            "auth_enabled",
        ]:
            self.assertIn(key, payload)

    def test_auth_setup_requires_the_first_run_token(self):
        payload = {
            "username": "tester",
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!",
        }

        missing_response = self.client.post("/api/auth/setup", json=payload)
        self.assertEqual(missing_response.status_code, 403)

        payload["setup_token"] = "incorrect-first-run-token"
        invalid_response = self.client.post("/api/auth/setup", json=payload)
        self.assertEqual(invalid_response.status_code, 403)

    def test_auth_config_allows_only_one_concurrent_first_user(self):
        isolated_users_file = _TEST_CONFIG / "isolated-users.json"
        manager = auth_module.AuthConfigManager()
        barrier = threading.Barrier(2)
        results = []

        def create_user(username):
            barrier.wait()
            results.append(manager.create_user(username, "StrongPassword123!"))

        with patch.object(auth_module, "USERS_FILE", isolated_users_file):
            threads = [
                threading.Thread(target=create_user, args=("first",)),
                threading.Thread(target=create_user, args=("second",)),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        self.assertEqual(sorted(results), [False, True])
        persisted = json.loads(isolated_users_file.read_text())
        self.assertEqual(len(persisted["users"]), 1)

    def test_auth_skip_setup_endpoint_cannot_open_the_api(self):
        response = self.client.post("/api/auth/skip-setup")

        self.assertEqual(response.status_code, 401)
        self.assertTrue(response.get_json()["setup_required"])

        settings_response = self.client.get("/api/settings")
        self.assertEqual(settings_response.status_code, 401)
        self.assertTrue(settings_response.get_json()["setup_required"])

    def test_home_page_redirects_until_setup_is_completed_then_renders_shell(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/setup", response.headers.get("Location", ""))

        setup_response = self.client.post(
            "/api/auth/setup",
            json={
                "setup_token": os.environ["NEUTARR_SETUP_TOKEN"],
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

    def test_default_app_instances_start_disabled(self):
        defaults_dir = _REPO_ROOT / "src" / "primary" / "default_configs"

        for app_name in ("sonarr", "radarr", "lidarr", "readarr", "whisparr", "eros"):
            with self.subTest(app=app_name):
                payload = json.loads((defaults_dir / f"{app_name}.json").read_text())
                self.assertGreater(len(payload["instances"]), 0)
                self.assertTrue(all(instance.get("enabled") is False for instance in payload["instances"]))

    def test_generated_setup_token_is_owner_only_and_consumable(self):
        token_file = _TEST_CONFIG / "generated-setup-token"
        configured_token = os.environ.pop("NEUTARR_SETUP_TOKEN")
        try:
            with patch.object(auth_module, "SETUP_TOKEN_FILE", token_file):
                token = auth_module.ensure_setup_token()

                self.assertGreaterEqual(len(token), auth_module.MIN_SETUP_TOKEN_LENGTH)
                self.assertEqual(token_file.read_text().strip(), token)
                self.assertEqual(token_file.stat().st_mode & 0o777, 0o600)

                auth_module.consume_setup_token()
                self.assertFalse(token_file.exists())
        finally:
            os.environ["NEUTARR_SETUP_TOKEN"] = configured_token

    def test_required_frontend_assets_exist(self):
        for asset in [
            _REPO_ROOT / "frontend" / "templates" / "index.html",
            _REPO_ROOT / "frontend" / "static" / "js" / "new-main.js",
            _REPO_ROOT / "frontend" / "static" / "js" / "settings_forms.js",
            _REPO_ROOT / "frontend" / "static" / "css" / "new-style.css",
            _REPO_ROOT / "frontend" / "static" / "css" / "redesign.css",
        ]:
            with self.subTest(asset=asset.name):
                self.assertTrue(asset.is_file())


if __name__ == "__main__":
    unittest.main()
