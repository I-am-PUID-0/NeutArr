# NeutArr

Automated missing media hunter and quality upgrader for \*arr apps.

A focused fork of [Huntarr](https://github.com/plexguide/Huntarr.io) v6.6.3 — the last clean release before the project was abandoned under [controversial circumstances](https://www.reddit.com/r/selfhosted/comments/1rckopd/huntarr_your_passwords_and_your_entire_arr_stacks/). NeutArr keeps the core functionality (hunt missing media, trigger quality upgrades) while replacing the broken auth system, removing telemetry, and stripping everything that grew beyond the original scope.

## Supported Apps

| App | Missing search | Quality upgrades |
|:----|:--------------:|:----------------:|
| Sonarr | ✅ | ✅ |
| Radarr | ✅ | ✅ |
| Lidarr | ✅ | ✅ |
| Readarr | ✅ | ✅ |
| Whisparr v2 | ✅ | ✅ |
| Whisparr v3 (Eros) | ✅ | ✅ |

Swaparr is also supported for stalled download detection and removal.

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
      - TZ=UTC
```

Visit `http://localhost:9705` — the first-run wizard creates your account and sets the auth mode.

## Authentication

NeutArr ships a JWT dual-token auth system (bcrypt + PyJWT, stateless):

| Mode | When to use |
|:-----|:------------|
| **Standard** | Username/password login; access token (1h) + refresh token (30d) via cookies |
| **Local access bypass** | Requests from trusted CIDR ranges skip auth — for LAN-only deployments |
| **Proxy auth bypass** | Skip auth entirely when behind a trusted SSO proxy (Authelia, Authentik, etc.) |

Auth mode is selected during the first-run setup wizard and can be changed in Settings.

## Configuration

All configuration is done through the web UI. Settings are persisted to `/config/`.

- **Apps** — URL + API key per \*arr instance; multiple instances per app type supported
- **Search settings** — items per cycle, sleep duration, API rate limits per app
- **Scheduling** — automated search windows per app
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

NeutArr forks at **v6.6.3**: multi-instance + Swaparr, before the Requestarr/Prowlarr bloat arrived.

## Changes from Upstream

- Renamed to NeutArr
- JWT dual-token auth (bcrypt hashing, stateless sessions) replaces SHA-256 + server-side sessions
- Auth modes: standard / local-bypass (CIDR) / proxy-bypass, with proper `ipaddress` validation
- 2FA removed
- Telemetry, phone-home, and update-check code removed
- Graceful Docker shutdown (SIGTERM handled correctly)
- Radarr v5 API compatibility fix
- XSS hardening on log renderer and status displays
- Dead upstream documentation links replaced with inline tooltips

## Security

A full audit of the inherited v6.6.3 codebase was performed. See [SECURITY-AUDIT.md](SECURITY-AUDIT.md) for the full report. To report a vulnerability, see [SECURITY.md](SECURITY.md).

**Confirmed absent in v6.6.3:** telemetry, phone-home, obfuscated code, data exfiltration.

## Development

The project ships a devcontainer. Open in VS Code with the Dev Containers extension — dependencies install automatically via `postCreateCommand`.

```bash
# Run locally (Flask dev server with auto-reload)
DEBUG=true python3 main.py
# → http://localhost:9705

# Lint
ruff check .
ruff format --check .
```

See [CONTRIBUTING.md](CONTRIBUTING.md) to contribute.

## License

Fork of Huntarr.io. See [LICENSE](LICENSE) for details.
