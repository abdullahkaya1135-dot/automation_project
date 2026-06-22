import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class SettingsError(ValueError):
    """Raised when required runtime configuration is missing or invalid."""


DEFAULT_CYCLE_TABLE_PATH = "makine cycle tablosu.xlsx"
DEFAULT_REPORT_OUTPUT_DIR = str(Path.home() / "Desktop")
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
DEFAULT_IFS_PART_PREFIX = "HM-02"
DEFAULT_IFS_PART_PREFIXES = ("HM-02", "HM-03", "HM-04")
DEFAULT_IFS_LABEL_PART_PREFIXES = ("MM",)
DEFAULT_IFS_LABEL_REPORT_IDS = ("SIMSEK_PALET_ETIKETI_REP",)
DEFAULT_IFS_PRODUCTION_LOSS_QUERY_START_DATE = "2026-06-01"
DEFAULT_PRODUCTION_PLANNING_DIR = "\\\\fileserver\\GENEL\\URETIM GUNLUK TAKIP"
DEFAULT_PRODUCTION_PLANNING_PATH = (
    "\\\\fileserver\\GENEL\\URETIM GUNLUK TAKIP\\10.06.2026 \u00c7\u0130ZELGE 2.xlsx"
)


@dataclass(frozen=True)
class Settings:
    excel_path: str = ""
    sheet_name: str = "PROSES 2026"
    app_pin: str = ""
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
    ifs_part_prefix: str = DEFAULT_IFS_PART_PREFIX
    ifs_part_prefixes: tuple[str, ...] = DEFAULT_IFS_PART_PREFIXES
    ifs_label_part_prefixes: tuple[str, ...] = DEFAULT_IFS_LABEL_PART_PREFIXES
    ifs_label_report_ids: tuple[str, ...] = DEFAULT_IFS_LABEL_REPORT_IDS
    ifs_u1_location: str = "U1"
    ifs_production_loss_query_start_date: str = (
        DEFAULT_IFS_PRODUCTION_LOSS_QUERY_START_DATE
    )
    production_planning_dir: str = ""
    production_planning_path: str = DEFAULT_PRODUCTION_PLANNING_PATH

    def validate(self) -> None:
        missing = [
            name
            for name, value in {
                "EXCEL_PATH": self.excel_path,
                "SHEET_NAME": self.sheet_name,
                "APP_PIN": self.app_pin,
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


def _csv_setting(value: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            item for raw_item in value.split(",") if (item := raw_item.strip())
        )
    )


def _ifs_part_prefixes_setting(legacy_prefix: str) -> tuple[str, ...]:
    raw_value = os.getenv("IFS_PART_PREFIXES")
    if raw_value is not None:
        return _csv_setting(raw_value) or DEFAULT_IFS_PART_PREFIXES
    legacy_prefixes = _csv_setting(legacy_prefix)
    if legacy_prefixes and legacy_prefixes != (DEFAULT_IFS_PART_PREFIX,):
        logger.info(
            "Using legacy IFS_PART_PREFIX to configure IFS part prefixes; "
            "prefer IFS_PART_PREFIXES.",
            extra={
                "legacy_setting": "IFS_PART_PREFIX",
                "replacement_setting": "IFS_PART_PREFIXES",
                "legacy_prefix_count": len(legacy_prefixes),
            },
        )
        return legacy_prefixes
    return DEFAULT_IFS_PART_PREFIXES


def get_settings(*, validate: bool = True) -> Settings:
    load_dotenv(encoding="utf-8-sig")

    ifs_part_prefix = (
        _string_setting("IFS_PART_PREFIX", DEFAULT_IFS_PART_PREFIX)
        or DEFAULT_IFS_PART_PREFIX
    )
    ifs_part_prefixes = _ifs_part_prefixes_setting(ifs_part_prefix)

    settings = Settings(
        excel_path=_string_setting("EXCEL_PATH"),
        sheet_name=_string_setting("SHEET_NAME", "PROSES 2026"),
        app_pin=_string_setting("APP_PIN"),
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
        ifs_part_prefix=ifs_part_prefix,
        ifs_part_prefixes=ifs_part_prefixes,
        ifs_label_part_prefixes=(
            _csv_setting(
                _string_setting(
                    "IFS_LABEL_PART_PREFIXES",
                    ",".join(DEFAULT_IFS_LABEL_PART_PREFIXES),
                )
            )
            or DEFAULT_IFS_LABEL_PART_PREFIXES
        ),
        ifs_label_report_ids=(
            _csv_setting(
                _string_setting(
                    "IFS_LABEL_REPORT_IDS",
                    ",".join(DEFAULT_IFS_LABEL_REPORT_IDS),
                )
            )
            or DEFAULT_IFS_LABEL_REPORT_IDS
        ),
        ifs_u1_location=_string_setting("IFS_U1_LOCATION", "U1") or "U1",
        ifs_production_loss_query_start_date=(
            _string_setting(
                "IFS_PRODUCTION_LOSS_QUERY_START_DATE",
                DEFAULT_IFS_PRODUCTION_LOSS_QUERY_START_DATE,
            )
            or DEFAULT_IFS_PRODUCTION_LOSS_QUERY_START_DATE
        ),
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
