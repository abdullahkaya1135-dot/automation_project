import os
from dataclasses import dataclass

from dotenv import load_dotenv


class SettingsError(ValueError):
    """Raised when required runtime configuration is missing or invalid."""


DEFAULT_CYCLE_TABLE_PATH = "makine cycle tablosu.xlsx"
DEFAULT_REPORT_OUTPUT_DIR = "."
DEFAULT_AUXILIARY_SYSTEMS_FORM_PATH = (
    r"\\fileserver\PRODUCTION\ÜRETİM RAPOR FK\PROSES-YARDIMCI SİSTEMLER"
    r"\2026\YARDIMCI SİSTEMLER TAKİBİ 2026 FORM.xlsx"
)
DEFAULT_AUXILIARY_SYSTEMS_TARGET_PATH = (
    r"\\fileserver\PRODUCTION\ÜRETİM RAPOR FK\PROSES-YARDIMCI SİSTEMLER"
    r"\2026\YARDIMCI SİSTEMLER TAKİBİ 2026.xlsx"
)
DEFAULT_IFS_BASE_URL = "https://ifs.simsekplastik.com"
DEFAULT_IFS_TOKEN_URL = (
    "https://ifs.simsekplastik.com/auth/realms/prod/protocol/openid-connect/token"
)
DEFAULT_PRODUCTION_PLANNING_DIR = "\\\\fileserver\\GENEL\\URETIM GUNLUK TAKIP"
DEFAULT_PRODUCTION_PLANNING_PATH = (
    "\\\\fileserver\\GENEL\\URETIM GUNLUK TAKIP\\10.06.2026 "
    "\u00c7\u0130ZELGE 2.xlsx"
)


@dataclass(frozen=True)
class Settings:
    excel_path: str = ""
    sheet_name: str = "PROSES 2026"
    app_pin: str = ""
    app_role_pins: str = ""
    session_secret: str = ""
    host: str = "0.0.0.0"
    port: int = 8080
    timezone: str = "Europe/Istanbul"
    sqlite_path: str = "data/process_entries.sqlite3"
    backup_dir: str = "data/backups"
    backup_keep_count: int = 20
    cycle_table_path: str = DEFAULT_CYCLE_TABLE_PATH
    report_output_dir: str = DEFAULT_REPORT_OUTPUT_DIR
    auxiliary_systems_form_path: str = DEFAULT_AUXILIARY_SYSTEMS_FORM_PATH
    auxiliary_systems_target_path: str = DEFAULT_AUXILIARY_SYSTEMS_TARGET_PATH
    auxiliary_systems_sheet_name: str = "YARDIMCI TESİSLER TAKİP"
    ifs_base_url: str = DEFAULT_IFS_BASE_URL
    ifs_token_url: str = DEFAULT_IFS_TOKEN_URL
    ifs_client_id: str = ""
    ifs_client_secret: str = ""
    ifs_username: str = ""
    ifs_password: str = ""
    ifs_contract: str = "S01"
    ifs_company_id: str = "C01"
    ifs_dispatch_filter_id: str = "PET"
    ifs_part_prefix: str = "HM-02"
    ifs_u1_location: str = "U1"
    production_planning_dir: str = ""
    production_planning_path: str = DEFAULT_PRODUCTION_PLANNING_PATH

    def validate(self) -> None:
        missing = [
            name
            for name, value in {
                "EXCEL_PATH": self.excel_path,
                "SHEET_NAME": self.sheet_name,
                "SESSION_SECRET": self.session_secret,
                "HOST": self.host,
                "TIMEZONE": self.timezone,
                "SQLITE_PATH": self.sqlite_path,
                "BACKUP_DIR": self.backup_dir,
                "CYCLE_TABLE_PATH": self.cycle_table_path,
                "REPORT_OUTPUT_DIR": self.report_output_dir,
                "AUXILIARY_SYSTEMS_FORM_PATH": self.auxiliary_systems_form_path,
                "AUXILIARY_SYSTEMS_TARGET_PATH": self.auxiliary_systems_target_path,
                "AUXILIARY_SYSTEMS_SHEET_NAME": self.auxiliary_systems_sheet_name,
            }.items()
            if not value.strip()
        ]
        if not (self.app_pin.strip() or self.app_role_pins.strip()):
            missing.append("APP_PIN or APP_ROLE_PINS")
        if not (
            self.production_planning_dir.strip()
            or self.production_planning_path.strip()
        ):
            missing.append("PRODUCTION_PLANNING_DIR or PRODUCTION_PLANNING_PATH")
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
    load_dotenv(encoding="utf-8-sig")

    settings = Settings(
        excel_path=_string_setting("EXCEL_PATH"),
        sheet_name=_string_setting("SHEET_NAME", "PROSES 2026"),
        app_pin=_string_setting("APP_PIN"),
        app_role_pins=_string_setting("APP_ROLE_PINS"),
        session_secret=_string_setting("SESSION_SECRET"),
        host=_string_setting("HOST", "0.0.0.0"),
        port=_int_setting("PORT", "8080"),
        timezone=_string_setting("TIMEZONE", "Europe/Istanbul"),
        sqlite_path=_string_setting("SQLITE_PATH", "data/process_entries.sqlite3"),
        backup_dir=_string_setting("BACKUP_DIR", "data/backups"),
        backup_keep_count=_int_setting("BACKUP_KEEP_COUNT", "20"),
        cycle_table_path=(
            _string_setting("CYCLE_TABLE_PATH", DEFAULT_CYCLE_TABLE_PATH)
            or DEFAULT_CYCLE_TABLE_PATH
        ),
        report_output_dir=(
            _string_setting("REPORT_OUTPUT_DIR", DEFAULT_REPORT_OUTPUT_DIR)
            or DEFAULT_REPORT_OUTPUT_DIR
        ),
        auxiliary_systems_form_path=(
            _string_setting(
                "AUXILIARY_SYSTEMS_FORM_PATH",
                DEFAULT_AUXILIARY_SYSTEMS_FORM_PATH,
            )
            or DEFAULT_AUXILIARY_SYSTEMS_FORM_PATH
        ),
        auxiliary_systems_target_path=(
            _string_setting(
                "AUXILIARY_SYSTEMS_TARGET_PATH",
                DEFAULT_AUXILIARY_SYSTEMS_TARGET_PATH,
            )
            or DEFAULT_AUXILIARY_SYSTEMS_TARGET_PATH
        ),
        auxiliary_systems_sheet_name=(
            _string_setting(
                "AUXILIARY_SYSTEMS_SHEET_NAME",
                "YARDIMCI TESİSLER TAKİP",
            )
            or "YARDIMCI TESİSLER TAKİP"
        ),
        ifs_base_url=(
            _string_setting("IFS_BASE_URL", DEFAULT_IFS_BASE_URL)
            or DEFAULT_IFS_BASE_URL
        ),
        ifs_token_url=(
            _string_setting("IFS_TOKEN_URL", DEFAULT_IFS_TOKEN_URL)
            or DEFAULT_IFS_TOKEN_URL
        ),
        ifs_client_id=_string_setting("IFS_CLIENT_ID"),
        ifs_client_secret=_string_setting("IFS_CLIENT_SECRET"),
        ifs_username=_string_setting("IFS_USERNAME"),
        ifs_password=_string_setting("IFS_PASSWORD"),
        ifs_contract=_string_setting("IFS_CONTRACT", "S01") or "S01",
        ifs_company_id=_string_setting("IFS_COMPANY_ID", "C01") or "C01",
        ifs_dispatch_filter_id=_string_setting("IFS_DISPATCH_FILTER_ID", "PET")
        or "PET",
        ifs_part_prefix=_string_setting("IFS_PART_PREFIX", "HM-02") or "HM-02",
        ifs_u1_location=_string_setting("IFS_U1_LOCATION", "U1") or "U1",
        production_planning_dir=_string_setting(
            "PRODUCTION_PLANNING_DIR",
            DEFAULT_PRODUCTION_PLANNING_DIR,
        ),
        production_planning_path=(
            _string_setting(
                "PRODUCTION_PLANNING_PATH",
                DEFAULT_PRODUCTION_PLANNING_PATH,
            )
        ),
    )
    if validate:
        settings.validate()
    return settings
