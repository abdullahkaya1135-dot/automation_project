from datetime import datetime, timedelta, timezone

from app.features.serialization import timestamp


def test_timestamp_matches_existing_api_format() -> None:
    value = datetime(
        2026,
        6,
        8,
        9,
        20,
        30,
        123456,
        tzinfo=timezone(timedelta(hours=3)),
    )

    assert timestamp(value) == "2026-06-08T09:20:30+03:00Z"


def test_timestamp_preserves_none() -> None:
    assert timestamp(None) is None
