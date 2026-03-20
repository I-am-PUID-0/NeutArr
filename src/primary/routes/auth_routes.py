#!/usr/bin/env python3
"""
Auth API Blueprint for NeutArr.

Endpoints:
  GET  /api/auth/status          — public; returns auth state
  POST /api/auth/setup           — public; creates first user
  POST /api/auth/skip-setup      — public; marks setup_skipped
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

import logging
from flask import Blueprint, request, jsonify, make_response, redirect, render_template

from ..auth import (
    _get_client_ip,
    _get_local_bypass,
    _is_local_ip,
    LEGACY_REFRESH_COOKIE,
    REFRESH_COOKIE,
    INSTANCE_STORAGE_KEY,
    auth_config,
    verify_login,
    verify_password,
    validate_password_strength,
    create_token_pair,
    decode_token,
    set_auth_cookies,
    clear_auth_cookies,
    get_current_user,
    get_api_key_from_request,
    validate_api_key,
)
from .. import settings_manager

logger = logging.getLogger("neutarr.auth_routes")

auth_bp = Blueprint("auth", __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_privileged() -> bool:
    """Return True if request carries valid JWT or valid API key credentials.

    Used inside route handlers that must not be accessible via bypass modes
    alone — e.g. reading or rotating the API key.
    """
    if get_current_user():
        return True
    api_key = get_api_key_from_request()
    return bool(api_key and validate_api_key(api_key))


def _get_authenticated_username() -> str | None:
    """Return the acting username for JWT auth or valid instance API key auth."""
    username = get_current_user()
    if username:
        return username

    api_key = get_api_key_from_request()
    if not api_key or not validate_api_key(api_key):
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

    client_ip = _get_client_ip()
    local_client = bool(client_ip and _is_local_ip(client_ip))

    data = {
        "has_users": auth_config.has_users(),
        "instance_storage_key": INSTANCE_STORAGE_KEY,
        "proxy_auth_bypass": proxy_bypass,
        "local_access_bypass": local_bypass,
        "setup_skipped": auth_config.is_setup_skipped(),
        "auth_enabled": auth_config.has_users() and not proxy_bypass,
    }

    # Frontend-bypass modes still authenticate API calls using the instance API
    # key instead of JWT. Only expose the key when this request is currently
    # eligible to bypass the web login page.
    if auth_config.has_users() and (proxy_bypass or (local_bypass and local_client)):
        data["frontend_api_key"] = auth_config.get_api_key()

    return jsonify(data)


@auth_bp.route("/api/auth/setup", methods=["POST"])
def auth_setup():
    """Create the first user account. Only works when no users exist."""
    if auth_config.has_users():
        return jsonify({"error": "Setup already complete"}), 400

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    confirm_password = data.get("confirm_password") or ""

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400
    if password != confirm_password:
        return jsonify({"error": "Passwords do not match"}), 400

    strength_error = validate_password_strength(password)
    if strength_error:
        return jsonify({"error": strength_error}), 400

    if not auth_config.create_user(username, password):
        return jsonify({"error": "Failed to create user"}), 500

    logger.info(f"First user '{username}' created via setup.")
    return _token_response(username, status=201)


@auth_bp.route("/api/auth/skip-setup", methods=["POST"])
def auth_skip_setup():
    """Mark setup as skipped (enables proxy-bypass / no-login mode)."""
    if auth_config.has_users():
        return jsonify({"error": "Cannot skip setup — users already exist"}), 400
    auth_config.skip_setup()
    logger.info("Setup skipped — proxy auth bypass mode active.")
    return jsonify({"success": True, "setup_skipped": True})


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

    if not verify_login(username, password):
        logger.warning(f"Failed login attempt for user '{username}'.")
        return jsonify({"error": "Invalid username or password"}), 401

    logger.info(f"User '{username}' logged in.")
    return _token_response(username)


@auth_bp.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    """Clear auth cookies."""
    response = make_response(jsonify({"success": True}))
    clear_auth_cookies(response)
    return response


@auth_bp.route("/api/auth/refresh", methods=["POST"])
def auth_refresh():
    """
    Issue a new token pair using the refresh token.
    The instance-scoped httponly refresh cookie is sent automatically by the browser.
    JS clients can also send the refresh token in the request body.
    """
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

    username = payload.get("sub")
    user = auth_config.get_user(username)
    if not user or user.get("disabled", False):
        return jsonify({"error": "User not found or disabled"}), 401

    logger.debug(f"Token refreshed for user '{username}'.")
    return _token_response(username)


# ---------------------------------------------------------------------------
# Token verify
# ---------------------------------------------------------------------------


@auth_bp.route("/api/auth/verify", methods=["POST"])
def auth_verify():
    """Check if a token is valid. Accepts token in body or Authorization header."""
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

    username = payload.get("sub")
    user = auth_config.get_user(username)
    if not user or user.get("disabled", False):
        return jsonify({"valid": False})

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

    data = request.get_json(silent=True) or {}
    current_password = data.get("current_password") or ""
    new_password = data.get("new_password") or ""

    if not current_password or not new_password:
        return jsonify({"error": "Current and new passwords are required"}), 400

    user = auth_config.get_user(username)
    if not user or not verify_password(user["password"], current_password):
        return jsonify({"error": "Current password is incorrect"}), 401

    strength_error = validate_password_strength(new_password)
    if strength_error:
        return jsonify({"error": strength_error}), 400

    if not auth_config.update_password(username, new_password):
        return jsonify({"error": "Failed to update password"}), 500

    logger.info(f"Password changed for user '{username}'.")
    return jsonify({"success": True})


@auth_bp.route("/api/auth/change-username", methods=["POST"])
def auth_change_username():
    """Change the current user's username."""
    username = _get_authenticated_username()
    if not username:
        return jsonify({"error": "Not authenticated"}), 401

    data = request.get_json(silent=True) or {}
    new_username = (data.get("username") or "").strip()
    current_password = data.get("password") or ""

    if not new_username or not current_password:
        return jsonify({"error": "New username and current password are required"}), 400
    if len(new_username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400

    user = auth_config.get_user(username)
    if not user or not verify_password(user["password"], current_password):
        return jsonify({"error": "Current password is incorrect"}), 401

    if not auth_config.update_username(username, new_username):
        return jsonify({"error": "Username already taken or update failed"}), 400

    logger.info(f"Username changed from '{username}' to '{new_username}'.")

    if get_current_user():
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
        return jsonify({"auth_mode": settings.get("auth_mode", "login")})

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

    if settings_manager.save_settings("general", current):
        logger.info(f"Auth mode changed to '{mode}'.")
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Failed to save auth mode"}), 500


# ---------------------------------------------------------------------------
# Page routes for login and setup
# ---------------------------------------------------------------------------


@auth_bp.route("/login", methods=["GET"])
def login_page():
    if not auth_config.has_users() and not auth_config.is_setup_skipped():
        return redirect("/setup")
    try:
        if settings_manager.get_setting("general", "proxy_auth_bypass", False):
            return redirect("/")
    except Exception:
        pass
    return render_template("login.html")


@auth_bp.route("/setup", methods=["GET"])
def setup_page():
    if auth_config.has_users():
        return redirect("/login")
    return render_template("setup.html")
