import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
project_root_text = str(PROJECT_ROOT)
if project_root_text not in sys.path:
    sys.path.insert(0, project_root_text)

from app.config import DEFAULT_SHOP_ORDER_SOURCE_PATH  # noqa: E402
from app.shop_order_source import shop_order_source_payload  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract OrderNo and ResourceId pairs for process entry dropdowns.",
    )
    parser.add_argument(
        "source_path",
        nargs="?",
        default=DEFAULT_SHOP_ORDER_SOURCE_PATH,
        help="Path to the saved OData payload. Defaults to Desktop/html_to_parse.txt.",
    )
    args = parser.parse_args()

    payload = shop_order_source_payload(args.source_path)
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if payload["available"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
