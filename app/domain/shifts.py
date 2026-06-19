from datetime import UTC, datetime, timedelta, timezone
from datetime import date as Date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..core.config import Settings

DISPLAY_DATE_FORMAT = "%d.%m.%Y"
SHIFT_OPTIONS = ("24.00-08.00", "08.00-16.00", "16.00-24.00")
SHIFT_CHIEF_OPTIONS = ("Selman", "Serkan", "Hakan")
FIXED_TIMEZONE_OFFSETS = {
    "Europe/Istanbul": timezone(timedelta(hours=3), "Europe/Istanbul"),
}


def recorded_date(value: Date) -> str:
    return value.strftime(DISPLAY_DATE_FORMAT)


def recorded_date_text(value: str) -> str:
    try:
        return recorded_date(Date.fromisoformat(value))
    except ValueError:
        return value


def request_timezone(settings: Settings):
    try:
        return ZoneInfo(settings.timezone)
    except ZoneInfoNotFoundError:
        if settings.timezone in FIXED_TIMEZONE_OFFSETS:
            return FIXED_TIMEZONE_OFFSETS[settings.timezone]
        local_timezone = datetime.now().astimezone().tzinfo
        return local_timezone or UTC


def request_datetime(settings: Settings) -> datetime:
    return datetime.now(request_timezone(settings))


def shift_for_request_time(value: datetime) -> str:
    if value.hour < 8:
        return SHIFT_OPTIONS[0]
    if value.hour < 16:
        return SHIFT_OPTIONS[1]
    return SHIFT_OPTIONS[2]


def tour_timing_for_datetime(settings: Settings, request_time: datetime) -> dict[str, str]:
    return {
        "date": recorded_date(request_time.date()),
        "shift": shift_for_request_time(request_time),
        "timezone": settings.timezone,
        "generated_at": request_time.isoformat(timespec="seconds"),
    }


def automatic_tour_timing(settings: Settings) -> dict[str, str]:
    return tour_timing_for_datetime(settings, request_datetime(settings))
