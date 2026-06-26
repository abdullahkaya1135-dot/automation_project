import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "process_entries.sqlite3"


def main() -> None:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    print(json.dumps({"db_path": str(DB_PATH), "exists": DB_PATH.exists(), "size": DB_PATH.stat().st_size}, ensure_ascii=False))

    print("tables")
    for row in connection.execute("select name from sqlite_master where type='table' order by name"):
        print(row["name"])

    print("entries columns")
    for row in connection.execute("pragma table_info(entries)"):
        print(json.dumps(dict(row), ensure_ascii=False))

    print("counts")
    for table in ["entries", "machine_cycle_table_rows"]:
        try:
            count = connection.execute(f"select count(*) from {table}").fetchone()[0]
        except sqlite3.Error as exc:
            print(json.dumps({"table": table, "error": str(exc)}, ensure_ascii=False))
        else:
            print(json.dumps({"table": table, "count": count}, ensure_ascii=False))

    print("sample rows")
    query = """
        select id, process_date, machine_code, col_f, col_g, col_h, col_j, col_k, col_l
        from entries
        where coalesce(col_l, '') <> ''
        order by process_date desc, id desc
        limit 12
    """
    for row in connection.execute(query):
        print(json.dumps(dict(row), ensure_ascii=False))


if __name__ == "__main__":
    main()
