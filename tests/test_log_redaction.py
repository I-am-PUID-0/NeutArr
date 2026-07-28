import io
import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "tests"))

from test_support import configure_test_environment

configure_test_environment()

from src.primary import auth
from src.primary.apps.whisparr import api as whisparr_api
from src.primary.apps import whisparr_routes
from src.primary.auth import auth_config
from src.primary.log_redaction import (
    REDACTED,
    SensitiveDataFilter,
    redact_sensitive_data,
)
from src.primary.utils.logger import get_logger, logger as neutarr_logger
from src.primary.web_server import KNOWN_LOG_FILES, KNOWN_LOG_PATHS, app


class LogRedactionTests(unittest.TestCase):
    @staticmethod
    def _logged_calls(mock_logger):
        return " ".join(str(log_call) for log_call in mock_logger.method_calls)

    def test_common_credential_shapes_are_redacted_idempotently(self):
        samples = {
            "arr-secret": "{'api_key': 'arr-secret', 'name': 'Main'}",
            "password-secret": '{"password":"password-secret"}',
            "current-password-secret": '{"current_password":"current-password-secret"}',
            "access-secret": "access_token=access-secret",
            "refresh-secret": "'refresh_token': 'refresh-secret'",
            "setup-secret": "'setup_token': 'setup-secret'",
            "client-secret": '{"client_secret":"client-secret"}',
            "bearer-secret": "Authorization: Bearer bearer-secret",
            "cookie-secret": "Cookie: session=cookie-secret; theme=dark",
            "query-secret": "GET /api/items?apikey=query-secret&page=1",
            "userinfo-secret": "https://user:userinfo-secret@example.invalid/api",
            "eyJheader.eyJpayload.signature": "token eyJheader.eyJpayload.signature",
        }

        for secret, source in samples.items():
            with self.subTest(source=source):
                redacted = redact_sensitive_data(source)
                self.assertNotIn(secret, redacted)
                self.assertIn(REDACTED, redacted)
                self.assertEqual(redact_sensitive_data(redacted), redacted)

    def test_documented_first_run_token_message_remains_available(self):
        bootstrap_message = "First-run setup token: one-time-bootstrap-value"

        self.assertEqual(redact_sensitive_data(bootstrap_message), bootstrap_message)

    def test_logging_filter_redacts_formatted_messages_and_tracebacks(self):
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        handler.addFilter(SensitiveDataFilter())
        handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        test_logger = logging.Logger("redaction-test")
        test_logger.addHandler(handler)

        try:
            raise RuntimeError("request failed with password=traceback-secret")
        except RuntimeError:
            test_logger.exception(
                "Saving settings: %s",
                {"api_key": "message-secret", "name": "Main"},
            )

        rendered = output.getvalue()
        self.assertNotIn("message-secret", rendered)
        self.assertNotIn("traceback-secret", rendered)
        self.assertGreaterEqual(rendered.count(REDACTED), 2)
        self.assertIn("RuntimeError", rendered)

    def test_neutarr_console_and_file_handlers_install_the_filter(self):
        for configured_logger in (neutarr_logger, get_logger("sonarr")):
            self.assertTrue(configured_logger.handlers)
            for handler in configured_logger.handlers:
                self.assertTrue(any(isinstance(existing, SensitiveDataFilter) for existing in handler.filters))

    def test_invalid_trusted_proxy_configuration_is_not_logged(self):
        invalid_proxy_value = "192.0.2.0/24,proxy-config-secret"
        mock_logger = MagicMock()

        with (
            patch.dict(os.environ, {auth.TRUSTED_PROXIES_ENV: invalid_proxy_value}),
            patch.object(auth, "logger", mock_logger),
        ):
            self.assertEqual(auth._get_trusted_proxy_networks(), [])

        logged = self._logged_calls(mock_logger)
        self.assertNotIn(invalid_proxy_value, logged)
        self.assertNotIn("proxy-config-secret", logged)
        self.assertIn("Invalid trusted proxy configuration", logged)

    def test_whisparr_request_logs_omit_url_exception_and_response_body(self):
        api_url = "https://user:url-password-secret@whisparr.example.invalid"
        api_key = "whisparr-api-secret"
        response_body = "upstream-response-secret"
        response = MagicMock()
        response.status_code = 500
        response.text = response_body
        response.raise_for_status.side_effect = whisparr_api.requests.exceptions.HTTPError(
            f"request failed for {api_url}"
        )
        mock_logger = MagicMock()

        with (
            patch.object(whisparr_api, "whisparr_logger", mock_logger),
            patch.object(whisparr_api, "get_ssl_verify_setting", return_value=True),
            patch.object(whisparr_api.session, "get", return_value=response),
        ):
            self.assertIsNone(whisparr_api.arr_request(api_url, api_key, 10, "system/status"))

        logged = self._logged_calls(mock_logger)
        for secret in (api_url, "url-password-secret", api_key, response_body):
            self.assertNotIn(secret, logged)
        self.assertIn("response body omitted", logged)

    def test_whisparr_connection_logs_omit_upstream_version(self):
        upstream_version = "2.0-upstream-version-secret"
        mock_logger = MagicMock()

        with (
            patch.object(whisparr_api, "whisparr_logger", mock_logger),
            patch.object(whisparr_api, "arr_request", return_value={"version": upstream_version}),
        ):
            self.assertTrue(
                whisparr_api.check_connection(
                    "https://whisparr.example.invalid",
                    "whisparr-api-secret",
                    10,
                )
            )

        logged = self._logged_calls(mock_logger)
        self.assertNotIn(upstream_version, logged)
        self.assertIn("compatible Whisparr V2 API", logged)

    def test_whisparr_version_fallback_log_omits_instance_settings(self):
        instance_name = "private-instance-name"
        api_url = "https://user:url-password-secret@whisparr.example.invalid"
        api_key = "whisparr-api-secret"
        first_response = MagicMock(status_code=404)
        second_response = MagicMock(status_code=200)
        second_response.json.return_value = {"version": "2.0.0"}
        mock_logger = MagicMock()

        with (
            app.test_request_context("/api/whisparr/versions"),
            patch.object(
                whisparr_routes,
                "load_settings",
                return_value={
                    "instances": [
                        {
                            "name": instance_name,
                            "api_url": api_url,
                            "api_key": api_key,
                            "enabled": True,
                        }
                    ]
                },
            ),
            patch.object(
                whisparr_routes.requests,
                "get",
                side_effect=[first_response, second_response],
            ),
            patch.object(whisparr_routes, "whisparr_logger", mock_logger),
        ):
            response = whisparr_routes.get_versions()

        self.assertTrue(response.get_json()["results"][0]["success"])
        logged = self._logged_calls(mock_logger)
        for secret in (instance_name, api_url, "url-password-secret", api_key):
            self.assertNotIn(secret, logged)
        self.assertIn("trying v3 path", logged)

    def test_whisparr_log_response_redacts_historical_file_content(self):
        app.config.update(TESTING=True)
        client = app.test_client()
        api_key = "log-response-auth-key"

        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "whisparr.log"
            log_path.write_text("api_key=historic-whisparr-secret\nnormal diagnostic\n")

            with (
                patch.object(auth_config, "get_api_key", return_value=api_key),
                patch.dict(whisparr_routes.APP_LOG_FILES, {"whisparr": log_path}),
            ):
                response = client.get(
                    "/api/whisparr/logs",
                    headers={"X-Api-Key": api_key},
                    environ_base={"REMOTE_ADDR": "192.0.2.40"},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        content = response.get_json()["logs"]
        self.assertNotIn("historic-whisparr-secret", content)
        self.assertIn("api_key=[REDACTED]", content)
        self.assertIn("normal diagnostic", content)

    def test_sse_log_response_redacts_historical_file_content(self):
        app.config.update(TESTING=True)
        client = app.test_client()
        api_key = "sse-log-auth-key"

        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "neutarr.log"
            log_path.write_text("Authorization: Bearer historic-sse-secret\n")

            with (
                patch.object(auth_config, "get_api_key", return_value=api_key),
                patch.dict(KNOWN_LOG_FILES, {"system": log_path}, clear=True),
                patch.dict(KNOWN_LOG_PATHS, {"system": log_path}, clear=True),
            ):
                response = client.get(
                    "/logs?app=system",
                    headers={"X-Api-Key": api_key},
                    environ_base={"REMOTE_ADDR": "192.0.2.41"},
                    buffered=False,
                )
                chunks = []
                try:
                    for _ in range(2):
                        chunk = next(response.response)
                        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
                finally:
                    response.close()

        content = "".join(chunks)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertNotIn("historic-sse-secret", content)
        self.assertIn(f"Authorization: {REDACTED}", content)


if __name__ == "__main__":
    unittest.main()
