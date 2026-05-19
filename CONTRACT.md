# hotdata-runtime Contract

`hotdata-runtime` is the framework-agnostic runtime contract for Hotdata integrations.

## Scope

This package provides shared primitives for:

- Environment and workspace resolution
- Query execution and polling
- Normalized tabular result handling
- Basic workspace health checks

## Public Runtime Contract

The supported import surface is:

- `HotdataClient`
- `QueryResult`
- `from_env`
- `workspace_health_lines`
- `default_api_key`
- `default_host`
- `default_session_id`
- `explicit_workspace_id`
- `list_workspaces`
- `normalize_host`
- `pick_workspace`
- `resolve_workspace_selection`
- `ResultSummary`
- `RunHistoryItem`
- `WorkspaceSelection`
- `ManagedDatabase`
- `ManagedTable`
- `LoadManagedTableResult`
- `MANAGED_SOURCE_TYPE`
- `DEFAULT_SCHEMA`
- `build_managed_config`
- `create_connection_request`
- `is_parquet_path`

Adapters should import from `hotdata_runtime` and treat this surface as the stable API.

## Semantic Guarantees

### `HotdataClient`

- Represents runtime context: API key, host, workspace, optional session.
- `from_env()` resolves runtime context from env vars and selected workspace.
- `execute_sql(sql)` returns `QueryResult` or raises `RuntimeError`/`TimeoutError`.
- `get_result(result_id)` returns a ready `QueryResult` and waits for readiness when needed.
- `connections()` returns the connections API wrapper for adapter UI/status features.
- `query_runs()` returns the query-runs API wrapper for adapter history views.
- `results()` returns the results API wrapper for adapter result pickers.
- `list_recent_results(...)` returns normalized `ResultSummary` entries.
- `list_run_history(limit=...)` returns normalized `RunHistoryItem` entries.
- `list_qualified_table_names(...)` returns sorted fully qualified table names.
- `columns_for_qualified(qualified, connection_id=...)` resolves table columns, and
  adapters should pass `connection_id` when known.
- `uploads()` returns the uploads API wrapper for parquet staging.
- `list_managed_databases()` returns managed-catalog connections (`source_type: managed`).
- `resolve_managed_database(name_or_id)` resolves a managed database by name or id.
- `create_managed_database(name, schema=..., tables=...)` creates a managed database and optionally declares tables up front.
- `delete_managed_database(name_or_id)` deletes a managed database connection.
- `list_managed_tables(database, schema=...)` lists tables in a managed database.
- `upload_parquet(path)` uploads a local parquet file and returns an upload id.
- `load_managed_table(database, table, schema=..., upload_id=..., file=...)` publishes parquet data into a declared managed table.
- `delete_managed_table(database, table, schema=...)` deletes a managed table.

### `QueryResult`

- Canonical tabular result model with `columns`, `rows`, and `row_count`.
- Carries server identifiers and execution metadata when available.
- `to_pandas()` converts to a DataFrame with stable column ordering.
- `to_records(max_rows=...)` returns row dicts keyed by column names.
- `metadata_dict()` returns normalized result metadata for adapter rendering.

### Env Resolution

- `default_api_key()` reads `HOTDATA_API_KEY`.
- `default_host()` reads `HOTDATA_API_URL` (default: `https://api.hotdata.dev`) and normalizes it.
- `default_session_id()` reads `HOTDATA_SANDBOX`.
- `explicit_workspace_id()` reads `HOTDATA_WORKSPACE` (workspace public id).
- `pick_workspace()` prefers explicit env workspace, then active workspace, then first workspace.
- `resolve_workspace_selection()` is the canonical workspace selection algorithm. It returns `WorkspaceSelection` with selected workspace id, selection source, and discovered workspaces when auto-selected.

## Adapter Responsibilities

Framework packages (Jupyter, Marimo, LangChain, LangGraph, LlamaIndex, Streamlit) own:

- Framework-native lifecycle and state management
- Rendering/UI concerns
- Tool/agent wrappers and callback integration

They should not duplicate runtime env/workspace/query semantics.

## Runtime Non-Goals

`hotdata-runtime` does not define framework UI primitives and does not require framework dependencies.

## Versioning Policy

- Backward-incompatible contract changes require a major version bump.
- Additive contract changes are minor versions.
- Bug fixes that preserve contract semantics are patch versions.

## Enforcement

Contract stability is enforced by tests that verify the public export surface and key behavioral invariants.
