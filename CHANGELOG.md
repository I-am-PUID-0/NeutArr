# Changelog

## [1.0.0](https://github.com/I-am-PUID-0/NeutArr/compare/0.1.0...1.0.0) (2026-03-02)


### ⚠ BREAKING CHANGES

* Huntarr auth system fully replaced. Existing SHA-256 password hashes and Flask session cookies are incompatible. A fresh /config/users.json is written on first run; the setup wizard creates the initial user account.

### ✨ Features

* initial NeutArr release — fork of Huntarr v6.6.3 ([82577d5](https://github.com/I-am-PUID-0/NeutArr/commit/82577d584721bb20c96348fd2bf6192cc22ffe8a))


### 🐛 Bug Fixes

* **ci:** add poetry-plugin-export, F541 ignore, remove dead code, update actions ([2d58caa](https://github.com/I-am-PUID-0/NeutArr/commit/2d58caa3bd2c22bc102bf26f138d930317b9013f))
* update content-hash in poetry.lock for dependency resolution ([9759810](https://github.com/I-am-PUID-0/NeutArr/commit/97598106fb60fc7485113fbaee592f0fcb855fa0))

## Changelog

All notable changes to NeutArr will be documented in this file.

Maintained by [release-please](https://github.com/googleapis/release-please).
