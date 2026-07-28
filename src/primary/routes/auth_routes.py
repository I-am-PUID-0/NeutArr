#!/usr/bin/env python3
"""
Auth API Blueprint for NeutArr.

Endpoints:
  GET  /api/auth/status          — public; returns auth state
  POST /api/auth/setup           — public; creates first user
  POST /api/auth/login           — public; returns tokens + sets cookies
  POST /api/auth/refresh         — public; uses refresh cookie to issue new tokens
  POST /api/auth/logout          — clears cookies
  POST /api/auth/verify          — validates a token
  GET  /api/auth/user            — returns current user info (requires auth)
  POST /api/auth/change-password — changes password (requires auth)
  POST /api/auth/change-username — changes username (requires auth)
  GET  /api/auth/apikey          — returns current API key (requires auth or API key)
  POST /api/auth/apikey/rotate   — rotates API key (requires auth or API key)
  GET  /api/auth/mode            — returns current auth mode (requires auth)
  POST /api/auth/mode            — updates auth mode (requires auth)
"""

import hashlib
import ipaddress
import logging
from flask import Blueprint, request, jsonify, make_response, redirect, render_template

from ..auth import (
    _get_client_ip,
    _get_local_bypass,
    _is_local_bypass_request,
    _is_proxy_authenticated_request,
    normalize_local_bypass_cidrs,
    reset_bypass_caches,
    LEGACY_REFRESH_COOKIE,
    REFRESH_COOKIE,
    INSTANCE_STORAGE_KEY,
    INVALID_LOCAL_BYPASS_CIDRS_ERROR,
    auth_config,
    consume_setup_token,
    ensure_setup_token,
    verify_login,
    verify_password,
    validate_password_strength,
    create_token_pair,
    decode_token,
    set_auth_cookies,
    validate_setup_token,
    clear_auth_cookies,
    get_current_user,
    get_token_from_request,
    get_valid_token_username,
    get_api_key_from_request,
    validate_api_key,
)
from .. import settings_manager
from ..rate_limiter import SlidingWindowRateLimiter

logger = logging.getLogger("neutarr.auth_routes")

auth_bp = Blueprint("auth", __name__)

LOGIN_RATE_LIMITER = SlidingWindowRateLimiter(limit=5, window_seconds=300)
PASSWORD_RATE_LIMITER = SlidingWindowRateLimiter(limit=5, window_seconds=300)
SETUP_RATE_LIMITER = SlidingWindowRateLimiter(limit=5, window_seconds=900)
REFRESH_RATE_LIMITER = SlidingWindowRateLimiter(limit=10, window_seconds=300)
VERIFY_RATE_LIMITER = SlidingWindowRateLimiter(limit=30, window_seconds=60)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _client_rate_limit_key() -> str:
    """Return a normalized client key without trusting arbitrary header text."""
    candidates = (_get_client_ip(), request.remote_addr)
    for candidate in candidates:
        try:
            return f"client:{ipaddress.ip_address(candidate or '')}"
        except ValueError:
            continue
    return "client:unknown"


def _account_rate_limit_key(username: str) -> str:
    """Return a non-reversible account bucket key."""
    normalized = username.strip().casefold().encode("utf-8")
    return f"account:{hashlib.sha256(normalized).hexdigest()}"


def _rate_limit_response(retry_after: int):
    """Return a consistent 429 response without disclosing which bucket filled."""
    response = make_response(
        jsonify({"error": "Too many authentication attempts. Try again later."}),
        429,
    )
    response.headers["Retry-After"] = str(max(1, retry_after))
    return response


def _consume_rate_limit(limiter: SlidingWindowRateLimiter, keys: list[str]):
    decision = limiter.consume(keys)
    if decision.allowed:
        return None
    return _rate_limit_response(decision.retry_after)


def _is_privileged() -> bool:
    """Return True for explicit credentials or authenticated reverse-proxy users.

    Local CIDR bypass alone is intentionally not enough to read or rotate the
    durable API key.
    """
    if get_current_user():
        return True
    api_key = get_api_key_from_request()
    return bool((api_key and validate_api_key(api_key)) or _is_proxy_authenticated_request())


def _get_authenticated_username() -> str | None:
    """Return the acting username for JWT auth or valid instance API key auth."""
    username = get_current_user()
    if username:
        return username

    api_key = get_api_key_from_request()
    if not api_key or not validate_api_key(api_key):
        if not _is_proxy_authenticated_request():
            return None

    for user in auth_config.config.get("users", []):
        if not user.get("disabled", False) and user.get("username"):
            return user["username"]
    return None


def _token_response(username: str, status: int = 200):
    """Build a JSON response with token pair + auth cookies set."""
    access_token, refresh_token = create_token_pair(username)
    data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",  # nosec B105
        "username": username,
    }
    response = make_response(jsonify(data), status)
    set_auth_cookies(response, access_token, refresh_token)
    return response


# ---------------------------------------------------------------------------
# Status / setup
# ---------------------------------------------------------------------------


@auth_bp.route("/api/auth/status", methods=["GET"])
def auth_status():
    """Return current auth state. Always public."""
    try:
        proxy_bypass = settings_manager.get_setting("general", "proxy_auth_bypass", False)
    except Exception:
        proxy_bypass = False
    try:
        local_bypass = _get_local_bypass()
    except Exception:
        local_bypass = False

    proxy_request_authenticated = _is_proxy_authenticated_request()
    local_client_bypass = _is_local_bypass_request()

    data = {
        "has_users": auth_config.has_users(),
        "instance_storage_key": INSTANCE_STORAGE_KEY,
        "proxy_auth_bypass": proxy_bypass,
        "local_access_bypass": local_bypass,
        "setup_skipped": False,
        "setup_token_required": not auth_config.has_users(),
        "auth_enabled": auth_config.has_users() and not (proxy_request_authenticated or local_client_bypass),
        "proxy_request_authenticated": proxy_request_authenticated,
        "local_client_bypass": local_client_bypass,
    }

    return jsonify(data)


@auth_bp.route("/api/auth/setup", methods=["POST"])
def auth_setup():
    """Create the first user account. Only works when no users exist."""
    if auth_config.has_users():
        return jsonify({"error": "Setup already complete"}), 400

    rate_limit_keys = [_client_rate_limit_key()]
    limited = _consume_rate_limit(SETUP_RATE_LIMITER, rate_limit_keys)
    if limited:
        return limited

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    confirm_password = data.get("confirm_password") or ""
    setup_token = data.get("setup_token") or request.headers.get("X-Setup-Token", "")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400
    if password != confirm_password:
        return jsonify({"error": "Passwords do not match"}), 400

    strength_error = validate_password_strength(password)
    if strength_error:
        return jsonify({"error": strength_error}), 400
    if not ensure_setup_token():
        return jsonify({"error": "First-run setup token is not available; check the server logs"}), 503
    if not validate_setup_token(setup_token):
        logger.warning("Rejected first-user setup request with an invalid setup token.")
        return jsonify({"error": "Valid first-run setup token required"}), 403

    if not auth_config.create_user(username, password):
        if auth_config.has_users():
            return jsonify({"error": "Setup already complete"}), 409
        return jsonify({"error": "Failed to create user"}), 500

    consume_setup_token()
    SETUP_RATE_LIMITER.reset(rate_limit_keys)
    logger.info(f"First user '{username}' created via setup.")
    return _token_response(username, status=201)


# ---------------------------------------------------------------------------
# Login / Logout / Refresh
# ---------------------------------------------------------------------------


@auth_bp.route("/api/auth/login", methods=["POST"])
def auth_login():
    """Validate credentials and issue JWT tokens."""
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    rate_limit_keys = [_client_rate_limit_key(), _account_rate_limit_key(username)]
    limited = _consume_rate_limit(LOGIN_RATE_LIMITER, rate_limit_keys)
    if limited:
        return limited

    if not verify_login(username, password):
        logger.warning("Failed login attempt.")
        return jsonify({"error": "Invalid username or password"}), 401

    LOGIN_RATE_LIMITER.reset(rate_limit_keys)
    logger.info("User logged in.")
    return _token_response(username)


@auth_bp.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    """Revoke the authenticated user's JWT sessions and clear auth cookies."""
    username = None
    access_token = get_token_from_request()
    if access_token:
        username = get_valid_token_username(decode_token(access_token), expected_type="access")

    if not username:
        data = request.get_json(silent=True) or {}
        refresh_token = (
            request.cookies.get(REFRESH_COOKIE)
            or request.cookies.get(LEGACY_REFRESH_COOKIE)
            or data.get("refresh_token")
        )
        if refresh_token:
            username = get_valid_token_username(decode_token(refresh_token), expected_type="refresh")

    if username and not auth_config.revoke_user_sessions(username):
        logger.error("Failed to persist JWT session revocation during logout.")
        response = make_response(jsonify({"error": "Failed to revoke active sessions"}), 500)
        clear_auth_cookies(response)
        return response

    response = make_response(jsonify({"success": True}))
    clear_auth_cookies(response)
    if username:
        logger.info("User logged out and active JWT sessions were revoked.")
    return response


@auth_bp.route("/api/auth/refresh", methods=["POST"])
def auth_refresh():
    """
    Issue a new token pair using the refresh token.
    The instance-scoped httponly refresh cookie is sent automatically by the browser.
    JS clients can also send the refresh token in the request body.
    """
    rate_limit_keys = [_client_rate_limit_key()]
    limited = _consume_rate_limit(REFRESH_RATE_LIMITER, rate_limit_keys)
    if limited:
        return limited

    # Try httponly cookie first (browser), then JSON body (API clients)
    refresh_token = request.cookies.get(REFRESH_COOKIE) or request.cookies.get(LEGACY_REFRESH_COOKIE)
    if not refresh_token:
        data = request.get_json(silent=True) or {}
        refresh_token = data.get("refresh_token")

    if not refresh_token:
        return jsonify({"error": "Refresh token required"}), 401

    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        return jsonify({"error": "Invalid or expired refresh token"}), 401

    username = get_valid_token_username(payload, expected_type="refresh")
    if not username:
        return jsonify({"error": "Invalid or expired refresh token"}), 401

    REFRESH_RATE_LIMITER.reset(rate_limit_keys)
    logger.debug(f"Token refreshed for user '{username}'.")
    return _token_response(username)


# ---------------------------------------------------------------------------
# Token verify
# ---------------------------------------------------------------------------


@auth_bp.route("/api/auth/verify", methods=["POST"])
def auth_verify():
    """Check if a token is valid. Accepts token in body or Authorization header."""
    rate_limit_keys = [_client_rate_limit_key()]
    limited = _consume_rate_limit(VERIFY_RATE_LIMITER, rate_limit_keys)
    if limited:
        return limited

    data = request.get_json(silent=True) or {}
    token = data.get("token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        return jsonify({"valid": False, "error": "No token provided"}), 400

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return jsonify({"valid": False})

    username = get_valid_token_username(payload, expected_type="access")
    if not username:
        return jsonify({"valid": False})

    VERIFY_RATE_LIMITER.reset(rate_limit_keys)
    return jsonify({"valid": True, "username": username})


# ---------------------------------------------------------------------------
# User info / change credentials
# ---------------------------------------------------------------------------


@auth_bp.route("/api/auth/user", methods=["GET"])
def auth_user():
    """Return current user info. Requires authentication."""
    username = _get_authenticated_username()
    if not username:
        return jsonify({"error": "Not authenticated"}), 401
    return jsonify({"username": username})


@auth_bp.route("/api/auth/change-password", methods=["POST"])
def auth_change_password():
    """Change the current user's password."""
    username = _get_authenticated_username()
    if not username:
        return jsonify({"error": "Not authenticated"}), 401
    was_jwt_authenticated = bool(get_current_user())

    data = request.get_json(silent=True) or {}
    current_password = data.get("current_password") or ""
    new_password = data.get("new_password") or ""

    if not current_password or not new_password:
        return jsonify({"error": "Current and new passwords are required"}), 400

    rate_limit_keys = [_client_rate_limit_key(), _account_rate_limit_key(username)]
    limited = _consume_rate_limit(PASSWORD_RATE_LIMITER, rate_limit_keys)
    if limited:
        return limited

    user = auth_config.get_user(username)
    if not user or not verify_password(user["password"], current_password):
        return jsonify({"error": "Current password is incorrect"}), 401

    strength_error = validate_password_strength(new_password)
    if strength_error:
        return jsonify({"error": strength_error}), 400

    if not auth_config.update_password(username, new_password):
        return jsonify({"error": "Failed to update password"}), 500

    PASSWORD_RATE_LIMITER.reset(rate_limit_keys)
    logger.info(f"Password changed and prior JWT sessions revoked for user '{username}'.")
    if was_jwt_authenticated:
        return _token_response(username)
    return jsonify({"success": True})


@auth_bp.route("/api/auth/change-username", methods=["POST"])
def auth_change_username():
    """Change the current user's username."""
    username = _get_authenticated_username()
    if not username:
        return jsonify({"error": "Not authenticated"}), 401
    was_jwt_authenticated = bool(get_current_user())

    data = request.get_json(silent=True) or {}
    new_username = (data.get("username") or "").strip()
    current_password = data.get("password") or ""

    if not new_username or not current_password:
        return jsonify({"error": "New username and current password are required"}), 400
    if len(new_username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400

    rate_limit_keys = [_client_rate_limit_key(), _account_rate_limit_key(username)]
    limited = _consume_rate_limit(PASSWORD_RATE_LIMITER, rate_limit_keys)
    if limited:
        return limited

    user = auth_config.get_user(username)
    if not user or not verify_password(user["password"], current_password):
        return jsonify({"error": "Current password is incorrect"}), 401

    if not auth_config.update_username(username, new_username):
        return jsonify({"error": "Username already taken or update failed"}), 400

    PASSWORD_RATE_LIMITER.reset(rate_limit_keys)
    logger.info(f"Username changed from '{username}' to '{new_username}'.")

    if was_jwt_authenticated:
        # JWT-backed sessions need fresh tokens when the subject changes.
        return _token_response(new_username)

    return jsonify({"success": True, "username": new_username})


# ---------------------------------------------------------------------------
# API key management
# ---------------------------------------------------------------------------


@auth_bp.route("/api/auth/apikey", methods=["GET"])
def auth_get_apikey():
    """Return the current API key. Requires JWT or API key auth."""
    if not _is_privileged():
        return jsonify({"error": "Authentication required"}), 401
    return jsonify({"api_key": auth_config.get_api_key()})


@auth_bp.route("/api/auth/apikey/rotate", methods=["POST"])
def auth_rotate_apikey():
    """Generate and persist a new API key. Requires JWT or API key auth."""
    if not _is_privileged():
        return jsonify({"error": "Authentication required"}), 401
    new_key = auth_config.rotate_api_key()
    logger.info("API key rotated.")
    return jsonify({"api_key": new_key})


@auth_bp.route("/api/auth/mode", methods=["GET", "POST"])
def auth_mode():
    """Read or update the authentication mode. Requires JWT or API key auth."""
    if not _is_privileged():
        return jsonify({"error": "Authentication required"}), 401

    if request.method == "GET":
        settings = settings_manager.load_settings("general")
        return jsonify(
            {
                "auth_mode": settings.get("auth_mode", "login"),
                "local_bypass_cidrs": normalize_local_bypass_cidrs(settings.get("local_bypass_cidrs")),
            }
        )

    # POST — update mode
    if not request.is_json:
        return jsonify({"success": False, "error": "Expected JSON data"}), 400
    mode = request.json.get("auth_mode")
    if mode not in ("login", "local_bypass", "no_login"):
        return jsonify({"success": False, "error": "Invalid auth_mode value"}), 400

    current = settings_manager.load_settings("general")
    current["auth_mode"] = mode
    current["local_access_bypass"] = mode == "local_bypass"
    current["proxy_auth_bypass"] = mode == "no_login"
    if "local_bypass_cidrs" in request.json:
        try:
            current["local_bypass_cidrs"] = normalize_local_bypass_cidrs(request.json.get("local_bypass_cidrs"))
        except ValueError:
            logger.warning("Rejected invalid local bypass CIDR configuration")
            return jsonify({"success": False, "error": INVALID_LOCAL_BYPASS_CIDRS_ERROR}), 400

    if settings_manager.save_settings("general", current):
        reset_bypass_caches()
        logger.info(f"Auth mode changed to '{mode}'.")
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Failed to save auth mode"}), 500


# ---------------------------------------------------------------------------
# Page routes for login and setup
# ---------------------------------------------------------------------------


@auth_bp.route("/login", methods=["GET"])
def login_page():
    if not auth_config.has_users():
        return redirect("/setup")
    if _is_proxy_authenticated_request() or _is_local_bypass_request():
        return redirect("/")
    return render_template("login.html")


@auth_bp.route("/setup", methods=["GET"])
def setup_page():
    if auth_config.has_users():
        return redirect("/login")
    ensure_setup_token()
    return render_template("setup.html")
