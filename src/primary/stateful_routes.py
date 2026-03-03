#!/usr/bin/env python3
"""
Stateful Management API Routes
Handles API endpoints for stateful management
"""

from flask import Blueprint, jsonify, request
from src.primary.stateful_manager import get_stateful_management_info, reset_stateful_management, update_lock_expiration
from src.primary.utils.logger import get_logger

# Create logger
stateful_logger = get_logger("stateful")

# Create blueprint
stateful_api = Blueprint("stateful_api", __name__)


def _json_response(payload: dict, status: int = 200):
    """Return a JSON response with the required CORS header."""
    response = jsonify(payload)
    response.status_code = status
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


@stateful_api.route("/info", methods=["GET"])
def get_info():
    """Get stateful management information."""
    try:
        info = get_stateful_management_info()
        response_data = {
            "success": True,
            "created_at_ts": info.get("created_at_ts"),
            "expires_at_ts": info.get("expires_at_ts"),
            "interval_hours": info.get("interval_hours"),
        }
        return _json_response(response_data)
    except Exception as e:
        stateful_logger.error(f"Error getting stateful info: {e}")
        return _json_response({"success": False, "message": "Error getting stateful info"}, status=500)


@stateful_api.route("/reset", methods=["POST"])
def reset_stateful():
    """Reset the stateful management system."""
    try:
        success = reset_stateful_management()
        if success:
            return _json_response({"success": True, "message": "Stateful management reset successfully"})
        else:
            return _json_response({"success": False, "message": "Failed to reset stateful management"}, status=500)
    except Exception as e:
        stateful_logger.error(f"Error resetting stateful management: {e}")
        return _json_response({"success": False, "message": "Error resetting stateful management"}, status=500)


@stateful_api.route("/update-expiration", methods=["POST"])
def update_expiration():
    """Update the stateful management expiration time."""
    try:
        data = request.get_json(silent=True) or {}
        hours = data.get("hours")
        if hours is None or not isinstance(hours, int) or hours <= 0:
            stateful_logger.error(f"Invalid hours value for update-expiration: {hours}")
            return _json_response(
                {"success": False, "message": "Invalid hours value. Must be a positive integer."}, status=400
            )

        updated = update_lock_expiration(hours)
        if updated:
            # Get updated info
            info = get_stateful_management_info()
            response_data = {
                "success": True,
                "message": "Expiration updated successfully",
                "expires_at": info.get("expires_at"),
                "expires_date": info.get("expires_date"),
            }
            return _json_response(response_data)
        else:
            return _json_response({"success": False, "message": "Failed to update expiration"}, status=500)
    except Exception as e:
        stateful_logger.error(f"Error updating expiration: {e}", exc_info=True)
        return _json_response({"success": False, "message": "Error updating expiration"}, status=500)
