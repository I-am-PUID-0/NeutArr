# Security Audit Comparison — Huntarr vs. NeutArr

**Reference audit:** Huntarr.io commit `fa475ab6` (2026-02-23)
**Comparison date:** 2026-03-03
**NeutArr version:** 1.0.0

This document maps every finding from the Huntarr security review against the current NeutArr codebase. The short version: 7 findings are directly resolved, 11 are not applicable (the vulnerable features were never added or were removed), and 0 are open after the fixes made during this review.

---

## Summary

| Severity | Total | Resolved | Not Applicable | Open |
|:---------|:-----:|:--------:|:--------------:|:----:|
| Critical | 7 | 2 | 5 | 0 |
| High | 6 | 3 | 3 | 0 |
| Medium | 5 | 1 | 3 | 0 |
| OSS Best-Practice | 2 | 2 | 0 | 0 |
| **Total** | **20** | **8** | **11** | **0** |

---

## Critical Findings

### #1 — Unauthenticated write to global settings + full credential disclosure in response

**Status: RESOLVED**

NeutArr rebuilt the auth system from scratch. The bypass list is a `frozenset` of explicit paths checked by exact equality (`ALWAYS_PUBLIC_PATHS` in `src/primary/auth.py`). `/api/settings/*` is not in it. All `/api/*` endpoints require a valid JWT or API key. The credential-exposure issue is moot since the endpoint itself is auth-gated.

### #2 — Unauthenticated Plex account linking (account takeover path)

**Status: NOT APPLICABLE**

Plex auth was introduced in Huntarr v7.x. NeutArr forks at v6.6.3, which predates it entirely. No Plex routes, no `plex_auth_routes.py`.

### #3 — Unauthenticated Plex unlink

**Status: NOT APPLICABLE**

Same as #2.

### #4 — Unauthenticated 2FA enrollment on owner account

**Status: NOT APPLICABLE**

2FA (pyotp, qrcode) was removed in its entirety during the auth overhaul. No `/api/user/2fa/` routes exist.

### #5 — Unauthenticated recovery key generation via client-controlled `setup_mode`

**Status: NOT APPLICABLE**

NeutArr has no recovery key system. Not present in v6.6.3 and not added.

### #6 — Zip Slip arbitrary file write via backup upload

**Status: NOT APPLICABLE**

No `backup_routes.py` in NeutArr. Backup/restore was introduced in a later Huntarr version and is not part of this fork.

### #7 — Unauthenticated setup clear re-arms account creation

**Status: NOT APPLICABLE**

No `/api/setup/clear` endpoint. The setup flow uses `/api/auth/setup` and `/api/auth/skip-setup`, both in `ALWAYS_PUBLIC_PATHS`, but these endpoints check server-side state (`has_users`, `setup_skipped`) and become inert once setup is complete.

---

## High Findings

### #8 — Local access bypass trusts spoofable `X-Forwarded-For`

**Status: RESOLVED**

`X-Forwarded-For` is only read when the `TRUSTED_PROXIES` environment variable is set. Without it, only `request.remote_addr` is used for local bypass checks (`src/primary/auth.py`).

### #9 — Windows service/install scripts grant `Everyone:(OI)(CI)F` recursively

**Status: NOT APPLICABLE**

All Windows service and install scripts were deleted in Phase 1. NeutArr is Linux/container only.

### #10 — Hardcoded TMDB / Trakt credentials in source

**Status: NOT APPLICABLE**

NeutArr integrates only with *arr apps directly (Sonarr, Radarr, Lidarr, Readarr, Whisparr, Eros). TMDB, Trakt, Prowlarr, and all third-party service integrations were added in Huntarr v7.x+ and are not present.

### #11 — Full cross-app credential exposure in settings response (aggravates #1)

**Status: RESOLVED**

Consequence of #1 being resolved: the settings endpoint requires authentication, so the disclosure path is closed.

### #12 — Path traversal in backup restore and delete operations

**Status: NOT APPLICABLE**

No backup functionality. See #6.

### #13 — Auth bypass whitelist uses overly broad substring/suffix matching

**Status: RESOLVED**

`ALWAYS_PUBLIC_PATHS` is a `frozenset` (exact equality). `ALWAYS_PUBLIC_PREFIXES` covers only `/static/` and `/logo/` (prefix match, no suffix or substring patterns). The specific patterns cited in the audit — `'/api/user/2fa/' in request.path`, `request.path.endswith('/setup')`, `request.path.endswith('/ping')` — are not present.

---

## Medium Findings

### #14 — Password hashing uses salted SHA-256 instead of a memory-hard KDF

**Status: RESOLVED**

bcrypt replaces SHA-256 entirely. `auth.py` uses `bcrypt.hashpw` / `bcrypt.checkpw` with `bcrypt.gensalt()`.

### #15 — Low-entropy recovery key + rate-limit keying trusts spoofed IP

**Status: NOT APPLICABLE**

No recovery key system. See #5.

### #16 — Network calls without explicit timeouts (Plex auth routes)

**Status: NOT APPLICABLE**

The affected calls were all in Plex auth routes, which do not exist in NeutArr. All *arr API calls in NeutArr pass an `api_timeout` parameter.

### #17 — XML parsing of untrusted data via `ElementTree`

**Status: NOT APPLICABLE**

RSS sync, NZB parser, and import list fetchers are all v7.x+ additions. NeutArr has no XML parsing of external data.

### #18 — Flask CVE-2026-27205 (flask 3.1.2, cache/session behaviour)

**Status: RESOLVED**

`pyproject.toml` constraint updated to `flask = ">=3.1.3,<4.0.0"` which requires the patched version. NeutArr is stateless (no Flask sessions — JWT only), so practical impact was already minimal, but the constraint is now ahead of the CVE regardless.

---

## OSS Best-Practice Findings

### #19 — CI/CD action pinning and dependabot gaps

**Status: RESOLVED**

All GitHub Actions in all four workflow files are now pinned to immutable commit SHAs with the version tag in a trailing comment for readability:

| Action | Tag | SHA |
|:-------|:----|:----|
| `actions/checkout` | v6 | `de0fac2e...` |
| `actions/setup-python` | v6 | `a309ff8b...` |
| `docker/setup-qemu-action` | v3 | `c7c53464...` |
| `docker/setup-buildx-action` | v3 | `8d2750c6...` |
| `docker/login-action` | v3 | `c94ce9fb...` |
| `docker/build-push-action` | v6 | `10e90e36...` |
| `actions/github-script` | v8 | `ed597411...` |
| `googleapis/release-please-action` | v4 | `16a9c908...` |
| `webiny/action-conventional-commits` | v1.3.1 | `faccb24f...` |

`dependabot.yml` monitors both `github-actions` and `pip` weekly, targeting `dev`, and will open PRs to update SHA pins when new versions are released.

### #20 — Container defaults to root (PUID=0 / PGID=0)

**Status: RESOLVED**

`Dockerfile` creates a `neutarr` system group and user (UID 1000). The container now starts through an entrypoint that can remap to `PUID`/`PGID`, repairs `/config` ownership for bind mounts, and then drops privileges to the configured runtime user before launching the app.

---

## Notes

**Why so many "Not Applicable" findings?**

NeutArr forks at Huntarr v6.6.3 specifically because it predates the features that introduced most of the critical vulnerabilities: Plex OAuth (v7.x), backup/restore (v7.x), 2FA (v6.x but removed here), recovery keys, and the scope-expanding integrations. The choice of fork point was partly a security decision — the attack surface in v6.6.3 is dramatically smaller.

**Automated CI enforcement**

The following checks run on every PR and push to `dev`:

| Check | Tool | What it catches |
|:------|:-----|:----------------|
| Static analysis | Bandit | Python security anti-patterns |
| Dependency CVEs | pip-audit | Known vulnerabilities in pinned deps |
| Lint | Ruff | Code quality, undefined names |
| Conventional commits | webiny/action-conventional-commits | Changelog hygiene |

The CI security job exports `poetry`'s locked dependency tree to a `requirements.txt` and runs `pip-audit` against it, so new CVEs in transitive dependencies will be caught automatically on each PR.
