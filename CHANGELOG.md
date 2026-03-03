# Changelog

## [2.0.0](https://github.com/I-am-PUID-0/NeutArr/compare/1.0.0...2.0.0) (2026-03-03)


### ⚠ BREAKING CHANGES

* Huntarr auth system fully replaced. Existing SHA-256 password hashes and Flask session cookies are incompatible. A fresh /config/users.json is written on first run; the setup wizard creates the initial user account.

### ✨ Features

* initial NeutArr release — fork of Huntarr v6.6.3 ([82577d5](https://github.com/I-am-PUID-0/NeutArr/commit/82577d584721bb20c96348fd2bf6192cc22ffe8a))


### 🐛 Bug Fixes

* **ci:** add poetry-plugin-export, F541 ignore, remove dead code, update actions ([2d58caa](https://github.com/I-am-PUID-0/NeutArr/commit/2d58caa3bd2c22bc102bf26f138d930317b9013f))
* **config:** update paths to use NEUTARR_CONFIG_DIR environment variable ([b46ae4b](https://github.com/I-am-PUID-0/NeutArr/commit/b46ae4bf092f0a68e6a1c4a9695e376154ede1fa))
* **config:** update paths to use NEUTARR_CONFIG_DIR environment variable ([0cf6398](https://github.com/I-am-PUID-0/NeutArr/commit/0cf6398ea0f14d1a0251c4846d38d455ad58dc82))
* **config:** update paths to use NEUTARR_CONFIG_DIR environment variable for configuration files ([70224be](https://github.com/I-am-PUID-0/NeutArr/commit/70224be1e2bfbecf6ef11787a9f875f3df3fd730))
* **settings:** update SETTINGS_DIR to support per-instance config path ([08ab380](https://github.com/I-am-PUID-0/NeutArr/commit/08ab380157ed2942a5ef4ba32eee7474ef0af62d))
* **stats:** update STATS_DIR to support environment-controlled configuration ([34227a4](https://github.com/I-am-PUID-0/NeutArr/commit/34227a41adcf24554efb55bd1cd261a4a8aad5e3))
* update content-hash in poetry.lock for dependency resolution ([9759810](https://github.com/I-am-PUID-0/NeutArr/commit/97598106fb60fc7485113fbaee592f0fcb855fa0))
* **workflows:** enhance Discord announcements for release and dev builds ([0bd7af1](https://github.com/I-am-PUID-0/NeutArr/commit/0bd7af1c5a30d3e446404cd48619770b6bc0c7f9))
* **workflows:** update conditions for Discord announcement and release checks ([b2583fd](https://github.com/I-am-PUID-0/NeutArr/commit/b2583fde7fe6da1290ba86ba14022782b72b5466))
* **workflows:** update Docker Hub credentials and Discord webhook URL ([1feb914](https://github.com/I-am-PUID-0/NeutArr/commit/1feb91458c61127fb9d3f410c9c7e4d141c3119a))


### 🤡 Other Changes

* **main:** release 1.0.0 ([#1](https://github.com/I-am-PUID-0/NeutArr/issues/1)) ([c0f8927](https://github.com/I-am-PUID-0/NeutArr/commit/c0f8927d9de036b77a467d090e2dff4c42db6ca6))


### 🛠️ Build System

* **deps:** Bump bcrypt from 4.3.0 to 5.0.0 ([#6](https://github.com/I-am-PUID-0/NeutArr/issues/6)) ([dc8be51](https://github.com/I-am-PUID-0/NeutArr/commit/dc8be51ff807b3a96ca5a9b87cf4774d104a180c))

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
