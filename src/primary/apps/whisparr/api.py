#!/usr/bin/env python3
"""
Whisparr-specific API functions
Handles all communication with the Whisparr API

Exclusively uses the Whisparr V2 API
"""

import requests
import json
import time
import datetime
import traceback
import sys
from typing import List, Dict, Any, Optional, Union, Callable
from src.primary.utils.logger import get_logger
from src.primary.settings_manager import get_ssl_verify_setting

# Get logger for the Whisparr app
whisparr_logger = get_logger("whisparr")

# Use a session for better performance
session = requests.Session()


def arr_request(
    api_url: str, api_key: str, api_timeout: int, endpoint: str, method: str = "GET", data: Dict = None
) -> Any:
    """
    Make a request to the Whisparr API.

    Args:
        api_url: The base URL of the Whisparr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        endpoint: The API endpoint to call
        method: HTTP method (GET, POST, PUT, DELETE)
        data: Optional data payload for POST/PUT requests

    Returns:
        The parsed JSON response or None if the request failed
    """
    try:
        if not api_url or not api_key:
            whisparr_logger.error("No URL or API key provided")
            return None

        # Ensure api_url has a scheme
        if not (api_url.startswith("http://") or api_url.startswith("https://")):
            whisparr_logger.error("Invalid Whisparr URL format; URL must start with http:// or https://")
            return None

        # Construct the full URL properly
        full_url = f"{api_url.rstrip('/')}/api/v3/{endpoint.lstrip('/')}"

        whisparr_logger.debug("Making request to the Whisparr API")

        # Set up headers with User-Agent to identify NeutArr
        headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json",
            "User-Agent": "NeutArr/1.0 (https://github.com/I-am-PUID-0/NeutArr)",
        }

        # Get SSL verification setting
        verify_ssl = get_ssl_verify_setting()

        if not verify_ssl:
            whisparr_logger.debug("SSL verification disabled by user setting")

        try:
            if method.upper() == "GET":
                response = session.get(full_url, headers=headers, timeout=api_timeout, verify=verify_ssl)
            elif method.upper() == "POST":
                response = session.post(full_url, headers=headers, json=data, timeout=api_timeout, verify=verify_ssl)
            elif method.upper() == "PUT":
                response = session.put(full_url, headers=headers, json=data, timeout=api_timeout, verify=verify_ssl)
            elif method.upper() == "DELETE":
                response = session.delete(full_url, headers=headers, timeout=api_timeout, verify=verify_ssl)
            else:
                whisparr_logger.error("Unsupported HTTP method for Whisparr API request")
                return None

            # If we get a 404, try with v3 path instead
            if response.status_code == 404:
                api_base = "api/v3"
                v3_url = f"{api_url.rstrip('/')}/{api_base}/{endpoint.lstrip('/')}"
                whisparr_logger.debug("Standard Whisparr API path returned 404; trying v3 path")

                if method == "GET":
                    response = session.get(v3_url, headers=headers, timeout=api_timeout)
                elif method == "POST":
                    response = session.post(v3_url, headers=headers, json=data, timeout=api_timeout)
                elif method == "PUT":
                    response = session.put(v3_url, headers=headers, json=data, timeout=api_timeout)
                elif method == "DELETE":
                    response = session.delete(v3_url, headers=headers, timeout=api_timeout)

                whisparr_logger.debug(f"V3 path request returned status code: {response.status_code}")

            # Check if the request was successful
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError:
                whisparr_logger.error(
                    "Whisparr API request failed with HTTP status %s; response body omitted",
                    response.status_code,
                )
                return None

            # Try to parse JSON response
            try:
                if response.text:
                    result = response.json()
                    whisparr_logger.debug("Whisparr API returned valid JSON")
                    return result
                else:
                    whisparr_logger.debug("Whisparr API returned an empty response")
                    return {}
            except json.JSONDecodeError:
                whisparr_logger.error("Whisparr API returned invalid JSON; response body omitted")
                return None

        except requests.exceptions.RequestException:
            whisparr_logger.error("Whisparr API request failed; request details omitted")
            return None
    except Exception:
        whisparr_logger.error("Unexpected error during Whisparr API request; details omitted")
        return None


def get_download_queue_size(api_url: str, api_key: str, api_timeout: int) -> int:
    """
    Get the current size of the download queue.

    Args:
        api_url: The base URL of the Whisparr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request

    Returns:
        The number of items in the download queue, or -1 if the request failed
    """
    response = arr_request(api_url, api_key, api_timeout, "queue")

    if response is None:
        return -1

    # V2 API uses records in queue response
    if isinstance(response, dict) and "records" in response:
        return len(response["records"])
    elif isinstance(response, list):
        return len(response)
    else:
        return -1


def get_items_with_missing(api_url: str, api_key: str, api_timeout: int, monitored_only: bool) -> List[Dict[str, Any]]:
    """
    Get a list of items with missing files (not downloaded/available).

    Args:
        api_url: The base URL of the Whisparr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: If True, only return monitored items.

    Returns:
        A list of item objects with missing files, or None if the request failed.
    """
    try:
        whisparr_logger.debug(f"Retrieving missing items...")

        # Endpoint parameters - always use v2 format
        endpoint = "wanted/missing?pageSize=1000&sortKey=airDateUtc&sortDirection=descending"

        response = arr_request(api_url, api_key, api_timeout, endpoint)

        if response is None:
            return None

        # Extract the episodes/items
        items = []
        if isinstance(response, dict) and "records" in response:
            items = response["records"]

        # Filter monitored if needed
        if monitored_only:
            items = [item for item in items if item.get("monitored", False)]

        whisparr_logger.debug(f"Found {len(items)} missing items")
        return items

    except Exception:
        whisparr_logger.error("Error retrieving missing Whisparr items; details omitted")
        return None


def get_cutoff_unmet_items(api_url: str, api_key: str, api_timeout: int, monitored_only: bool) -> List[Dict[str, Any]]:
    """
    Get a list of items that don't meet their quality profile cutoff.

    Args:
        api_url: The base URL of the Whisparr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: If True, only return monitored items.

    Returns:
        A list of item objects that need quality upgrades, or None if the request failed.
    """
    try:
        whisparr_logger.debug(f"Retrieving cutoff unmet items...")

        # Endpoint - always use v2 format
        endpoint = "wanted/cutoff?pageSize=1000&sortKey=airDateUtc&sortDirection=descending"

        response = arr_request(api_url, api_key, api_timeout, endpoint)

        if response is None:
            return None

        # Extract the episodes/items
        items = []
        if isinstance(response, dict) and "records" in response:
            items = response["records"]

        whisparr_logger.debug(f"Found {len(items)} cutoff unmet items")

        # Just filter monitored if needed
        if monitored_only:
            items = [item for item in items if item.get("monitored", False)]
            whisparr_logger.debug(f"Found {len(items)} cutoff unmet items after filtering monitored")

        return items

    except Exception:
        whisparr_logger.error("Error retrieving cutoff-unmet Whisparr items; details omitted")
        return None


def refresh_item(api_url: str, api_key: str, api_timeout: int, item_id: int) -> int:
    """
    Refresh functionality has been removed as it was a performance bottleneck.
    This function now returns a placeholder command ID without making any API calls.

    Args:
        api_url: The base URL of the Whisparr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        item_id: The ID of the item to refresh

    Returns:
        A placeholder command ID (123) to simulate success
    """
    whisparr_logger.debug("Refresh functionality is disabled for Whisparr items")
    # Return a placeholder command ID to simulate success without actually refreshing
    return 123


def item_search(api_url: str, api_key: str, api_timeout: int, item_ids: List[int]) -> int:
    """
    Trigger a search for one or more items.

    Args:
        api_url: The base URL of the Whisparr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        item_ids: A list of item IDs to search for

    Returns:
        The command ID if the search command was triggered successfully, None otherwise
    """
    try:
        whisparr_logger.debug("Searching for %s Whisparr item(s)", len(item_ids))

        # Always use the same payload format since we're always using v2 API
        payload = {"name": "EpisodeSearch", "episodeIds": item_ids}

        # For commands, we need to directly try both path formats
        command_endpoint = "command"
        url = f"{api_url.rstrip('/')}/api/{command_endpoint}"
        backup_url = f"{api_url.rstrip('/')}/api/v3/{command_endpoint}"

        headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}

        # Try standard API path first
        whisparr_logger.debug("Attempting Whisparr search command with standard API path")
        try:
            response = session.post(url, headers=headers, json=payload, timeout=api_timeout)
            # If we get a 404 or 405, try the v3 path
            if response.status_code in [404, 405]:
                whisparr_logger.debug(
                    "Standard Whisparr command path returned HTTP %s; trying v3 path",
                    response.status_code,
                )
                response = session.post(backup_url, headers=headers, json=payload, timeout=api_timeout)

            response.raise_for_status()
            result = response.json()

            if result and "id" in result:
                command_id = result["id"]
                whisparr_logger.debug("Whisparr search command triggered successfully")
                return command_id
            else:
                whisparr_logger.error("Failed to trigger search command - no command ID returned")
                return None
        except requests.exceptions.HTTPError:
            whisparr_logger.error(
                "Whisparr search command failed with HTTP status %s; response body omitted",
                response.status_code,
            )
            return None
        except Exception:
            whisparr_logger.error("Error sending Whisparr search command; details omitted")
            return None

    except Exception:
        whisparr_logger.error("Error preparing Whisparr item search; details omitted")
        return None


def get_command_status(api_url: str, api_key: str, api_timeout: int, command_id: int) -> Optional[Dict]:
    """
    Get the status of a specific command.

    Args:
        api_url: The base URL of the Whisparr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        command_id: The ID of the command to check

    Returns:
        A dictionary containing the command status, or None if the request failed.
    """
    if not command_id:
        whisparr_logger.error("No command ID provided for status check.")
        return None

    try:
        # For commands, we need to directly try both path formats
        command_endpoint = f"command/{command_id}"
        url = f"{api_url.rstrip('/')}/api/{command_endpoint}"
        backup_url = f"{api_url.rstrip('/')}/api/v3/{command_endpoint}"

        headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}

        # Try standard API path first
        whisparr_logger.debug("Checking Whisparr command status with standard API path")
        try:
            response = session.get(url, headers=headers, timeout=api_timeout)
            # If we get a 404, try the v3 path
            if response.status_code == 404:
                whisparr_logger.debug("Standard Whisparr command path returned 404; trying v3 path")
                response = session.get(backup_url, headers=headers, timeout=api_timeout)

            response.raise_for_status()
            result = response.json()

            whisparr_logger.debug("Retrieved Whisparr command status")
            return result
        except requests.exceptions.HTTPError:
            whisparr_logger.error(
                "Whisparr command-status request failed with HTTP status %s; response body omitted",
                response.status_code,
            )
            return None
        except Exception:
            whisparr_logger.error("Error getting Whisparr command status; details omitted")
            return None

    except Exception:
        whisparr_logger.error("Error preparing Whisparr command-status request; details omitted")
        return None


def check_connection(api_url: str, api_key: str, api_timeout: int) -> bool:
    """
    Check the connection to Whisparr V2 API.

    Args:
        api_url: The base URL of the Whisparr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request

    Returns:
        True if the connection is successful, False otherwise
    """
    try:
        # For Whisparr V2, we need to handle both regular and v3 API formats
        whisparr_logger.debug("Checking connection to the Whisparr V2 API")

        # First try with standard path
        endpoint = "system/status"
        response = arr_request(api_url, api_key, api_timeout, endpoint)

        # If that failed, try with v3 path format
        if response is None:
            whisparr_logger.debug("Standard API path failed, trying v3 format...")
            # Try direct HTTP request to v3 endpoint without using arr_request
            url = f"{api_url.rstrip('/')}/api/v3/system/status"
            headers = {"X-Api-Key": api_key}

            try:
                resp = session.get(url, headers=headers, timeout=api_timeout)
                resp.raise_for_status()
                response = resp.json()
            except Exception:
                whisparr_logger.debug("Whisparr v3 API fallback also failed; request details omitted")
                return False

        if response is not None:
            # Get the version information if available
            version = response.get("version", "unknown")

            # Check if this is a v2.x version
            if version and version.startswith("2"):
                whisparr_logger.debug("Successfully connected to a compatible Whisparr V2 API")
                return True
            else:
                whisparr_logger.warning("Connected to Whisparr but found an incompatible API version; expected 2.x")
                return False
        else:
            whisparr_logger.error("Failed to connect to Whisparr V2 API")
            return False

    except Exception:
        whisparr_logger.error("Error checking the Whisparr V2 API connection; details omitted")
        return False
