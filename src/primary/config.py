#!/usr/bin/env python3
"""
Configuration module for NeutArr
Provides utility functions to access settings via settings_manager.
"""

from src.primary import settings_manager
from src.primary.utils.logger import get_logger


def get_debug_mode():
    """Get the debug mode setting from general settings"""
    try:
        return settings_manager.get_setting("general", "debug_mode", False)
    except Exception:
        return False


def determine_hunt_mode(app_name: str) -> str:
    """Determine the hunt mode for a specific app based on its settings."""
    hunt_missing = 0
    hunt_upgrade = 0

    if app_name == "sonarr":
        hunt_missing = settings_manager.get_setting(app_name, "hunt_missing_items", 0)
        hunt_upgrade = settings_manager.get_setting(app_name, "hunt_upgrade_items", 0)
    elif app_name == "radarr":
        hunt_missing = settings_manager.get_setting(app_name, "hunt_missing_movies", 0)
        hunt_upgrade = settings_manager.get_setting(app_name, "hunt_upgrade_movies", 0)
    elif app_name.lower() == "lidarr":
        hunt_missing = settings_manager.get_setting(app_name, "hunt_missing_items", 0)
        hunt_upgrade = settings_manager.get_setting(app_name, "hunt_upgrade_items", 0)
    elif app_name == "readarr":
        hunt_missing = settings_manager.get_setting(app_name, "hunt_missing_books", 0)
        hunt_upgrade = settings_manager.get_setting(app_name, "hunt_upgrade_books", 0)
    else:
        return "disabled"

    if hunt_missing > 0 and hunt_upgrade > 0:
        return "both"
    elif hunt_missing > 0:
        return "missing"
    elif hunt_upgrade > 0:
        return "upgrade"
    else:
        return "disabled"


def log_configuration(app_name: str):
    """Log the current configuration settings for a specific app."""
    log = get_logger(app_name)
    settings = settings_manager.load_settings(app_name)

    if not settings:
        log.error(f"Could not load settings for app: {app_name}. Cannot log configuration.")
        return

    state_reset_interval = settings_manager.get_advanced_setting("stateful_management_hours", 168)

    log.info(f"--- Configuration for {app_name} ---")
    log.info(f"Debug Mode: {settings.get('debug_mode', False)}")
    log.info(f"Hunt Mode: {determine_hunt_mode(app_name)}")
    log.info(f"Sleep Duration: {settings.get('sleep_duration', 900)} seconds")
    log.info(f"State Reset Interval: {state_reset_interval} hours")
    log.info(f"Monitored Only: {settings.get('monitored_only', True)}")
    log.info(f"Maximum Download Queue Size: {settings.get('minimum_download_queue_size', -1)}")

    if app_name == "sonarr":
        log.info(f"Hunt Missing Items: {settings.get('hunt_missing_items', 0)}")
        log.info(f"Hunt Upgrade Items: {settings.get('hunt_upgrade_items', 0)}")
        log.info(f"Skip Future Episodes: {settings.get('skip_future_episodes', True)}")
        log.info(f"Skip Series Refresh: {settings.get('skip_series_refresh', False)}")
    elif app_name == "radarr":
        log.info(f"Hunt Missing Movies: {settings.get('hunt_missing_movies', 0)}")
        log.info(f"Hunt Upgrade Movies: {settings.get('hunt_upgrade_movies', 0)}")
        log.info(f"Skip Future Releases: {settings.get('skip_future_releases', True)}")
        log.info(f"Skip Movie Refresh: {settings.get('skip_movie_refresh', False)}")
    elif app_name.lower() == "lidarr":
        log.info(f"Mode: {settings.get('hunt_missing_mode', 'artist')}")
        log.info(f"Hunt Missing Items: {settings.get('hunt_missing_items', 0)}")
        log.info(f"Hunt Upgrade Items: {settings.get('hunt_upgrade_items', 0)}")
        log.info(f"Sleep Duration: {settings.get('sleep_duration', 900)} seconds")
        log.info(f"State Reset Interval: {state_reset_interval} hours")
        log.info(f"Monitored Only: {settings.get('monitored_only', True)}")
        log.info(f"Maximum Download Queue Size: {settings.get('minimum_download_queue_size', -1)}")
    elif app_name == "readarr":
        log.info(f"Hunt Missing Books: {settings.get('hunt_missing_books', 0)}")
        log.info(f"Hunt Upgrade Books: {settings.get('hunt_upgrade_books', 0)}")
        log.info(f"Skip Future Releases: {settings.get('skip_future_releases', True)}")
        log.info(f"Skip Author Refresh: {settings.get('skip_author_refresh', False)}")
    log.info(f"--- End Configuration for {app_name} ---")
