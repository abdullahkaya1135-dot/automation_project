import secrets

from ...config import Settings

ROLE_OPERATOR = "operator"
ROLE_UTILITY = "utility"
ROLE_SUPERVISOR = "supervisor"
ROLE_PLANNING = "planning"
ROLE_ADMIN = "admin"
KNOWN_ROLES = {
    ROLE_OPERATOR,
    ROLE_UTILITY,
    ROLE_SUPERVISOR,
    ROLE_PLANNING,
    ROLE_ADMIN,
}
ROLE_LABELS = {
    ROLE_OPERATOR: "Operator",
    ROLE_UTILITY: "Utility",
    ROLE_SUPERVISOR: "Supervisor",
    ROLE_PLANNING: "Planning",
    ROLE_ADMIN: "Admin",
}
ROLE_DEFAULT_PATHS = {
    ROLE_OPERATOR: "/operator",
    ROLE_UTILITY: "/utility",
    ROLE_SUPERVISOR: "/supervisor",
    ROLE_PLANNING: "/planning",
    ROLE_ADMIN: "/operator",
}


def role_pins(settings: Settings) -> dict[str, str]:
    pins: dict[str, str] = {}
    for item in settings.app_role_pins.split(","):
        role, separator, raw_pin = item.partition(":")
        if not separator:
            continue
        normalized_role = role.strip().casefold()
        pin = raw_pin.strip()
        if normalized_role in KNOWN_ROLES and pin:
            pins[normalized_role] = pin
    return pins


def authenticate_pin(pin: str, settings: Settings) -> str | None:
    candidate = pin.strip()
    for role, role_pin in role_pins(settings).items():
        if secrets.compare_digest(candidate, role_pin):
            return role
    if settings.app_pin and secrets.compare_digest(candidate, settings.app_pin):
        return ROLE_ADMIN
    return None


def default_path_for_role(role: str | None) -> str:
    return ROLE_DEFAULT_PATHS.get(role or "", "/login")
