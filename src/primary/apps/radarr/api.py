#!/usr/bin/env python3
"""
Radarr-specific API functions
Handles all communication with the Radarr API
"""

import requests
import json
import sys
import time
import traceback
from typing import List, Dict, Any, Optional, Union

# Correct the import path
from src.primary.utils.logger import get_logger
from src.primary.settings_manager import get_ssl_verify_setting

# Get logger for the Radarr app
radarr_logger = get_logger("radarr")

# Use a session for better performance
session = requests.Session()


def arr_request(
    api_url: str, api_key: str, api_timeout: int, endpoint: str, method: str = "GET", data: Dict = None
) -> Any:
    """
    Make a request to the Radarr API.

    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        endpoint: The API endpoint to call (without /api/v3/)
        method: HTTP method (GET, POST, PUT, DELETE)
        data: Optional data payload for POST/PUT requests

    Returns:
        The parsed JSON response or None if the request failed
    """
    try:
        if not api_url or not api_key:
            radarr_logger.error("No URL or API key provided")
            return None

        # Construct the full URL properly
        full_url = f"{api_url.rstrip('/')}/api/v3/{endpoint.lstrip('/')}"

        radarr_logger.debug(f"Making {method} request to: {full_url}")

        # Set up headers with the API key
        headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json",
            "User-Agent": "NeutArr/1.0 (https://github.com/I-am-PUID-0/NeutArr)",
        }

        # Get SSL verification setting
        verify_ssl = get_ssl_verify_setting()

        if not verify_ssl:
            radarr_logger.debug("SSL verification disabled by user setting")

        # Make the request based on the method
        if method.upper() == "GET":
            response = session.get(full_url, headers=headers, timeout=api_timeout, verify=verify_ssl)
        elif method.upper() == "POST":
            response = session.post(full_url, headers=headers, json=data, timeout=api_timeout, verify=verify_ssl)
        elif method.upper() == "PUT":
            response = session.put(full_url, headers=headers, json=data, timeout=api_timeout, verify=verify_ssl)
        elif method.upper() == "DELETE":
            response = session.delete(full_url, headers=headers, timeout=api_timeout, verify=verify_ssl)
        else:
            radarr_logger.error(f"Unsupported HTTP method: {method}")
            return None

        # Check for errors
        response.raise_for_status()

        # Parse JSON response
        if response.text:
            return response.json()
        return {}

    except requests.exceptions.RequestException as e:
        radarr_logger.error(f"API request failed: {e}")
        return None


def get_download_queue_size(api_url: str, api_key: str, api_timeout: int) -> int:
    """
    Get the current size of the download queue.

    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request

    Returns:
        The number of items in the download queue, or -1 if the request failed
    """
    if not api_url or not api_key:
        radarr_logger.error("Radarr API URL or API Key not provided for queue size check.")
        return -1
    try:
        # Radarr uses /api/v3/queue
        endpoint = f"{api_url.rstrip('/')}/api/v3/queue?page=1&pageSize=1000"  # Fetch a large page size
        headers = {"X-Api-Key": api_key}
        response = session.get(endpoint, headers=headers, timeout=api_timeout)
        response.raise_for_status()
        queue_data = response.json()
        queue_size = queue_data.get("totalRecords", 0)
        radarr_logger.debug(f"Radarr download queue size: {queue_size}")
        return queue_size
    except requests.exceptions.RequestException as e:
        radarr_logger.error(f"Error getting Radarr download queue size: {e}")
        return -1  # Return -1 to indicate an error
    except Exception as e:
        radarr_logger.error(f"An unexpected error occurred while getting Radarr queue size: {e}")
        return -1


def get_indexer_config(api_url: str, api_key: str, api_timeout: int) -> Optional[Dict[str, Any]]:
    """Get Radarr indexer configuration, including availability delay."""
    config = arr_request(api_url, api_key, api_timeout, "config/indexer")
    if isinstance(config, dict):
        return config
    radarr_logger.error("Failed to retrieve Radarr indexer configuration.")
    return None


def get_availability_delay_days(api_url: str, api_key: str, api_timeout: int) -> int:
    """Return Radarr's indexer availability delay in days, defaulting to no delay."""
    config = get_indexer_config(api_url, api_key, api_timeout)
    if not config:
        return 0

    try:
        return int(config.get("availabilityDelay", 0) or 0)
    except (TypeError, ValueError):
        radarr_logger.warning(
            f"Invalid Radarr availabilityDelay value: {config.get('availabilityDelay')}. Using 0 days."
        )
        return 0


def get_movies_with_missing(api_url: str, api_key: str, api_timeout: int, monitored_only: bool) -> Optional[List[Dict]]:
    """
    Get a list of movies with missing files (not downloaded/available).

    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: If True, only return monitored movies.

    Returns:
        A list of movie objects with missing files, or None if the request failed.
    """
    # Use the updated arr_request with passed arguments
    movies = arr_request(api_url, api_key, api_timeout, "movie")
    if movies is None:  # Check for None explicitly, as an empty list is valid
        radarr_logger.error("Failed to retrieve movies from Radarr API.")
        return None

    missing_movies = []
    for movie in movies:
        is_monitored = movie.get("monitored", False)
        has_file = movie.get("hasFile", False)
        # Apply monitored_only filter if requested
        if not has_file and (not monitored_only or is_monitored):
            missing_movies.append(movie)

    radarr_logger.debug(f"Found {len(missing_movies)} missing movies (monitored_only={monitored_only}).")
    return missing_movies


def _build_quality_profile_map(profiles: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    """Build lookup metadata for Radarr quality and custom-format cutoff checks."""
    profile_map = {}
    for profile in profiles:
        rank = 0
        quality_rank = {}
        for item in profile.get("items", []):
            if item.get("quality"):
                quality_rank[item["quality"]["id"]] = rank
                rank += 1
            elif item.get("items"):
                for sub_item in item["items"]:
                    if sub_item.get("quality"):
                        quality_rank[sub_item["quality"]["id"]] = rank
                rank += 1

        format_scores = {}
        for item in profile.get("formatItems", []):
            custom_format = item.get("format")
            if isinstance(custom_format, dict):
                format_id = custom_format.get("id") or item.get("formatId")
            else:
                format_id = item.get("formatId") or custom_format
            if format_id is not None:
                format_scores[format_id] = item.get("score", 0) or 0

        profile_map[profile["id"]] = {
            "cutoff_id": profile.get("cutoff"),
            "quality_rank": quality_rank,
            "min_format_score": profile.get("minFormatScore", 0) or 0,
            "cutoff_format_score": profile.get("cutoffFormatScore", 0) or 0,
            "format_scores": format_scores,
        }

    return profile_map


def _get_movie_file_custom_format_score(movie: Dict[str, Any], profile_info: Dict[str, Any]) -> Optional[int]:
    """Return a movie file's current custom-format score when Radarr exposes enough data."""
    movie_file = movie.get("movieFile") or {}

    for source in (movie_file, movie):
        score = source.get("customFormatScore")
        if isinstance(score, (int, float)):
            return int(score)

    custom_formats = movie_file.get("customFormats") or movie.get("customFormats")
    if not isinstance(custom_formats, list):
        return None

    total = 0
    matched_any = False
    format_scores = profile_info.get("format_scores", {})
    for custom_format in custom_formats:
        if not isinstance(custom_format, dict):
            continue
        format_id = custom_format.get("id")
        if format_id in format_scores:
            total += format_scores[format_id]
            matched_any = True

    return total if matched_any else None


def _movie_has_custom_format_data(movie: Dict[str, Any]) -> bool:
    movie_file = movie.get("movieFile") or {}
    for source in (movie_file, movie):
        if isinstance(source.get("customFormatScore"), (int, float)):
            return True
        if isinstance(source.get("customFormats"), list):
            return True
    return False


def _get_movie_file_id(movie: Dict[str, Any]) -> Optional[int]:
    movie_file = movie.get("movieFile") or {}
    movie_file_id = movie_file.get("id") or movie.get("movieFileId")
    return movie_file_id if isinstance(movie_file_id, int) else None


def _merge_detailed_movie_file(movie: Dict[str, Any], detailed_movie_file: Dict[str, Any]) -> Dict[str, Any]:
    enriched_movie = dict(movie)
    enriched_movie["movieFile"] = {
        **(movie.get("movieFile") or {}),
        **detailed_movie_file,
    }
    return enriched_movie


def _enrich_movie_file_custom_format_data(
    movie: Dict[str, Any],
    api_url: str,
    api_key: str,
    api_timeout: int,
    movie_file_cache: Dict[int, Dict[str, Any]],
) -> Dict[str, Any]:
    """Fetch Radarr movie-file detail when /movie omits custom-format score data."""
    if _movie_has_custom_format_data(movie):
        return movie

    movie_file_id = _get_movie_file_id(movie)
    if movie_file_id is None:
        return movie

    if movie_file_id not in movie_file_cache:
        detailed_movie_file = arr_request(api_url, api_key, api_timeout, f"moviefile/{movie_file_id}")
        if isinstance(detailed_movie_file, dict):
            movie_file_cache[movie_file_id] = detailed_movie_file
        else:
            radarr_logger.debug(
                f"Radarr movie file detail was unavailable for movieFile ID {movie_file_id}; "
                "custom-format score upgrade check will use embedded movie data."
            )
            movie_file_cache[movie_file_id] = {}

    detailed_movie_file = movie_file_cache[movie_file_id]
    if not detailed_movie_file:
        return movie

    return _merge_detailed_movie_file(movie, detailed_movie_file)


def _is_quality_cutoff_unmet(movie: Dict[str, Any], profile_info: Dict[str, Any]) -> bool:
    movie_file = movie.get("movieFile") or {}
    quality_rank = profile_info["quality_rank"]
    current_quality_id = movie_file.get("quality", {}).get("quality", {}).get("id")

    current_rank = quality_rank.get(current_quality_id)
    cutoff_rank = quality_rank.get(profile_info["cutoff_id"])

    return current_rank is not None and cutoff_rank is not None and current_rank < cutoff_rank


def _is_custom_format_cutoff_unmet(movie: Dict[str, Any], profile_info: Dict[str, Any]) -> bool:
    current_score = _get_movie_file_custom_format_score(movie, profile_info)
    if current_score is None:
        return False

    target_score = max(profile_info.get("min_format_score", 0), profile_info.get("cutoff_format_score", 0))
    return current_score < target_score


def _is_radarr_upgrade_candidate(movie: Dict[str, Any], profile_info: Dict[str, Any]) -> bool:
    return _is_quality_cutoff_unmet(movie, profile_info) or _is_custom_format_cutoff_unmet(movie, profile_info)


def _build_upgrade_search_context(
    movie: Dict[str, Any],
    profile_info: Dict[str, Any],
    quality_unmet: bool,
    format_unmet: bool,
) -> Dict[str, Any]:
    """Describe why NeutArr selected a Radarr movie for an upgrade search."""
    reasons = []
    if quality_unmet:
        reasons.append("Quality is below profile cutoff")

    current_score = _get_movie_file_custom_format_score(movie, profile_info)
    target_score = max(profile_info.get("min_format_score", 0), profile_info.get("cutoff_format_score", 0))
    if format_unmet:
        label = "custom format score" if reasons else "Custom format score"
        reasons.append(f"{label} {current_score} is below target {target_score}")

    context = {"search_reason": "; ".join(reasons)}
    if current_score is not None:
        context["custom_format_target_score"] = target_score
    return context


def get_cutoff_unmet_movies(api_url: str, api_key: str, api_timeout: int, monitored_only: bool) -> Optional[List[Dict]]:
    """
    Get movies that do not meet their quality or custom-format profile cutoffs.

    Radarr's wanted/cutoff behavior is not used here because NeutArr also needs to
    catch movies that already meet Upgrade Until Quality but have fallen below the
    profile's custom-format score expectations.
    """
    radarr_logger.debug("Fetching all movies to determine quality/custom-format cutoff status...")
    movies = arr_request(api_url, api_key, api_timeout, "movie")
    if movies is None:
        radarr_logger.error("Failed to retrieve movies from Radarr API for cutoff check.")
        return None

    profiles = arr_request(api_url, api_key, api_timeout, "qualityprofile")
    if profiles is None:
        radarr_logger.error("Failed to retrieve quality profiles from Radarr API.")
        return None

    profile_map = _build_quality_profile_map(profiles)

    unmet_movies = []
    quality_unmet_count = 0
    format_unmet_count = 0
    movie_file_cache = {}
    for movie in movies:
        is_monitored = movie.get("monitored", False)
        has_file = movie.get("hasFile", False)
        profile_id = movie.get("qualityProfileId")
        movie_file = movie.get("movieFile")

        if monitored_only and not is_monitored:
            continue
        if not has_file or not movie_file or profile_id not in profile_map:
            continue

        profile_info = profile_map[profile_id]
        quality_unmet = _is_quality_cutoff_unmet(movie, profile_info)
        enriched_movie = _enrich_movie_file_custom_format_data(movie, api_url, api_key, api_timeout, movie_file_cache)
        format_unmet = _is_custom_format_cutoff_unmet(enriched_movie, profile_info)

        if quality_unmet or format_unmet:
            enriched_movie = dict(enriched_movie)
            enriched_movie["_neutarr_search_context"] = _build_upgrade_search_context(
                enriched_movie,
                profile_info,
                quality_unmet,
                format_unmet,
            )
            unmet_movies.append(enriched_movie)
            if quality_unmet:
                quality_unmet_count += 1
            if format_unmet:
                format_unmet_count += 1

    radarr_logger.debug(
        f"Found {len(unmet_movies)} Radarr upgrade candidates "
        f"({quality_unmet_count} quality cutoff, {format_unmet_count} custom-format score; monitored_only={monitored_only})."
    )
    return unmet_movies


def refresh_movie(
    api_url: str,
    api_key: str,
    api_timeout: int,
    movie_id: int,
    command_wait_delay: int = 1,
    command_wait_attempts: int = 600,
) -> Optional[int]:
    """
    Refresh functionality has been removed as it was a performance bottleneck.
    This function now returns a placeholder success value without making any API calls.

    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        movie_id: The ID of the movie to refresh
        command_wait_delay: Seconds to wait between command status checks
        command_wait_attempts: Maximum number of status check attempts

    Returns:
        A placeholder command ID (123) to simulate success
    """
    radarr_logger.debug(f"Refresh functionality disabled for movie ID: {movie_id}")
    # Return a placeholder command ID (123) to simulate success without actually refreshing
    return 123


def movie_search(api_url: str, api_key: str, api_timeout: int, movie_ids: List[int]) -> Optional[int]:
    """
    Trigger a search for one or more movies.

    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        movie_ids: A list of movie IDs to search for

    Returns:
        The command ID if the search command was triggered successfully, None otherwise
    """
    if not movie_ids:
        radarr_logger.warning("No movie IDs provided for search.")
        return None

    endpoint = "command"
    data = {"name": "MoviesSearch", "movieIds": movie_ids}

    # Use the updated arr_request
    response = arr_request(api_url, api_key, api_timeout, endpoint, method="POST", data=data)
    if response and "id" in response:
        command_id = response["id"]
        radarr_logger.debug(f"Triggered search for movie IDs: {movie_ids}. Command ID: {command_id}")
        return command_id
    else:
        radarr_logger.error(f"Failed to trigger search command for movie IDs {movie_ids}. Response: {response}")
        return None


def check_connection(api_url: str, api_key: str, api_timeout: int) -> bool:
    """Check the connection to Radarr API."""
    try:
        # Ensure api_url is properly formatted
        if not api_url:
            radarr_logger.error("API URL is empty or not set")
            return False

        # Make sure api_url has a scheme
        if not (api_url.startswith("http://") or api_url.startswith("https://")):
            radarr_logger.error(f"Invalid URL format: {api_url} - URL must start with http:// or https://")
            return False

        # Ensure URL doesn't end with a slash before adding the endpoint
        base_url = api_url.rstrip("/")
        full_url = f"{base_url}/api/v3/system/status"

        response = requests.get(full_url, headers={"X-Api-Key": api_key}, timeout=api_timeout)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        radarr_logger.debug("Successfully connected to Radarr.")
        return True
    except requests.exceptions.RequestException as e:
        radarr_logger.error(f"Error connecting to Radarr: {e}")
        return False
    except Exception as e:
        radarr_logger.error(f"An unexpected error occurred during Radarr connection check: {e}")
        return False


def wait_for_command(
    api_url: str, api_key: str, api_timeout: int, command_id: int, delay_seconds: int = 1, max_attempts: int = 600
) -> bool:
    """
    Wait for a command to complete.

    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        command_id: The ID of the command to wait for
        delay_seconds: Seconds to wait between command status checks
        max_attempts: Maximum number of status check attempts

    Returns:
        True if the command completed successfully, False if timed out
    """
    attempts = 0
    while attempts < max_attempts:
        response = arr_request(api_url, api_key, api_timeout, f"command/{command_id}")
        if response and "state" in response:
            state = response["state"]
            if state == "completed":
                return True
            elif state == "failed":
                radarr_logger.error(f"Command {command_id} failed")
                return False
        time.sleep(delay_seconds)
        attempts += 1
    radarr_logger.warning(f"Timed out waiting for command {command_id} to complete")
    return False
