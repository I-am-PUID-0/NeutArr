# Changelog

## [1.5.1](https://github.com/I-am-PUID-0/NeutArr/compare/1.5.0...1.5.1) (2026-03-18)


### 🤡 Other Changes

* **ci:** add Code of Conduct and Pull Request Template ([fae6adf](https://github.com/I-am-PUID-0/NeutArr/commit/fae6adf1e0158287a6cc36b291cc65b7da8f0dd2))
* **docs:** adjust logo size in README for better display ([2a5cde1](https://github.com/I-am-PUID-0/NeutArr/commit/2a5cde12c791bf457580950967ea8c7fea241427))
* **docs:** enhance README and issue templates with community links and improved guidance ([be9992a](https://github.com/I-am-PUID-0/NeutArr/commit/be9992a8dba9834dc4391747011ec1f9ba7fead2))


### 🛠️ Build System

* **deps-dev:** Bump ruff from 0.15.4 to 0.15.5 ([#19](https://github.com/I-am-PUID-0/NeutArr/issues/19)) ([0644406](https://github.com/I-am-PUID-0/NeutArr/commit/064440698e7383cd7de512432e36bf0955694a59))
* **deps-dev:** Bump ruff from 0.15.5 to 0.15.6 ([#20](https://github.com/I-am-PUID-0/NeutArr/issues/20)) ([d783bf6](https://github.com/I-am-PUID-0/NeutArr/commit/d783bf6060cc96183ef2b34788ae45e4bc9ba4ad))
* **deps:** Bump docker/build-push-action from 6.19.2 to 7.0.0 ([#15](https://github.com/I-am-PUID-0/NeutArr/issues/15)) ([a2b2b7a](https://github.com/I-am-PUID-0/NeutArr/commit/a2b2b7a57ef4b1637d0a27df0cbea134d6f16027))
* **deps:** Bump docker/login-action from 3.7.0 to 4.0.0 ([#16](https://github.com/I-am-PUID-0/NeutArr/issues/16)) ([c9e1feb](https://github.com/I-am-PUID-0/NeutArr/commit/c9e1feb059aaebf41c495850c2c3b808f160df60))
* **deps:** Bump docker/setup-buildx-action from 3.12.0 to 4.0.0 ([#17](https://github.com/I-am-PUID-0/NeutArr/issues/17)) ([c9cada1](https://github.com/I-am-PUID-0/NeutArr/commit/c9cada1e4b8f4c5382613a50b677947d290f1d37))
* **deps:** Bump docker/setup-qemu-action from 3.7.0 to 4.0.0 ([#18](https://github.com/I-am-PUID-0/NeutArr/issues/18)) ([e6af1ce](https://github.com/I-am-PUID-0/NeutArr/commit/e6af1ce99004c03d8ee7eaeffd1027dfd971c54e))
* **deps:** Bump pyjwt from 2.11.0 to 2.12.1 ([#21](https://github.com/I-am-PUID-0/NeutArr/issues/21)) ([634cb48](https://github.com/I-am-PUID-0/NeutArr/commit/634cb48e5f5ae0c163eeef0c9b92881366af84e6))

## [1.5.0](https://github.com/I-am-PUID-0/NeutArr/compare/1.4.0...1.5.0) (2026-03-03)


### ✨ Features

* **version:** Centralize runtime version retrieval ([b8a48dc](https://github.com/I-am-PUID-0/NeutArr/commit/b8a48dc6096a808392e09620dc916a1721c3975d))
* **version:** implement dynamic version retrieval from environment and pyproject.toml ([b8a48dc](https://github.com/I-am-PUID-0/NeutArr/commit/b8a48dc6096a808392e09620dc916a1721c3975d))

## [1.4.0](https://github.com/I-am-PUID-0/NeutArr/compare/1.3.0...1.4.0) (2026-03-03)


### ✨ Features

* **docker:** enable provenance and SBOM generation in build step ([dbfa5ff](https://github.com/I-am-PUID-0/NeutArr/commit/dbfa5ffd362d8df00c254b2b79cae819b82ff398))
* improve connection testing and error handling across multiple apps ([2011507](https://github.com/I-am-PUID-0/NeutArr/commit/201150712d1ed98b0d4bb28f51ab42092d0739ba))
* **swaparr:** add app directory validation and improve error handling ([d5d71a3](https://github.com/I-am-PUID-0/NeutArr/commit/d5d71a379bbfa3fc2ded890de4d689fc7a625c39))


### 🐛 Bug Fixes

* **workflow:** add permissions for contents and pull-requests in CI workflows ([f80082d](https://github.com/I-am-PUID-0/NeutArr/commit/f80082d35fb842a9bcc7f02c1457d90cae50b013))


### 🤡 Other Changes

* **settings:** implement app type validation in settings manager ([d5d71a3](https://github.com/I-am-PUID-0/NeutArr/commit/d5d71a379bbfa3fc2ded890de4d689fc7a625c39))


### 📖 Documentation

* **README:** enhance project description for clarity ([f62cdfa](https://github.com/I-am-PUID-0/NeutArr/commit/f62cdfa7b28e09b5926cda1242b8897598aa27a4))


### 🛠️ Refactors

* **apps:** enhance error message handling in apps module ([d5d71a3](https://github.com/I-am-PUID-0/NeutArr/commit/d5d71a379bbfa3fc2ded890de4d689fc7a625c39))
* **devcontainer:** simplify postCreateCommand for Poetry installation ([f62cdfa](https://github.com/I-am-PUID-0/NeutArr/commit/f62cdfa7b28e09b5926cda1242b8897598aa27a4))
* **Dockerfile:** streamline virtual environment setup and dependency installation ([f62cdfa](https://github.com/I-am-PUID-0/NeutArr/commit/f62cdfa7b28e09b5926cda1242b8897598aa27a4))
* **eros_routes:** simplify connection success logging and error handling ([4dd302e](https://github.com/I-am-PUID-0/NeutArr/commit/4dd302e37340a71c8fafedbc071258a8d8a7ece1))
* **history:** update operation status rendering in history section ([d5d71a3](https://github.com/I-am-PUID-0/NeutArr/commit/d5d71a379bbfa3fc2ded890de4d689fc7a625c39))
* **swaparr:** replace safe app directory retrieval with fixed app directory mapping ([8c18023](https://github.com/I-am-PUID-0/NeutArr/commit/8c1802356bc69379c7b7a37c7094a86904b05e03))

## [1.3.0](https://github.com/I-am-PUID-0/NeutArr/compare/1.2.0...1.3.0) (2026-03-03)


### ✨ Features

* **workflow:** add Docker Hub description update workflow ([6e472fb](https://github.com/I-am-PUID-0/NeutArr/commit/6e472fbc4f47b9a60f5d984f83ef2a5433482509))

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
