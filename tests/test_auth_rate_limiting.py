import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "tests"))

from test_support import configure_test_environment

configure_test_environment()

from src.primary import settings_manager
from src.primary.auth import DEFAULT_LOCAL_BYPASS_CIDRS, auth_config, reset_bypass_caches
from src.primary.rate_limiter import SlidingWindowRateLimiter
from src.primary.routes.auth_routes import (
    LOGIN_RATE_LIMITER,
    PASSWORD_RATE_LIMITER,
    REFRESH_RATE_LIMITER,
    SETUP_RATE_LIMITER,
    VERIFY_RATE_LIMITER,
)
from src.primary.web_server import app


class SlidingWindowRateLimiterTests(unittest.TestCase):
    def test_window_expiration_allows_a_new_attempt(self):
        now = [100.0]
        limiter = SlidingWindowRateLimiter(2, 10, clock=lambda: now[0])

        self.assertTrue(limiter.consume(["client:test"]).allowed)
        self.assertTrue(limiter.consume(["client:test"]).allowed)
        denied = limiter.consume(["client:test"])
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.retry_after, 10)

        now[0] += 10
        self.assertTrue(limiter.consume(["client:test"]).allowed)

    def test_concurrent_attempts_cannot_exceed_limit(self):
        limiter = SlidingWindowRateLimiter(5, 60)
        barrier = Barrier(20)

        def attempt():
            barrier.wait()
            return limiter.consume(["client:test"]).allowed

        with ThreadPoolExecutor(max_workers=20) as executor:
            allowed = list(executor.map(lambda _: attempt(), range(20)))

        self.assertEqual(sum(allowed), 5)

    def test_client_bucket_storage_is_bounded(self):
        limiter = SlidingWindowRateLimiter(2, 60, max_keys=3)

        for index in range(20):
            self.assertTrue(limiter.consume([f"client:{index}"]).allowed)

        self.assertLessEqual(len(limiter._attempts), 3)


class AuthenticationRateLimitingTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()
        if not auth_config.has_users():
            self.assertTrue(auth_config.create_user("rate-test-user", "StrongPassword123!"))
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
            SETUP_RATE_LIMITER,
            REFRESH_RATE_LIMITER,
            VERIFY_RATE_LIMITER,
        ):
            limiter.reset()

    def test_login_limits_rotating_accounts_from_one_client(self):
        with patch("src.primary.routes.auth_routes.verify_login", return_value=False):
            responses = [
                self.client.post(
                    "/api/auth/login",
                    json={"username": f"user-{index}", "password": "incorrect"},
                    environ_base={"REMOTE_ADDR": "192.0.2.10"},
                )
                for index in range(6)
            ]

        self.assertEqual([response.status_code for response in responses[:5]], [401] * 5)
        self.assertEqual(responses[5].status_code, 429)
        self.assertGreaterEqual(int(responses[5].headers["Retry-After"]), 1)

    def test_login_limits_one_account_across_multiple_clients(self):
        with patch("src.primary.routes.auth_routes.verify_login", return_value=False):
            responses = [
                self.client.post(
                    "/api/auth/login",
                    json={"username": "target-user", "password": "incorrect"},
                    environ_base={"REMOTE_ADDR": f"192.0.2.{index + 1}"},
                )
                for index in range(6)
            ]

        self.assertEqual([response.status_code for response in responses[:5]], [401] * 5)
        self.assertEqual(responses[5].status_code, 429)

    def test_successful_login_clears_failure_buckets(self):
        outcomes = [False] * 4 + [True] + [False] * 6
        with patch("src.primary.routes.auth_routes.verify_login", side_effect=outcomes):
            responses = [
                self.client.post(
                    "/api/auth/login",
                    json={"username": "rate-test-user", "password": "candidate"},
                    environ_base={"REMOTE_ADDR": "192.0.2.20"},
                )
                for _ in outcomes
            ]

        self.assertEqual(responses[4].status_code, 200)
        self.assertEqual([response.status_code for response in responses[5:10]], [401] * 5)
        self.assertEqual(responses[10].status_code, 429)

    def test_invalid_setup_tokens_are_rate_limited(self):
        payload = {
            "username": "setup-user",
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!",
            "setup_token": "invalid-setup-token",
        }
        with (
            patch.object(auth_config, "has_users", return_value=False),
            patch("src.primary.routes.auth_routes.ensure_setup_token", return_value=True),
            patch("src.primary.routes.auth_routes.validate_setup_token", return_value=False),
        ):
            responses = [
                self.client.post(
                    "/api/auth/setup",
                    json=payload,
                    environ_base={"REMOTE_ADDR": "192.0.2.30"},
                )
                for _ in range(6)
            ]

        self.assertEqual([response.status_code for response in responses[:5]], [403] * 5)
        self.assertEqual(responses[5].status_code, 429)

    def test_invalid_refresh_tokens_are_rate_limited(self):
        with patch("src.primary.routes.auth_routes.decode_token", return_value=None):
            responses = [
                self.client.post(
                    "/api/auth/refresh",
                    json={"refresh_token": "invalid"},
                    environ_base={"REMOTE_ADDR": "192.0.2.40"},
                )
                for _ in range(11)
            ]

        self.assertEqual([response.status_code for response in responses[:10]], [401] * 10)
        self.assertEqual(responses[10].status_code, 429)

    def test_current_password_checks_share_a_rate_limit(self):
        headers = {"X-Api-Key": auth_config.get_api_key()}
        requests = [
            (
                "/api/auth/change-password",
                {"current_password": "incorrect", "new_password": "AnotherStrongPassword123!"},
            ),
            (
                "/api/auth/change-username",
                {"username": "renamed-user", "password": "incorrect"},
            ),
        ]
        with patch("src.primary.routes.auth_routes.verify_password", return_value=False):
            responses = [
                self.client.post(
                    path,
                    headers=headers,
                    json=payload,
                    environ_base={"REMOTE_ADDR": "192.0.2.45"},
                )
                for path, payload in (requests * 3)
            ]

        self.assertEqual([response.status_code for response in responses[:5]], [401] * 5)
        self.assertEqual(responses[5].status_code, 429)

    def test_invalid_token_verification_is_rate_limited(self):
        with patch("src.primary.routes.auth_routes.decode_token", return_value=None):
            responses = [
                self.client.post(
                    "/api/auth/verify",
                    json={"token": "invalid"},
                    environ_base={"REMOTE_ADDR": "192.0.2.50"},
                )
                for _ in range(31)
            ]

        self.assertEqual([response.status_code for response in responses[:30]], [200] * 30)
        self.assertEqual(responses[30].status_code, 429)


if __name__ == "__main__":
    unittest.main()
