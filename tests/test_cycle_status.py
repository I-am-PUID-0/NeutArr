import sys
import unittest
from pathlib import Path
from unittest.mock import patch


_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))

from test_support import configure_test_environment

configure_test_environment()

from primary import background
from primary import web_server

api_cycle_status = web_server.api_cycle_status
app = web_server.app


class CycleStatusTests(unittest.TestCase):
    def setUp(self):
        with background.cycle_status_lock:
            background.cycle_status.clear()

    def tearDown(self):
        with background.cycle_status_lock:
            background.cycle_status.clear()

    def test_snapshot_reports_authoritative_remaining_seconds(self):
        with patch.object(background.time, "time", return_value=100.25):
            background._set_cycle_status(
                "sonarr",
                "waiting",
                next_cycle_at=131.0,
                interval_seconds=30,
            )
            snapshot = background.get_cycle_status_snapshot()

        self.assertEqual(snapshot["server_time"], 100.25)
        self.assertEqual(
            snapshot["cycles"]["sonarr"],
            {
                "state": "waiting",
                "next_cycle_at": 131.0,
                "interval_seconds": 30,
                "remaining_seconds": 31,
            },
        )

    def test_wait_publishes_retry_deadline_before_blocking(self):
        with (
            patch.object(background.time, "time", return_value=200.0),
            patch.object(background.stop_event, "wait") as wait,
        ):
            background._wait_with_cycle_status(
                "radarr",
                60,
                state="retrying",
                reason="Settings unavailable",
            )

        wait.assert_called_once_with(60)
        self.assertEqual(
            background.cycle_status["radarr"],
            {
                "state": "retrying",
                "next_cycle_at": 260.0,
                "interval_seconds": 60,
                "reason": "Settings unavailable",
            },
        )

    def test_reset_request_preserves_the_configured_interval(self):
        background._set_cycle_status(
            "lidarr",
            "waiting",
            next_cycle_at=500.0,
            interval_seconds=900,
        )

        background.mark_cycle_reset_requested("lidarr")

        self.assertEqual(
            background.cycle_status["lidarr"],
            {
                "state": "reset_pending",
                "next_cycle_at": None,
                "interval_seconds": 900,
                "reason": "Manual reset requested",
            },
        )

    def test_cycle_status_endpoint_returns_the_background_snapshot(self):
        payload = {
            "server_time": 100.0,
            "cycles": {
                "eros": {
                    "state": "running",
                    "next_cycle_at": None,
                    "interval_seconds": 900,
                    "remaining_seconds": None,
                }
            },
        }

        with (
            app.app_context(),
            patch.object(background, "get_cycle_status_snapshot", return_value=payload),
        ):
            response = api_cycle_status()

        self.assertEqual(response.get_json(), payload)

    def test_web_server_uses_the_runtime_background_module(self):
        self.assertIs(web_server.background, background)


if __name__ == "__main__":
    unittest.main()
