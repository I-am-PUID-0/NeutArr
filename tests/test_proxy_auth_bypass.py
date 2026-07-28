import os
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
    PROXY_AUTH_HEADER_ENV,
    TRUSTED_PROXIES_ENV,
    auth_config,
    reset_bypass_caches,
)
from src.primary.web_server import app


class ProxyAuthBypassTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()
        self.original_environment = {
            name: os.environ.get(name) for name in (PROXY_AUTH_HEADER_ENV, TRUSTED_PROXIES_ENV)
        }
        if not auth_config.has_users():
            self.assertTrue(auth_config.create_user("proxy-test-user", "StrongPassword123!"))
        self._set_auth_mode("login")

    def tearDown(self):
        self._set_auth_mode("login")
        for name, value in self.original_environment.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def _set_auth_mode(self, mode):
        settings_manager.save_settings(
            "general",
            {
                "auth_mode": mode,
                "local_access_bypass": mode == "local_bypass",
                "proxy_auth_bypass": mode == "no_login",
                "local_bypass_cidrs": list(DEFAULT_LOCAL_BYPASS_CIDRS),
            },
        )
        reset_bypass_caches()

    def _configure_proxy_auth(self):
        os.environ[TRUSTED_PROXIES_ENV] = "10.20.30.0/24"
        os.environ[PROXY_AUTH_HEADER_ENV] = "Remote-User"
        self._set_auth_mode("no_login")

    def test_status_never_discloses_api_key(self):
        self._configure_proxy_auth()

        response = self.client.get(
            "/api/auth/status",
            headers={"Remote-User": "authenticated-user"},
            environ_base={"REMOTE_ADDR": "10.20.30.5"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["proxy_request_authenticated"])
        self.assertNotIn("frontend_api_key", payload)
        self.assertNotIn(auth_config.get_api_key(), response.get_data(as_text=True))

    def test_trusted_proxy_with_identity_header_can_access_api(self):
        self._configure_proxy_auth()

        response = self.client.get(
            "/api/stats",
            headers={"Remote-User": "authenticated-user"},
            environ_base={"REMOTE_ADDR": "10.20.30.5"},
        )

        self.assertEqual(response.status_code, 200)

    def test_trusted_proxy_can_explicitly_manage_api_key(self):
        self._configure_proxy_auth()

        response = self.client.get(
            "/api/auth/apikey",
            headers={"Remote-User": "authenticated-user"},
            environ_base={"REMOTE_ADDR": "10.20.30.5"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["api_key"], auth_config.get_api_key())

    def test_spoofed_identity_header_from_untrusted_source_is_rejected(self):
        self._configure_proxy_auth()

        response = self.client.get(
            "/api/stats",
            headers={"Remote-User": "spoofed-user"},
            environ_base={"REMOTE_ADDR": "203.0.113.10"},
        )

        self.assertEqual(response.status_code, 401)

    def test_trusted_proxy_without_identity_header_is_rejected(self):
        self._configure_proxy_auth()

        response = self.client.get("/api/stats", environ_base={"REMOTE_ADDR": "10.20.30.5"})

        self.assertEqual(response.status_code, 401)

    def test_proxy_mode_without_trust_configuration_fails_closed(self):
        os.environ.pop(TRUSTED_PROXIES_ENV, None)
        os.environ.pop(PROXY_AUTH_HEADER_ENV, None)
        self._set_auth_mode("no_login")

        api_response = self.client.get("/api/stats", environ_base={"REMOTE_ADDR": "127.0.0.1"})
        login_response = self.client.get("/login", environ_base={"REMOTE_ADDR": "127.0.0.1"})

        self.assertEqual(api_response.status_code, 401)
        self.assertEqual(login_response.status_code, 200)

    def test_local_bypass_authorizes_eligible_api_request_without_api_key(self):
        self._set_auth_mode("local_bypass")

        local_response = self.client.get("/api/stats", environ_base={"REMOTE_ADDR": "192.168.1.25"})
        remote_response = self.client.get("/api/stats", environ_base={"REMOTE_ADDR": "203.0.113.10"})
        api_key_response = self.client.get(
            "/api/auth/apikey",
            environ_base={"REMOTE_ADDR": "192.168.1.25"},
        )

        self.assertEqual(local_response.status_code, 200)
        self.assertEqual(remote_response.status_code, 401)
        self.assertEqual(api_key_response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
