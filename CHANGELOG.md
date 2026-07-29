# Changelog

## [1.11.1](https://github.com/I-am-PUID-0/NeutArr/compare/1.11.0...1.11.1) (2026-07-29)


### 🐛 Bug Fixes

* **version:** reject stale standalone runtime markers ([494b712](https://github.com/I-am-PUID-0/NeutArr/commit/494b71281ff8a31daf735ed995973ed378445cb3))

## [1.11.0](https://github.com/I-am-PUID-0/NeutArr/compare/1.10.0...1.11.0) (2026-07-29)


### ✨ Features

* **history:** explain Arr upgrade searches in centered details dialog ([e492b55](https://github.com/I-am-PUID-0/NeutArr/commit/e492b5552f169b5ed3aecd37673e72c009b406de))


### 🐛 Bug Fixes

* **history:** replace redundant details with media metadata snapshots ([e22f993](https://github.com/I-am-PUID-0/NeutArr/commit/e22f99385320ceaa222b8fe4151c92ad353c2c2a)), closes [#80](https://github.com/I-am-PUID-0/NeutArr/issues/80)

## [1.10.0](https://github.com/I-am-PUID-0/NeutArr/compare/1.9.1...1.10.0) (2026-07-28)


### ✨ Features

* **ui:** complete the responsive interface redesign ([738aaea](https://github.com/I-am-PUID-0/NeutArr/commit/738aaea89651216ec8ae2e6503a918b1f41e0a94)), closes [#85](https://github.com/I-am-PUID-0/NeutArr/issues/85)


### 🐛 Bug Fixes

* **auth:** keep browser sessions in protected cookies ([e9e3d13](https://github.com/I-am-PUID-0/NeutArr/commit/e9e3d1391e796be9f84c1775bcb7da372a7f73b6))
* **auth:** rate limit credential verification endpoints ([fb9162b](https://github.com/I-am-PUID-0/NeutArr/commit/fb9162b620c7e7b614668d30fd9821df09043bb8))
* **auth:** reject API keys in URL query strings ([88d0d03](https://github.com/I-am-PUID-0/NeutArr/commit/88d0d037f3b4d27e8e7fdc5bd00cb68003f0adc2))
* **auth:** revoke JWT sessions on logout and password change ([bca1363](https://github.com/I-am-PUID-0/NeutArr/commit/bca136311795d7a4060c6e40700d7216e7143847))
* **auth:** secure first-run account creation ([41e94a2](https://github.com/I-am-PUID-0/NeutArr/commit/41e94a2b6281f7fd86d3e1c9d71776b5993b499e))
* **auth:** secure proxy bypass without exposing the API key ([1f63dd3](https://github.com/I-am-PUID-0/NeutArr/commit/1f63dd38666bb3bde785706b6b93b04c2ef012c5))
* **history:** make media details accessible and visible ([114f940](https://github.com/I-am-PUID-0/NeutArr/commit/114f9400862fd1938b10f5628a8083311bfcd999)), closes [#80](https://github.com/I-am-PUID-0/NeutArr/issues/80)
* **history:** persist safely and isolate malformed records ([40743e1](https://github.com/I-am-PUID-0/NeutArr/commit/40743e10160b96f44bc399c7d715cbaf995bf5e4))
* **history:** preserve data when renamed paths collide ([674a534](https://github.com/I-am-PUID-0/NeutArr/commit/674a534cf381621598efd0bed8970a6e7914f569))
* **logging:** redact credentials from logs and log responses ([63b9c0a](https://github.com/I-am-PUID-0/NeutArr/commit/63b9c0a72663de52cf104f758c541d56af913a0a))
* **logs:** highlight searches without rewriting html ([9ffe6b4](https://github.com/I-am-PUID-0/NeutArr/commit/9ffe6b4e11e08286e17d95b440bf57f666614e7c))
* **scheduler:** fail actions with no configured targets ([4c8d98e](https://github.com/I-am-PUID-0/NeutArr/commit/4c8d98e1f0f0236893c87f9fedce15107e6c350f))
* **scheduler:** persist schedule definitions safely ([44886d5](https://github.com/I-am-PUID-0/NeutArr/commit/44886d56af18f1a7b4a9ff5dc81014a6b68c15c9))
* **scheduler:** persist scheduled settings safely ([e6fb8ed](https://github.com/I-am-PUID-0/NeutArr/commit/e6fb8eda26466be315ddf3747da59ae4a7146f81))
* **scheduler:** preserve execution windows across midnight ([73fd560](https://github.com/I-am-PUID-0/NeutArr/commit/73fd560a83e11504786da1af54c625c151ca8218))
* **scheduler:** resolve UI app targets correctly ([f2943fe](https://github.com/I-am-PUID-0/NeutArr/commit/f2943fe9a503a0bf9fdd08539fd68fc5304c19e5))
* **scheduling:** prevent stored xss in schedule rows ([6f6a365](https://github.com/I-am-PUID-0/NeutArr/commit/6f6a36553add8a08a2432d9d19a22d8166badc63))
* **security:** constrain history paths to trusted roots ([5e3961c](https://github.com/I-am-PUID-0/NeutArr/commit/5e3961c3ea9fdb95892a009bf19444949dc130eb))
* **security:** prevent exception details from leaking in API responses ([b25eae3](https://github.com/I-am-PUID-0/NeutArr/commit/b25eae3e00fda6c41ee2aa82452f41a1ecf47b86))
* **security:** prevent sensitive upstream data from reaching logs ([db97bc9](https://github.com/I-am-PUID-0/NeutArr/commit/db97bc90317bc7d3d558001a66f6e5cc2d193820))
* **settings:** avoid redundant system timezone writes ([cbf5d46](https://github.com/I-am-PUID-0/NeutArr/commit/cbf5d46eed86cdcd2eb1ed59a1d449f2ce451086)), closes [#79](https://github.com/I-am-PUID-0/NeutArr/issues/79)
* **settings:** escape persisted values in app forms ([95fc45e](https://github.com/I-am-PUID-0/NeutArr/commit/95fc45e1cbbe194487d72e519f0f76e1a6a11680))
* **settings:** prevent partial configuration writes ([b4bcb5a](https://github.com/I-am-PUID-0/NeutArr/commit/b4bcb5a03b83704e89979d23536a4465d4ca9103))
* **stateful:** serialize and atomically persist state ([65016b7](https://github.com/I-am-PUID-0/NeutArr/commit/65016b7e8c9cc76ea9c472497d97f8c0b6bdff61))
* **stats:** serialize hourly resets and persist counters atomically ([1580e42](https://github.com/I-am-PUID-0/NeutArr/commit/1580e4288eee88e61a1ece4c9581db056735a582))
* **storage:** isolate colliding instance state files ([2b34098](https://github.com/I-am-PUID-0/NeutArr/commit/2b3409861bda5d2e95e79b8c1ffe00a490221e12))
* **swaparr:** isolate and safely persist instance state ([524c43b](https://github.com/I-am-PUID-0/NeutArr/commit/524c43b83a3d6a41edbbb5130de27214e1cab7c4))
* **swaparr:** prevent stored xss in log views ([372b97d](https://github.com/I-am-PUID-0/NeutArr/commit/372b97d9ca7181e70bd80fad0226c0c1dcdb1597))
* **swaparr:** support paginated v1 queue responses ([c592b0b](https://github.com/I-am-PUID-0/NeutArr/commit/c592b0bb01e689b2f969a2f8a020aa802448bad9)), closes [#78](https://github.com/I-am-PUID-0/NeutArr/issues/78)
* **ui:** correct local bypass auth and cycle status ([741254f](https://github.com/I-am-PUID-0/NeutArr/commit/741254fab9a6c2907cb03e76e2dca39d4baf92bc))
* **ui:** establish an accessible application shell ([631a292](https://github.com/I-am-PUID-0/NeutArr/commit/631a29206db2af0c8027b6be44b89c755b853a85))
* **ui:** prevent activity card overflow on mobile ([a301354](https://github.com/I-am-PUID-0/NeutArr/commit/a3013548a4f3c17e23b4bd10744ce88641d48a57))
* **ui:** scale automation cards to enabled app count ([05da44d](https://github.com/I-am-PUID-0/NeutArr/commit/05da44dc11300fa097cff3f2ba83b4e24ee7ec57))


### 📖 Documentation

* **readme:** guide first-time users through setup ([67db50f](https://github.com/I-am-PUID-0/NeutArr/commit/67db50fd640258b0a4a8a8c782d609fb99ab8fb5))


### 🛠️ Build System

* **deps:** refresh Python dependencies and GitHub Actions ([b51c10c](https://github.com/I-am-PUID-0/NeutArr/commit/b51c10c802fb7386f3e5cd86510f4967d5aa27f7))

## [1.9.1](https://github.com/I-am-PUID-0/NeutArr/compare/1.9.0...1.9.1) (2026-07-09)


### 🐛 Bug Fixes

* **radarr:** fetch moviefile detail for custom format scoring ([d51e8f1](https://github.com/I-am-PUID-0/NeutArr/commit/d51e8f1dc892e0ae0a75f822f6fec1fe3b8928f0))

## [1.9.0](https://github.com/I-am-PUID-0/NeutArr/compare/1.8.0...1.9.0) (2026-07-09)


### ✨ Features

* **auth:** make local bypass CIDRs configurable ([83fef9a](https://github.com/I-am-PUID-0/NeutArr/commit/83fef9a8dad4c20d2e71d5de5f63882ea7287cb9))


### 🛠️ Build System

* **deps:** update workflow actions and python lockfile ([7b0ff1b](https://github.com/I-am-PUID-0/NeutArr/commit/7b0ff1b9da4321e3cb8de5839628e34580b5643e))

## [1.8.0](https://github.com/I-am-PUID-0/NeutArr/compare/1.7.0...1.8.0) (2026-06-17)


### ✨ Features

* update dependencies and add pre-commit configuration ([d1217c7](https://github.com/I-am-PUID-0/NeutArr/commit/d1217c74e27bbd479ac9a74f00ae3ed7702a25f9))


### 🐛 Bug Fixes

* **radarr:** enhance quality profile handling to accept scalar custom format IDs and format IDs without nested format ([bd802ad](https://github.com/I-am-PUID-0/NeutArr/commit/bd802ad7db827d7819ddc858d9545be4d24d30a8)), closes [#57](https://github.com/I-am-PUID-0/NeutArr/issues/57)

## [1.7.0](https://github.com/I-am-PUID-0/NeutArr/compare/1.6.1...1.7.0) (2026-05-26)


### ✨ Features

* Multiple action for Release Type Radarr ([f0b86f4](https://github.com/I-am-PUID-0/NeutArr/commit/f0b86f4288f958bf03538d20a940500262ba54b6)), closes [#43](https://github.com/I-am-PUID-0/NeutArr/issues/43)
* **radarr:** add availability delay handling for release date checks ([3370c2a](https://github.com/I-am-PUID-0/NeutArr/commit/3370c2accf223ca140bf6d2039d6455cdea7018d)), closes [#44](https://github.com/I-am-PUID-0/NeutArr/issues/44)
* **radarr:** implement quality and custom-format cutoff checks for upgrade candidates ([a80055d](https://github.com/I-am-PUID-0/NeutArr/commit/a80055da867f6141a046d78a065becffce450357)), closes [#37](https://github.com/I-am-PUID-0/NeutArr/issues/37)
* **settings:** enhance timezone application handling and add unit tests ([5d8ffa5](https://github.com/I-am-PUID-0/NeutArr/commit/5d8ffa57159b778c7986a6e69bce8ea41567f851)), closes [#51](https://github.com/I-am-PUID-0/NeutArr/issues/51)
* **swaparr:** enhance per-instance settings management and update configuration structure ([5c562d6](https://github.com/I-am-PUID-0/NeutArr/commit/5c562d646be2b060f5f6e2677f7657c575af73cf)), closes [#48](https://github.com/I-am-PUID-0/NeutArr/issues/48)


### 🤡 Other Changes

* **deps:** update action versions in workflows and bump package versions in poetry.lock ([f806dae](https://github.com/I-am-PUID-0/NeutArr/commit/f806dae4eba7f3d6294af00238281ebfbbfae632))
* **deps:** update docker/login-action and docker/build-push-action to latest versions ([78dcb53](https://github.com/I-am-PUID-0/NeutArr/commit/78dcb535cc7acca48a20ed8978d7cc4293db6b5f))


### 🚀 CI/CD Pipeline

* **tests:** add unit tests for Radarr release types and application smoke tests ([00b904c](https://github.com/I-am-PUID-0/NeutArr/commit/00b904c7ee6584f192c6254b9dd92aa0169863ed))

## [1.6.1](https://github.com/I-am-PUID-0/NeutArr/compare/1.6.0...1.6.1) (2026-03-30)


### 🐛 Bug Fixes

* **runtime:** harden timezone setup and enforce hourly-cap/stateful reset behavior ([da77643](https://github.com/I-am-PUID-0/NeutArr/commit/da77643e11be77834e3fc71c3084a68b318e66ac)), closes [#27](https://github.com/I-am-PUID-0/NeutArr/issues/27)

## [1.6.0](https://github.com/I-am-PUID-0/NeutArr/compare/1.5.1...1.6.0) (2026-03-20)


### ✨ Features

* **auth:** Enhance multi-instance support and API key handling ([59f7b8e](https://github.com/I-am-PUID-0/NeutArr/commit/59f7b8e073ddaf160a9b8a79657d041116dddb70))


### 🐛 Bug Fixes

* **auth:** add logout endpoint to always public paths ([d76ebd8](https://github.com/I-am-PUID-0/NeutArr/commit/d76ebd85ac459c471709f52c98eea56b82b8b5f8))
* **auth:** Invalidate bypass caches; refine username update ([d2d8b00](https://github.com/I-am-PUID-0/NeutArr/commit/d2d8b00ab043f84196ecc167175bfab56a4796ef))
* **logout:** update logout function to use AuthManager and correct API endpoint ([9756c25](https://github.com/I-am-PUID-0/NeutArr/commit/9756c25ac00b9d775d83fb8f72c6df8ed74088f1)), closes [#23](https://github.com/I-am-PUID-0/NeutArr/issues/23)


### 🛠️ Refactors

* **auth:** Encapsulates API key in AuthManager ([fe340bf](https://github.com/I-am-PUID-0/NeutArr/commit/fe340bf9688898a9f73ec767c8426e7cea8cac74))
* **auth:** Improve instance storage key generation ([d6fc7d9](https://github.com/I-am-PUID-0/NeutArr/commit/d6fc7d9f74e487edf715a78a843719a42664c216))
* Improve client-side config and auth handling ([e75147d](https://github.com/I-am-PUID-0/NeutArr/commit/e75147d330510beb79f18cdf206fa0477c32ef89))

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
