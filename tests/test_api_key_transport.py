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

from src.primary.auth import auth_config
from src.primary.web_server import app


class ApiKeyTransportTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()
        self.api_key = "test-api-key-that-must-stay-out-of-urls"

    def test_api_key_header_authenticates_api_requests(self):
        with patch.object(auth_config, "get_api_key", return_value=self.api_key):
            response = self.client.get(
                "/api/settings",
                headers={"X-Api-Key": self.api_key},
                environ_base={"REMOTE_ADDR": "192.0.2.10"},
            )

        self.assertEqual(response.status_code, 200)

    def test_api_key_query_parameter_is_rejected_without_echoing_secret(self):
        response = self.client.get(
            "/api/settings",
            query_string={"apikey": self.api_key},
            environ_base={"REMOTE_ADDR": "192.0.2.10"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["code"], "api_key_query_unsupported")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertNotIn(self.api_key, response.get_data(as_text=True))

    def test_query_parameter_is_rejected_even_with_valid_header(self):
        response = self.client.get(
            "/api/settings",
            query_string={"apikey": "remove-this-value"},
            headers={"X-Api-Key": self.api_key},
            environ_base={"REMOTE_ADDR": "192.0.2.10"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["code"], "api_key_query_unsupported")

    def test_public_routes_also_reject_api_key_query_parameters(self):
        response = self.client.get(
            "/api/health",
            query_string={"apikey": ""},
            environ_base={"REMOTE_ADDR": "192.0.2.10"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["code"], "api_key_query_unsupported")


if __name__ == "__main__":
    unittest.main()
