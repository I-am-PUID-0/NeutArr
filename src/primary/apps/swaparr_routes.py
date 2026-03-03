"""
Route definitions for Swaparr API endpoints.
"""

from flask import Blueprint, request, jsonify
import os
import json
from pathlib import Path
from src.primary.utils.logger import get_logger
from src.primary.settings_manager import load_settings, save_settings
from src.primary.apps.swaparr.handler import process_stalled_downloads

# Create the blueprint directly in this file
swaparr_bp = Blueprint("swaparr", __name__)
swaparr_logger = get_logger("swaparr")
RESETTABLE_APPS = frozenset({"radarr", "sonarr", "lidarr", "readarr", "whisparr", "eros"})


def _get_swaparr_app_dirs(state_dir: Path) -> dict[str, Path]:
    """Return the fixed set of app state directories under the swaparr root."""
    return {
        "radarr": state_dir / "radarr",
        "sonarr": state_dir / "sonarr",
        "lidarr": state_dir / "lidarr",
        "readarr": state_dir / "readarr",
        "whisparr": state_dir / "whisparr",
        "eros": state_dir / "eros",
    }


@swaparr_bp.route("/status", methods=["GET"])
def get_status():
    """Get Swaparr status and statistics"""
    settings = load_settings("swaparr")
    enabled = settings.get("enabled", False)

    # Get strike statistics from all app state directories
    statistics = {}
    state_dir = Path(os.getenv("NEUTARR_CONFIG_DIR", "/config")).resolve() / "swaparr"
    app_dirs = _get_swaparr_app_dirs(state_dir)

    if state_dir.exists():
        for app_name, app_dir in app_dirs.items():
            if app_dir.is_dir():
                strike_file = app_dir / "strikes.json"
                if strike_file.exists():
                    try:
                        with open(strike_file, "r") as f:
                            strike_data = json.load(f)

                        total_items = len(strike_data)
                        removed_items = sum(1 for item in strike_data.values() if item.get("removed", False))
                        striked_items = sum(
                            1
                            for item in strike_data.values()
                            if item.get("strikes", 0) > 0 and not item.get("removed", False)
                        )

                        statistics[app_name] = {
                            "total_tracked": total_items,
                            "currently_striked": striked_items,
                            "removed": removed_items,
                        }
                    except (json.JSONDecodeError, IOError) as e:
                        swaparr_logger.error(f"Error reading strike data for {app_name}: {str(e)}")
                        statistics[app_name] = {"error": str(e)}

    return jsonify(
        {
            "enabled": enabled,
            "settings": {
                "max_strikes": settings.get("max_strikes", 3),
                "max_download_time": settings.get("max_download_time", "2h"),
                "ignore_above_size": settings.get("ignore_above_size", "25GB"),
                "remove_from_client": settings.get("remove_from_client", True),
                "dry_run": settings.get("dry_run", False),
            },
            "statistics": statistics,
        }
    )


@swaparr_bp.route("/settings", methods=["GET"])
def get_settings():
    """Get Swaparr settings"""
    settings = load_settings("swaparr")
    return jsonify(settings)


@swaparr_bp.route("/settings", methods=["POST"])
def update_settings():
    """Update Swaparr settings"""
    data = request.json

    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400

    # Load current settings
    settings = load_settings("swaparr")

    # Update settings with provided data
    for key, value in data.items():
        settings[key] = value

    # Save updated settings
    success = save_settings("swaparr", settings)

    if success:
        return jsonify({"success": True, "message": "Settings updated successfully"})
    else:
        return jsonify({"success": False, "message": "Failed to save settings"}), 500


@swaparr_bp.route("/reset", methods=["POST"])
def reset_strikes():
    """Reset all strikes for all apps or a specific app"""
    data = request.json
    app_name = data.get("app_name") if data else None

    state_dir = Path(os.getenv("NEUTARR_CONFIG_DIR", "/config")).resolve() / "swaparr"
    app_dirs = _get_swaparr_app_dirs(state_dir)

    if not state_dir.exists():
        return jsonify({"success": True, "message": "No strike data to reset"})

    if app_name:
        # Reset strikes for a specific app
        if app_name not in RESETTABLE_APPS:
            return jsonify({"success": False, "message": f"Invalid app name: {app_name}"}), 400
        app_dir = app_dirs[app_name]

        if app_dir.exists():
            strike_file = app_dir / "strikes.json"
            if strike_file.exists():
                try:
                    os.remove(strike_file)
                    swaparr_logger.info(f"Reset strikes for {app_name}")
                    return jsonify({"success": True, "message": f"Strikes reset for {app_name}"})
                except IOError as e:
                    swaparr_logger.error(f"Error resetting strikes for {app_name}: {str(e)}")
                    return jsonify(
                        {"success": False, "message": f"Failed to reset strikes for {app_name}: {str(e)}"}
                    ), 500
        return jsonify({"success": False, "message": f"No strike data found for {app_name}"}), 404
    else:
        # Reset strikes for all apps
        try:
            for app_dir in app_dirs.values():
                if app_dir.is_dir():
                    strike_file = app_dir / "strikes.json"
                    if strike_file.exists():
                        os.remove(strike_file)

            swaparr_logger.info("Reset all strikes")
            return jsonify({"success": True, "message": "All strikes reset"})
        except IOError as e:
            swaparr_logger.error(f"Error resetting all strikes: {str(e)}")
            return jsonify({"success": False, "message": f"Failed to reset all strikes: {str(e)}"}), 500


def register_routes(app):
    """Register Swaparr routes with the Flask app."""
    app.register_blueprint(swaparr_bp, url_prefix="/api/swaparr")
