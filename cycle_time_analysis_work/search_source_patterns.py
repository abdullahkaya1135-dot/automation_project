import json
import re
from pathlib import Path

import openpyxl


SOURCE = Path(__file__).with_name("PROSES 2026_FK_source_copy.xlsx")
PATTERNS = {
    "PET": re.compile(r"PET", re.I),
    "MM_GR": re.compile(r"\b\d+(?:[,.]\d+)?\s*MM\b.*\b\d+(?:[,.]\d+)?\s*GR\b", re.I),
    "24MM_16GR": re.compile(r"24\s*MM.*16\s*GR", re.I),
}


def main() -> None:
    wb = openpyxl.load_workbook(SOURCE, data_only=True, read_only=True)
    counts = {name: 0 for name in PATTERNS}
    examples = {name: [] for name in PATTERNS}
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=False):
            for cell in row:
                value = cell.value
                if not isinstance(value, str):
                    continue
                for name, pattern in PATTERNS.items():
                    if pattern.search(value):
                        counts[name] += 1
                        if len(examples[name]) < 12:
                            examples[name].append(
                                {
                                    "sheet": ws.title,
                                    "cell": cell.coordinate,
                                    "value": value,
                                }
                            )
    print(json.dumps({"counts": counts, "examples": examples}, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
