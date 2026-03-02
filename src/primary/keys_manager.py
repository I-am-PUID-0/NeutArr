#!/usr/bin/env python3
"""
Keys manager for NeutArr
Handles storage and retrieval of API keys and URLs from neutarr.json
"""

import json
import logging
import os
import pathlib
from typing import Any, Dict, Optional, Tuple

# Create a simple logger
logging.basicConfig(level=logging.INFO)
keys_logger = logging.getLogger("keys_manager")

# Settings directory — controlled by NEUTARR_CONFIG_DIR env var
SETTINGS_DIR = pathlib.Path(os.environ.get("NEUTARR_CONFIG_DIR", "/config"))
SETTINGS_DIR.mkdir(parents=True, exist_ok=True)

SETTINGS_FILE = SETTINGS_DIR / "neutarr.json"

# Removed save_api_keys function

# Removed get_api_keys function

# Removed list_configured_apps function

# Keep other functions if they exist and are needed, otherwise the file might become empty.
# If this file solely managed API keys in the old way, it might be removable entirely,
# but let's keep it for now in case other key-related logic exists or is added later.
