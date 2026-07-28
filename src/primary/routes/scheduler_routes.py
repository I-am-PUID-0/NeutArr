#!/usr/bin/env python3
"""
Scheduler API Routes
Handles API endpoints for scheduler management
"""

import json
import logging
from flask import Blueprint, jsonify, request, Response
from datetime import datetime

# Import the scheduler engine to share validated schedule persistence
from src.primary.scheduler_engine import (
    SCHEDULE_FILE,
    ScheduleValidationError,
    get_execution_history,
    load_schedule,
    save_schedule,
)

# Create logger
scheduler_logger = logging.getLogger("scheduler")

# Create blueprint
scheduler_api = Blueprint("scheduler_api", __name__)


@scheduler_api.route("/api/scheduler/load", methods=["GET"])
def load_schedules():
    """Load schedules from the JSON file"""
    try:
        schedules = load_schedule()
        scheduler_logger.info(f"Loaded schedules from {SCHEDULE_FILE}")

        # Add CORS headers
        response = Response(json.dumps(schedules))
        response.headers["Content-Type"] = "application/json"
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    except Exception as e:
        error_msg = f"Error loading schedules: {str(e)}"
        scheduler_logger.error(error_msg)
        return jsonify({"error": "Error loading schedules"}), 500


@scheduler_api.route("/api/scheduler/history", methods=["GET"])
def get_scheduler_history():
    """Get the execution history of the scheduler"""
    try:
        # Get the execution history from the scheduler engine
        history = get_execution_history()

        # Add CORS headers
        response = Response(json.dumps({"success": True, "history": history, "timestamp": datetime.now().isoformat()}))
        response.headers["Content-Type"] = "application/json"
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    except Exception as e:
        error_msg = f"Error getting scheduler history: {str(e)}"
        scheduler_logger.error(error_msg)
        return jsonify({"error": "Error getting scheduler history"}), 500


@scheduler_api.route("/api/scheduler/save", methods=["POST"])
def save_schedules():
    """Save schedules to the JSON file"""
    try:
        schedules = request.get_json(silent=True)
        save_schedule(schedules)

        scheduler_logger.info(f"Saved schedules to {SCHEDULE_FILE}")

        # Add timestamp to response
        response_data = {
            "success": True,
            "message": "Schedules saved successfully",
            "timestamp": datetime.now().isoformat(),
            "file": SCHEDULE_FILE,
        }

        # Add CORS headers
        response = Response(json.dumps(response_data))
        response.headers["Content-Type"] = "application/json"
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    except ScheduleValidationError as error:
        scheduler_logger.warning(f"Rejected invalid schedule data: {error}")
        return jsonify({"error": "Schedule data is invalid"}), 400
    except Exception as e:
        error_msg = f"Error saving schedules: {str(e)}"
        scheduler_logger.error(error_msg)
        return jsonify({"error": "Error saving schedules"}), 500
