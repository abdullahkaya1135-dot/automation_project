import httpx

from ...config import Settings
from .errors import IFSClientError, require_settings
from .http_client import raise_for_ifs_status


def token_request_data(settings: Settings) -> dict[str, str]:
    require_settings(
        settings,
        (
            ("ifs_token_url", "IFS_TOKEN_URL"),
            ("ifs_client_id", "IFS_CLIENT_ID"),
            ("ifs_username", "IFS_USERNAME"),
            ("ifs_password", "IFS_PASSWORD"),
        ),
    )
    data = {
        "grant_type": "password",
        "client_id": settings.ifs_client_id,
        "username": settings.ifs_username,
        "password": settings.ifs_password,
    }
    if settings.ifs_client_secret.strip():
        data["client_secret"] = settings.ifs_client_secret
    return data


async def obtain_access_token(
    settings: Settings,
    *,
    client: httpx.AsyncClient | None = None,
) -> str:
    data = token_request_data(settings)

    close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30.0)
    try:
        response = await http_client.post(
            settings.ifs_token_url,
            data=data,
        )
        raise_for_ifs_status(response, endpoint_category="oauth-token")
        payload = response.json()
    except ValueError as exc:
        raise IFSClientError("IFS oauth-token response was not valid JSON") from exc
    finally:
        if close_client:
            await http_client.aclose()

    if not isinstance(payload, dict):
        raise IFSClientError("IFS oauth-token response JSON was not an object")
    token = str(payload.get("access_token") or "").strip()
    if not token:
        raise IFSClientError("IFS oauth-token response did not include access_token")
    return token
