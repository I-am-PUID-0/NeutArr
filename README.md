<div align="center" style="max-width: 100%; height: auto;">
  <h1>NeutArr</h1>
  <p><strong>Automated missing media hunter and quality upgrader for *arr apps.</strong></p>
  <a href="https://github.com/I-am-PUID-0/NeutArr">
    <img alt="NeutArr" src="frontend/static/logo/neutarr.svg" style="max-width: 400px; height: auto;">
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
```

Visit `http://localhost:9705` — the first-run wizard creates your account and sets the auth mode.

For bind mounts created by Portainer or other tools as `root:root`, set `PUID` and `PGID` to your host user. The container entrypoint will repair `/config` ownership before starting NeutArr.

NeutArr also exposes a native unauthenticated health endpoint at `GET /api/health` (with `/ping` kept as a legacy alias).
The Docker image now uses this endpoint for a native container `HEALTHCHECK`, so Portainer/Docker can report app health instead of only process liveness.

## Authentication

NeutArr ships a JWT dual-token auth system (bcrypt + PyJWT, stateless):

| Mode | When to use |
|:-----|:------------|
| **Standard** | Username/password login; access token (1h) + refresh token (30d) via cookies |
| **Local access bypass** | Requests from trusted CIDR ranges skip the web login — for LAN-only deployments |
| **Proxy auth bypass** | Skip auth entirely when behind a trusted SSO proxy (Authelia, Authentik, etc.) |
| **API key** | `X-Api-Key` header or `?apikey=` query param; for automation and integrations |

Auth mode is selected during the first-run setup wizard and can be changed in Settings. The API key is shown in `Settings -> Account & API` with rotate, show/hide, and copy controls.

> **Note:** `/api/*` endpoints always require JWT or API key regardless of bypass mode. Bypass modes only skip the web UI login redirect.

## Configuration

All configuration is done through the web UI. Settings are persisted to `/config/`.

- **Apps** — URL + API key per \*arr instance; multiple instances per app type supported
- **Search settings** — items per cycle, sleep duration, API rate limits per app
- **Scheduling** — automated search windows per app
- **Security** — auth mode selection (standard, local bypass, proxy bypass)
- **Account & API** — username, password, and API key management inside Settings
- **Swaparr** — stalled download detection thresholds and removal settings

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
- Auth modes: standard / local-bypass (CIDR) / proxy-bypass, with proper `ipaddress` network validation
- `X-Forwarded-For` only trusted when `TRUSTED_PROXIES` env var is set
- API key auth: auto-generated, timing-safe comparison, rotate endpoint
- 2FA removed
- Standalone `User` page removed; account controls now live in `Settings -> Account & API`

**Security:**
- Bandit static analysis clean pass: MD5 marked `usedforsecurity=False`, bind-all documented, `random` calls marked non-crypto, bare `except` narrowed
- pip-audit clean pass: waitress upgraded to `>=3.0.1` (patched PYSEC-2024-210 + PYSEC-2024-211)
- Flask constraint raised to `>=3.1.3` (patched CVE-2026-27205)
- XSS hardening on log renderer and Swaparr status/reset displays
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

The project ships a devcontainer. Open in VS Code with the Dev Containers extension — Poetry and all dependencies install automatically.

```bash
# Run locally
DEBUG=true poetry run python main.py
# → http://localhost:9705

# Lint
poetry run ruff check .
poetry run ruff format --check .

# Security scan
poetry run bandit -r src/ main.py -ll
```

See [CONTRIBUTING.md](CONTRIBUTING.md) to contribute.

## Community

- Discord: [Join the NeutArr channel](https://discord.gg/HWhbsBmRF4)
- Issues: [Open an issue](https://github.com/I-am-PUID-0/NeutArr/issues)
