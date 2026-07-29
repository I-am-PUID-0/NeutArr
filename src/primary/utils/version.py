#!/usr/bin/env python3
"""Shared runtime version helpers for NeutArr."""

import os
import re

FALLBACK_VERSION = "0.1.0"
_SEMANTIC_VERSION_PATTERN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


def _get_project_version() -> str:
    """Return the version bundled with the current source tree."""
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

    return ""


def _semantic_version_core(version: str) -> tuple[int, int, int] | None:
    """Return a comparable release tuple while ignoring valid build suffixes."""
    match = _SEMANTIC_VERSION_PATTERN.fullmatch(version)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def get_runtime_version() -> str:
    """Return the best available runtime version string.

    Docker and DUMB may provide a richer runtime marker such as
    ``1.11.0-dev.12`` or ``dev-<sha>``. A plain semantic environment value
    must still describe the bundled source version; otherwise a stale
    deployment override could make upgraded code report an older release.
    """
    env_version = os.environ.get("NEUTARR_VERSION", "").strip()
    project_version = _get_project_version()

    if env_version and project_version:
        env_core = _semantic_version_core(env_version)
        project_core = _semantic_version_core(project_version)
        if env_core is not None and project_core is not None and env_core != project_core:
            return project_version
        return env_version

    return env_version or project_version or FALLBACK_VERSION
