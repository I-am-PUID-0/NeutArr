<div align="center">
  <h1>NeutArr</h1>
  <p><strong>Keep your media searches moving.</strong></p>
  <a href="https://github.com/I-am-PUID-0/NeutArr">
    <img alt="NeutArr" src="frontend/static/logo/neutarr.svg" width="340">
  </a>
  <p>
    NeutArr finds missing media and unmet quality upgrades in your existing
    Arr apps, then asks those apps to search for them.
  </p>
</div>

<div align="center">
  <a href="https://hub.docker.com/r/iampuid0/neutarr">
    <img alt="Docker pulls" src="https://img.shields.io/docker/pulls/iampuid0/neutarr?style=flat-square&logo=docker">
  </a>
  <a href="https://github.com/I-am-PUID-0/NeutArr/actions/workflows/docker-image.yml">
    <img alt="Build status" src="https://img.shields.io/github/actions/workflow/status/I-am-PUID-0/NeutArr/docker-image.yml?style=flat-square">
  </a>
  <a href="https://github.com/I-am-PUID-0/NeutArr/blob/main/LICENSE">
    <img alt="License" src="https://img.shields.io/github/license/I-am-PUID-0/NeutArr?style=flat-square">
  </a>
  <a href="https://discord.gg/HWhbsBmRF4">
    <img alt="Discord" src="https://img.shields.io/badge/Discord-NeutArr-5865F2?style=flat-square&logo=discord&logoColor=white">
  </a>
</div>

## What NeutArr Does

NeutArr periodically checks your configured apps and triggers searches for:

- missing movies, series, episodes, music, books, or other supported media;
- items that have not yet met their configured quality cutoff;
- stalled downloads when Swaparr is enabled.

You control how many items NeutArr processes, how often it runs, and when each
app is allowed to search. Multiple instances of the same app are supported.

NeutArr does **not** replace Sonarr, Radarr, your download client, or your media
server. It works alongside your existing stack and uses each app's API to
request searches.

## Supported Apps

| App | Missing media | Quality upgrades |
|:----|:-------------:|:----------------:|
| Sonarr | Yes | Yes |
| Radarr | Yes | Yes |
| Lidarr | Yes | Yes |
| Readarr | Yes | Yes |
| Whisparr v2 | Yes | Yes |
| Whisparr v3 / Eros | Yes | Yes |
| Swaparr | Stalled-download handling | Not applicable |

## Before You Start

You will need:

- Docker with Docker Compose;
- at least one supported app that is already running;
- the app's URL and API key;
- a writable directory for NeutArr's persistent configuration.

The URL must be reachable **from the NeutArr container**. If Sonarr is another
container on the same Docker network, for example, use
`http://sonarr:8989` rather than `http://localhost:8989`.

## Quick Start

Create a `compose.yaml` file:

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
      PUID: 1000
      PGID: 1000
      TZ: UTC
```

Start NeutArr:

```bash
docker compose up -d
```

On the first start, NeutArr generates a one-time setup token. Retrieve it with:

```bash
docker compose logs neutarr 2>&1 | grep 'First-run setup token'
```

The generated value is also stored at `./config/.setup-token`.

Open [http://localhost:9705](http://localhost:9705), enter the setup token,
create your account, and choose an authentication mode. The generated token
file is deleted after setup is complete.

To supply your own first-run token instead, add a 16-or-more-character
`NEUTARR_SETUP_TOKEN` environment variable. An explicitly supplied token is
not printed to the logs or written to `.setup-token`.

### Finish Your First Setup

After signing in:

1. Open **Apps** and select the app you want to connect.
2. Enter a name, the container-reachable URL, and the app's API key.
3. Use **Test Connection** to confirm NeutArr can reach the app.
4. Save the instance and review its **Search Settings**.
5. Open **Scheduling** if searches should run only during selected times.
6. Check **Logs** after the first cycle to confirm searches are working as
   expected.

Start with conservative item limits and increase them after observing how your
indexers and download clients respond.

## Authentication

The setup wizard offers three modes:

| Mode | Best for |
|:-----|:---------|
| **Login Mode** | Most installations. Every connection uses the NeutArr username and password. |
| **Local Bypass Mode** | Trusted private networks where selected CIDR ranges may skip login. |
| **Proxy Auth Mode** | An authenticating reverse proxy or SSO service that supplies a trusted identity header. |

Login Mode is the recommended starting point. Authentication mode and Local
Bypass CIDRs can be changed later under **Settings → Security**.

Proxy Auth Mode requires both of these environment variables:

```yaml
environment:
  TRUSTED_PROXIES: 172.20.0.0/16
  NEUTARR_PROXY_AUTH_HEADER: Remote-User
```

Use the narrowest possible proxy range. Your proxy must remove any
client-supplied copy of the identity header before setting its own value after
authentication. Invalid or incomplete proxy-auth configuration fails closed.

If NeutArr is available only through HTTPS but cannot detect the proxy's
original scheme, `NEUTARR_SECURE_COOKIES=true` forces secure session cookies.
Do not enable it for direct HTTP access.

## API Access

NeutArr creates an API key for integrations and automation. View or rotate it
under **Settings → Account & API**, then send it in the `X-Api-Key` header:

```bash
curl -H "X-Api-Key: ${NEUTARR_API_KEY}" \
  http://neutarr.example/api/settings
```

API keys in URL query strings are rejected. If an older integration uses
`?apikey=...`, update it to use the header so credentials do not leak into
browser history, proxy logs, monitoring tools, or referrer data.

## Data, Updates, and Health

All persistent NeutArr settings, state, and logs live under `/config`. Back up
the host directory mapped to that path before upgrades.

Update the container with:

```bash
docker compose pull
docker compose up -d
```

Review startup and application output with:

```bash
docker compose logs --tail=200 neutarr
```

NeutArr exposes `GET /api/health`, and the published image uses it for Docker's
container health check.

If a bind-mounted `config` directory was created as `root:root`, set `PUID` and
`PGID` to the host account that should own it. The container repairs `/config`
ownership during startup.

### Upgrading from an Older Build

Current releases redact common credentials from configured application logs
and from log lines returned through the web interface. This does not rewrite
historical files already stored under `/config/logs`. Rotate older logs and
replace any credential that may previously have been exposed.

The generated first-run setup token is intentionally visible in startup logs
until account creation consumes it. Treat log access as administrative access
while initial setup is incomplete.

## Troubleshooting

- **The UI does not open:** check `docker compose ps` and
  `docker compose logs neutarr`.
- **An app connection fails:** confirm the URL works from inside the NeutArr
  container and that the API key is current.
- **The container is unhealthy:** request `http://localhost:9705/api/health`
  and inspect the startup logs.
- **The UI works but nothing is searched:** review the instance's item limits,
  sleep interval, schedule, and NeutArr logs.
- **Login fails behind a proxy:** confirm the proxy source is covered by
  `TRUSTED_PROXIES` and that it replaces the configured identity header.

Still stuck? [Open an issue](https://github.com/I-am-PUID-0/NeutArr/issues) or
join the [NeutArr Discord channel](https://discord.gg/HWhbsBmRF4).

## Security and Contributing

Read [SECURITY.md](SECURITY.md) before reporting a vulnerability. The
[security audit comparison](SECURITY-AUDIT-COMPARISON.md) contains the detailed
finding-by-finding hardening record that is intentionally kept out of this
first-time setup guide.

Development setup, checks, branch policy, and pull request guidance are in
[CONTRIBUTING.md](CONTRIBUTING.md).

## Project Background

NeutArr's code lineage began with Huntarr v6.6.3 and continued through
ElfHosted's NewtArr. NeutArr is independently maintained as a focused helper
for missing-media searches, quality upgrades, and stalled-download handling.
