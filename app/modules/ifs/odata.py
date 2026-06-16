from collections.abc import Mapping
from typing import Any
from urllib.parse import quote, urlencode

from ...config import Settings
from .constants import PROJECTION_ROOT_PATH
from .errors import IFSClientError


def projection_url(settings: Settings, relative_path: str) -> str:
    base_url = settings.ifs_base_url.rstrip("/")
    path = relative_path.lstrip("/")
    return f"{base_url}{PROJECTION_ROOT_PATH}/{path}"


def url_with_params(url: str, params: Mapping[str, Any] | None) -> str:
    if not params:
        return url
    separator = "&" if "?" in url else "?"
    return url + separator + urlencode(params, quote_via=quote)


def odata_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def odata_key_string(value: str) -> str:
    escaped = value.replace("'", "''")
    return f"'{quote(escaped, safe='')}'"


def pet_operations_path(settings: Settings) -> str:
    args = (
        ("Contract", odata_string(settings.ifs_contract)),
        (
            "FilterBy",
            "IfsApp.ShopFloorWorkbenchHandling.DispatchListFilterBy"
            "'PredefinedFilter'",
        ),
        ("DispListFilterId", odata_string(settings.ifs_dispatch_filter_id)),
        (
            "Selection",
            "IfsApp.ShopFloorWorkbenchHandling.DisListFilterSelection'Ongoing'",
        ),
        (
            "DispatchRule",
            "IfsApp.ShopFloorWorkbenchHandling.DispatchRule'AsScheduled'",
        ),
        ("DepartmentList", "null"),
        ("WorkCenterList", "null"),
        (
            "WorkCenterCode",
            "IfsApp.ShopFloorWorkbenchHandling.WorkCenterCodeShopFloor"
            "'InternalWorkCenter'",
        ),
        ("ProductionLineList", "null"),
        ("ResourceList", "null"),
        ("LaborClassList", "null"),
        ("DateFrom", "null"),
        ("DateTo", "null"),
        (
            "BaseIntervalOn",
            "IfsApp.ShopFloorWorkbenchHandling.DispListIntervalBasis"
            "'PlannedFinishTime'",
        ),
        ("MyAssignedOper", "false"),
        ("BarcodeId", "null"),
        ("OrderNo", "null"),
        ("ReleaseNo", "null"),
        ("SequenceNo", "null"),
        ("ProgramId", "null"),
        ("ProjectId", "null"),
        ("SubProjectId", "null"),
        ("ActivityNo", "null"),
        ("ActivitySeq", "null"),
        ("CompanyId", odata_string(settings.ifs_company_id)),
        ("EmployeeId", "null"),
        ("TeamId", "null"),
    )
    arg_text = ",".join(f"{name}={value}" for name, value in args)
    return f"ShopFloorWorkbenchHandling.svc/GetOperations({arg_text})"


def shop_order_operations_path(settings: Settings, order_no: str) -> str:
    args = (
        ("Contract", odata_string(settings.ifs_contract)),
        (
            "FilterBy",
            "IfsApp.ShopFloorWorkbenchHandling.DispatchListFilterBy"
            "'ShopOrder'",
        ),
        ("DispListFilterId", "null"),
        ("Selection", "null"),
        (
            "DispatchRule",
            "IfsApp.ShopFloorWorkbenchHandling.DispatchRule'AsScheduled'",
        ),
        ("DepartmentList", "null"),
        ("WorkCenterList", "null"),
        ("WorkCenterCode", "null"),
        ("ProductionLineList", "null"),
        ("ResourceList", "null"),
        ("LaborClassList", "null"),
        ("DateFrom", "null"),
        ("DateTo", "null"),
        (
            "BaseIntervalOn",
            "IfsApp.ShopFloorWorkbenchHandling.DispListIntervalBasis"
            "'PlannedFinishTime'",
        ),
        ("MyAssignedOper", "false"),
        ("BarcodeId", "null"),
        ("OrderNo", odata_string(order_no)),
        ("ReleaseNo", odata_string("*")),
        ("SequenceNo", odata_string("*")),
        ("ProgramId", "null"),
        ("ProjectId", "null"),
        ("SubProjectId", "null"),
        ("ActivityNo", "null"),
        ("ActivitySeq", "null"),
        ("CompanyId", odata_string(settings.ifs_company_id)),
        ("EmployeeId", "null"),
        ("TeamId", "null"),
    )
    arg_text = ",".join(f"{name}={value}" for name, value in args)
    return f"ShopFloorWorkbenchHandling.svc/GetOperations({arg_text})"


def required_operation_text(operation: Mapping[str, Any], field_name: str) -> str:
    value = str(operation.get(field_name) or "").strip()
    if not value:
        raise IFSClientError(f"Operation is missing required {field_name}")
    return value


def required_operation_no(operation: Mapping[str, Any]) -> int:
    value = operation.get("OperationNo")
    if value is None:
        raise IFSClientError("Operation is missing required OperationNo")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise IFSClientError("Operation OperationNo must be an integer") from exc


def operation_materials_path(operation: Mapping[str, Any]) -> str:
    order_no = required_operation_text(operation, "OrderNo")
    release_no = required_operation_text(operation, "ReleaseNo")
    sequence_no = required_operation_text(operation, "SequenceNo")
    operation_no = required_operation_no(operation)
    return (
        "ShopFloorWorkbenchHandling.svc/"
        "DispatchListOperationSet("
        f"OrderNo={odata_key_string(order_no)},"
        f"ReleaseNo={odata_key_string(release_no)},"
        f"SequenceNo={odata_key_string(sequence_no)},"
        f"OperationNo={operation_no}"
        ")/OperationMaterialArray"
    )
