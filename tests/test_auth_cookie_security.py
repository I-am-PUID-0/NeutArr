import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "tests"))

from test_support import configure_test_environment

configure_test_environment()

from src.primary import settings_manager
from src.primary.auth import (
    ACCESS_COOKIE,
    DEFAULT_LOCAL_BYPASS_CIDRS,
    LEGACY_ACCESS_COOKIE,
    LEGACY_REFRESH_COOKIE,
    REFRESH_COOKIE,
    REFRESH_COOKIE_PATH,
    auth_config,
    reset_bypass_caches,
)
from src.primary.routes.auth_routes import LOGIN_RATE_LIMITER, PASSWORD_RATE_LIMITER, REFRESH_RATE_LIMITER
from src.primary.web_server import app


class AuthenticationCookieSecurityTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()
        if not auth_config.has_users():
            self.assertTrue(auth_config.create_user("cookie-test-user", "StrongPassword123!"))
        self.username = next(
            user["username"] for user in auth_config.config["users"] if not user.get("disabled", False)
        )
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
        LOGIN_RATE_LIMITER.reset()
        PASSWORD_RATE_LIMITER.reset()
        REFRESH_RATE_LIMITER.reset()
        self.original_environment = {
            name: os.environ.get(name) for name in ("NEUTARR_SECURE_COOKIES", "TRUSTED_PROXIES")
        }
        os.environ.pop("NEUTARR_SECURE_COOKIES", None)
        os.environ.pop("TRUSTED_PROXIES", None)

    def tearDown(self):
        LOGIN_RATE_LIMITER.reset()
        PASSWORD_RATE_LIMITER.reset()
        REFRESH_RATE_LIMITER.reset()
        for name, value in self.original_environment.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def _login(self, **kwargs):
        with patch("src.primary.routes.auth_routes.verify_login", return_value=True):
            return self.client.post(
                "/api/auth/login",
                json={"username": self.username, "password": "candidate"},
                **kwargs,
            )

    @staticmethod
    def _cookie_header(response, name):
        return next(header for header in response.headers.getlist("Set-Cookie") if header.startswith(f"{name}="))

    def test_browser_session_cookies_are_httponly_and_strict(self):
        response = self._login(environ_base={"REMOTE_ADDR": "127.0.0.1"})

        self.assertEqual(response.status_code, 200)
        access_cookie = self._cookie_header(response, ACCESS_COOKIE)
        refresh_cookie = self._cookie_header(response, REFRESH_COOKIE)
        for cookie in (access_cookie, refresh_cookie):
            self.assertIn("HttpOnly", cookie)
            self.assertIn("SameSite=Strict", cookie)
        self.assertIn("Path=/", access_cookie)
        self.assertIn(f"Path={REFRESH_COOKIE_PATH}", refresh_cookie)
        self.assertNotIn("Secure", access_cookie)
        for legacy_cookie in (LEGACY_ACCESS_COOKIE, LEGACY_REFRESH_COOKIE):
            deletion = self._cookie_header(response, legacy_cookie)
            self.assertIn("Max-Age=0", deletion)
            self.assertIn("HttpOnly", deletion)

    def test_trusted_https_proxy_marks_session_cookies_secure(self):
        os.environ["TRUSTED_PROXIES"] = "10.20.30.0/24"

        response = self._login(
            headers={"X-Forwarded-Proto": "https"},
            environ_base={"REMOTE_ADDR": "10.20.30.5"},
        )

        self.assertIn("Secure", self._cookie_header(response, ACCESS_COOKIE))
        self.assertIn("Secure", self._cookie_header(response, REFRESH_COOKIE))

    def test_untrusted_forwarded_proto_cannot_force_cookie_policy(self):
        os.environ["TRUSTED_PROXIES"] = "10.20.30.0/24"

        response = self._login(
            headers={"X-Forwarded-Proto": "https"},
            environ_base={"REMOTE_ADDR": "192.0.2.10"},
        )

        self.assertNotIn("Secure", self._cookie_header(response, ACCESS_COOKIE))

    def test_secure_cookie_environment_override_is_supported(self):
        os.environ["NEUTARR_SECURE_COOKIES"] = "true"

        response = self._login(environ_base={"REMOTE_ADDR": "127.0.0.1"})

        self.assertIn("Secure", self._cookie_header(response, ACCESS_COOKIE))
        self.assertIn("Secure", self._cookie_header(response, REFRESH_COOKIE))

    def test_cookie_session_authenticates_browser_requests(self):
        self._login(environ_base={"REMOTE_ADDR": "127.0.0.1"})

        response = self.client.get("/api/settings", environ_base={"REMOTE_ADDR": "127.0.0.1"})

        self.assertEqual(response.status_code, 200)

    def test_only_middleware_auth_rejections_request_session_refresh(self):
        unauthenticated_client = app.test_client()
        middleware_response = unauthenticated_client.get(
            "/api/settings",
            environ_base={"REMOTE_ADDR": "192.0.2.25"},
        )

        self._login(environ_base={"REMOTE_ADDR": "127.0.0.1"})
        with patch("src.primary.routes.auth_routes.verify_password", return_value=False):
            endpoint_response = self.client.post(
                "/api/auth/change-password",
                json={
                    "current_password": "incorrect",
                    "new_password": "AnotherStrongPassword123!",
                },
                environ_base={"REMOTE_ADDR": "127.0.0.1"},
            )

        self.assertEqual(middleware_response.status_code, 401)
        self.assertEqual(middleware_response.headers["X-NeutArr-Auth-Required"], "1")
        self.assertEqual(endpoint_response.status_code, 401)
        self.assertNotIn("X-NeutArr-Auth-Required", endpoint_response.headers)

    def test_refresh_cookie_works_without_token_in_request_body(self):
        self._login(environ_base={"REMOTE_ADDR": "127.0.0.1"})
        self.client.delete_cookie(ACCESS_COOKIE, path="/")

        refresh_response = self.client.post(
            "/api/auth/refresh",
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        )
        protected_response = self.client.get(
            "/api/settings",
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        )

        self.assertEqual(refresh_response.status_code, 200)
        self.assertEqual(protected_response.status_code, 200)

    def test_bearer_token_api_clients_remain_supported(self):
        login_response = self._login(environ_base={"REMOTE_ADDR": "127.0.0.1"})
        access_token = login_response.get_json()["access_token"]
        api_client = app.test_client()

        response = api_client.get(
            "/api/settings",
            headers={"Authorization": f"Bearer {access_token}"},
            environ_base={"REMOTE_ADDR": "192.0.2.20"},
        )

        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
