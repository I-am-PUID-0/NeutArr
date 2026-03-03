#!/usr/bin/env python3
"""
Common routes blueprint for NeutArr.

Handles: static files, stats API, theme preference, local bypass status.
Auth routes (login/setup/logout/user management) live in auth_routes.py.
"""

import logging
from flask import Blueprint, request, jsonify, send_from_directory

from ..utils.logger import logger
from .. import settings_manager

common_bp = Blueprint("common", __name__)


# ---------------------------------------------------------------------------
# Static file serving
# ---------------------------------------------------------------------------


@common_bp.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(common_bp.static_folder, filename)


@common_bp.route("/favicon.ico")
def favicon():
    return send_from_directory(common_bp.static_folder, "favicon.ico", mimetype="image/vnd.microsoft.icon")


@common_bp.route("/logo/<path:filename>")
def logo_files(filename):
    import os

    logo_dir = os.path.join(common_bp.static_folder, "logo")
    return send_from_directory(logo_dir, filename)


# ---------------------------------------------------------------------------
# Bypass status (used by frontend to hide/show user menu)
# ---------------------------------------------------------------------------


@common_bp.route("/api/get_local_access_bypass_status", methods=["GET"])
def get_local_access_bypass_status_route():
    """Return whether any auth bypass mode is active (hides user menu in UI)."""
    try:
        local_access_bypass = settings_manager.get_setting("general", "local_access_bypass", False)
        proxy_auth_bypass = settings_manager.get_setting("general", "proxy_auth_bypass", False)
        bypass_enabled = local_access_bypass or proxy_auth_bypass
        logger.debug(f"Bypass status: local={local_access_bypass}, proxy={proxy_auth_bypass}")
        return jsonify({"isEnabled": bypass_enabled})
    except Exception as e:
        logger.error(f"Error retrieving bypass status: {e}", exc_info=True)
        return jsonify({"error": "Failed to retrieve bypass status"}), 500


# ---------------------------------------------------------------------------
# Theme preference
# ---------------------------------------------------------------------------


@common_bp.route("/api/settings/theme", methods=["POST"])
def set_theme():
    """Save dark/light mode preference. Protected by before_request auth."""
    try:
        data = request.get_json(silent=True) or {}
        dark_mode = data.get("dark_mode")

        if dark_mode is None or not isinstance(dark_mode, bool):
            return jsonify({"success": False, "error": "Invalid 'dark_mode' value"}), 400

        general = settings_manager.load_settings("general")
        general["ui_theme"] = "dark" if dark_mode else "light"
        settings_manager.save_settings("general", general)

        logger.info(f"Theme set to {'dark' if dark_mode else 'light'}")
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Error setting theme: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to set theme"}), 500


# ---------------------------------------------------------------------------
# Stats API
# ---------------------------------------------------------------------------


@common_bp.route("/api/stats", methods=["GET"])
def get_stats_api():
    """Return media hunt statistics."""
    try:
        from ..stats_manager import get_stats

        stats = get_stats()
        return jsonify({"success": True, "stats": stats})
    except Exception as e:
        logger.error(f"Error retrieving stats: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500


@common_bp.route("/api/stats/reset", methods=["POST"])
def reset_stats_api():
    """Reset media hunt statistics. Protected by before_request auth."""
    try:
        from ..stats_manager import reset_stats

        data = request.get_json(silent=True) or {}
        app_type = data.get("app_type")  # None resets all

        valid_types = {"sonarr", "radarr", "lidarr", "readarr", "whisparr"}
        if app_type is not None and app_type not in valid_types:
            return jsonify({"success": False, "error": "Invalid app_type"}), 400

        if reset_stats(app_type):
            message = f"Reset statistics for {app_type}" if app_type else "Reset all statistics"
            logger.info(message)
            return jsonify({"success": True, "message": message})

        error_msg = f"Failed to reset statistics for {app_type}" if app_type else "Failed to reset all statistics"
        logger.error(error_msg)
        return jsonify({"success": False, "error": error_msg}), 500
    except Exception as e:
        logger.error(f"Error resetting stats: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500
