#!/usr/bin/env python3

from src.primary.history_manager import add_history_entry
from src.primary.utils.logger import get_logger

logger = get_logger("history")


def _first_value(data, *paths):
    """Return the first non-empty value found at one of the supplied paths."""
    for path in paths:
        value = data
        for key in path:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def build_media_details(app_type, media, media_type=None):
    """Build a small, safe metadata snapshot from an Arr API media object."""
    if not isinstance(media, dict):
        return {}

    search_context = (
        media.get("_neutarr_search_context") if isinstance(media.get("_neutarr_search_context"), dict) else {}
    )

    if app_type == "radarr":
        details = {
            "media_type": media_type or "Movie",
            "original_title": media.get("originalTitle"),
            "year": media.get("year"),
            "status": media.get("status"),
            "monitored": media.get("monitored"),
            "minimum_availability": media.get("minimumAvailability"),
            "runtime_minutes": media.get("runtime"),
            "studio": media.get("studio"),
            "certification": media.get("certification"),
            "genres": media.get("genres"),
            "quality": _first_value(
                media,
                ("movieFile", "quality", "quality", "name"),
                ("quality", "quality", "name"),
            ),
            "custom_format_score": _first_value(
                media,
                ("movieFile", "customFormatScore"),
                ("customFormatScore",),
            ),
            "custom_format_target_score": search_context.get("custom_format_target_score"),
            "search_reason": search_context.get("search_reason"),
            "quality_profile_id": media.get("qualityProfileId"),
            "tmdb_id": media.get("tmdbId"),
            "imdb_id": media.get("imdbId"),
        }
    elif app_type == "sonarr":
        series = media.get("series") if isinstance(media.get("series"), dict) else {}
        details = {
            "media_type": media_type or "Episode",
            "series": series.get("title"),
            "episode_title": media.get("title"),
            "season": media.get("seasonNumber"),
            "episode": media.get("episodeNumber"),
            "absolute_episode": media.get("absoluteEpisodeNumber"),
            "air_date": media.get("airDate"),
            "monitored": media.get("monitored"),
            "file_available": media.get("hasFile"),
            "quality": _first_value(
                media,
                ("episodeFile", "quality", "quality", "name"),
                ("quality", "quality", "name"),
            ),
            "custom_format_score": _first_value(
                media,
                ("episodeFile", "customFormatScore"),
                ("customFormatScore",),
            ),
            "search_reason": search_context.get("search_reason"),
            "series_year": series.get("year"),
            "series_status": series.get("status"),
            "network": series.get("network"),
            "genres": series.get("genres"),
            "tvdb_id": media.get("tvdbId"),
        }
    else:
        return {}

    return {key: value for key, value in details.items() if value not in (None, "", [], {})}


def log_processed_media(
    app_type,
    media_name,
    media_id,
    instance_name,
    operation_type="missing",
    details=None,
):
    """
    Log when media is processed by an app instance

    Parameters:
    - app_type: str - The app type (sonarr, radarr, etc)
    - media_name: str - Name of the processed media
    - media_id: str/int - ID of the processed media
    - instance_name: str - Name of the instance that processed it
    - operation_type: str - Type of operation ("missing" or "upgrade")
    - details: dict - Optional app-specific metadata snapshot

    Returns:
    - bool - Success or failure
    """
    try:
        logger.debug(f"Logging history entry for {app_type} - {instance_name}: '{media_name}' (ID: {media_id})")

        entry_data = {
            "name": media_name,
            "id": str(media_id),
            "instance_name": instance_name,
            "operation_type": operation_type,
        }
        if isinstance(details, dict) and details:
            entry_data["details"] = details

        result = add_history_entry(app_type, entry_data)
        if result:
            logger.info(f"Logged history entry for {app_type} - {instance_name}: {media_name} ({operation_type})")
            return True
        else:
            logger.error(f"Failed to log history entry for {app_type} - {instance_name}: {media_name}")
            return False
    except Exception as e:
        logger.error(f"Error logging history entry: {str(e)}")
        return False
