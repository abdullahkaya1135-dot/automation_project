import pytest

from app.core import config
from app.core.config import Settings, SettingsError


def test_settings_defaults_package_label_checklist_archive_lookback_days():
    assert Settings().ifs_package_label_checklist_archive_lookback_days == 14


def test_get_settings_defaults_package_label_checklist_archive_lookback_days(
    monkeypatch,
    tmp_path,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(
        "IFS_PACKAGE_LABEL_CHECKLIST_ARCHIVE_LOOKBACK_DAYS",
        raising=False,
    )

    settings = config.get_settings(validate=False)

    assert settings.ifs_package_label_checklist_archive_lookback_days == 14


def test_get_settings_reads_package_label_checklist_archive_lookback_days(
    monkeypatch,
    tmp_path,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("IFS_PACKAGE_LABEL_CHECKLIST_ARCHIVE_LOOKBACK_DAYS", "30")

    settings = config.get_settings(validate=False)

    assert settings.ifs_package_label_checklist_archive_lookback_days == 30


def test_settings_rejects_non_positive_package_label_checklist_archive_lookback_days():
    settings = Settings(
        excel_path="process.xlsx",
        app_pin="1234",
        session_secret="secret",
        ifs_package_label_checklist_archive_lookback_days=0,
    )

    with pytest.raises(
        SettingsError,
        match="IFS_PACKAGE_LABEL_CHECKLIST_ARCHIVE_LOOKBACK_DAYS",
    ):
        settings.validate()
