# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Repository text cleanup: the changelog and test docstrings no longer reference external issue trackers. No functional changes; 0.6.2 is byte-identical to 0.6.1 in package code.


## [0.6.1] - 2026-07-08

### Fixed

- `ManagedDatabaseClient.fetch_table` now carries the `X-Database-Id` scope header on the result poll, the query-run poll, and the Arrow fetch — not only on the query submit. Results of database-scoped queries are themselves database-scoped, so every read against an existing synced table (merge/append loads, dlt state restore) failed with `400: Bad Request` once the table had data.
- API error messages now include the response body (flattened, truncated to 500 chars). `400: Bad Request` alone hid the server's actual explanation.

### Changed

- The `hotdata` SDK dependency is now `>=0.6.0`, and the scope above rides its native `x_database_id` parameters (`get_result`, `get_query_run`, `get_result_arrow`). Note 0.6.0 made `x_database_id` **required** on `get_result_arrow`, so older framework releases cannot run on it.

## [0.6.0] - 2026-06-30

### Added

- `HotdataClient.add_managed_table(database, table, *, schema)` declares a new table on an existing managed database (wrapping the SDK `add_database_table` endpoint). This allows additive schema evolution without recreating the database.

## [0.5.0] - 2026-06-28

### Changed

- Adopt the `hotdata` 0.5.0 SDK surface (dependency bumped from `>=0.4.1` to `>=0.5.0`). The release is backward compatible for everything the framework uses; the only API changes are additive (a new optional `format` field on `LoadManagedTableRequest` and an optional `format` parameter on `ResultsApi.get_result`), so no framework code changes were required.

## [0.4.1] - 2026-06-26

### Fixed

- `ManagedDatabaseClient.fetch_table` now waits for the persisted result to reach `ready` before fetching it as Arrow on the synchronous query path (it previously only waited on the async path). This fixes failures on read-modify-write loads (merge/append) and state reads against the live backend, where the result is often still `processing` when the inline preview returns.

## [0.4.0] - 2026-06-26

### Changed

- **Renamed the distribution from `hotdata-runtime` to `hotdata-framework`** and the import package from `hotdata_runtime` to `hotdata_framework`. Consumers should depend on `hotdata-framework` and use `import hotdata_framework`. The GitHub repository is now `sdk-python-framework`.
- Added PyPI classifiers, keywords, and an updated description identifying the project as a Python framework.

## [0.3.0] - 2026-06-22

### Added

- Adopt the `hotdata` 0.4.1 SDK surface.
- New typed error-handling public API: `HotdataError`, `HotdataTerminalError`, `HotdataTransientError`, and `classify_sdk_error` (`hotdata_framework/errors.py`).
- `ManagedDatabaseClient` for managed database operations (`hotdata_framework/managed_client.py`).
- `py.typed` marker so downstream consumers pick up inline type information.

### Changed

- Bump the `hotdata` dependency pin to `>=0.4.1`.
- Add ruff and mypy tooling configuration and dev dependencies (`ruff>=0.5`, `mypy>=1.5`); apply ruff lint/format cleanup across the package.


## [0.2.4] - 2026-06-01

### Changed

- Release 0.2.4

## [0.2.3] - 2026-05-27

### Changed

- Release 0.2.3

## [0.2.2] - 2026-05-27

### Changed

- Release 0.2.2

## [0.2.1] - 2026-05-24

### Added

- `execute_sql` accepts an optional `database` keyword argument. When provided, the database name is resolved to an ID and sent as the `X-Database-Id` header so SQL can reference managed database tables as `"default"."<schema>"."<table>"`. Behaviour is unchanged when `database` is omitted.

## [0.2.0] - 2026-05-24

### Changed

- Switch managed database operations from the connections API to the dedicated `/databases` API (`hotdata>=0.2.3` required).
- `create_managed_database` first parameter renamed from `name` to `description` (keyword-only).
- `ManagedDatabase` dataclass: replace `name`/`source_type` fields with `description`/`default_connection_id`.
- `resolve_managed_database` tries direct ID lookup first, then falls back to a description scan.
- `list_managed_databases` now fetches all databases regardless of source type.
- `list_managed_tables`, `load_managed_table`, and `delete_managed_table` use `default_connection_id` instead of database `id` for connection-scoped operations.

### Added

- `create_managed_database` accepts an optional `expires_at` parameter.

### Removed

- `MANAGED_SOURCE_TYPE`, `build_managed_config`, and `create_connection_request` removed from the public API.

## [0.1.1] - 2026-05-19

### Added

- Managed database helpers on `HotdataClient`.

## [0.1.0] - 2026-05-06

### Added

- Initial release.
