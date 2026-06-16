from typing import Any

from fastapi import Request

from ..config import Settings
from ..modules.auth.service import (
    ROLE_ADMIN,
    ROLE_LABELS,
    default_path_for_role,
    is_request_authenticated,
    request_role,
)
from .workspaces import Workspace, nav_items_for_role


class WorkspaceForbiddenError(PermissionError):
    """Raised when an authenticated role is not allowed to open a workspace."""


def authenticated_default_path(request: Request, settings: Settings) -> str | None:
    if not is_request_authenticated(request, settings):
        return None
    role = request_role(request, settings)
    if role is None:
        return None
    return default_path_for_role(role)


def workspace_template_context(
    request: Request,
    settings: Settings,
    *,
    workspace: Workspace,
) -> dict[str, Any] | None:
    role = request_role(request, settings)
    if role is None:
        return None
    if role != ROLE_ADMIN and role != workspace.role:
        raise WorkspaceForbiddenError

    return {
        "role": role,
        "role_label": ROLE_LABELS.get(role, role),
        "page_id": workspace.page_id,
        "nav_items": nav_items_for_role(role),
        "current_path": request.url.path,
    }
