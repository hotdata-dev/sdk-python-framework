# hotdata-runtime

Shared runtime primitives for Hotdata integrations: workspace/session semantics, execution context, query state, run history, and replayable result handles. Framework packages (Marimo, Jupyter, Streamlit, LangGraph) depend on this package.

Install:

```bash
uv pip install hotdata-runtime
# or: pip install hotdata-runtime
```

Development (uses **uv**; creates `.venv/` in this repo):

```bash
uv sync --locked
uv run pytest
```

`uv.lock` is checked in so CI can run `uv sync --locked`. The default **dev** group (pytest) is enabled via `[tool.uv] default-groups`.
