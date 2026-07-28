#!/usr/bin/env python3
"""
Authentication module for NeutArr.

JWT dual-token auth (access 60min / refresh 30 days) backed by bcrypt password
hashing. Config persisted in /config/users.json. Supports two bypass modes:
  - proxy_auth_bypass: trust authenticated identity headers from configured proxies
  - local_access_bypass: configured client CIDRs skip auth

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
import hmac
import re
import threading
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
SETUP_TOKEN_FILE = Path(os.environ.get("NEUTARR_CONFIG_DIR", "/config")) / ".setup-token"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 30
JWT_ALGORITHM = "HS256"
MIN_SETUP_TOKEN_LENGTH = 16
PROXY_AUTH_HEADER_ENV = "NEUTARR_PROXY_AUTH_HEADER"
TRUSTED_PROXIES_ENV = "TRUSTED_PROXIES"
_HTTP_HEADER_NAME_PATTERN = re.compile(r"^[A-Za-z0-9!#$%&'*+.^_`|~-]+$")

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
ACCESS_COOKIE = f"neutarr_token_{INSTANCE_STORAGE_KEY}"
REFRESH_COOKIE = f"neutarr_refresh_{INSTANCE_STORAGE_KEY}"

# Private RFC-1918 + loopback CIDR ranges for local access bypass
DEFAULT_LOCAL_BYPASS_CIDRS = [
    "127.0.0.0/8",
    "::1/128",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "fc00::/7",
]
_DEFAULT_LOCAL_NETWORKS = [ipaddress.ip_network(cidr) for cidr in DEFAULT_LOCAL_BYPASS_CIDRS]

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
        "/api/auth/logout",
        "/api/auth/refresh",
        "/api/auth/status",
        "/api/auth/setup",
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
        self._lock = threading.RLock()

    def _load(self) -> None:
        with self._lock:
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
        }

    def _save(self) -> bool:
        """Persist auth configuration atomically with owner-only permissions."""
        with self._lock:
            USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
            temp_file = USERS_FILE.with_name(f".{USERS_FILE.name}.{os.getpid()}.{threading.get_ident()}.tmp")
            try:
                with open(temp_file, "w") as f:
                    json.dump(self._config, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.chmod(temp_file, 0o600)
                os.replace(temp_file, USERS_FILE)
                return True
            except Exception as e:
                logger.error(f"Failed to save users.json: {e}")
                try:
                    temp_file.unlink(missing_ok=True)
                except OSError:
                    pass
                return False

    @property
    def config(self) -> dict:
        with self._lock:
            if self._config is None:
                self._load()
            return self._config

    def get_jwt_secret(self) -> str:
        return self.config.get("jwt_secret", "")

    def has_users(self) -> bool:
        with self._lock:
            return len(self.config.get("users", [])) > 0

    def get_user(self, username: str) -> Optional[dict]:
        with self._lock:
            for user in self.config.get("users", []):
                if user.get("username") == username:
                    return user
            return None

    def create_user(self, username: str, password: str) -> bool:
        """Atomically create the first user and refuse every later creation."""
        with self._lock:
            if self.config.get("users"):
                logger.warning("Refused user creation because setup is already complete.")
                return False

            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
            user = {
                "username": username,
                "password": hashed,
                "disabled": False,
            }
            self.config.setdefault("users", []).append(user)
            if not self._save():
                self.config["users"].remove(user)
                return False
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

_setup_token_lock = threading.Lock()


def _read_setup_token_file() -> Optional[str]:
    try:
        token = SETUP_TOKEN_FILE.read_text(encoding="utf-8").strip()
        return token or None
    except FileNotFoundError:
        return None
    except OSError as e:
        logger.error(f"Failed to read setup token file {SETUP_TOKEN_FILE}: {e}")
        return None


def ensure_setup_token() -> Optional[str]:
    """Return the configured first-run token, generating a persistent one if needed."""
    if auth_config.has_users():
        try:
            SETUP_TOKEN_FILE.unlink(missing_ok=True)
        except OSError as e:
            logger.warning(f"Could not remove stale setup token file {SETUP_TOKEN_FILE}: {e}")
        return None

    environment_token = os.environ.get("NEUTARR_SETUP_TOKEN", "").strip()
    if environment_token:
        if len(environment_token) < MIN_SETUP_TOKEN_LENGTH:
            logger.error(
                "NEUTARR_SETUP_TOKEN must contain at least "
                f"{MIN_SETUP_TOKEN_LENGTH} characters before first-run setup can continue."
            )
            return None
        return environment_token

    with _setup_token_lock:
        existing_token = _read_setup_token_file()
        if existing_token:
            return existing_token

        token = secrets.token_urlsafe(24)
        SETUP_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp_file = SETUP_TOKEN_FILE.with_name(f".{SETUP_TOKEN_FILE.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(f"{token}\n")
                f.flush()
                os.fsync(f.fileno())
            os.chmod(temp_file, 0o600)
            os.replace(temp_file, SETUP_TOKEN_FILE)
        except OSError as e:
            logger.error(f"Failed to create first-run setup token: {e}")
            try:
                temp_file.unlink(missing_ok=True)
            except OSError:
                pass
            return None

        logger.warning(
            "First-run setup token: %s (also stored at %s; it is removed after account creation)",
            token,
            SETUP_TOKEN_FILE,
        )
        return token


def validate_setup_token(candidate: str) -> bool:
    expected = ensure_setup_token()
    if not expected or not candidate:
        return False
    return hmac.compare_digest(expected.encode("utf-8"), candidate.strip().encode("utf-8"))


def consume_setup_token() -> None:
    """Remove the generated setup-token file after successful account creation."""
    try:
        SETUP_TOKEN_FILE.unlink(missing_ok=True)
    except OSError as e:
        logger.warning(f"Could not remove consumed setup token file {SETUP_TOKEN_FILE}: {e}")


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
    """Set browser session cookies without exposing JWTs to JavaScript."""
    secure = _use_secure_cookies()
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=secure,
        samesite="Strict",
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=True,
        secure=secure,
        samesite="Strict",
        path="/api/auth/refresh",
    )
    _delete_auth_cookie(response, LEGACY_ACCESS_COOKIE, "/")
    _delete_auth_cookie(response, LEGACY_REFRESH_COOKIE, "/api/auth/refresh")


def _use_secure_cookies() -> bool:
    """Determine whether session cookies should carry the Secure attribute."""
    configured = os.environ.get("NEUTARR_SECURE_COOKIES", "").strip().casefold()
    if configured in {"1", "true", "yes", "on"}:
        return True
    if configured in {"0", "false", "no", "off"}:
        return False

    if request.is_secure:
        return True
    if _is_trusted_proxy_source():
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "").split(",", 1)[0].strip().casefold()
        return forwarded_proto == "https"
    return False


def clear_auth_cookies(response) -> None:
    _delete_auth_cookie(response, ACCESS_COOKIE, "/")
    _delete_auth_cookie(response, REFRESH_COOKIE, "/api/auth/refresh")
    _delete_auth_cookie(response, LEGACY_ACCESS_COOKIE, "/")
    _delete_auth_cookie(response, LEGACY_REFRESH_COOKIE, "/api/auth/refresh")


def _delete_auth_cookie(response, name: str, path: str) -> None:
    response.delete_cookie(
        name,
        path=path,
        httponly=True,
        secure=_use_secure_cookies(),
        samesite="Strict",
    )


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
    if _is_trusted_proxy_source():
        xff = request.headers.get("X-Forwarded-For", "")
        if xff:
            return xff.split(",")[0].strip()
    return request.remote_addr


def _get_trusted_proxy_networks() -> list[ipaddress._BaseNetwork]:
    """Return configured proxy networks, failing closed on any invalid entry."""
    configured = os.environ.get(TRUSTED_PROXIES_ENV, "")
    entries = [entry.strip() for entry in configured.split(",") if entry.strip()]
    if not entries:
        return []

    try:
        return [ipaddress.ip_network(entry, strict=False) for entry in entries]
    except ValueError as exc:
        logger.warning(f"Invalid {TRUSTED_PROXIES_ENV} configuration; proxy trust disabled: {exc}")
        return []


def _is_trusted_proxy_source() -> bool:
    """Return whether the immediate TCP peer is a configured trusted proxy."""
    try:
        remote_ip = ipaddress.ip_address(request.remote_addr or "")
    except ValueError:
        return False
    return any(remote_ip in network for network in _get_trusted_proxy_networks())


def _get_proxy_identity() -> Optional[str]:
    """Return a proxy-asserted identity only for a request from a trusted proxy."""
    if not _is_trusted_proxy_source():
        return None

    header_name = os.environ.get(PROXY_AUTH_HEADER_ENV, "").strip()
    if not header_name or not _HTTP_HEADER_NAME_PATTERN.fullmatch(header_name):
        return None

    identity = request.headers.get(header_name, "").strip()
    if not identity or len(identity) > 512:
        return None
    return identity


def _is_proxy_authenticated_request() -> bool:
    """Return whether proxy bypass is enabled and this request is authenticated."""
    return _get_proxy_bypass() and _get_proxy_identity() is not None


def _is_local_bypass_request() -> bool:
    """Return whether local bypass is enabled and the resolved client is allowed."""
    if not _get_local_bypass():
        return False
    client_ip = _get_client_ip()
    return bool(client_ip and _is_local_ip(client_ip))


def normalize_local_bypass_cidrs(value, *, use_defaults_when_empty: bool = True) -> list[str]:
    """Return validated local-bypass CIDR strings for config/UI persistence."""
    if value is None:
        entries = []
    elif isinstance(value, str):
        entries = []
        for line in value.replace(",", "\n").splitlines():
            cidr = line.strip()
            if cidr:
                entries.append(cidr)
    elif isinstance(value, list):
        entries = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError("CIDR ranges must be strings")
            cidr = item.strip()
            if cidr:
                entries.append(cidr)
    else:
        raise ValueError("CIDR ranges must be a list or text value")

    if not entries and use_defaults_when_empty:
        entries = list(DEFAULT_LOCAL_BYPASS_CIDRS)

    normalized = []
    seen = set()
    for cidr in entries:
        try:
            network = ipaddress.ip_network(cidr, strict=False)
        except ValueError as exc:
            raise ValueError(f"Invalid CIDR range: {cidr}") from exc

        network_str = str(network)
        if network_str not in seen:
            normalized.append(network_str)
            seen.add(network_str)

    return normalized


def _get_local_networks() -> list[ipaddress._BaseNetwork]:
    try:
        from src.primary import settings_manager

        settings = settings_manager.load_settings("general")
        if "local_bypass_cidrs" not in settings:
            return _DEFAULT_LOCAL_NETWORKS
        configured_cidrs = normalize_local_bypass_cidrs(
            settings.get("local_bypass_cidrs"),
            use_defaults_when_empty=False,
        )
        return [ipaddress.ip_network(cidr, strict=False) for cidr in configured_cidrs]
    except Exception as exc:
        logger.warning(f"Invalid local bypass CIDR configuration; local bypass disabled until fixed: {exc}")
        return []


def _is_local_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in net for net in _get_local_networks())
    except ValueError:
        return False


def _get_proxy_bypass() -> bool:
    now = time.time()
    if _proxy_bypass_cache["expires"] > now and _proxy_bypass_cache["value"] is not None:
        return _proxy_bypass_cache["value"]
    try:
        from src.primary import settings_manager

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
        from src.primary import settings_manager

        value = settings_manager.get_setting("general", "local_access_bypass", False)
    except Exception:
        value = False
    _local_bypass_cache["value"] = value
    _local_bypass_cache["expires"] = now + 60.0
    return value


def reset_bypass_caches() -> None:
    """Clear cached bypass mode values after auth settings change."""
    _proxy_bypass_cache["value"] = None
    _proxy_bypass_cache["expires"] = 0.0
    _local_bypass_cache["value"] = None
    _local_bypass_cache["expires"] = 0.0


# ---------------------------------------------------------------------------
# Flask before_request handler
# ---------------------------------------------------------------------------


def authenticate_request():
    """
    Run before every Flask request. Returns None to allow the request through,
    or a redirect/JSON response to reject it. Priority order:
      1. Always-public paths (static, /login, /setup, /api/auth/*)
      2. Valid JWT access token OR valid API key (explicit credentials always win)
      3. No users → force the token-protected setup flow
      4. Request-scoped proxy or local bypass authorization
      5. API requests without credentials or an eligible bypass are rejected
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

    # 3. No users — force the token-protected setup flow
    if not auth_config.has_users():
        if is_api:
            return jsonify({"error": "Setup required", "setup_required": True}), 401
        return redirect("/setup")

    # 4. Bypass modes authorize only requests that meet their trust boundary.
    #    No durable credential is disclosed to the browser.
    if _is_proxy_authenticated_request() or _is_local_bypass_request():
        return None

    # 5. API requests require explicit credentials or an eligible bypass.
    if is_api:
        response = jsonify({"error": "Authentication required"})
        response.status_code = 401
        response.headers["X-NeutArr-Auth-Required"] = "1"
        return response

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
