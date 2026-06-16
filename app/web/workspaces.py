from dataclasses import dataclass

from ..modules.auth.service import (
    ROLE_ADMIN,
    ROLE_OPERATOR,
    ROLE_PLANNING,
    ROLE_SUPERVISOR,
    ROLE_UTILITY,
)


@dataclass(frozen=True)
class Workspace:
    page_id: str
    role: str
    label: str
    path: str
    template_name: str


WORKSPACES = (
    Workspace(
        page_id="operator",
        role=ROLE_OPERATOR,
        label="Operator",
        path="/operator",
        template_name="pages/operator.html",
    ),
    Workspace(
        page_id="utility",
        role=ROLE_UTILITY,
        label="Utility",
        path="/utility",
        template_name="pages/utility.html",
    ),
    Workspace(
        page_id="supervisor",
        role=ROLE_SUPERVISOR,
        label="Supervisor",
        path="/supervisor",
        template_name="pages/supervisor.html",
    ),
    Workspace(
        page_id="planning",
        role=ROLE_PLANNING,
        label="Planning",
        path="/planning",
        template_name="pages/planning.html",
    ),
)
WORKSPACE_BY_PAGE_ID = {workspace.page_id: workspace for workspace in WORKSPACES}
WORKSPACE_BY_ROLE = {workspace.role: workspace for workspace in WORKSPACES}


def workspace_by_page_id(page_id: str) -> Workspace:
    return WORKSPACE_BY_PAGE_ID[page_id]


def nav_items_for_role(role: str) -> list[dict[str, str]]:
    workspaces = WORKSPACES if role == ROLE_ADMIN else role_workspaces(role)
    return [
        {"label": workspace.label, "href": workspace.path}
        for workspace in workspaces
    ]


def role_workspaces(role: str) -> tuple[Workspace, ...]:
    workspace = WORKSPACE_BY_ROLE.get(role)
    if workspace is None:
        return ()
    return (workspace,)


__all__ = [
    "WORKSPACES",
    "WORKSPACE_BY_PAGE_ID",
    "WORKSPACE_BY_ROLE",
    "Workspace",
    "nav_items_for_role",
    "role_workspaces",
    "workspace_by_page_id",
]
