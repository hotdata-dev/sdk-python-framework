"""Basic hotdata-framework usage."""

from hotdata_framework import from_env


def main() -> None:
    client = from_env()
    result = client.execute_sql("SELECT 1 AS ok")

    print("result metadata:", result.metadata_dict())
    print("records:", result.to_records(max_rows=5))

    print("recent results:")
    for item in client.list_recent_results(limit=5, offset=0):
        print(item.to_dict())

    print("run history:")
    for item in client.list_run_history(limit=5):
        print(item.to_dict())

    client.close()


if __name__ == "__main__":
    main()
