<div align="center" style="max-width: 100%; height: auto;">
  <h1>NeutArr</h1>
  <p><strong>Automated missing media hunter and quality upgrader for *arr apps.</strong></p>
  <a href="https://github.com/I-am-PUID-0/NeutArr">
    <img alt="NeutArr" src="frontend/static/logo/neutarr.svg" style="max-width: 340px; height: auto;">
  </a>
</div>
<div
  align="center"
  style="display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; margin-top: 1em;"
>
  <a href="https://github.com/I-am-PUID-0/NeutArr/stargazers">
    <img
      alt="GitHub Repo stars"
      src="https://img.shields.io/github/stars/I-am-PUID-0/NeutArr?style=for-the-badge"
    />
  </a>
  <a href="https://github.com/I-am-PUID-0/NeutArr/issues">
    <img
      alt="Issues"
      src="https://img.shields.io/github/issues/I-am-PUID-0/NeutArr?style=for-the-badge"
    />
  </a>
  <a href="https://github.com/I-am-PUID-0/NeutArr/blob/main/LICENSE">
    <img
      alt="License"
      src="https://img.shields.io/github/license/I-am-PUID-0/NeutArr?style=for-the-badge"
    />
  </a>
  <a href="https://github.com/I-am-PUID-0/NeutArr/graphs/contributors">
    <img
      alt="Contributors"
      src="https://img.shields.io/github/contributors/I-am-PUID-0/NeutArr?style=for-the-badge"
    />
  </a>
  <a href="https://github.com/sponsors/I-am-PUID-0">
    <img
      alt="Sponsors"
      src="https://img.shields.io/github/sponsors/I-am-PUID-0?style=for-the-badge&color=%23FF1493"
    />
  </a>
  <a href="https://hub.docker.com/r/iampuid0/neutarr">
    <img
      alt="Docker Pulls"
      src="https://img.shields.io/docker/pulls/iampuid0/neutarr?style=for-the-badge&logo=docker&logoColor=white"
    />
  </a>
  <a href="https://github.com/I-am-PUID-0/NeutArr/actions/workflows/docker-image.yml">
    <img
      alt="Build Status"
      src="https://img.shields.io/github/actions/workflow/status/I-am-PUID-0/NeutArr/docker-image.yml?style=for-the-badge"
    />
  </a>
  <a href="https://discord.gg/HWhbsBmRF4">
    <img
      alt="Join Discord"
      src="https://img.shields.io/badge/Join%20us%20on%20Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white"
    />
  </a>
</div>

<div align="center">
  <p>A focused fork lineage of Huntarr v6.6.3, rebuilt around tighter scope, stronger auth, and cleaner operations.</p>
</div>

NeutArr traces its code lineage from [Huntarr](https://github.com/plexguide/Huntarr.io) v6.6.3 — the last clean release before the project was abandoned under [controversial circumstances](https://www.reddit.com/r/selfhosted/comments/1rckopd/huntarr_your_passwords_and_your_entire_arr_stacks/) — through ElfHosted's [NewtArr](https://github.com/elfhosted/newtarr) v1.0.0, which served as the starting point for this project.

NeutArr keeps the core functionality (hunt missing media, trigger quality upgrades) while rebuilding the auth system, hardening security, and stripping everything that grew beyond the original scope.

## Supported Apps

| App | Missing search | Quality upgrades |
|:----|:--------------:|:----------------:|
| Sonarr | ✅ | ✅ |
| Radarr | ✅ | ✅ |
| Lidarr | ✅ | ✅ |
| Readarr | ✅ | ✅ |
| Whisparr v2 | ✅ | ✅ |
| Whisparr v3 (Eros) | ✅ | ✅ |
| Swaparr | stalled download detection + removal | — |

Multiple instances per app type are supported.

## Quick Start

```yaml
services:
  neutarr:
    image: iampuid0/neutarr:latest
    container_name: neutarr
    restart: unless-stopped
    ports:
      - "9705:9705"
    volumes:
      - ./config:/config
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=UTC
      # Optional: provide your own 16+ character first-run token.
      # If omitted, NeutArr generates one and prints it to the container log.
      # - NEUTARR_SETUP_TOKEN=replace-with-a-long-random-token
```

On the first start, retrieve the one-time setup token:

```bash
docker logs neutarr 2>&1 | grep 'First-run setup token'
# The same generated value is stored at ./config/.setup-token.
```

Visit `http://localhost:9705`, enter that token in the first-run wizard, create your account, and select the auth mode. NeutArr deletes the generated token file after the account is created. When `NEUTARR_SETUP_TOKEN` is supplied explicitly, use that value instead; it is not printed or written to the token file.

For bind mounts created by Portainer or other tools as `root:root`, set `PUID` and `PGID` to your host user. The container entrypoint will repair `/config` ownership before starting NeutArr.

NeutArr also exposes a native unauthenticated health endpoint at `GET /api/health` (with `/ping` kept as a legacy alias).
The Docker image now uses this endpoint for a native container `HEALTHCHECK`, so Portainer/Docker can report app health instead of only process liveness.

## Authentication

NeutArr ships a JWT dual-token auth system (bcrypt + PyJWT, stateless):

| Mode | When to use |
|:-----|:------------|
| **Standard** | Username/password login; access token (1h) + refresh token (30d) in HttpOnly cookies |
| **Local access bypass** | Requests from trusted CIDR ranges skip the web login — for LAN-only deployments |
| **Proxy authentication** | Trust identity assertions only from explicitly configured SSO proxy networks |
| **API key** | `X-Api-Key` header or `?apikey=` query param; for automation and integrations |

Auth mode is selected during the first-run setup wizard and can be changed in Settings. The API key is shown in `Settings -> Account & API` with rotate, show/hide, and copy controls when the request has a JWT, valid API key, or trusted proxy identity; local CIDR bypass alone cannot reveal or rotate it.
Local access bypass CIDR ranges can be edited in `Settings -> Security`; defaults cover loopback, RFC-1918 private networks, and IPv6 ULA.

> **Note:** Initial account creation requires the one-time setup token. There is no unauthenticated skip-setup mode. After setup, JWT and API key credentials work in every mode. Local and proxy bypass authorize both UI and API requests only when the current request satisfies the configured trust boundary; the durable API key is never returned by the public auth-status endpoint.

### Reverse-proxy authentication

Proxy Auth Mode delegates login to an authenticating reverse proxy without disabling NeutArr's request checks. Both environment variables are required:

- `TRUSTED_PROXIES` — comma-separated IP addresses or CIDRs for the immediate reverse-proxy peers, such as `172.20.0.0/16`
- `NEUTARR_PROXY_AUTH_HEADER` — the identity header set by that proxy after successful authentication, such as `Remote-User` or `X-authentik-username`

Requests are authorized only when their immediate source is in `TRUSTED_PROXIES` and the configured identity header is non-empty. Missing or invalid configuration fails closed. Configure the proxy to remove any client-supplied copy of the identity header before setting its trusted value, and replace—not append to—client-supplied `X-Forwarded-For`.

### Authentication attempt limits

NeutArr applies process-local sliding-window limits to credential-verification endpoints:

| Endpoint | Limit |
|:---------|:------|
| Login | 5 consecutive attempts per client and account every 5 minutes |
| Current-password checks | 5 consecutive attempts per client and account every 5 minutes |
| First-run setup | 5 attempts per client every 15 minutes |
| Token refresh | 10 consecutive attempts per client every 5 minutes |
| Token verification | 30 consecutive attempts per client every minute |

Successful authentication clears the applicable attempt buckets. Rejected requests return HTTP `429` with a `Retry-After` header. Limits reset when the NeutArr process restarts and complement—not replace—rate limiting at an internet-facing reverse proxy.

### Browser session cookies

Browser JWTs are stored only in server-managed, `HttpOnly`, `SameSite=Strict` cookies; NeutArr does not persist or inject them through JavaScript or localStorage. When upgrading, the frontend removes legacy localStorage tokens, refreshes an existing session into protected cookies, and expires legacy cookie names.

Cookies receive the `Secure` attribute automatically for direct HTTPS requests and for `X-Forwarded-Proto: https` requests from peers in `TRUSTED_PROXIES`. Set `NEUTARR_SECURE_COOKIES=true` to force secure cookies when HTTPS termination cannot be detected. Do not enable that override for plain-HTTP access because browsers will not return Secure cookies over HTTP.

The login and refresh APIs continue returning JWTs in their JSON responses for non-browser clients that use `Authorization: Bearer`. The bundled frontend ignores those token values and relies on its HttpOnly cookie session.

## Configuration

All configuration is done through the web UI. Settings are persisted to `/config/`.

- **Apps** — URL + API key per \*arr instance; multiple instances per app type supported
- **Search settings** — items per cycle, sleep duration, API rate limits per app
- **Scheduling** — automated search windows per app
- **Security** — auth mode selection (standard, local bypass, proxy bypass)
- **Account & API** — username, password, and API key management inside Settings
- **Swaparr** — per-instance enable toggles, stalled download detection thresholds, and removal settings

## Why v6.6.3?

Huntarr evolved from a simple \*arr helper into a full media acquisition platform:

| Era | What happened |
|:----|:--------------|
| v5.x | 4 apps, ~300 lines, simple and clean |
| v6.x | Multi-instance, Swaparr, scheduler — still an \*arr helper |
| v7.x | Requestarr, Prowlarr, Plex OAuth — 529 commits of scope explosion |
| v8.x | Consolidation, ~9 deps |
| v9.x | Built-in Usenet/torrent clients, internal media libraries — a different app entirely |

NeutArr forks at **v6.6.3**: multi-instance + Swaparr, before the Requestarr/Prowlarr bloat arrived. This version also predates the telemetry and obfuscation additions that followed in later releases — there is nothing to remove because it was never there.

## Changes from Upstream

**Auth:**
- JWT dual-token auth (bcrypt hashing, stateless sessions) replaces SHA-256 + server-side sessions
- Auth modes: standard / local-bypass (GUI-configurable CIDR ranges) / proxy-auth, with proper `ipaddress` network validation
- Proxy-auth requests require both a trusted immediate proxy (`TRUSTED_PROXIES`) and a non-empty configured identity header (`NEUTARR_PROXY_AUTH_HEADER`)
- `X-Forwarded-For` is only trusted when the immediate peer is in `TRUSTED_PROXIES`
- API key auth: auto-generated, timing-safe comparison, rotate endpoint
- Thread-safe, bounded rate limiting protects login, current-password, setup-token, refresh-token, and token-verification endpoints
- Browser JWTs remain in HttpOnly, strict same-site cookies with trusted-proxy-aware Secure handling and legacy localStorage cleanup
- 2FA removed
- Standalone `User` page removed; account controls now live in `Settings -> Account & API`

**Security:**
- Bandit static analysis clean pass: MD5 marked `usedforsecurity=False`, bind-all documented, `random` calls marked non-crypto, bare `except` narrowed
- pip-audit clean pass: waitress upgraded to `>=3.0.1` (patched PYSEC-2024-210 + PYSEC-2024-211)
- Flask constraint raised to `>=3.1.3` (patched CVE-2026-27205)
- XSS hardening across the main and Swaparr log renderers plus Swaparr status/reset displays; log-derived values are rendered as text rather than executable HTML
- Dead code removed: unregistered blueprints, unreachable routes, legacy helper files
- GitHub Actions pinned to immutable commit SHAs; Dependabot monitors both `pip` and `github-actions` weekly
- See [SECURITY-AUDIT-COMPARISON.md](SECURITY-AUDIT-COMPARISON.md) for a finding-by-finding comparison against the Huntarr.io security audit (20 findings: 8 resolved, 11 N/A, 0 open)

**Operations:**
- Dependency management via Poetry (`pyproject.toml`); `requirements.txt` removed
- Multi-arch Docker images (linux/amd64 + linux/arm64)
- `NEUTARR_VERSION` build arg propagated into the container for `/api/version`
- Graceful Docker shutdown (SIGTERM handled correctly)
- Radarr v5 API compatibility fix
- Dead upstream documentation links replaced with inline tooltips
- Removed frontend-only placeholder features that were not part of NeutArr's core scope (`community-resources` toggle/UI and the Cleanuparr info page)

## Development

The project ships a devcontainer. Open in VS Code with the Dev Containers extension — Poetry and all dependencies install automatically into the repo-local `.venv`.

NeutArr does not use a Node/pnpm frontend build. The frontend files are checked-in Flask templates and static assets, so use Poetry and Make for local development.

```bash
# Install dependencies
poetry install --no-root --with dev

# Run locally
DEBUG=true poetry run python main.py
# → http://localhost:9705

# Run the standard local verification suite
make verify

# Optional: install git hooks
make pre-commit-install

# Individual checks
make lint
make format-check
make compile
make test

# Security scan
make security
```

If an older devcontainer was created before the repo-local `.venv` workflow, rebuild the container or run `poetry env remove --all && poetry install --no-root --with dev` from `/app`. Avoid disabling Poetry virtualenvs in the devcontainer; doing so can make `poetry update` try to modify root-owned system packages.

The automated test suite includes application smoke tests for the Flask app, auth setup flow, health/version endpoints, default config JSON, required frontend assets, and focused unit tests for helper logic. CI runs the same unittest discovery command on pull requests.

See [CONTRIBUTING.md](CONTRIBUTING.md) to contribute.

## Community

- Discord: [Join the NeutArr channel](https://discord.gg/HWhbsBmRF4)
- Issues: [Open an issue](https://github.com/I-am-PUID-0/NeutArr/issues)
