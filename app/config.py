import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class SettingsError(ValueError):
    """Raised when required runtime configuration is missing or invalid."""


DEFAULT_SHOP_ORDER_SOURCE_PATH = str(Path.home() / "Desktop" / "html_to_parse.txt")
DEFAULT_CYCLE_TABLE_PATH = str(Path.home() / "Desktop" / "makine cycle tablosu.xlsx")
DEFAULT_REPORT_OUTPUT_DIR = str(Path.home() / "Desktop")


@dataclass(frozen=True)
class Settings:
    excel_path: str = ""
    sheet_name: str = "PROSES 2026"
    app_pin: str = ""
    host: str = "0.0.0.0"
    port: int = 8080
    timezone: str = "Europe/Istanbul"
    sqlite_path: str = "data/process_entries.sqlite3"
    backup_dir: str = "data/backups"
    backup_keep_count: int = 20
    shop_order_source_path: str = DEFAULT_SHOP_ORDER_SOURCE_PATH
    cycle_table_path: str = DEFAULT_CYCLE_TABLE_PATH
    report_output_dir: str = DEFAULT_REPORT_OUTPUT_DIR

    def validate(self) -> None:
        missing = [
            name
            for name, value in {
                "EXCEL_PATH": self.excel_path,
                "SHEET_NAME": self.sheet_name,
                "APP_PIN": self.app_pin,
                "HOST": self.host,
                "TIMEZONE": self.timezone,
                "SQLITE_PATH": self.sqlite_path,
                "BACKUP_DIR": self.backup_dir,
                "SHOP_ORDER_SOURCE_PATH": self.shop_order_source_path,
                "CYCLE_TABLE_PATH": self.cycle_table_path,
                "REPORT_OUTPUT_DIR": self.report_output_dir,
            }.items()
            if not value.strip()
        ]
        if missing:
            raise SettingsError(
                "Eksik zorunlu ayar(lar): " + ", ".join(sorted(missing))
            )
        if not 1 <= self.port <= 65535:
            raise SettingsError("PORT 1 ile 65535 arasında olmalıdır.")
        if self.backup_keep_count < 1:
            raise SettingsError("BACKUP_KEEP_COUNT en az 1 olmalıdır.")


def _int_setting(name: str, default: str) -> int:
    raw_value = os.getenv(name, default).strip()
    try:
        return int(raw_value)
    except ValueError as exc:
        raise SettingsError(f"{name} tam sayı olmalıdır.") from exc


def _string_setting(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def get_settings(*, validate: bool = True) -> Settings:
    load_dotenv()

    settings = Settings(
        excel_path=_string_setting("EXCEL_PATH"),
        sheet_name=_string_setting("SHEET_NAME", "PROSES 2026"),
        app_pin=_string_setting("APP_PIN"),
        host=_string_setting("HOST", "0.0.0.0"),
        port=_int_setting("PORT", "8080"),
        timezone=_string_setting("TIMEZONE", "Europe/Istanbul"),
        sqlite_path=_string_setting("SQLITE_PATH", "data/process_entries.sqlite3"),
        backup_dir=_string_setting("BACKUP_DIR", "data/backups"),
        backup_keep_count=_int_setting("BACKUP_KEEP_COUNT", "20"),
        shop_order_source_path=(
            _string_setting(
                "SHOP_ORDER_SOURCE_PATH",
                DEFAULT_SHOP_ORDER_SOURCE_PATH,
            )
            or DEFAULT_SHOP_ORDER_SOURCE_PATH
        ),
        cycle_table_path=(
            _string_setting("CYCLE_TABLE_PATH", DEFAULT_CYCLE_TABLE_PATH)
            or DEFAULT_CYCLE_TABLE_PATH
        ),
        report_output_dir=(
            _string_setting("REPORT_OUTPUT_DIR", DEFAULT_REPORT_OUTPUT_DIR)
            or DEFAULT_REPORT_OUTPUT_DIR
        ),
    )
    if validate:
        settings.validate()
    return settings
