import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import jwt

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
    JWT_ALGORITHM,
    auth_config,
    reset_bypass_caches,
)
from src.primary.routes.auth_routes import (
    LOGIN_RATE_LIMITER,
    PASSWORD_RATE_LIMITER,
    REFRESH_RATE_LIMITER,
    VERIFY_RATE_LIMITER,
)
from src.primary.web_server import app


class AuthenticationSessionRevocationTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.username = "session-test-user"
        self.jwt_secret = "session-revocation-test-secret-with-safe-hmac-length"
        isolated_config = {
            "jwt_secret": self.jwt_secret,
            "api_key": "session-revocation-api-key",
            "users": [
                {
                    "username": self.username,
                    "password": "test-password-hash",
                    "disabled": False,
                    "session_version": 0,
                }
            ],
        }
        self.config_patch = patch.object(auth_config, "_config", isolated_config)
        self.save_patch = patch.object(auth_config, "_save", return_value=True)
        self.config_patch.start()
        self.save_patch.start()
        self.addCleanup(self.config_patch.stop)
        self.addCleanup(self.save_patch.stop)

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
        self._reset_limiters()

    def tearDown(self):
        self._reset_limiters()

    @staticmethod
    def _reset_limiters():
        for limiter in (
            LOGIN_RATE_LIMITER,
            PASSWORD_RATE_LIMITER,
            REFRESH_RATE_LIMITER,
            VERIFY_RATE_LIMITER,
        ):
            limiter.reset()

    def _login(self, client):
        with patch("src.primary.routes.auth_routes.verify_login", return_value=True):
            response = client.post(
                "/api/auth/login",
                json={"username": self.username, "password": "candidate"},
                environ_base={"REMOTE_ADDR": "192.0.2.10"},
            )
        self.assertEqual(response.status_code, 200)
        return response

    @staticmethod
    def _get_protected(client, access_token):
        return client.get(
            "/api/settings",
            headers={"Authorization": f"Bearer {access_token}"},
            environ_base={"REMOTE_ADDR": "192.0.2.20"},
        )

    def test_logout_revokes_previously_issued_access_and_refresh_tokens(self):
        browser_client = app.test_client()
        login_response = self._login(browser_client)
        access_token = login_response.get_json()["access_token"]
        refresh_token = login_response.get_json()["refresh_token"]

        self.assertEqual(self._get_protected(app.test_client(), access_token).status_code, 200)

        expired_access_token = jwt.encode(
            {
                "sub": self.username,
                "type": "access",
                "session_version": 0,
                "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            },
            self.jwt_secret,
            algorithm=JWT_ALGORITHM,
        )
        browser_client.set_cookie(ACCESS_COOKIE, expired_access_token, path="/")

        logout_response = browser_client.post(
            "/api/auth/logout",
            environ_base={"REMOTE_ADDR": "192.0.2.10"},
        )

        self.assertEqual(logout_response.status_code, 200)
        self.assertEqual(auth_config.get_session_version(self.username), 1)
        self.assertEqual(self._get_protected(app.test_client(), access_token).status_code, 401)

        refresh_response = app.test_client().post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
            environ_base={"REMOTE_ADDR": "192.0.2.20"},
        )
        self.assertEqual(refresh_response.status_code, 401)
        self.assertEqual(refresh_response.get_json()["error"], "Invalid or expired refresh token")

    def test_password_change_revokes_other_sessions_and_refreshes_current_one(self):
        current_client = app.test_client()
        other_client = app.test_client()
        current_login = self._login(current_client).get_json()
        other_login = self._login(other_client).get_json()

        with patch("src.primary.routes.auth_routes.verify_password", return_value=True):
            password_response = current_client.post(
                "/api/auth/change-password",
                json={
                    "current_password": "candidate",
                    "new_password": "AnotherStrongPassword123!",
                },
                environ_base={"REMOTE_ADDR": "192.0.2.10"},
            )

        self.assertEqual(password_response.status_code, 200)
        self.assertEqual(auth_config.get_session_version(self.username), 1)
        self.assertEqual(
            self._get_protected(app.test_client(), current_login["access_token"]).status_code,
            401,
        )
        self.assertEqual(
            self._get_protected(app.test_client(), other_login["access_token"]).status_code,
            401,
        )

        other_refresh = app.test_client().post(
            "/api/auth/refresh",
            json={"refresh_token": other_login["refresh_token"]},
            environ_base={"REMOTE_ADDR": "192.0.2.20"},
        )
        self.assertEqual(other_refresh.status_code, 401)

        current_session = current_client.get(
            "/api/settings",
            environ_base={"REMOTE_ADDR": "192.0.2.10"},
        )
        self.assertEqual(current_session.status_code, 200)
        replacement_payload = jwt.decode(
            password_response.get_json()["access_token"],
            self.jwt_secret,
            algorithms=[JWT_ALGORITHM],
        )
        self.assertEqual(replacement_payload["session_version"], 1)

    def test_legacy_tokens_are_valid_until_the_first_session_revocation(self):
        legacy_access_token = jwt.encode(
            {
                "sub": self.username,
                "type": "access",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            },
            self.jwt_secret,
            algorithm=JWT_ALGORITHM,
        )

        self.assertEqual(self._get_protected(app.test_client(), legacy_access_token).status_code, 200)

        logout_response = app.test_client().post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {legacy_access_token}"},
            environ_base={"REMOTE_ADDR": "192.0.2.20"},
        )

        self.assertEqual(logout_response.status_code, 200)
        self.assertEqual(self._get_protected(app.test_client(), legacy_access_token).status_code, 401)


if __name__ == "__main__":
    unittest.main()
