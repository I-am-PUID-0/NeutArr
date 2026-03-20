#!/usr/bin/env python3
"""
Authentication module for NeutArr.

JWT dual-token auth (access 60min / refresh 30 days) backed by bcrypt password
hashing. Config persisted in /config/users.json. Supports two bypass modes:
  - proxy_auth_bypass: disable all auth when behind an SSO reverse proxy
  - local_access_bypass: LAN IPs skip auth (proper ipaddress CIDR validation)

API key auth: an auto-generated key stored in users.json is always a valid
credential via X-Api-Key header or ?apikey= query param, independent of
login/bypass mode. Useful for scripts and external tool integrations.
"""

import json
import logging
import ipaddress
import os
import secrets
import time
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import bcrypt
import jwt
from flask import request, redirect, jsonify

logger = logging.getLogger("neutarr.auth")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USERS_FILE = Path(os.environ.get("NEUTARR_CONFIG_DIR", "/config")) / "users.json"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 30
JWT_ALGORITHM = "HS256"

LEGACY_ACCESS_COOKIE = "neutarr_token"
LEGACY_REFRESH_COOKIE = "neutarr_refresh"


def get_instance_storage_key() -> str:
    """Return a stable per-instance key for cookie and browser storage namespacing."""
    parts = [
        os.environ.get("NEUTARR_INSTANCE_ID", "").strip(),
        os.environ.get("NEUTARR_CONFIG_DIR", "").strip(),
        os.environ.get("PORT", "").strip(),
    ]
    combined_id = "|".join(part for part in parts if part) or "default"
    digest = hashlib.sha256(combined_id.encode("utf-8")).hexdigest()[:12]
    return f"inst_{digest}"


INSTANCE_STORAGE_KEY = get_instance_storage_key()
ACCESS_COOKIE = f"neutarr_token_{INSTANCE_STORAGE_KEY}"  # non-httponly; JS-readable for AJAX
REFRESH_COOKIE = f"neutarr_refresh_{INSTANCE_STORAGE_KEY}"  # httponly; auto-sent to refresh endpoint

# Private RFC-1918 + loopback CIDR ranges for local access bypass
_LOCAL_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("fc00::/7"),  # IPv6 ULA
]

# Paths that bypass auth entirely — explicit set + prefix list, no substring tricks
ALWAYS_PUBLIC_PATHS = frozenset(
    {
        "/favicon.ico",
        "/api/health",
        "/api/version",
        "/api/get_local_access_bypass_status",
        "/ping",
        "/login",
        "/setup",
        "/api/auth/login",
        "/api/auth/refresh",
        "/api/auth/status",
        "/api/auth/setup",
        "/api/auth/skip-setup",
        "/api/auth/verify",
    }
)
ALWAYS_PUBLIC_PREFIXES = ("/static/", "/logo/")

# 60-second caches for settings reads on every request
_proxy_bypass_cache: dict = {"value": None, "expires": 0.0}
_local_bypass_cache: dict = {"value": None, "expires": 0.0}


# ---------------------------------------------------------------------------
# AuthConfigManager
# ---------------------------------------------------------------------------


class AuthConfigManager:
    """Manages /config/users.json — user accounts and JWT secret."""

    def __init__(self):
        self._config: Optional[dict] = None

    def _load(self) -> None:
        if USERS_FILE.exists():
            try:
                with open(USERS_FILE) as f:
                    self._config = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load users.json: {e}")
                self._config = self._default_config()
        else:
            self._config = self._default_config()
            self._save()

    def _default_config(self) -> dict:
        return {
            "jwt_secret": secrets.token_urlsafe(32),
            "api_key": secrets.token_urlsafe(24),
            "users": [],
            "setup_skipped": False,
        }

    def _save(self) -> None:
        USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(USERS_FILE, "w") as f:
                json.dump(self._config, f, indent=2)
            os.chmod(USERS_FILE, 0o600)
        except Exception as e:
            logger.error(f"Failed to save users.json: {e}")

    @property
    def config(self) -> dict:
        if self._config is None:
            self._load()
        return self._config

    def get_jwt_secret(self) -> str:
        return self.config.get("jwt_secret", "")

    def has_users(self) -> bool:
        return len(self.config.get("users", [])) > 0

    def is_setup_skipped(self) -> bool:
        return self.config.get("setup_skipped", False)

    def get_user(self, username: str) -> Optional[dict]:
        for user in self.config.get("users", []):
            if user.get("username") == username:
                return user
        return None

    def create_user(self, username: str, password: str) -> bool:
        """Create first (and only) user. Returns False if user already exists."""
        if self.get_user(username):
            logger.warning(f"User '{username}' already exists.")
            return False
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
        self.config.setdefault("users", []).append(
            {
                "username": username,
                "password": hashed,
                "disabled": False,
            }
        )
        self._save()
        logger.info(f"User '{username}' created.")
        return True

    def update_password(self, username: str, new_password: str) -> bool:
        for user in self.config.get("users", []):
            if user.get("username") == username:
                user["password"] = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt(rounds=12)).decode()
                self._save()
                return True
        return False

    def update_username(self, old_username: str, new_username: str) -> bool:
        if self.get_user(new_username):
            return False  # New username already taken
        for user in self.config.get("users", []):
            if user.get("username") == old_username:
                user["username"] = new_username
                self._save()
                return True
        return False

    def skip_setup(self) -> None:
        self.config["setup_skipped"] = True
        self._save()

    def get_api_key(self) -> str:
        """Return stored API key, generating one if missing (migration path)."""
        key = self.config.get("api_key")
        if not key:
            key = secrets.token_urlsafe(24)
            self.config["api_key"] = key
            self._save()
        return key

    def rotate_api_key(self) -> str:
        """Generate and persist a new API key, returning it."""
        key = secrets.token_urlsafe(24)
        self.config["api_key"] = key
        self._save()
        return key


auth_config = AuthConfigManager()


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), stored_hash.encode())
    except Exception:
        return False


def validate_password_strength(password: str) -> Optional[str]:
    """Return error string if password is too weak, None if OK."""
    if len(password) < 8:
        return "Password must be at least 8 characters long"
    return None


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


def create_access_token(username: str) -> str:
    payload = {
        "sub": username,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, auth_config.get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(username: str) -> str:
    payload = {
        "sub": username,
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, auth_config.get_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, auth_config.get_jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def create_token_pair(username: str) -> tuple:
    """Return (access_token, refresh_token)."""
    return create_access_token(username), create_refresh_token(username)


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------


def set_auth_cookies(response, access_token: str, refresh_token: str) -> None:
    """Set access (non-httponly) and refresh (httponly) cookies on response."""
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=False,  # JS-readable so frontend can add Authorization headers
        samesite="Lax",
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=True,  # Not readable by JS — only auto-sent to refresh endpoint
        samesite="Lax",
        path="/api/auth/refresh",
    )


def clear_auth_cookies(response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth/refresh")
    response.delete_cookie(LEGACY_ACCESS_COOKIE, path="/")
    response.delete_cookie(LEGACY_REFRESH_COOKIE, path="/api/auth/refresh")


# ---------------------------------------------------------------------------
# Request token extraction
# ---------------------------------------------------------------------------


def get_token_from_request() -> Optional[str]:
    """Extract access token from Authorization header, falling back to cookie."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return request.cookies.get(ACCESS_COOKIE) or request.cookies.get(LEGACY_ACCESS_COOKIE)


def get_api_key_from_request() -> Optional[str]:
    """Extract API key from X-Api-Key header or ?apikey= query param."""
    key = request.headers.get("X-Api-Key")
    if key:
        return key
    return request.args.get("apikey")


def validate_api_key(key: str) -> bool:
    """Timing-safe comparison of provided key against the stored API key."""
    stored = auth_config.get_api_key()
    if not stored or not key:
        return False
    return secrets.compare_digest(key, stored)


def get_current_user() -> Optional[str]:
    """Return username for current request, or None if not authenticated."""
    token = get_token_from_request()
    if not token:
        return None
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None
    username = payload.get("sub")
    if not username:
        return None
    user = auth_config.get_user(username)
    if not user or user.get("disabled", False):
        return None
    return username


# ---------------------------------------------------------------------------
# Path classification
# ---------------------------------------------------------------------------


def is_public_path(path: str) -> bool:
    if path in ALWAYS_PUBLIC_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in ALWAYS_PUBLIC_PREFIXES)


# ---------------------------------------------------------------------------
# IP-based bypass helpers
# ---------------------------------------------------------------------------


def _get_client_ip() -> Optional[str]:
    """
    Return the real client IP.
    X-Forwarded-For is only trusted when TRUSTED_PROXIES env var is set,
    preventing spoofing when the app is directly internet-exposed.
    """
    trusted_proxies_env = os.environ.get("TRUSTED_PROXIES", "")
    if trusted_proxies_env:
        trusted = [p.strip() for p in trusted_proxies_env.split(",") if p.strip()]
        remote = request.remote_addr or ""
        try:
            remote_ip = ipaddress.ip_address(remote)
            is_trusted = any(remote_ip in ipaddress.ip_network(cidr, strict=False) for cidr in trusted)
            if is_trusted:
                xff = request.headers.get("X-Forwarded-For", "")
                if xff:
                    return xff.split(",")[0].strip()
        except ValueError:
            pass
    return request.remote_addr


def _is_local_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in net for net in _LOCAL_NETWORKS)
    except ValueError:
        return False


def _get_proxy_bypass() -> bool:
    now = time.time()
    if _proxy_bypass_cache["expires"] > now and _proxy_bypass_cache["value"] is not None:
        return _proxy_bypass_cache["value"]
    try:
        from primary import settings_manager

        value = settings_manager.get_setting("general", "proxy_auth_bypass", False)
    except Exception:
        value = False
    _proxy_bypass_cache["value"] = value
    _proxy_bypass_cache["expires"] = now + 60.0
    return value


def _get_local_bypass() -> bool:
    now = time.time()
    if _local_bypass_cache["expires"] > now and _local_bypass_cache["value"] is not None:
        return _local_bypass_cache["value"]
    try:
        from primary import settings_manager

        value = settings_manager.get_setting("general", "local_access_bypass", False)
    except Exception:
        value = False
    _local_bypass_cache["value"] = value
    _local_bypass_cache["expires"] = now + 60.0
    return value


# ---------------------------------------------------------------------------
# Flask before_request handler
# ---------------------------------------------------------------------------


def authenticate_request():
    """
    Run before every Flask request. Returns None to allow the request through,
    or a redirect/JSON response to reject it. Priority order:
      1. Always-public paths (static, /login, /setup, /api/auth/*)
      2. Valid JWT access token OR valid API key (explicit credentials always win)
      3. No users and setup not skipped → force setup flow
      4. API requests: always require credentials — bypass modes do not exempt
         API calls. The only exception is no-user proxy mode (setup_skipped=True,
         has_users=False) where no API key has been issued to anyone.
      5. Page requests: proxy_auth_bypass OR (local_access_bypass + LAN IP)
         removes the login redirect — the web UI is accessible without logging in.
      6. Reject: redirect /login for page requests
    """
    path = request.path
    is_api = path.startswith("/api/")

    # 1. Public paths
    if is_public_path(path):
        return None

    # 2. Explicit credentials: valid JWT or valid API key
    api_key = get_api_key_from_request()
    if api_key and validate_api_key(api_key):
        return None
    if get_current_user():
        return None

    # 3. No users and setup not skipped — force setup flow
    if not auth_config.has_users() and not auth_config.is_setup_skipped():
        if is_api:
            return jsonify({"error": "Setup required", "setup_required": True}), 401
        return redirect("/setup")

    # 4. API requests always require credentials (JWT or API key).
    #    Bypass modes do not exempt API calls — they only skip the web UI login.
    #    Exception: no-user proxy mode (setup_skipped, no users) — fully open
    #    because there is no API key issued to anyone in this configuration.
    if is_api:
        if not auth_config.has_users():  # no-user proxy mode, setup_skipped=True
            return None
        return jsonify({"error": "Authentication required"}), 401

    # 5. Page requests: bypass modes remove the login redirect
    if _get_proxy_bypass():
        return None
    if _get_local_bypass():
        client_ip = _get_client_ip()
        if client_ip and _is_local_ip(client_ip):
            return None

    # 6. Reject page request — send to login
    return redirect("/login")


# ---------------------------------------------------------------------------
# Login helper used by auth_routes
# ---------------------------------------------------------------------------


def verify_login(username: str, password: str) -> bool:
    """Return True if username + password are correct and user is not disabled."""
    user = auth_config.get_user(username)
    if not user or user.get("disabled", False):
        return False
    return verify_password(user["password"], password)
