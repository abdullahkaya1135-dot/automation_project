from __future__ import annotations

import argparse
from pathlib import Path

from app.config import get_settings
from app.database import init_db
from app.services.process_excel_import import import_process_excel_to_database


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import process Excel rows into the SQLite entries table.",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Workbook path. Defaults to EXCEL_PATH from settings.",
    )
    parser.add_argument(
        "--sheet",
        default=None,
        help="Worksheet name. Defaults to SHEET_NAME from settings.",
    )
    args = parser.parse_args()

    settings = get_settings()
    init_db(settings)
    result = import_process_excel_to_database(
        settings,
        source_path=args.path,
        sheet_name=args.sheet,
    )
    print(
        "Imported process workbook "
        f"{result.source_path} / {result.sheet_name}: "
        f"scanned={result.scanned_rows}, "
        f"inserted={result.inserted_rows}, "
        f"skipped_duplicates={result.skipped_duplicates}"
    )


if __name__ == "__main__":
    main()
