# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]





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
