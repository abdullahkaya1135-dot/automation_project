from ...config import Settings


class IFSConfigurationError(RuntimeError):
    """Raised when IFS integration settings are incomplete."""


class IFSClientError(RuntimeError):
    """Raised when IFS returns an error or an unexpected payload."""

    def __init__(
        self,
        message: str,
        *,
        endpoint_category: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.endpoint_category = endpoint_category
        self.status_code = status_code


def require_settings(settings: Settings, names: tuple[tuple[str, str], ...]) -> None:
    missing = [
        env_name
        for attr_name, env_name in names
        if not str(getattr(settings, attr_name, "")).strip()
    ]
    if missing:
        raise IFSConfigurationError(
            "Missing IFS configuration: " + ", ".join(sorted(missing))
        )
