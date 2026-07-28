import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_support import configure_test_environment

configure_test_environment()

from src.primary.apps.swaparr.handler import get_queue_items


def queue_response(payload):
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


class SwaparrQueueTests(unittest.TestCase):
    @patch("src.primary.apps.swaparr.handler.requests.get")
    def test_lidarr_paginated_object_fetches_every_page(self, get):
        get.side_effect = [
            queue_response(
                {
                    "page": 1,
                    "pageSize": 1,
                    "totalRecords": 2,
                    "records": [
                        {
                            "id": 101,
                            "album": {"title": "First Album"},
                            "size": 1000,
                            "status": "Downloading",
                        }
                    ],
                }
            ),
            queue_response(
                {
                    "page": 2,
                    "pageSize": 1,
                    "totalRecords": 2,
                    "records": [
                        {
                            "id": 102,
                            "album": {"title": "Second Album"},
                            "size": 2000,
                            "status": "Queued",
                        }
                    ],
                }
            ),
        ]

        result = get_queue_items("lidarr", "http://lidarr:8686/", "secret", api_timeout=30)

        self.assertEqual([item["id"] for item in result], [101, 102])
        self.assertEqual([item["name"] for item in result], ["First Album", "Second Album"])
        self.assertEqual([item["status"] for item in result], ["downloading", "queued"])
        self.assertEqual(
            get.call_args_list,
            [
                call(
                    "http://lidarr:8686/api/v1/queue?page=1&pageSize=100",
                    headers={"X-Api-Key": "secret"},
                    timeout=30,
                ),
                call(
                    "http://lidarr:8686/api/v1/queue?page=2&pageSize=100",
                    headers={"X-Api-Key": "secret"},
                    timeout=30,
                ),
            ],
        )

    @patch("src.primary.apps.swaparr.handler.requests.get")
    def test_readarr_paginated_object_is_parsed_as_records(self, get):
        get.return_value = queue_response(
            {
                "page": 1,
                "pageSize": 100,
                "totalRecords": 1,
                "records": [
                    {
                        "id": 201,
                        "book": {"title": "Example Book"},
                        "size": 3000,
                        "status": "Completed",
                    }
                ],
            }
        )

        result = get_queue_items("readarr", "http://readarr:8787", "secret")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], 201)
        self.assertEqual(result[0]["name"], "Example Book")
        self.assertEqual(result[0]["status"], "completed")
        get.assert_called_once()

    @patch("src.primary.apps.swaparr.handler.requests.get")
    def test_legacy_v1_bare_list_remains_supported(self, get):
        get.return_value = queue_response(
            [
                {
                    "id": 301,
                    "album": {"title": "Legacy Album"},
                    "size": 4000,
                    "status": "Queued",
                }
            ]
        )

        result = get_queue_items("lidarr", "http://lidarr:8686", "secret")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], 301)
        self.assertEqual(result[0]["name"], "Legacy Album")
        get.assert_called_once()

    @patch("src.primary.apps.swaparr.handler.requests.get")
    def test_malformed_records_value_is_rejected(self, get):
        get.return_value = queue_response({"totalRecords": 1, "records": {"id": 401}})

        result = get_queue_items("lidarr", "http://lidarr:8686", "secret")

        self.assertEqual(result, [])
        get.assert_called_once()


if __name__ == "__main__":
    unittest.main()
