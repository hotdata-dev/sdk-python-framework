from hotdata_runtime.result import QueryResult


def _result() -> QueryResult:
    return QueryResult(
        columns=["a", "b"],
        rows=[[1, "x"], [2, "y"]],
        row_count=2,
        result_id="res_1",
        query_run_id="run_1",
        execution_time_ms=12,
        warning="warn",
        error_message=None,
    )


def test_to_records_returns_row_dicts():
    records = _result().to_records()
    assert records == [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]


def test_to_records_honors_max_rows():
    records = _result().to_records(max_rows=1)
    assert records == [{"a": 1, "b": "x"}]


def test_metadata_dict_contains_normalized_fields():
    meta = _result().metadata_dict()
    assert meta == {
        "row_count": 2,
        "column_count": 2,
        "result_id": "res_1",
        "query_run_id": "run_1",
        "execution_time_ms": 12,
        "warning": "warn",
        "error_message": None,
    }
