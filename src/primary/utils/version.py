#!/usr/bin/env python3
"""Shared runtime version helpers for NeutArr."""

import os

FALLBACK_VERSION = "0.1.0"


def get_runtime_version() -> str:
    """Return the best available runtime version string."""
    env_version = os.environ.get("NEUTARR_VERSION", "").strip()
    if env_version:
        return env_version

    try:
        import tomllib

        pyproject_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            "pyproject.toml",
        )
        if os.path.exists(pyproject_path):
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
            version = str(data["tool"]["poetry"]["version"]).strip()
            if version:
                return version
    except Exception:
        pass

    return FALLBACK_VERSION
