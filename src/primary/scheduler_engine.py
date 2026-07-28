#!/usr/bin/env python3
"""
Scheduler Engine for NeutArr
Handles execution of scheduled actions from schedule.json
"""

import os
import json
import threading
import datetime
import time
import traceback
import pathlib
import shutil
import stat
import tempfile
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple
import collections

# Import settings_manager for validated, atomic configuration updates
from src.primary import settings_manager

from src.primary.utils.logger import get_logger

# Initialize logger
scheduler_logger = get_logger("scheduler")

# Scheduler constants
SCHEDULE_CHECK_INTERVAL = 60  # Check schedule every minute
SCHEDULE_DIR = os.path.join(os.environ.get("NEUTARR_CONFIG_DIR", "/config"), "scheduler")
SCHEDULE_FILE = os.path.join(SCHEDULE_DIR, "schedule.json")
SCHEDULABLE_APP_TYPES = ("sonarr", "radarr", "lidarr", "readarr", "whisparr", "eros")
SCHEDULE_GROUPS = ("global", *SCHEDULABLE_APP_TYPES)
SCHEDULE_DAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
MAX_SCHEDULE_ENTRIES = 1000

# Track last executed actions to prevent duplicates
last_executed_actions = {}

# Track execution history for logging
max_history_entries = 50
execution_history = collections.deque(maxlen=max_history_entries)

stop_event = threading.Event()
scheduler_thread = None
_schedule_file_lock = threading.RLock()


class ScheduleValidationError(ValueError):
    """Raised when a schedule payload cannot be persisted safely."""


def _empty_schedule() -> Dict[str, List[Dict[str, Any]]]:
    """Return a new schedule structure with every supported group."""
    return {group: [] for group in SCHEDULE_GROUPS}


def _normalize_schedule_days(days: Any, entry_label: str) -> List[str]:
    """Validate and normalize full or abbreviated weekday names."""
    if not isinstance(days, list):
        raise ScheduleValidationError(f"{entry_label}.days must be an array")

    normalized_days = []
    for day in days:
        if not isinstance(day, str):
            raise ScheduleValidationError(f"{entry_label}.days must contain only strings")
        normalized_day = day.strip().lower()
        matches = [weekday for weekday in SCHEDULE_DAYS if weekday.startswith(normalized_day)]
        if len(normalized_day) < 3 or len(matches) != 1:
            raise ScheduleValidationError(f"{entry_label}.days contains an invalid weekday")
        weekday = matches[0]
        if weekday not in normalized_days:
            normalized_days.append(weekday)
    return normalized_days


def _normalize_schedule_time(schedule: Dict[str, Any], entry_label: str) -> Dict[str, int]:
    """Validate current and legacy schedule time representations."""
    schedule_time = schedule.get("time")
    if isinstance(schedule_time, str):
        try:
            hour_text, minute_text = schedule_time.split(":", maxsplit=1)
            hour = int(hour_text)
            minute = int(minute_text)
        except (TypeError, ValueError):
            raise ScheduleValidationError(f"{entry_label}.time must use HH:MM") from None
    elif isinstance(schedule_time, dict):
        hour = schedule_time.get("hour")
        minute = schedule_time.get("minute")
    elif "hour" in schedule or "minute" in schedule:
        hour = schedule.get("hour")
        minute = schedule.get("minute")
    else:
        raise ScheduleValidationError(f"{entry_label}.time is required")

    if (
        isinstance(hour, bool)
        or not isinstance(hour, int)
        or isinstance(minute, bool)
        or not isinstance(minute, int)
        or not 0 <= hour <= 23
        or not 0 <= minute <= 59
    ):
        raise ScheduleValidationError(f"{entry_label}.time must contain a valid hour and minute")
    return {"hour": hour, "minute": minute}


def _validate_schedule_action(action: Any, entry_label: str) -> str:
    """Validate supported current and legacy scheduler actions."""
    if not isinstance(action, str):
        raise ScheduleValidationError(f"{entry_label}.action must be a string")
    if action in {"enable", "disable", "pause", "resume"}:
        return action

    prefix = "api-" if action.startswith("api-") else "API Limits " if action.startswith("API Limits ") else None
    if prefix is None:
        raise ScheduleValidationError(f"{entry_label}.action is not supported")
    try:
        api_limit = int(action.removeprefix(prefix))
    except ValueError:
        raise ScheduleValidationError(f"{entry_label}.action has an invalid API limit") from None
    if not 1 <= api_limit <= 500:
        raise ScheduleValidationError(f"{entry_label}.action API limit must be between 1 and 500")
    return action


def validate_schedule_data(schedule_data: Any) -> Dict[str, List[Dict[str, Any]]]:
    """Validate and normalize a complete schedule document."""
    if not isinstance(schedule_data, dict):
        raise ScheduleValidationError("Schedule data must be a JSON object")
    if not schedule_data:
        raise ScheduleValidationError("Schedule data must contain at least one application group")

    unknown_groups = set(schedule_data) - set(SCHEDULE_GROUPS)
    if unknown_groups:
        raise ScheduleValidationError("Schedule data contains an unsupported application group")

    normalized_data = _empty_schedule()
    seen_ids = set()
    entry_count = 0

    for group in SCHEDULE_GROUPS:
        entries = schedule_data.get(group, [])
        if not isinstance(entries, list):
            raise ScheduleValidationError(f"{group} schedules must be an array")

        for index, schedule in enumerate(entries):
            entry_count += 1
            if entry_count > MAX_SCHEDULE_ENTRIES:
                raise ScheduleValidationError(f"Schedule data may contain at most {MAX_SCHEDULE_ENTRIES} entries")

            entry_label = f"{group}[{index}]"
            if not isinstance(schedule, dict):
                raise ScheduleValidationError(f"{entry_label} must be an object")

            schedule_id = schedule.get("id")
            if not isinstance(schedule_id, str) or not schedule_id.strip() or len(schedule_id) > 128:
                raise ScheduleValidationError(f"{entry_label}.id must be a non-empty string up to 128 characters")
            schedule_id = schedule_id.strip()
            if schedule_id in seen_ids:
                raise ScheduleValidationError(f"{entry_label}.id must be unique")
            seen_ids.add(schedule_id)

            target = schedule.get("app")
            if _resolve_schedule_target(target) is None:
                raise ScheduleValidationError(f"{entry_label}.app is not a supported target")

            enabled = schedule.get("enabled", True)
            if not isinstance(enabled, bool):
                raise ScheduleValidationError(f"{entry_label}.enabled must be true or false")

            normalized_data[group].append(
                {
                    "id": schedule_id,
                    "time": _normalize_schedule_time(schedule, entry_label),
                    "days": _normalize_schedule_days(schedule.get("days", []), entry_label),
                    "action": _validate_schedule_action(schedule.get("action"), entry_label),
                    "app": target,
                    "enabled": enabled,
                    "appType": group,
                }
            )

    return normalized_data


def _atomic_write_schedule(schedule_data: Dict[str, List[Dict[str, Any]]]) -> None:
    """Durably replace schedule.json without exposing a partial document."""
    schedule_file = pathlib.Path(SCHEDULE_FILE)
    schedule_file.parent.mkdir(parents=True, exist_ok=True)
    existing_mode = stat.S_IMODE(schedule_file.stat().st_mode) if schedule_file.exists() else 0o600
    file_descriptor = None
    temp_path = None

    try:
        file_descriptor, temp_name = tempfile.mkstemp(
            dir=schedule_file.parent,
            prefix=f".{schedule_file.name}.",
            suffix=".tmp",
        )
        temp_path = pathlib.Path(temp_name)
        os.fchmod(file_descriptor, existing_mode)

        with os.fdopen(file_descriptor, "w", encoding="utf-8") as temp_file:
            file_descriptor = None
            json.dump(schedule_data, temp_file, indent=2)
            temp_file.write("\n")
            temp_file.flush()
            os.fsync(temp_file.fileno())

        os.replace(temp_path, schedule_file)
        temp_path = None

        try:
            directory_descriptor = os.open(schedule_file.parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        except OSError as error:
            scheduler_logger.debug(f"Unable to fsync scheduler directory {schedule_file.parent}: {error}")
    finally:
        if file_descriptor is not None:
            os.close(file_descriptor)
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def save_schedule(schedule_data: Any) -> Dict[str, List[Dict[str, Any]]]:
    """Validate and atomically persist a complete schedule document."""
    normalized_data = validate_schedule_data(deepcopy(schedule_data))
    with _schedule_file_lock:
        _atomic_write_schedule(normalized_data)
    return normalized_data


def _resolve_schedule_target(target: Any) -> Optional[Tuple[str, Optional[int]]]:
    """Resolve UI and legacy scheduler target values to a config and instance."""
    if target == "global":
        return "global", None

    if not isinstance(target, str):
        return None

    aliases = {
        "whisparr-v2": "whisparr",
        "whisparr-v3": "eros",
    }
    if target in aliases:
        return aliases[target], None

    if target in SCHEDULABLE_APP_TYPES:
        return target, None

    for app_type in SCHEDULABLE_APP_TYPES:
        prefix = f"{app_type}-"
        if not target.startswith(prefix):
            continue

        target_suffix = target.removeprefix(prefix)
        if target_suffix == "all":
            return app_type, None
        if target_suffix.isdecimal():
            return app_type, int(target_suffix)
        return None

    return None


def _set_enabled(config_data: Dict[str, Any], enabled: bool, instance_index: Optional[int] = None) -> None:
    """Apply a scheduled enabled state to all instances or one instance."""
    instances = config_data.get("instances")
    if instance_index is not None:
        if not isinstance(instances, list) or instance_index >= len(instances):
            raise ValueError(f"Unknown instance index: {instance_index}")
        instance = instances[instance_index]
        if not isinstance(instance, dict):
            raise ValueError(f"Invalid instance entry at index: {instance_index}")
        instance["enabled"] = enabled
        config_data["enabled"] = any(
            isinstance(candidate, dict) and candidate.get("enabled", True) for candidate in instances
        )
        return

    config_data["enabled"] = enabled
    if not isinstance(instances, list):
        return
    for instance in instances:
        if isinstance(instance, dict):
            instance["enabled"] = enabled


def _set_hourly_cap(config_data: Dict[str, Any], hourly_cap: int) -> None:
    """Apply a scheduled hourly API cap."""
    config_data["hourly_cap"] = hourly_cap


def _update_scheduled_app_settings(app_type: str, update_callback) -> bool:
    """Apply one update to a validated app target or every schedulable app."""
    target_apps = SCHEDULABLE_APP_TYPES if app_type == "global" else (app_type,)
    updated_apps = []

    for target_app in target_apps:
        settings_file = settings_manager.get_settings_file_path(target_app)
        if not settings_file.exists():
            if app_type != "global":
                scheduler_logger.error(
                    f"Unable to apply scheduled update for {target_app}; settings file does not exist"
                )
                return False
            scheduler_logger.debug(f"Skipping unconfigured app {target_app} during global scheduled update")
            continue
        if not settings_manager.update_settings(target_app, update_callback):
            return False
        updated_apps.append(target_app)

    if not updated_apps:
        scheduler_logger.error(
            f"Unable to apply scheduled update for {app_type}; no configured app settings were found"
        )
        return False

    return True


def load_schedule():
    """Load and validate schedule.json, repairing malformed files safely."""
    default_schedule = _empty_schedule()
    schedule_file = pathlib.Path(SCHEDULE_FILE)

    try:
        with _schedule_file_lock:
            schedule_file.parent.mkdir(parents=True, exist_ok=True)
            if not schedule_file.exists():
                _atomic_write_schedule(default_schedule)
                scheduler_logger.info("Created new schedule file with default structure")
                return default_schedule

            try:
                content = schedule_file.read_text(encoding="utf-8")
                if not content.strip():
                    raise ScheduleValidationError("Schedule file is empty")
                return validate_schedule_data(json.loads(content))
            except (json.JSONDecodeError, ScheduleValidationError) as error:
                scheduler_logger.error(f"Invalid schedule file: {error}")
                backup_file = schedule_file.with_name(f"{schedule_file.name}.backup.{time.time_ns()}")
                shutil.copy2(schedule_file, backup_file)
                _atomic_write_schedule(default_schedule)
                scheduler_logger.info(f"Backed up invalid schedule file to {backup_file}")
                scheduler_logger.info("Created new empty schedule file")
                return default_schedule
    except Exception as e:
        scheduler_logger.error(f"Error loading schedule: {e}")
        scheduler_logger.error(traceback.format_exc())
        return default_schedule


def add_to_history(action_entry, status, message):
    """Add an action execution to the history log"""
    now = datetime.datetime.now()
    time_str = now.strftime("%Y-%m-%d %H:%M:%S")

    history_entry = {
        "timestamp": time_str,
        "id": action_entry.get("id", "unknown"),
        "action": action_entry.get("action", "unknown"),
        "app": action_entry.get("app", "unknown"),
        "status": status,
        "message": message,
    }

    execution_history.appendleft(history_entry)
    scheduler_logger.debug(
        f"Scheduler history: {time_str} - {action_entry.get('action')} for {action_entry.get('app')} - {status} - {message}"
    )


def execute_action(action_entry, scheduled_for=None):
    """Execute a scheduled action"""
    if not isinstance(action_entry, dict):
        scheduler_logger.error("Refused malformed scheduler action: expected an object")
        return False

    action_type = action_entry.get("action")
    raw_target = action_entry.get("app")
    app_id = action_entry.get("id")

    if not isinstance(action_type, str):
        message = "Invalid scheduler action type"
        scheduler_logger.error(message)
        add_to_history(action_entry, "error", message)
        return False

    resolved_target = _resolve_schedule_target(raw_target)
    if resolved_target is None:
        message = f"Invalid scheduler app target: {raw_target}"
        scheduler_logger.error(message)
        add_to_history(action_entry, "error", message)
        return False
    app_type, instance_index = resolved_target

    if isinstance(scheduled_for, datetime.datetime):
        execution_date = scheduled_for.date()
    elif isinstance(scheduled_for, datetime.date):
        execution_date = scheduled_for
    else:
        execution_date = datetime.datetime.now().date()
    execution_key = f"{app_id}_{execution_date.isoformat()}"

    # Check if this action was already executed for this scheduled occurrence
    if execution_key in last_executed_actions:
        message = f"Action {app_id} for {app_type} already executed for {execution_date.isoformat()}, skipping"
        scheduler_logger.debug(message)
        add_to_history(action_entry, "skipped", message)
        return False  # Already executed

    try:
        # Handle both old "pause" and new "disable" terminology
        if action_type == "pause" or action_type == "disable":
            if app_type == "global":
                message = "Executing global pause action"
                result_message = "All apps disabled successfully"
            else:
                message = f"Executing disable action for {app_type}"
                result_message = f"{app_type} disabled successfully"

            scheduler_logger.info(message)
            if not _update_scheduled_app_settings(
                app_type,
                lambda config: _set_enabled(config, False, instance_index),
            ):
                error_message = f"Error disabling {raw_target}"
                scheduler_logger.error(error_message)
                add_to_history(action_entry, "error", error_message)
                return False
            scheduler_logger.info(result_message)
            add_to_history(action_entry, "success", result_message)

        # Handle both old "resume" and new "enable" terminology
        elif action_type == "resume" or action_type == "enable":
            if app_type == "global":
                message = "Executing global enable action"
                result_message = "All apps enabled successfully"
            else:
                message = f"Executing enable action for {app_type}"
                result_message = f"{app_type} enabled successfully"

            scheduler_logger.info(message)
            if not _update_scheduled_app_settings(
                app_type,
                lambda config: _set_enabled(config, True, instance_index),
            ):
                error_message = f"Error enabling {raw_target}"
                scheduler_logger.error(error_message)
                add_to_history(action_entry, "error", error_message)
                return False
            scheduler_logger.info(result_message)
            add_to_history(action_entry, "success", result_message)

        # Handle the API limit actions based on the predefined values
        elif action_type.startswith("api-") or action_type.startswith("API Limits "):
            # Extract the API limit value from the action type
            try:
                # Handle both formats: "api-5" and "API Limits 5"
                if action_type.startswith("api-"):
                    api_limit = int(action_type.replace("api-", ""))
                else:
                    api_limit = int(action_type.replace("API Limits ", ""))

                if app_type == "global":
                    message = f"Setting global API cap to {api_limit}"
                    result_message = f"API cap set to {api_limit} for all apps"
                else:
                    message = f"Setting API cap for {app_type} to {api_limit}"
                    result_message = f"API cap set to {api_limit} for {app_type}"

                scheduler_logger.info(message)
                if not _update_scheduled_app_settings(
                    app_type,
                    lambda config: _set_hourly_cap(config, api_limit),
                ):
                    error_message = f"Error setting API cap for {app_type} to {api_limit}"
                    scheduler_logger.error(error_message)
                    add_to_history(action_entry, "error", error_message)
                    return False
                scheduler_logger.info(result_message)
                add_to_history(action_entry, "success", result_message)
            except ValueError:
                error_message = f"Invalid API limit format: {action_type}"
                scheduler_logger.error(error_message)
                add_to_history(action_entry, "error", error_message)
                return False

        else:
            error_message = f"Invalid scheduler action: {action_type}"
            scheduler_logger.error(error_message)
            add_to_history(action_entry, "error", error_message)
            return False

        # Mark this action as executed for today
        last_executed_actions[execution_key] = datetime.datetime.now()
        return True

    except Exception as e:
        scheduler_logger.error(f"Error executing action {action_type} for {app_type}: {e}")
        scheduler_logger.error(traceback.format_exc())
        return False


def should_execute_schedule(schedule_entry, current_time=None):
    """Check whether the most recent scheduled occurrence is in its run window."""
    if not isinstance(schedule_entry, dict):
        scheduler_logger.warning("Invalid schedule entry: expected an object")
        return False

    schedule_entry.pop("_scheduled_for", None)
    schedule_id = schedule_entry.get("id", "unknown")
    scheduler_logger.debug(f"Checking if schedule {schedule_id} should be executed")

    if not schedule_entry.get("enabled", True):
        scheduler_logger.debug(f"Schedule {schedule_id} is disabled, skipping")
        return False

    if current_time is None:
        current_time = datetime.datetime.now()
    if not isinstance(current_time, datetime.datetime):
        scheduler_logger.warning("Invalid scheduler comparison time")
        return False

    try:
        schedule_hour = schedule_entry.get("hour")
        schedule_minute = schedule_entry.get("minute")

        if schedule_hour is None or schedule_minute is None:
            schedule_hour = schedule_entry.get("time", {}).get("hour")
            schedule_minute = schedule_entry.get("time", {}).get("minute")

        schedule_hour = int(schedule_hour)
        schedule_minute = int(schedule_minute)
        if not 0 <= schedule_hour <= 23 or not 0 <= schedule_minute <= 59:
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        scheduler_logger.warning(f"Invalid schedule time format in entry: {schedule_entry}")
        return False

    scheduled_at = current_time.replace(
        hour=schedule_hour,
        minute=schedule_minute,
        second=0,
        microsecond=0,
    )
    if scheduled_at > current_time:
        scheduled_at -= datetime.timedelta(days=1)

    days = schedule_entry.get("days", [])
    scheduled_day = scheduled_at.strftime("%A").lower()
    if days and scheduled_day not in {str(day).lower() for day in days}:
        scheduler_logger.debug(
            f"Schedule {schedule_id} is not configured for its most recent occurrence on {scheduled_day}"
        )
        return False

    elapsed = current_time - scheduled_at
    should_execute = datetime.timedelta(0) <= elapsed < datetime.timedelta(minutes=4)
    if should_execute:
        schedule_entry["_scheduled_for"] = scheduled_at
        scheduler_logger.info(
            f"Schedule {schedule_id} is within its execution window "
            f"({scheduled_at.strftime('%Y-%m-%d %H:%M')} scheduled)"
        )
    else:
        scheduler_logger.debug(
            f"Schedule {schedule_id} is outside its execution window "
            f"({scheduled_at.strftime('%Y-%m-%d %H:%M')} scheduled)"
        )
    return should_execute


def check_and_execute_schedules():
    """Check all schedules and execute those that should run now"""
    try:
        # Format time
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        scheduler_logger.debug(f"Checking schedules at {current_time}")

        # Check if schedule file exists and log its status
        if not os.path.exists(SCHEDULE_FILE):
            scheduler_logger.debug(f"Schedule file does not exist: {SCHEDULE_FILE}")
            add_to_history({"action": "check"}, "debug", f"Schedule file not found at {SCHEDULE_FILE}")
            return

        scheduler_logger.debug(
            f"Schedule file exists at {SCHEDULE_FILE} with size {os.path.getsize(SCHEDULE_FILE)} bytes"
        )

        # Load the schedule
        schedule_data = load_schedule()
        if not schedule_data:
            return

        # Log schedule data summary
        schedule_summary = {app: len(schedules) for app, schedules in schedule_data.items()}
        scheduler_logger.debug(f"Loaded schedules: {schedule_summary}")

        # Add to history that we've checked schedules
        add_to_history({"action": "check"}, "debug", f"Checking schedules at {current_time}")

        # Initialize counter for schedules found
        schedules_found = 0

        # Check for schedules to execute
        for app_type, schedules in schedule_data.items():
            for schedule_entry in schedules:
                schedules_found += 1
                if should_execute_schedule(schedule_entry):
                    # Check if we already executed this entry in the last 5 minutes
                    entry_id = schedule_entry.get("id")
                    if entry_id and entry_id in last_executed_actions:
                        last_time = last_executed_actions[entry_id]
                        now = datetime.datetime.now()
                        delta = (now - last_time).total_seconds() / 60  # Minutes

                        if delta < 5:  # Don't re-execute if less than 5 minutes have passed
                            scheduler_logger.info(
                                f"Skipping recently executed schedule '{entry_id}' ({delta:.1f} minutes ago)"
                            )
                            add_to_history(schedule_entry, "skipped", f"Already executed {delta:.1f} minutes ago")
                            continue

                    # Execute the action
                    schedule_entry["appType"] = app_type
                    action_succeeded = execute_action(
                        schedule_entry,
                        scheduled_for=schedule_entry.pop("_scheduled_for", None),
                    )

                    # Update last executed time
                    if entry_id and action_succeeded:
                        last_executed_actions[entry_id] = datetime.datetime.now()

        # No need to log anything when no schedules are found, as this is expected

    except Exception as e:
        error_msg = f"Error checking schedules: {e}"
        scheduler_logger.error(error_msg)
        scheduler_logger.error(traceback.format_exc())
        add_to_history({"action": "check"}, "error", error_msg)


def scheduler_loop():
    """Main scheduler loop - runs in a background thread"""
    scheduler_logger.info("Scheduler engine started")

    # Clean up expired entries from last_executed_actions
    now = datetime.datetime.now()
    yesterday = now - datetime.timedelta(days=1)
    for key in list(last_executed_actions.keys()):
        if last_executed_actions[key] < yesterday:
            del last_executed_actions[key]

    while not stop_event.is_set():
        try:
            check_and_execute_schedules()

            # Sleep until the next check
            stop_event.wait(SCHEDULE_CHECK_INTERVAL)

        except Exception as e:
            scheduler_logger.error(f"Error in scheduler loop: {e}")
            scheduler_logger.error(traceback.format_exc())
            # Sleep briefly to avoid rapidly repeating errors
            time.sleep(5)

    scheduler_logger.info("Scheduler engine stopped")


def get_execution_history():
    """Get the execution history for the scheduler"""
    return list(execution_history)


def start_scheduler():
    """Start the scheduler engine"""
    global scheduler_thread

    if scheduler_thread and scheduler_thread.is_alive():
        scheduler_logger.info("Scheduler already running")
        return

    # Reset the stop event
    stop_event.clear()

    # Create and start the scheduler thread
    scheduler_thread = threading.Thread(target=scheduler_loop, name="SchedulerEngine", daemon=True)
    scheduler_thread.start()

    # Add a startup entry to the history
    startup_entry = {"id": "system", "action": "startup", "app": "scheduler"}
    add_to_history(startup_entry, "info", "Scheduler engine started")

    scheduler_logger.info(f"Scheduler engine started. Thread is alive: {scheduler_thread.is_alive()}")
    return True


def stop_scheduler():
    """Stop the scheduler engine"""
    global scheduler_thread

    if not scheduler_thread or not scheduler_thread.is_alive():
        scheduler_logger.info("Scheduler not running")
        return

    # Signal the thread to stop
    stop_event.set()

    # Wait for the thread to terminate (with timeout)
    scheduler_thread.join(timeout=5.0)

    if scheduler_thread.is_alive():
        scheduler_logger.warning("Scheduler did not terminate gracefully")
    else:
        scheduler_logger.info("Scheduler stopped gracefully")
