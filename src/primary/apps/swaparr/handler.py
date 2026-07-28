"""
Implementation of the swaparr functionality to detect and remove stalled downloads in Starr apps.
Based on the functionality provided by https://github.com/ThijmenGThN/swaparr
"""

import os
import json
import time
import hashlib
import pathlib
import stat
import tempfile
import threading
from datetime import UTC, datetime, timedelta
import requests

from src.primary.instance_storage import instance_storage_key
from src.primary.utils.logger import get_logger
from src.primary.settings_manager import load_settings

# Create logger
swaparr_logger = get_logger("swaparr")

# Create state directory for tracking strikes
SWAPARR_STATE_DIR = os.path.join(os.getenv("NEUTARR_CONFIG_DIR", "/config"), "swaparr")
SWAPARR_APP_TYPES = ["sonarr", "radarr", "lidarr", "readarr", "whisparr", "eros"]
swaparr_state_locks = {}
swaparr_state_locks_guard = threading.Lock()
swaparr_legacy_migration_lock = threading.Lock()


def _get_state_lock(app_name, instance_name):
    """Return the lock protecting one app instance's complete state cycle."""
    lock_key = (app_name, instance_storage_key(instance_name))
    with swaparr_state_locks_guard:
        return swaparr_state_locks.setdefault(lock_key, threading.RLock())


def _get_state_file(app_name, instance_name, filename):
    """Return a collision-resistant state path for one Swaparr instance."""
    app_state_dir = pathlib.Path(ensure_state_directory(app_name))
    instance_state_dir = app_state_dir / instance_storage_key(instance_name)
    instance_state_dir.mkdir(parents=True, exist_ok=True)
    return instance_state_dir / filename


def _atomic_write_json(file_path, data):
    """Durably replace Swaparr state without exposing partial JSON."""
    file_path = pathlib.Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    existing_mode = stat.S_IMODE(file_path.stat().st_mode) if file_path.exists() else 0o600
    file_descriptor = None
    temp_path = None

    try:
        file_descriptor, temp_name = tempfile.mkstemp(
            dir=file_path.parent,
            prefix=f".{file_path.name}.",
            suffix=".tmp",
        )
        temp_path = pathlib.Path(temp_name)
        os.fchmod(file_descriptor, existing_mode)

        with os.fdopen(file_descriptor, "w", encoding="utf-8") as temp_file:
            file_descriptor = None
            json.dump(data, temp_file, indent=2)
            temp_file.write("\n")
            temp_file.flush()
            os.fsync(temp_file.fileno())

        os.replace(temp_path, file_path)
        temp_path = None

        try:
            directory_descriptor = os.open(file_path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        except OSError as error:
            swaparr_logger.debug(f"Unable to fsync Swaparr state directory {file_path.parent}: {error}")
    finally:
        if file_descriptor is not None:
            os.close(file_descriptor)
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _migrate_legacy_state_file(app_name, instance_name, filename, allow_legacy_migration):
    """Move app-global state only when it can be assigned to one instance safely."""
    state_file = _get_state_file(app_name, instance_name, filename)
    legacy_file = pathlib.Path(ensure_state_directory(app_name)) / filename

    if state_file.exists() or not legacy_file.exists():
        return state_file

    if not allow_legacy_migration:
        swaparr_logger.warning(
            "Ignoring legacy app-global Swaparr state for %s because multiple instances are enabled",
            app_name,
        )
        return state_file

    with swaparr_legacy_migration_lock:
        if not state_file.exists() and legacy_file.exists():
            os.replace(legacy_file, state_file)
            swaparr_logger.info(
                "Migrated legacy Swaparr %s state to instance %s/%s",
                filename,
                app_name,
                instance_name,
            )

    return state_file


def _load_state_object(file_path, state_label):
    """Load a state object while preserving malformed documents for recovery."""
    try:
        with open(file_path, "r", encoding="utf-8") as state_document:
            data = json.load(state_document)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError) as error:
        swaparr_logger.error(f"Error loading {state_label} from {file_path}: {error}")
        return None

    if not isinstance(data, dict):
        swaparr_logger.error(f"Error loading {state_label} from {file_path}: expected an object")
        return None

    return data


def _utc_now():
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


def _parse_utc_timestamp(value):
    """Normalize legacy naive and offset timestamps to timezone-aware UTC."""
    parsed_timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed_timestamp.tzinfo is None:
        parsed_timestamp = parsed_timestamp.replace(tzinfo=UTC)
    return parsed_timestamp.astimezone(UTC)


def is_enabled_for_app(app_name, swaparr_settings):
    """Return whether Swaparr should process a specific app type."""
    app_enabled = swaparr_settings.get("app_enabled", {}) if swaparr_settings else {}
    if not isinstance(app_enabled, dict):
        return False
    return app_enabled.get(app_name, False) is True


def is_enabled_for_app_instance(app_name, app_settings, swaparr_settings):
    """Return whether Swaparr should process a specific app instance."""
    if not is_enabled_for_app(app_name, swaparr_settings):
        return False

    app_instances = swaparr_settings.get("app_instances", {}) if swaparr_settings else {}
    if not isinstance(app_instances, dict):
        return False

    instance_toggles = app_instances.get(app_name, {})
    if not isinstance(instance_toggles, dict):
        return False

    instance_name = app_settings.get("instance_name") or app_settings.get("name") or "Default"
    instance_index = app_settings.get("instance_index")

    if instance_name in instance_toggles:
        return instance_toggles[instance_name] is True
    if instance_index is not None and str(instance_index) in instance_toggles:
        return instance_toggles[str(instance_index)] is True

    return False


def ensure_state_directory(app_name):
    """Ensure the state directory exists for tracking strikes for a specific app"""
    app_state_dir = os.path.join(SWAPARR_STATE_DIR, app_name)
    if not os.path.exists(app_state_dir):
        os.makedirs(app_state_dir, exist_ok=True)
        swaparr_logger.info(f"Created swaparr state directory for {app_name}: {app_state_dir}")
    return app_state_dir


def load_strike_data(app_name, instance_name="Default", allow_legacy_migration=True):
    """Load strike data for a specific app instance."""
    strike_file = _migrate_legacy_state_file(
        app_name,
        instance_name,
        "strikes.json",
        allow_legacy_migration,
    )
    return _load_state_object(strike_file, f"strike data for {app_name}/{instance_name}")


def save_strike_data(app_name, strike_data, instance_name="Default"):
    """Save strike data for a specific app instance."""
    strike_file = _get_state_file(app_name, instance_name, "strikes.json")

    try:
        _atomic_write_json(strike_file, strike_data)
        return True
    except (OSError, TypeError, ValueError) as error:
        swaparr_logger.error(f"Error saving strike data for {app_name}/{instance_name}: {error}")
        return False


def load_removed_items(app_name, instance_name="Default", allow_legacy_migration=True):
    """Load permanently removed items for a specific app instance."""
    removed_file = _migrate_legacy_state_file(
        app_name,
        instance_name,
        "removed_items.json",
        allow_legacy_migration,
    )
    return _load_state_object(removed_file, f"removed items for {app_name}/{instance_name}")


def save_removed_items(app_name, removed_items, instance_name="Default"):
    """Save permanently removed items for a specific app instance."""
    removed_file = _get_state_file(app_name, instance_name, "removed_items.json")

    try:
        _atomic_write_json(removed_file, removed_items)
        return True
    except (OSError, TypeError, ValueError) as error:
        swaparr_logger.error(f"Error saving removed items for {app_name}/{instance_name}: {error}")
        return False


def generate_item_hash(item):
    """Generate a unique hash for an item based on its name and size.
    This helps track items across restarts even if their queue ID changes."""
    hash_input = f"{item['name']}_{item['size']}"
    return hashlib.md5(hash_input.encode("utf-8"), usedforsecurity=False).hexdigest()


def parse_time_string_to_seconds(time_string):
    """Parse a time string like '2h', '30m', '1d' to seconds"""
    if not time_string:
        return 7200  # Default 2 hours

    unit = time_string[-1].lower()
    try:
        value = int(time_string[:-1])
    except ValueError:
        swaparr_logger.error(f"Invalid time string: {time_string}, using default 2 hours")
        return 7200

    if unit == "d":
        return value * 86400  # Days to seconds
    elif unit == "h":
        return value * 3600  # Hours to seconds
    elif unit == "m":
        return value * 60  # Minutes to seconds
    else:
        swaparr_logger.error(f"Unknown time unit in: {time_string}, using default 2 hours")
        return 7200


def parse_size_string_to_bytes(size_string):
    """Parse a size string like '25GB', '1TB' to bytes"""
    if not size_string:
        return 25 * 1024 * 1024 * 1024  # Default 25GB

    # Extract the numeric part and unit
    unit = ""
    for i in range(len(size_string) - 1, -1, -1):
        if not size_string[i].isalpha():
            value = float(size_string[: i + 1])
            unit = size_string[i + 1 :].upper()
            break
    else:
        swaparr_logger.error(f"Invalid size string: {size_string}, using default 25GB")
        return 25 * 1024 * 1024 * 1024

    # Convert to bytes based on unit
    if unit == "B":
        return int(value)
    elif unit == "KB":
        return int(value * 1024)
    elif unit == "MB":
        return int(value * 1024 * 1024)
    elif unit == "GB":
        return int(value * 1024 * 1024 * 1024)
    elif unit == "TB":
        return int(value * 1024 * 1024 * 1024 * 1024)
    else:
        swaparr_logger.error(f"Unknown size unit in: {size_string}, using default 25GB")
        return 25 * 1024 * 1024 * 1024


def get_queue_items(app_name, api_url, api_key, api_timeout=120):
    """Get download queue items from a Starr app API with pagination support"""
    api_version_map = {"radarr": "v3", "sonarr": "v3", "lidarr": "v1", "readarr": "v1", "whisparr": "v3"}

    api_version = api_version_map.get(app_name, "v3")

    # Initialize an empty list to store all records
    all_records = []

    # Start with page 1
    page = 1
    page_size = 100  # Request a large page size to reduce API calls

    while True:
        # Add pagination parameters
        queue_url = f"{api_url.rstrip('/')}/api/{api_version}/queue?page={page}&pageSize={page_size}"
        headers = {"X-Api-Key": api_key}

        try:
            response = requests.get(queue_url, headers=headers, timeout=api_timeout)
            response.raise_for_status()
            queue_data = response.json()

            if isinstance(queue_data, dict):
                records = queue_data.get("records", [])
                total_records = queue_data.get("totalRecords")
            elif isinstance(queue_data, list):
                records = queue_data
                total_records = len(records)
            else:
                swaparr_logger.error(
                    f"Unexpected queue response for {app_name} (page {page}): "
                    f"expected an object or list, got {type(queue_data).__name__}"
                )
                break

            if not isinstance(records, list):
                swaparr_logger.error(
                    f"Unexpected records value for {app_name} (page {page}): "
                    f"expected a list, got {type(records).__name__}"
                )
                break

            if total_records is None:
                total_records = len(all_records) + len(records)
            else:
                try:
                    total_records = int(total_records)
                except (TypeError, ValueError):
                    swaparr_logger.warning(
                        f"Invalid totalRecords value for {app_name} (page {page}): {total_records!r}; "
                        "treating the current page as complete"
                    )
                    total_records = len(all_records) + len(records)

            # Add this page's records to our collection
            all_records.extend(records)

            # If we've fetched all records or there are no more, break the loop
            if len(all_records) >= total_records or len(records) == 0:
                break

            # Otherwise, move to the next page
            page += 1

        except requests.exceptions.RequestException as e:
            swaparr_logger.error(f"Error fetching queue for {app_name} (page {page}): {str(e)}")
            break

    swaparr_logger.info(f"Fetched {len(all_records)} queue items for {app_name}")

    # Normalize the response based on app type
    if app_name in ["radarr", "whisparr", "eros"]:
        return parse_queue_items(all_records, "movie", app_name)
    elif app_name == "sonarr":
        return parse_queue_items(all_records, "series", app_name)
    elif app_name == "lidarr":
        return parse_queue_items(all_records, "album", app_name)
    elif app_name == "readarr":
        return parse_queue_items(all_records, "book", app_name)
    else:
        swaparr_logger.error(f"Unknown app type: {app_name}")
        return []


def parse_queue_items(records, item_type, app_name):
    """Parse queue items from API response into a standardized format"""
    queue_items = []

    for record in records:
        # Skip non-dictionary records
        if not isinstance(record, dict):
            swaparr_logger.warning(f"Skipping non-dictionary record in {app_name} queue: {record}")
            continue

        # Extract the name based on the item type
        name = None
        if item_type == "movie" and record.get("movie"):
            name = record["movie"].get("title", "Unknown Movie")
        elif item_type == "series" and record.get("series"):
            name = record["series"].get("title", "Unknown Series")
        elif item_type == "album" and record.get("album"):
            name = record["album"].get("title", "Unknown Album")
        elif item_type == "book" and record.get("book"):
            name = record["book"].get("title", "Unknown Book")

        # If no name was found, try to use the download title
        if not name and record.get("title"):
            name = record.get("title", "Unknown Download")

        # Parse ETA if available
        eta_seconds = 0
        if record.get("timeleft"):
            eta = record.get("timeleft", "")
            # Basic parsing of timeleft format like "00:30:00" (30 minutes)
            try:
                eta_parts = eta.split(":")
                if len(eta_parts) == 3:
                    eta_seconds = int(eta_parts[0]) * 3600 + int(eta_parts[1]) * 60 + int(eta_parts[2])
            except (ValueError, IndexError):
                eta_seconds = 0

        queue_items.append(
            {
                "id": record.get("id"),
                "name": name,
                "size": record.get("size", 0),
                "status": record.get("status", "unknown").lower(),
                "eta": eta_seconds,
                "error_message": record.get("errorMessage", ""),
            }
        )

    return queue_items


def delete_download(app_name, api_url, api_key, download_id, remove_from_client=True, api_timeout=120):
    """Delete a download from a Starr app"""
    api_version_map = {"radarr": "v3", "sonarr": "v3", "lidarr": "v1", "readarr": "v1", "whisparr": "v3"}

    api_version = api_version_map.get(app_name, "v3")
    delete_url = f"{api_url.rstrip('/')}/api/{api_version}/queue/{download_id}?removeFromClient={str(remove_from_client).lower()}&blocklist=true"
    headers = {"X-Api-Key": api_key}

    try:
        response = requests.delete(delete_url, headers=headers, timeout=api_timeout)
        response.raise_for_status()
        swaparr_logger.info(f"Successfully removed download {download_id} from {app_name}")
        return True
    except requests.exceptions.RequestException as e:
        swaparr_logger.error(f"Error removing download {download_id} from {app_name}: {str(e)}")
        return False


def _legacy_migration_is_safe(app_name, swaparr_settings):
    """Return whether app-global state can be assigned to one enabled instance."""
    app_instances = swaparr_settings.get("app_instances", {}) if swaparr_settings else {}
    instance_toggles = app_instances.get(app_name, {}) if isinstance(app_instances, dict) else {}
    if not isinstance(instance_toggles, dict):
        return False
    return sum(value is True for value in instance_toggles.values()) <= 1


def process_stalled_downloads(app_name, app_settings, swaparr_settings=None):
    """Process one app instance while serializing its state transition."""
    if not swaparr_settings:
        swaparr_settings = load_settings("swaparr")

    if not swaparr_settings or not swaparr_settings.get("enabled", False):
        swaparr_logger.debug(
            f"Swaparr is disabled, skipping {app_name} instance: {app_settings.get('instance_name', 'Unknown')}"
        )
        return

    if not is_enabled_for_app_instance(app_name, app_settings, swaparr_settings):
        swaparr_logger.debug(
            f"Swaparr is disabled for {app_name} instance: {app_settings.get('instance_name', 'Unknown')}"
        )
        return

    instance_name = app_settings.get("instance_name") or app_settings.get("name") or "Default"
    with _get_state_lock(app_name, instance_name):
        return _process_stalled_downloads(app_name, app_settings, swaparr_settings)


def _process_stalled_downloads(app_name, app_settings, swaparr_settings):
    """Run a Swaparr cycle with the instance state lock already held."""
    swaparr_logger.info(
        f"Processing stalled downloads for {app_name} instance: {app_settings.get('instance_name', 'Unknown')}"
    )

    # Get settings
    max_strikes = swaparr_settings.get("max_strikes", 3)
    max_download_time = parse_time_string_to_seconds(swaparr_settings.get("max_download_time", "2h"))
    ignore_above_size = parse_size_string_to_bytes(swaparr_settings.get("ignore_above_size", "25GB"))
    remove_from_client = swaparr_settings.get("remove_from_client", True)
    dry_run = swaparr_settings.get("dry_run", False)

    api_url = app_settings.get("api_url")
    api_key = app_settings.get("api_key")
    api_timeout = app_settings.get("api_timeout", 120)

    if not api_url or not api_key:
        swaparr_logger.error(
            f"Missing API URL or API Key for {app_name} instance: {app_settings.get('instance_name', 'Unknown')}"
        )
        return

    instance_name = app_settings.get("instance_name") or app_settings.get("name") or "Default"
    allow_legacy_migration = _legacy_migration_is_safe(app_name, swaparr_settings)

    # Load existing strike data
    strike_data = load_strike_data(app_name, instance_name, allow_legacy_migration)

    # Load list of permanently removed items
    removed_items = load_removed_items(app_name, instance_name, allow_legacy_migration)

    if strike_data is None or removed_items is None:
        swaparr_logger.error(
            "Refusing to process %s/%s because its persisted Swaparr state is malformed",
            app_name,
            instance_name,
        )
        return

    # Clean up expired removed items (older than 30 days)
    now = _utc_now()
    for item_hash in list(removed_items.keys()):
        try:
            removed_date = _parse_utc_timestamp(removed_items[item_hash]["removed_time"])
        except (KeyError, TypeError, ValueError):
            swaparr_logger.warning(f"Discarding malformed removed-item state for {app_name}/{instance_name}")
            del removed_items[item_hash]
            continue
        if (now - removed_date) > timedelta(days=30):
            swaparr_logger.debug(f"Removing expired entry from removed items list: {removed_items[item_hash]['name']}")
            del removed_items[item_hash]

    # Get current queue items
    queue_items = get_queue_items(app_name, api_url, api_key, api_timeout)

    if not queue_items:
        swaparr_logger.info(
            f"No queue items found for {app_name} instance: {app_settings.get('instance_name', 'Unknown')}"
        )
        return

    # Keep track of items still in queue for cleanup
    current_item_ids = set(item["id"] for item in queue_items)

    # Clean up items that are no longer in the queue
    for item_id in list(strike_data.keys()):
        if int(item_id) not in current_item_ids:
            swaparr_logger.debug(f"Removing item {item_id} from strike list as it's no longer in the queue")
            del strike_data[item_id]

    # Process each queue item
    for item in queue_items:
        item_id = str(item["id"])
        item_state = "Normal"
        item_hash = generate_item_hash(item)

        # Check if this item has been previously removed
        if item_hash in removed_items:
            last_removed_date = _parse_utc_timestamp(removed_items[item_hash]["removed_time"])
            days_since_removal = (now - last_removed_date).days

            # Re-remove it automatically if it's been less than 7 days since last removal
            if days_since_removal < 7:
                swaparr_logger.warning(
                    f"Found previously removed download that reappeared: {item['name']} (removed {days_since_removal} days ago)"
                )

                if not dry_run:
                    if delete_download(app_name, api_url, api_key, item["id"], remove_from_client, api_timeout):
                        swaparr_logger.info(f"Re-removed previously removed download: {item['name']}")
                        # Update the removal time
                        removed_items[item_hash]["removed_time"] = _utc_now().isoformat()
                else:
                    swaparr_logger.info(f"DRY RUN: Would have re-removed previously removed download: {item['name']}")

                item_state = "Re-removed" if not dry_run else "Would Re-remove (Dry Run)"
                continue

        # Skip large files if configured
        if item["size"] >= ignore_above_size:
            swaparr_logger.debug(
                f"Ignoring large download: {item['name']} ({item['size']} bytes > {ignore_above_size} bytes)"
            )
            item_state = "Ignored (Size)"
            continue

        # Handle delayed items - we'll skip these
        if item["status"] == "delay":
            swaparr_logger.debug(f"Ignoring delayed download: {item['name']}")
            item_state = "Ignored (Delayed)"
            continue

        # Special handling for "queued" status
        # We only skip truly queued items, not those with metadata issues
        metadata_issue = "metadata" in item["status"].lower() or "metadata" in item["error_message"].lower()

        if item["status"] == "queued" and not metadata_issue:
            # For regular queued items, check how long they've been in strike data
            if item_id in strike_data and "first_strike_time" in strike_data[item_id]:
                try:
                    first_strike = _parse_utc_timestamp(strike_data[item_id]["first_strike_time"])
                except (TypeError, ValueError):
                    first_strike = now
                    strike_data[item_id]["first_strike_time"] = now.isoformat()
                    swaparr_logger.warning(f"Reset malformed first-strike timestamp for {app_name}/{instance_name}")
                if (now - first_strike) < timedelta(hours=1):
                    # Skip if it's been less than 1 hour since first seeing it
                    swaparr_logger.debug(f"Ignoring recently queued download: {item['name']}")
                    item_state = "Ignored (Recently Queued)"
                    continue
            else:
                # Initialize with first strike time for queued items
                if item_id not in strike_data:
                    strike_data[item_id] = {
                        "strikes": 0,
                        "name": item["name"],
                        "first_strike_time": _utc_now().isoformat(),
                        "last_strike_time": None,
                    }
                swaparr_logger.debug(f"Monitoring new queued download: {item['name']}")
                item_state = "Monitoring (Queued)"
                continue

        # Initialize strike count if not already in strike data
        if item_id not in strike_data:
            strike_data[item_id] = {
                "strikes": 0,
                "name": item["name"],
                "first_strike_time": _utc_now().isoformat(),
                "last_strike_time": None,
            }

        # Check if download should be striked
        should_strike = False
        strike_reason = ""

        # Strike if metadata issue, eta too long, or no progress (eta = 0 and not queued)
        if metadata_issue:
            should_strike = True
            strike_reason = "Metadata"
        elif item["eta"] >= max_download_time:
            should_strike = True
            strike_reason = "ETA too long"
        elif item["eta"] == 0 and item["status"] not in ["queued", "delay"]:
            should_strike = True
            strike_reason = "No progress"

        # If we should strike this item, add a strike
        if should_strike:
            strike_data[item_id]["strikes"] += 1
            strike_data[item_id]["last_strike_time"] = _utc_now().isoformat()

            if strike_data[item_id]["first_strike_time"] is None:
                strike_data[item_id]["first_strike_time"] = _utc_now().isoformat()

            current_strikes = strike_data[item_id]["strikes"]
            swaparr_logger.info(
                f"Added strike ({current_strikes}/{max_strikes}) to {item['name']} - Reason: {strike_reason}"
            )

            # If max strikes reached, remove the download
            if current_strikes >= max_strikes:
                swaparr_logger.warning(f"Max strikes reached for {item['name']}, removing download")

                if not dry_run:
                    if delete_download(app_name, api_url, api_key, item["id"], remove_from_client, api_timeout):
                        swaparr_logger.info(f"Successfully removed {item['name']} after {max_strikes} strikes")

                        # Keep the item in strike data for reference but mark as removed
                        strike_data[item_id]["removed"] = True
                        strike_data[item_id]["removed_time"] = _utc_now().isoformat()

                        # Add to removed items list for persistent tracking
                        removed_items[item_hash] = {
                            "name": item["name"],
                            "size": item["size"],
                            "removed_time": _utc_now().isoformat(),
                            "reason": strike_reason,
                        }
                else:
                    swaparr_logger.info(f"DRY RUN: Would have removed {item['name']} after {max_strikes} strikes")

                item_state = "Removed" if not dry_run else "Would Remove (Dry Run)"
            else:
                item_state = f"Striked ({current_strikes}/{max_strikes})"

        swaparr_logger.debug(f"Processed download: {item['name']} - State: {item_state}")

    # Save updated strike data
    strike_saved = save_strike_data(app_name, strike_data, instance_name)

    # Save updated removed items list
    removed_saved = save_removed_items(app_name, removed_items, instance_name)

    if not strike_saved or not removed_saved:
        swaparr_logger.error(f"Failed to persist complete Swaparr state for {app_name}/{instance_name}")
        return

    swaparr_logger.info(
        f"Finished processing stalled downloads for {app_name} instance: {app_settings.get('instance_name', 'Unknown')}"
    )
