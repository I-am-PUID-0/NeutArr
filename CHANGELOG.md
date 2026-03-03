# Changelog

## [1.2.0](https://github.com/I-am-PUID-0/NeutArr/compare/1.1.0...1.2.0) (2026-03-03)


### ✨ Features

* **docker:** add entrypoint script and health check endpoint ([fccc41d](https://github.com/I-am-PUID-0/NeutArr/commit/fccc41dc5b12326e0afa5383ea5752a6aa162b05))
* **release:** add waiting mechanism for previous release PR tagging ([9212f49](https://github.com/I-am-PUID-0/NeutArr/commit/9212f49b0bb7809c7396615d2201cc4785b77e01))

## [1.1.0](https://github.com/I-am-PUID-0/NeutArr/compare/1.0.0...1.1.0) (2026-03-03)


### ✨ Features

* **ui:** consolidate account controls into settings and remove dead UI remnants ([353d46d](https://github.com/I-am-PUID-0/NeutArr/commit/353d46d2e4f7136e252af623c989930efbbf42da))


### 🐛 Bug Fixes

* **release:** add target-branch configuration for release-please action ([b2e3f6b](https://github.com/I-am-PUID-0/NeutArr/commit/b2e3f6b3aec5280a4995e606312ed847ec8e465a))
* **tests:** remove unnecessary blank lines in test connection logs for radarr, readarr, sonarr ([2cd81fc](https://github.com/I-am-PUID-0/NeutArr/commit/2cd81fc02b95692d091f2442e007b4f685121b61))

## [1.0.0](https://github.com/I-am-PUID-0/NeutArr/compare/0.1.0...1.0.0) (2026-03-02)


### ⚠ BREAKING CHANGES

* Huntarr auth system fully replaced. Existing SHA-256 password hashes and Flask session cookies are incompatible. A fresh /config/users.json is written on first run; the setup wizard creates the initial user account.

### ✨ Features

* initial NeutArr release — fork of Huntarr v6.6.3 ([82577d5](https://github.com/I-am-PUID-0/NeutArr/commit/82577d584721bb20c96348fd2bf6192cc22ffe8a))


### 🐛 Bug Fixes

* **ci:** add poetry-plugin-export, F541 ignore, remove dead code, update actions ([2d58caa](https://github.com/I-am-PUID-0/NeutArr/commit/2d58caa3bd2c22bc102bf26f138d930317b9013f))
* update content-hash in poetry.lock for dependency resolution ([9759810](https://github.com/I-am-PUID-0/NeutArr/commit/97598106fb60fc7485113fbaee592f0fcb855fa0))
