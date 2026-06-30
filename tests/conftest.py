import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
project_root_text = str(PROJECT_ROOT)

if project_root_text not in sys.path:
    sys.path.insert(0, project_root_text)

from tests.support import (  # noqa: E402
    IFSRequestRecorder,
    LegacySqliteBuilder,
    authenticated_test_client,
    create_auxiliary_form,
    create_auxiliary_workbook,
    create_cycle_seed_workbook,
    create_process_workbook,
    make_settings,
)


@pytest.fixture
def settings_factory(tmp_path):
    def factory(**overrides):
        return make_settings(tmp_path, **overrides)

    return factory


@pytest.fixture
def process_workbook_factory():
    return create_process_workbook


@pytest.fixture
def cycle_workbook_factory():
    return create_cycle_seed_workbook


@pytest.fixture
def auxiliary_workbook_factory():
    return create_auxiliary_workbook


@pytest.fixture
def auxiliary_form_factory():
    return create_auxiliary_form


@pytest.fixture
def legacy_sqlite_builder(tmp_path):
    return LegacySqliteBuilder(tmp_path / "legacy.sqlite3")


@pytest.fixture
def authenticated_client_factory(monkeypatch, tmp_path):
    def factory(**settings_overrides):
        return authenticated_test_client(monkeypatch, tmp_path, **settings_overrides)

    return factory


@pytest.fixture
def ifs_request_recorder():
    return IFSRequestRecorder
