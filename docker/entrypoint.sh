#!/usr/bin/env bash
set -euo pipefail

APP_USER="neutarr"
APP_GROUP="neutarr"

current_uid="$(id -u "${APP_USER}")"
current_gid="$(id -g "${APP_USER}")"
target_uid="${PUID:-${current_uid}}"
target_gid="${PGID:-${current_gid}}"

require_numeric_id() {
    local label="$1"
    local value="$2"

    if [[ ! "${value}" =~ ^[0-9]+$ ]]; then
        echo "Invalid ${label}: ${value}. Expected a numeric UID/GID." >&2
        exit 1
    fi
}

require_numeric_id "PUID" "${target_uid}"
require_numeric_id "PGID" "${target_gid}"

if [[ "${target_gid}" != "${current_gid}" ]]; then
    if getent group "${target_gid}" >/dev/null 2>&1; then
        existing_group="$(getent group "${target_gid}" | cut -d: -f1)"
        if [[ "${existing_group}" != "${APP_GROUP}" ]]; then
            usermod -g "${target_gid}" "${APP_USER}"
        fi
    else
        groupmod -o -g "${target_gid}" "${APP_GROUP}"
    fi
fi

if [[ "${target_uid}" != "${current_uid}" ]]; then
    usermod -o -u "${target_uid}" "${APP_USER}"
fi

mkdir -p \
    /config \
    /config/history \
    /config/logs \
    /config/reset \
    /config/scheduler \
    /config/settings \
    /config/stateful \
    /config/swaparr \
    /config/user

chown -R "${target_uid}:${target_gid}" /config

if [[ -n "${TZ:-}" ]]; then
    zoneinfo_path="/usr/share/zoneinfo/${TZ}"
    if [[ -e "${zoneinfo_path}" ]]; then
        ln -snf "${zoneinfo_path}" /etc/localtime
        printf '%s\n' "${TZ}" > /etc/timezone
    else
        echo "Warning: timezone '${TZ}' not found at ${zoneinfo_path}; falling back to UTC" >&2
        export TZ="UTC"
        ln -snf "/usr/share/zoneinfo/UTC" /etc/localtime
        printf '%s\n' "UTC" > /etc/timezone
    fi
else
    export TZ="UTC"
    ln -snf "/usr/share/zoneinfo/UTC" /etc/localtime
    printf '%s\n' "UTC" > /etc/timezone
fi

if [[ "${target_uid}" == "0" ]]; then
    exec "$@"
fi

cmd_string="$(printf '%q ' "$@")"
exec su -s /bin/sh "${APP_USER}" -c "exec ${cmd_string% }"
