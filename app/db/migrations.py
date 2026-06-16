from sqlalchemy import text

_OFFLINE_IDEMPOTENCY_COLUMNS = {
    "tour_contexts": {
        "client_request_id": "VARCHAR(64)",
        "client_recorded_at": "DATETIME",
    },
    "entries": {
        "client_request_id": "VARCHAR(64)",
        "client_recorded_at": "DATETIME",
    },
    "auxiliary_systems_submissions": {
        "client_request_id": "VARCHAR(64)",
        "client_recorded_at": "DATETIME",
    },
}
_ENTRY_COLUMNS = {
    f"col_{letter}": "TEXT" for letter in "abcdefghijklmnopqrstuvwxy"
}
_ENTRY_CANONICAL_FIELDS_MIGRATION = "entries_canonical_fields_v2"


def ensure_schema_migrations(connection) -> None:
    _ensure_columns(connection, "entries", _ENTRY_COLUMNS)
    for table_name, columns in _OFFLINE_IDEMPOTENCY_COLUMNS.items():
        _ensure_columns(connection, table_name, columns)

    connection.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "ux_tour_contexts_client_request_id "
            "ON tour_contexts (client_request_id)"
        )
    )
    connection.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "ux_entries_client_request_id "
            "ON entries (client_request_id)"
        )
    )
    connection.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "ux_auxiliary_systems_submissions_client_request_id "
            "ON auxiliary_systems_submissions (client_request_id)"
        )
    )
    connection.execute(text("DROP TABLE IF EXISTS machines_cache"))
    _migrate_legacy_entry_fields_to_canonical(connection)


def _ensure_columns(connection, table_name: str, columns: dict[str, str]) -> None:
    existing_columns = {
        row["name"]
        for row in connection.execute(
            text(f"PRAGMA table_info({table_name})")
        ).mappings()
    }
    for column_name, column_type in columns.items():
        if column_name not in existing_columns:
            connection.execute(
                text(
                    f"ALTER TABLE {table_name} "
                    f"ADD COLUMN {column_name} {column_type}"
                )
            )


def _migrate_legacy_entry_fields_to_canonical(connection) -> None:
    connection.execute(
        text(
            "CREATE TABLE IF NOT EXISTS app_migrations ("
            "name TEXT PRIMARY KEY, "
            "applied_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
    )
    already_applied = connection.execute(
        text("SELECT 1 FROM app_migrations WHERE name = :name"),
        {"name": _ENTRY_CANONICAL_FIELDS_MIGRATION},
    ).first()
    if already_applied is not None:
        return

    connection.execute(
        text(
            "UPDATE entries SET "
            "col_y = col_q, "
            "col_x = col_p, "
            "col_q = col_o, "
            "col_p = col_n, "
            "col_o = col_m, "
            "col_n = col_l, "
            "col_m = col_k, "
            "col_l = col_j, "
            "col_k = col_i, "
            "col_j = col_h, "
            "col_i = NULL, "
            "col_h = col_g, "
            "col_g = NULL "
            "WHERE col_x IS NULL "
            "AND col_y IS NULL "
            "AND (col_g IS NOT NULL OR col_p IS NOT NULL OR col_q IS NOT NULL)"
        )
    )
    connection.execute(
        text("INSERT INTO app_migrations (name) VALUES (:name)"),
        {"name": _ENTRY_CANONICAL_FIELDS_MIGRATION},
    )
