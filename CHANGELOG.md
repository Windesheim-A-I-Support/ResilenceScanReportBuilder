# Changelog

## [0.11.0](https://github.com/kamitor/dashboardpython/compare/v0.10.1...v0.11.0) (2026-02-21)


### Features

* add Linux packaging config files ([2e70ed2](https://github.com/kamitor/dashboardpython/commit/2e70ed28f9e227c3553025735007f4acdbdb4228))
* add packaging config tests and update README ([2170a25](https://github.com/kamitor/dashboardpython/commit/2170a2518ece6d7a52761daf75353f1521acdf42))
* produce proper platform-native packages ([9ba1a1b](https://github.com/kamitor/dashboardpython/commit/9ba1a1be7299310380cedfd6913e163b8fad86ef))

## [0.10.1](https://github.com/kamitor/dashboardpython/compare/v0.10.0...v0.10.1) (2026-02-21)


### Bug Fixes

* add app/__init__.py so tests can import the module in CI ([40fcd88](https://github.com/kamitor/dashboardpython/commit/40fcd8850d2d75c077967d64779182aec5ac3382))
* add pythonpath to pytest config so CI can resolve app module ([21de869](https://github.com/kamitor/dashboardpython/commit/21de8696a5ad0d1ed0a8940c16e8d1263309d89b))
* mock PySide6 when native Qt libs are missing in CI ([f70491e](https://github.com/kamitor/dashboardpython/commit/f70491e2e0c62e49499d315926020d115b47d908))
* only run release-please after CI passes ([69c024a](https://github.com/kamitor/dashboardpython/commit/69c024a20916c566a8cab15166f146d7b90ed514))
* shorten docstring to satisfy ruff line-length check ([3d493e2](https://github.com/kamitor/dashboardpython/commit/3d493e27276c04c0d13831d9b769c1f1cc1fdcb1))

## [0.10.0](https://github.com/kamitor/dashboardpython/compare/v0.9.0...v0.10.0) (2026-02-20)


### Features

* add pyproject.toml and update CI configs ([54eafb1](https://github.com/kamitor/dashboardpython/commit/54eafb1565bb18328da4b6e3def3b870230833d0))
* add real smoke tests and fix CI to fail on errors ([ca0eb7e](https://github.com/kamitor/dashboardpython/commit/ca0eb7e59313c675dcc9fc67295a84eacf0d3f2d))

## [0.9.0](https://github.com/kamitor/dashboardpython/compare/v0.8.0...v0.9.0) (2026-02-20)


### Features

* fix release artifacts not attaching to GitHub Releases ([e4bce03](https://github.com/kamitor/dashboardpython/commit/e4bce03565ebba3cf51e1bde16f117d77ae1fe74))

## [0.8.0](https://github.com/kamitor/dashboardpython/compare/v0.7.0...v0.8.0) (2026-02-20)


### Features

* rewrite build pipeline, drop WiX MSI installer ([39f1bea](https://github.com/kamitor/dashboardpython/commit/39f1bea213633ac19e0f4976f1f905a46659fa82))


### Bug Fixes

* fix CodeQL and Dependabot workflows ([2a47c05](https://github.com/kamitor/dashboardpython/commit/2a47c052d7a3e00f8d99ae70c0bc80eabc7c1eb0))
* quote WiX candle -d args for PowerShell variable expansion ([2a5a9de](https://github.com/kamitor/dashboardpython/commit/2a5a9de6e3651af30f795608dbb3d951297a2397))
* restructure WiX installer to fix ICE validation errors ([90f34bf](https://github.com/kamitor/dashboardpython/commit/90f34bf12750a3e6571da2b36b06d3f85e63f43e))

## [0.7.0](https://github.com/kamitor/dashboardpython/compare/v0.6.0...v0.7.0) (2026-02-20)


### Features

* Another build fix ([5ce1f78](https://github.com/kamitor/dashboardpython/commit/5ce1f78c519acee7fb824058771f18044f5967d1))
* build the damn windows ([8279189](https://github.com/kamitor/dashboardpython/commit/82791895f4c0e9be0aea3353a3c309761f6fd451))
* fix build pipeline for all platforms ([2970536](https://github.com/kamitor/dashboardpython/commit/2970536f1833126012d29af0d859c1cdb9f9a462))
* new build spec ([f3f9242](https://github.com/kamitor/dashboardpython/commit/f3f924218e81061616e5521337b5f34e8c6a44c5))
* windows... ([8600e21](https://github.com/kamitor/dashboardpython/commit/8600e21e09535ba939b3af7132635f92747fbc41))
* Wix fix ([3d5bc39](https://github.com/kamitor/dashboardpython/commit/3d5bc396a4994f8a8b57614cab4ae2d47f1dd4c8))

## [0.6.0](https://github.com/kamitor/dashboardpython/compare/v0.5.0...v0.6.0) (2026-02-18)


### Features

* Fucking work ([f0af0be](https://github.com/kamitor/dashboardpython/commit/f0af0be28c8f97015919fb454c0b84954127b6eb))

## [0.5.0](https://github.com/kamitor/dashboardpython/compare/v0.4.0...v0.5.0) (2026-02-18)


### Features

* fix the pipeline ([a19d718](https://github.com/kamitor/dashboardpython/commit/a19d71894446e984dbbb716149521d1404b88fe1))

## [0.4.0](https://github.com/kamitor/dashboardpython/compare/v0.3.1...v0.4.0) (2026-02-18)


### Features

* stabilize release pipeline ([0c7cee3](https://github.com/kamitor/dashboardpython/commit/0c7cee30d0c7ba16075dd67ec7d4ed2d40c36ebc))

## [0.3.1](https://github.com/kamitor/dashboardpython/compare/v0.3.0...v0.3.1) (2026-02-18)


### Bug Fixes

* .exe ([1b41493](https://github.com/kamitor/dashboardpython/commit/1b414936f95fdc58b08b880120867473ada969d8))

## [0.3.0](https://github.com/kamitor/dashboardpython/compare/v0.2.1...v0.3.0) (2026-02-18)


### Features

* trigger fresh release build ([6b8243a](https://github.com/kamitor/dashboardpython/commit/6b8243a5f3b7a18164fb1d7f6606e63a587cdac9))

## [0.2.1](https://github.com/kamitor/dashboardpython/compare/v0.2.0...v0.2.1) (2026-02-18)


### Bug Fixes

* allow workflow to upload release assets ([829a486](https://github.com/kamitor/dashboardpython/commit/829a4868802b24d1f673ef28175aae0b0294dce5))

## [0.2.0](https://github.com/kamitor/dashboardpython/compare/v0.1.0...v0.2.0) (2026-02-18)


### Features

* add automated release pipeline with release-please ([62b1187](https://github.com/kamitor/dashboardpython/commit/62b1187e6a27def03a78a454317f70063c3e09bd))
* add MSI installer generation with WiX ([1f70824](https://github.com/kamitor/dashboardpython/commit/1f708241a579180b63dc28810409c5a4c722dac1))
* add MSI installer generation with WiX ([bdc7e7e](https://github.com/kamitor/dashboardpython/commit/bdc7e7e57b38b0f9f69e016efbbe8f65d4f9a5a2))
* tests ([1c32170](https://github.com/kamitor/dashboardpython/commit/1c32170e01f73662e6752ba3d483db92d0ae3f45))
