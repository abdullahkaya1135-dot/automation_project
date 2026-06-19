import asyncio
import base64
import binascii
import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, time, timedelta
from datetime import date as Date
from typing import Any
from urllib.parse import quote, urlencode
from xml.etree import ElementTree
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from ...core.config import DEFAULT_IFS_PART_PREFIX, Settings
from ...features.production_planning.service import (
    read_visible_planning_orders,
    resolve_planning_workbook,
)

logger = logging.getLogger(__name__)

PROJECTION_ROOT_PATH = "/main/ifsapplications/projection/v1"
PLANNING_IFS_CONCURRENCY = 8
LABEL_ARCHIVE_CONCURRENCY = 6
SIMSEK_PALET_ETIKETI_REPORT_ID = "SIMSEK_PALET_ETIKETI_REP"
DEFAULT_LABEL_REPORT_IDS = (SIMSEK_PALET_ETIKETI_REPORT_ID,)
DEFAULT_OPERATION_HISTORY_PRODUCT_PREFIXES = ("MM-PET",)
ARCHIVE_SELECT_FIELDS = (
    "ResultKey",
    "ReportId",
    "Notes",
    "ExecTime",
    "Sender",
    "Owner",
    "Printed",
    "Title",
    "ReportMode",
)
ARCHIVE_DOCUMENT_SELECT_FIELDS = (
    "ResultKey",
    "Id",
    "ReportTitle",
    "PrintJobId",
    "FileName",
    "FileNameExt",
    "Notes",
    "TimeZone",
)
SIMSEK_LABEL_XML_FIELDS = {
    "IS_EMRI_NO": "job_order",
    "PAKET_ID": "package_id",
    "LOT_BATCH_NO": "lot_batch_no",
    "ENVANTER_KODU": "part_no",
    "ENVANTER_ADI": "product_description",
    "PALET_NO": "pallet_no",
    "SIRA_NO": "sequence_no",
    "IC_ADEDI": "quantity",
    "TARIH": "label_time",
    "RESOURCE_ID": "machine_code",
}
STOCK_SELECT_FIELDS = (
    "Contract",
    "PartNo",
    "LocationNo",
    "AvailableQty",
    "QtyOnhand",
    "UoM",
    "LotBatchNo",
    "ObjId",
    "ConfigurationId",
    "SerialNo",
    "EngChgLevel",
    "WaivDevRejNo",
    "ActivitySeq",
    "HandlingUnitId",
)
STOCK_FIELD_MAP = {
    "Contract": "contract",
    "PartNo": "part_no",
    "LocationNo": "location_no",
    "LotBatchNo": "lot_batch_no",
    "AvailableQty": "available_qty",
    "QtyOnhand": "qty_onhand",
    "UoM": "uom",
    "ObjId": "obj_id",
    "ConfigurationId": "configuration_id",
    "SerialNo": "serial_no",
    "EngChgLevel": "eng_chg_level",
    "WaivDevRejNo": "waiv_dev_rej_no",
    "ActivitySeq": "activity_seq",
    "HandlingUnitId": "handling_unit_id",
}
OPERATION_SELECT_FIELDS = (
    "OrderNo",
    "ReleaseNo",
    "SequenceNo",
    "OperationNo",
    "Contract",
    "WorkCenterNo",
    "PartNo",
    "PartNoDesc",
    "PreferredResourceId",
    "OperationNoDesc",
    "RemainingQty",
)
OPERATION_FIELD_MAP = {
    "OrderNo": "order_no",
    "ReleaseNo": "release_no",
    "SequenceNo": "sequence_no",
    "OperationNo": "operation_no",
    "Contract": "contract",
    "WorkCenterNo": "work_center_no",
    "PartNo": "part_no",
    "PartNoDesc": "part_description",
    "PreferredResourceId": "preferred_resource_id",
    "OperationNoDesc": "operation_description",
    "RemainingQty": "remaining_qty",
}
MATERIAL_SELECT_FIELDS = (
    "OrderNo",
    "ReleaseNo",
    "SequenceNo",
    "LineItemNo",
    "OperationNo",
    "PartNo",
    "IssueToLoc",
    "QtyRequired",
    "QtyAssigned",
    "QtyIssued",
    "QtyRemainingToReserve",
    "QtyAvailable",
    "PrintUnit",
    "SoPartNo",
    "Cf_Tercihedilenkaynak",
)
MATERIAL_FIELD_MAP = {
    "OrderNo": "order_no",
    "ReleaseNo": "release_no",
    "SequenceNo": "sequence_no",
    "LineItemNo": "line_item_no",
    "OperationNo": "operation_no",
    "PartNo": "part_no",
    "IssueToLoc": "issue_to_location",
    "QtyRequired": "qty_required",
    "QtyAssigned": "qty_assigned",
    "QtyIssued": "qty_issued",
    "QtyRemainingToReserve": "qty_remaining_to_reserve",
    "QtyAvailable": "qty_available",
    "PrintUnit": "print_unit",
    "SoPartNo": "produced_part_no",
    "Cf_Tercihedilenkaynak": "machine",
}
OPERATION_HISTORY_SELECT_FIELDS = (
    "TransactionId",
    "OrderNo",
    "ReleaseNo",
    "SequenceNo",
    "OperationNo",
    "Contract",
    "WorkCenterNo",
    "ResourceId",
    "ResourceDescription",
    "PartNo",
    "DateApplied",
    "TransactionDate",
    "Dated",
    "TimeOfProduction",
    "QtyComplete",
    "QtyScrapped",
    "TransactionCode",
    "OperStatusCode",
    "OrderType",
)
INVENTORY_PART_SELECT_FIELDS = (
    "Contract",
    "PartNo",
    "Description",
)


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


def _require_settings(settings: Settings, names: tuple[tuple[str, str], ...]) -> None:
    missing = [
        env_name
        for attr_name, env_name in names
        if not str(getattr(settings, attr_name, "")).strip()
    ]
    if missing:
        raise IFSConfigurationError(
            "Missing IFS configuration: " + ", ".join(sorted(missing))
        )


def _projection_url(settings: Settings, relative_path: str) -> str:
    base_url = settings.ifs_base_url.rstrip("/")
    path = relative_path.lstrip("/")
    return f"{base_url}{PROJECTION_ROOT_PATH}/{path}"


def _url_with_params(url: str, params: Mapping[str, Any] | None) -> str:
    if not params:
        return url
    separator = "&" if "?" in url else "?"
    return url + separator + urlencode(params, quote_via=quote)


def _odata_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _part_no_prefixes(settings: Settings) -> tuple[str, ...]:
    prefixes = tuple(
        dict.fromkeys(
            prefix
            for value in getattr(settings, "ifs_part_prefixes", ())
            if (prefix := str(value or "").strip())
        )
    )
    if prefixes:
        return prefixes

    legacy_prefix = str(getattr(settings, "ifs_part_prefix", "") or "").strip()
    if legacy_prefix:
        if legacy_prefix != DEFAULT_IFS_PART_PREFIX:
            logger.info(
                "Using legacy IFS_PART_PREFIX fallback for IFS part prefixes; "
                "prefer IFS_PART_PREFIXES.",
                extra={
                    "legacy_setting": "IFS_PART_PREFIX",
                    "replacement_setting": "IFS_PART_PREFIXES",
                    "legacy_prefix_count": 1,
                },
            )
        return (legacy_prefix,)

    raise IFSConfigurationError("Missing IFS configuration: IFS_PART_PREFIXES")


def _part_no_prefix_filter(settings: Settings) -> str:
    clauses = [
        f"startswith(PartNo,{_odata_string(prefix)})"
        for prefix in _part_no_prefixes(settings)
    ]
    if len(clauses) == 1:
        return clauses[0]
    return "(" + " or ".join(clauses) + ")"


def _odata_key_string(value: str) -> str:
    escaped = value.replace("'", "''")
    return f"'{quote(escaped, safe='')}'"


def _pet_operations_path(settings: Settings) -> str:
    args = (
        ("Contract", _odata_string(settings.ifs_contract)),
        (
            "FilterBy",
            "IfsApp.ShopFloorWorkbenchHandling.DispatchListFilterBy"
            "'PredefinedFilter'",
        ),
        ("DispListFilterId", _odata_string(settings.ifs_dispatch_filter_id)),
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
        ("CompanyId", _odata_string(settings.ifs_company_id)),
        ("EmployeeId", "null"),
        ("TeamId", "null"),
    )
    arg_text = ",".join(f"{name}={value}" for name, value in args)
    return f"ShopFloorWorkbenchHandling.svc/GetOperations({arg_text})"


def _shop_order_operations_path(settings: Settings, order_no: str) -> str:
    args = (
        ("Contract", _odata_string(settings.ifs_contract)),
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
        ("OrderNo", _odata_string(order_no)),
        ("ReleaseNo", _odata_string("*")),
        ("SequenceNo", _odata_string("*")),
        ("ProgramId", "null"),
        ("ProjectId", "null"),
        ("SubProjectId", "null"),
        ("ActivityNo", "null"),
        ("ActivitySeq", "null"),
        ("CompanyId", _odata_string(settings.ifs_company_id)),
        ("EmployeeId", "null"),
        ("TeamId", "null"),
    )
    arg_text = ",".join(f"{name}={value}" for name, value in args)
    return f"ShopFloorWorkbenchHandling.svc/GetOperations({arg_text})"


def _required_operation_text(operation: Mapping[str, Any], field_name: str) -> str:
    value = str(operation.get(field_name) or "").strip()
    if not value:
        raise IFSClientError(f"Operation is missing required {field_name}")
    return value


def _required_operation_no(operation: Mapping[str, Any]) -> int:
    value = operation.get("OperationNo")
    if value is None:
        raise IFSClientError("Operation is missing required OperationNo")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise IFSClientError("Operation OperationNo must be an integer") from exc


def _operation_materials_path(operation: Mapping[str, Any]) -> str:
    order_no = _required_operation_text(operation, "OrderNo")
    release_no = _required_operation_text(operation, "ReleaseNo")
    sequence_no = _required_operation_text(operation, "SequenceNo")
    operation_no = _required_operation_no(operation)
    return (
        "ShopFloorWorkbenchHandling.svc/"
        "DispatchListOperationSet("
        f"OrderNo={_odata_key_string(order_no)},"
        f"ReleaseNo={_odata_key_string(release_no)},"
        f"SequenceNo={_odata_key_string(sequence_no)},"
        f"OperationNo={operation_no}"
        ")/OperationMaterialArray"
    )


def _generated_at(settings: Settings) -> str:
    try:
        tzinfo = ZoneInfo(settings.timezone)
    except ZoneInfoNotFoundError:
        tzinfo = None
    return datetime.now(tzinfo).isoformat(timespec="seconds")


def _body_snippet(response: httpx.Response, limit: int = 500) -> str:
    text = response.text.replace("\r", " ").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _raise_for_ifs_status(
    response: httpx.Response,
    *,
    endpoint_category: str,
) -> None:
    if response.status_code < 400:
        return

    snippet = _body_snippet(response)
    message = f"IFS {endpoint_category} request failed with HTTP {response.status_code}"
    if snippet:
        message += f": {snippet}"
    raise IFSClientError(
        message,
        endpoint_category=endpoint_category,
        status_code=response.status_code,
    )


def _token_request_data(settings: Settings) -> dict[str, str]:
    _require_settings(
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
    data = _token_request_data(settings)

    close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30.0)
    try:
        response = await http_client.post(
            settings.ifs_token_url,
            data=data,
        )
        _raise_for_ifs_status(response, endpoint_category="oauth-token")
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


async def _get_json_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    endpoint_category: str,
    headers: Mapping[str, str],
    params: Mapping[str, Any] | None = None,
    retries: int = 2,
) -> dict[str, Any]:
    for attempt in range(retries + 1):
        response = await client.get(_url_with_params(url, params), headers=headers)
        if response.status_code < 500 or attempt == retries:
            break
        await asyncio.sleep(0.25 * (attempt + 1))

    _raise_for_ifs_status(response, endpoint_category=endpoint_category)
    try:
        payload = response.json()
    except ValueError as exc:
        raise IFSClientError(
            f"IFS {endpoint_category} response was not valid JSON",
            endpoint_category=endpoint_category,
        ) from exc
    if not isinstance(payload, dict):
        raise IFSClientError(
            f"IFS {endpoint_category} response JSON was not an object",
            endpoint_category=endpoint_category,
        )
    return payload


async def _get_all(
    client: httpx.AsyncClient,
    url: str,
    *,
    endpoint_category: str,
    headers: Mapping[str, str],
    params: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    next_url: str | None = url
    next_params: Mapping[str, Any] | None = params

    while next_url:
        payload = await _get_json_with_retry(
            client,
            next_url,
            endpoint_category=endpoint_category,
            headers=headers,
            params=next_params,
        )
        value = payload.get("value", [])
        if not isinstance(value, list):
            raise IFSClientError(
                f"IFS {endpoint_category} response did not include a value list",
                endpoint_category=endpoint_category,
            )
        rows.extend(row for row in value if isinstance(row, dict))
        next_url = payload.get("@odata.nextLink")
        next_params = None

    return rows


async def _post_json_action(
    client: httpx.AsyncClient,
    url: str,
    *,
    endpoint_category: str,
    headers: Mapping[str, str],
    json_body: Mapping[str, Any],
    retries: int = 2,
) -> dict[str, Any]:
    request_headers = {**dict(headers), "Content-Type": "application/json"}
    for attempt in range(retries + 1):
        response = await client.post(url, headers=request_headers, json=json_body)
        if response.status_code < 500 or attempt == retries:
            break
        await asyncio.sleep(0.25 * (attempt + 1))

    _raise_for_ifs_status(response, endpoint_category=endpoint_category)
    try:
        payload = response.json()
    except ValueError as exc:
        raise IFSClientError(
            f"IFS {endpoint_category} response was not valid JSON",
            endpoint_category=endpoint_category,
        ) from exc
    if not isinstance(payload, dict):
        raise IFSClientError(
            f"IFS {endpoint_category} response JSON was not an object",
            endpoint_category=endpoint_category,
        )
    return payload


async def _get_bytes_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    endpoint_category: str,
    headers: Mapping[str, str],
    retries: int = 2,
) -> bytes:
    for attempt in range(retries + 1):
        response = await client.get(url, headers=headers)
        if response.status_code < 500 or attempt == retries:
            break
        await asyncio.sleep(0.25 * (attempt + 1))

    _raise_for_ifs_status(response, endpoint_category=endpoint_category)
    return response.content


def _decode_odata_binary(value: Any, *, endpoint_category: str) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if not isinstance(value, str):
        raise IFSClientError(
            f"IFS {endpoint_category} FileData was not a string",
            endpoint_category=endpoint_category,
        )

    text = value.strip()
    if not text:
        return b""
    if text.lstrip().startswith("<"):
        return text.encode("utf-8")

    padding = "=" * (-len(text) % 4)
    candidates = (
        text + padding,
        text.replace("-", "+").replace("_", "/") + padding,
    )
    for candidate in candidates:
        try:
            return base64.b64decode(candidate, validate=True)
        except binascii.Error:
            continue

    return text.encode("utf-8")


def _decode_xml_bytes(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            return content.decode("utf-16")
        except UnicodeDecodeError:
            return content.decode("iso-8859-9")


async def _get_file_data_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    endpoint_category: str,
    headers: Mapping[str, str],
    retries: int = 2,
) -> bytes:
    for attempt in range(retries + 1):
        response = await client.get(url, headers=headers)
        if response.status_code < 500 or attempt == retries:
            break
        await asyncio.sleep(0.25 * (attempt + 1))

    _raise_for_ifs_status(response, endpoint_category=endpoint_category)

    content_type = response.headers.get("content-type", "")
    if "json" not in content_type.lower() and not response.content.lstrip().startswith(
        b"{"
    ):
        return response.content

    try:
        payload = response.json()
    except ValueError as exc:
        raise IFSClientError(
            f"IFS {endpoint_category} response was not valid JSON",
            endpoint_category=endpoint_category,
        ) from exc
    if not isinstance(payload, dict):
        raise IFSClientError(
            f"IFS {endpoint_category} response JSON was not an object",
            endpoint_category=endpoint_category,
        )
    file_data = payload.get("value", payload.get("FileData"))
    return _decode_odata_binary(file_data, endpoint_category=endpoint_category)


def _odata_datetime_utc(value: datetime) -> str:
    parsed = value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    parsed = parsed.astimezone(UTC)
    return parsed.isoformat(timespec="seconds").replace("+00:00", "Z")


def _label_report_filter(report_ids: Sequence[str]) -> str:
    cleaned = [
        report_id
        for value in report_ids
        if (report_id := str(value or "").strip())
    ]
    if not cleaned:
        cleaned = list(DEFAULT_LABEL_REPORT_IDS)
    clauses = [f"ReportId eq {_odata_string(report_id)}" for report_id in cleaned]
    return clauses[0] if len(clauses) == 1 else "(" + " or ".join(clauses) + ")"


def _archive_time_filter(
    date_from_utc: datetime,
    date_to_utc: datetime,
    report_ids: Sequence[str],
) -> str:
    return (
        f"{_label_report_filter(report_ids)} "
        f"and ExecTime ge {_odata_datetime_utc(date_from_utc)} "
        f"and ExecTime lt {_odata_datetime_utc(date_to_utc)}"
    )


def _operation_history_product_prefix_filter(product_prefixes: Sequence[str]) -> str:
    cleaned = tuple(
        dict.fromkeys(
            prefix
            for value in product_prefixes
            if (prefix := str(value or "").strip())
        )
    )
    prefixes = cleaned or DEFAULT_OPERATION_HISTORY_PRODUCT_PREFIXES
    clauses = [f"startswith(PartNo,{_odata_string(prefix)})" for prefix in prefixes]
    return clauses[0] if len(clauses) == 1 else "(" + " or ".join(clauses) + ")"


def _operation_history_bound(value: Any, field_name: str) -> tuple[datetime, bool]:
    if isinstance(value, datetime):
        return value, False
    if isinstance(value, Date):
        return datetime.combine(value, time.min), True

    text = str(value or "").strip()
    if not text:
        raise IFSClientError(f"{field_name} is required for operation history")
    try:
        if "T" in text or ":" in text:
            return datetime.fromisoformat(text.replace("Z", "+00:00")), False
        return datetime.combine(Date.fromisoformat(text), time.min), True
    except ValueError as exc:
        raise IFSClientError(
            f"{field_name} must be an ISO date or datetime for operation history"
        ) from exc


def _settings_timezone(settings: Settings) -> Any:
    try:
        return ZoneInfo(settings.timezone)
    except ZoneInfoNotFoundError:
        return UTC


def _operation_history_time_window(
    settings: Settings,
    date_from: Any,
    date_to: Any,
    *,
    padding_days: int,
) -> tuple[datetime, datetime]:
    tzinfo = _settings_timezone(settings)
    start, _start_date_only = _operation_history_bound(date_from, "date_from")
    end, end_date_only = _operation_history_bound(date_to, "date_to")
    if end_date_only:
        end = end + timedelta(days=1)

    if start.tzinfo is None:
        start = start.replace(tzinfo=tzinfo)
    if end.tzinfo is None:
        end = end.replace(tzinfo=tzinfo)

    padding = timedelta(days=max(padding_days, 0))
    start_utc = start.astimezone(UTC) - padding
    end_utc = end.astimezone(UTC) + padding
    if end_utc <= start_utc:
        raise IFSClientError("date_to must be after date_from for operation history")
    return start_utc, end_utc


def _operation_history_filter(
    settings: Settings,
    month_prefix: str,
    product_prefixes: Sequence[str],
) -> str:
    return (
        f"contains(Contract,{_odata_string(settings.ifs_contract)}) "
        f"and startswith(cast(DateApplied,Edm.String),{_odata_string(month_prefix)}) "
        f"and {_operation_history_product_prefix_filter(product_prefixes)}"
    )


def _operation_history_month_prefixes(
    settings: Settings,
    date_from: Any,
    date_to: Any,
    *,
    padding_days: int,
) -> tuple[str, ...]:
    start_utc, end_utc = _operation_history_time_window(
        settings,
        date_from,
        date_to,
        padding_days=padding_days,
    )
    tzinfo = _settings_timezone(settings)
    end_inclusive = end_utc - timedelta(microseconds=1)
    start_date = start_utc.astimezone(tzinfo).date()
    end_date = end_inclusive.astimezone(tzinfo).date()
    current = Date(start_date.year, start_date.month, 1)
    last = Date(end_date.year, end_date.month, 1)
    prefixes: list[str] = []
    while current <= last:
        prefixes.append(current.strftime("%Y-%m"))
        if current.month == 12:
            current = Date(current.year + 1, 1, 1)
        else:
            current = Date(current.year, current.month + 1, 1)
    return tuple(prefixes)


def _part_no_equals_filter(part_numbers: Sequence[str]) -> str:
    cleaned = [
        part_no
        for value in part_numbers
        if (part_no := str(value or "").strip())
    ]
    clauses = [f"PartNo eq {_odata_string(part_no)}" for part_no in cleaned]
    if not clauses:
        return ""
    return clauses[0] if len(clauses) == 1 else "(" + " or ".join(clauses) + ")"


def _batched(values: Sequence[str], size: int) -> list[list[str]]:
    if size < 1:
        raise IFSClientError("batch_size must be positive for inventory part lookup")
    return [list(values[index:index + size]) for index in range(0, len(values), size)]


def _odata_count_value(value: Any) -> int | None:
    if value is None:
        return None
    try:
        count = int(value)
    except (TypeError, ValueError):
        return None
    return count if count >= 0 else None


async def _get_paged_by_top_skip(
    client: httpx.AsyncClient,
    url: str,
    *,
    endpoint_category: str,
    headers: Mapping[str, str],
    params: Mapping[str, Any],
    page_size: int,
    dedupe_field: str,
    seen_values: set[str] | None = None,
) -> list[dict[str, Any]]:
    if page_size < 1:
        raise IFSClientError("page_size must be positive for operation history")

    rows: list[dict[str, Any]] = []
    seen = seen_values if seen_values is not None else set()
    fetched_count = 0
    total_count: int | None = None
    skip = 0

    while True:
        payload = await _get_json_with_retry(
            client,
            url,
            endpoint_category=endpoint_category,
            headers=headers,
            params={
                **dict(params),
                "$top": str(page_size),
                "$skip": str(skip),
            },
        )
        value = payload.get("value", [])
        if not isinstance(value, list):
            raise IFSClientError(
                f"IFS {endpoint_category} response did not include a value list",
                endpoint_category=endpoint_category,
            )

        page_rows = [row for row in value if isinstance(row, dict)]
        for row in page_rows:
            dedupe_value = _identity_value(row.get(dedupe_field))
            if dedupe_value:
                if dedupe_value in seen:
                    continue
                seen.add(dedupe_value)
            rows.append(dict(row))

        fetched_count += len(value)
        if total_count is None:
            total_count = _odata_count_value(payload.get("@odata.count"))
        if len(value) < page_size:
            break
        if total_count is not None and fetched_count >= total_count:
            break
        skip += page_size

    return rows


async def fetch_report_archive_label_rows(
    settings: Settings,
    *,
    date_from_utc: datetime,
    date_to_utc: datetime,
    report_ids: Sequence[str] = DEFAULT_LABEL_REPORT_IDS,
    client: httpx.AsyncClient | None = None,
    access_token: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch label report archive rows for a UTC half-open time window."""

    _require_settings(settings, (("ifs_base_url", "IFS_BASE_URL"),))

    close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30.0)
    try:
        token = access_token or await obtain_access_token(settings, client=http_client)
        headers = {"Authorization": f"Bearer {token}"}
        url = _projection_url(settings, "ReportArchive.svc/ArchiveSet")
        return await _get_all(
            http_client,
            url,
            endpoint_category="report-archive-labels",
            headers=headers,
            params={
                "$filter": _archive_time_filter(
                    date_from_utc,
                    date_to_utc,
                    report_ids,
                ),
                "$select": ",".join(ARCHIVE_SELECT_FIELDS),
                "$orderby": "ExecTime asc,ResultKey asc",
                "$top": "1000",
            },
        )
    finally:
        if close_client:
            await http_client.aclose()


async def fetch_simsek_palet_etiketi_archive_rows(
    settings: Settings,
    *,
    client: httpx.AsyncClient | None = None,
    access_token: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch ReportArchive rows for SIMSEK_PALET_ETIKETI_REP."""

    _require_settings(settings, (("ifs_base_url", "IFS_BASE_URL"),))

    close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30.0)
    try:
        token = access_token or await obtain_access_token(settings, client=http_client)
        headers = {"Authorization": f"Bearer {token}"}
        url = _projection_url(settings, "ReportArchive.svc/ArchiveSet")
        return await _get_all(
            http_client,
            url,
            endpoint_category="simsek-palet-etiketi-archive-rows",
            headers=headers,
            params={
                "$filter": (
                    f"ReportId eq {_odata_string(SIMSEK_PALET_ETIKETI_REPORT_ID)}"
                ),
                "$select": ",".join(ARCHIVE_SELECT_FIELDS),
                "$top": "1000",
            },
        )
    finally:
        if close_client:
            await http_client.aclose()


async def fetch_archive_document_rows(
    settings: Settings,
    result_key: Any,
    *,
    client: httpx.AsyncClient | None = None,
    access_token: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch archive document metadata for a result key."""

    _require_settings(settings, (("ifs_base_url", "IFS_BASE_URL"),))

    close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30.0)
    try:
        token = access_token or await obtain_access_token(settings, client=http_client)
        headers = {"Authorization": f"Bearer {token}"}
        url = _projection_url(settings, "ReportArchive.svc/ArchiveDocumentSet")
        return await _get_all(
            http_client,
            url,
            endpoint_category="report-archive-documents",
            headers=headers,
            params={
                "$filter": f"ResultKey eq {result_key}",
                "$select": ",".join(ARCHIVE_DOCUMENT_SELECT_FIELDS),
                "$top": "1000",
            },
        )
    finally:
        if close_client:
            await http_client.aclose()


async def fetch_report_archive_xml(
    settings: Settings,
    result_key: Any,
    *,
    client: httpx.AsyncClient | None = None,
    access_token: str | None = None,
) -> str:
    """Read report XML from ReportArchive GetXml + XmlVirtualset FileData."""

    _require_settings(settings, (("ifs_base_url", "IFS_BASE_URL"),))

    close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30.0)
    try:
        token = access_token or await obtain_access_token(settings, client=http_client)
        headers = {"Authorization": f"Bearer {token}"}
        action_url = _projection_url(settings, "ReportArchive.svc/GetXml")
        payload = await _post_json_action(
            http_client,
            action_url,
            endpoint_category="report-archive-get-xml",
            headers=headers,
            json_body={"ResultKey": result_key},
        )
        objkey = str(payload.get("value") or "").strip()
        if not objkey:
            raise IFSClientError(
                "IFS report-archive-get-xml response did not include value",
                endpoint_category="report-archive-get-xml",
            )
        file_url = _projection_url(
            settings,
            f"ReportArchive.svc/XmlVirtualset(Objkey={_odata_key_string(objkey)})/FileData",
        )
        content = await _get_file_data_with_retry(
            http_client,
            file_url,
            endpoint_category="report-archive-xml-file",
            headers=headers,
        )
        return _decode_xml_bytes(content)
    finally:
        if close_client:
            await http_client.aclose()


def _archive_result_key(row: Mapping[str, Any]) -> Any:
    result_key = row.get("ResultKey")
    if result_key is None or str(result_key).strip() == "":
        raise IFSClientError("ReportArchive ArchiveSet row did not include ResultKey")
    return result_key


def _xml_local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    if ":" in tag:
        return tag.rsplit(":", 1)[-1]
    return tag


def parse_simsek_pallet_label_xml(xml_text: bytes | str) -> dict[str, str | None]:
    """Parse the confirmed SIMSEK_PALET_ETIKETI_REP XML payload."""

    if isinstance(xml_text, bytes):
        xml_text = _decode_xml_bytes(xml_text)

    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        raise IFSClientError(
            "IFS label XML was not valid XML",
            endpoint_category="label-archive-xml-parse",
        ) from exc

    values: dict[str, str | None] = {
        output_name: None for output_name in SIMSEK_LABEL_XML_FIELDS.values()
    }
    for element in root.iter():
        name = _xml_local_name(element.tag).upper()
        if name not in SIMSEK_LABEL_XML_FIELDS:
            continue
        text = "".join(element.itertext()).strip()
        values[SIMSEK_LABEL_XML_FIELDS[name]] = text or None

    return values


def parse_simsek_palet_etiketi_rep_xml(
    xml_text: bytes | str,
) -> dict[str, str | None]:
    return parse_simsek_pallet_label_xml(xml_text)


async def fetch_simsek_palet_etiketi_archive_labels(
    settings: Settings,
    *,
    client: httpx.AsyncClient | None = None,
    access_token: str | None = None,
    concurrency: int = LABEL_ARCHIVE_CONCURRENCY,
) -> list[dict[str, str | None]]:
    """Fetch SIMSEK_PALET_ETIKETI_REP archives and parse their XML label fields."""

    close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30.0)
    try:
        token = access_token or await obtain_access_token(settings, client=http_client)
        archive_rows = await fetch_simsek_palet_etiketi_archive_rows(
            settings,
            client=http_client,
            access_token=token,
        )

        async def parse_row(row: Mapping[str, Any]) -> dict[str, str | None]:
            xml_text = await fetch_report_archive_xml(
                settings,
                _archive_result_key(row),
                client=http_client,
                access_token=token,
            )
            return parse_simsek_palet_etiketi_rep_xml(xml_text)

        return await _gather_limited(
            archive_rows,
            parse_row,
            concurrency=concurrency,
        )
    finally:
        if close_client:
            await http_client.aclose()


async def fetch_label_archive_event_rows(
    settings: Settings,
    *,
    date_from_utc: datetime,
    date_to_utc: datetime,
    report_ids: Sequence[str] = DEFAULT_LABEL_REPORT_IDS,
    client: httpx.AsyncClient | None = None,
    access_token: str | None = None,
    concurrency: int = LABEL_ARCHIVE_CONCURRENCY,
) -> list[dict[str, Any]]:
    """Fetch archive rows and attach parsed label XML fields."""

    close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30.0)
    try:
        token = access_token or await obtain_access_token(settings, client=http_client)
        archive_rows = await fetch_report_archive_label_rows(
            settings,
            date_from_utc=date_from_utc,
            date_to_utc=date_to_utc,
            report_ids=report_ids,
            client=http_client,
            access_token=token,
        )

        async def enrich(row: Mapping[str, Any]) -> dict[str, Any]:
            result_key = row.get("ResultKey")
            event = dict(row)
            xml_text = await fetch_report_archive_xml(
                settings,
                result_key,
                client=http_client,
                access_token=token,
            )
            event["raw_xml"] = xml_text
            event.update(parse_simsek_pallet_label_xml(xml_text))
            return event

        return await _gather_limited(
            archive_rows,
            enrich,
            concurrency=concurrency,
        )
    finally:
        if close_client:
            await http_client.aclose()


async def fetch_u1_hm02_stock(
    settings: Settings,
    *,
    client: httpx.AsyncClient | None = None,
    access_token: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch available configured material-prefix stock rows in U1."""

    _require_settings(
        settings,
        (
            ("ifs_base_url", "IFS_BASE_URL"),
            ("ifs_contract", "IFS_CONTRACT"),
            ("ifs_u1_location", "IFS_U1_LOCATION"),
        ),
    )

    close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30.0)
    try:
        token = access_token or await obtain_access_token(settings, client=http_client)
        headers = {"Authorization": f"Bearer {token}"}
        url = _projection_url(
            settings,
            "InventoryPartInStockHandling.svc/InventoryPartInStockSet",
        )
        params = {
            "$filter": (
                f"Contract eq {_odata_string(settings.ifs_contract)} "
                f"and {_part_no_prefix_filter(settings)} "
                f"and LocationNo eq {_odata_string(settings.ifs_u1_location)} "
                "and AvailableQty gt 0"
            ),
            "$select": ",".join(STOCK_SELECT_FIELDS),
            "$expand": "PartNoRef($select=Description)",
            "$top": "1000",
        }
        return await _get_all(
            http_client,
            url,
            endpoint_category="u1-hm02-stock",
            headers=headers,
            params=params,
        )
    finally:
        if close_client:
            await http_client.aclose()


async def fetch_pet_ongoing_operations(
    settings: Settings,
    *,
    client: httpx.AsyncClient | None = None,
    access_token: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch ongoing operations from the configured PET dispatch list."""

    _require_settings(
        settings,
        (
            ("ifs_base_url", "IFS_BASE_URL"),
            ("ifs_contract", "IFS_CONTRACT"),
            ("ifs_company_id", "IFS_COMPANY_ID"),
            ("ifs_dispatch_filter_id", "IFS_DISPATCH_FILTER_ID"),
        ),
    )

    close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30.0)
    try:
        token = access_token or await obtain_access_token(settings, client=http_client)
        headers = {"Authorization": f"Bearer {token}"}
        url = _projection_url(settings, _pet_operations_path(settings))
        params = {
            "$select": ",".join(OPERATION_SELECT_FIELDS),
            "$top": "1000",
        }
        return await _get_all(
            http_client,
            url,
            endpoint_category="pet-ongoing-operations",
            headers=headers,
            params=params,
        )
    finally:
        if close_client:
            await http_client.aclose()


async def fetch_operation_hm02_materials(
    settings: Settings,
    operation: Mapping[str, Any],
    *,
    client: httpx.AsyncClient | None = None,
    access_token: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch configured material-prefix lines for one dispatch-list operation."""

    _require_settings(
        settings,
        (
            ("ifs_base_url", "IFS_BASE_URL"),
        ),
    )

    close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30.0)
    try:
        token = access_token or await obtain_access_token(settings, client=http_client)
        headers = {"Authorization": f"Bearer {token}"}
        url = _projection_url(settings, _operation_materials_path(operation))
        params = {
            "$filter": _part_no_prefix_filter(settings),
            "$select": ",".join(MATERIAL_SELECT_FIELDS),
            "$top": "1000",
        }
        return await _get_all(
            http_client,
            url,
            endpoint_category="operation-hm02-materials",
            headers=headers,
            params=params,
        )
    finally:
        if close_client:
            await http_client.aclose()


def used_hm02_part_numbers(materials: Sequence[Mapping[str, Any]]) -> set[str]:
    return {
        part_no
        for material in materials
        if (part_no := str(material.get("PartNo") or "").strip())
    }


def return_candidate_stock_rows(
    stock_rows: Sequence[Mapping[str, Any]],
    used_parts: set[str],
) -> list[Mapping[str, Any]]:
    candidates = [
        row
        for row in stock_rows
        if str(row.get("PartNo") or "").strip() not in used_parts
    ]
    return sorted(candidates, key=lambda row: str(row.get("PartNo") or "").strip())


def _identity_value(value: Any) -> str:
    return str(value or "").strip()


def _deduplicated_rows(
    rows: Sequence[Mapping[str, Any]],
    key_fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    deduplicated: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, ...]] = set()
    for row in rows:
        key = tuple(_identity_value(row.get(field_name)) for field_name in key_fields)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduplicated.append(dict(row))
    return deduplicated


def _deduplicated_operations(
    operations: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return _deduplicated_rows(
        operations,
        ("OrderNo", "ReleaseNo", "SequenceNo", "OperationNo"),
    )


def _deduplicated_materials(
    materials: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return _deduplicated_rows(
        materials,
        ("OrderNo", "ReleaseNo", "SequenceNo", "OperationNo", "LineItemNo", "PartNo"),
    )


async def _gather_limited(
    items: Sequence[Any],
    worker: Any,
    *,
    concurrency: int,
) -> list[Any]:
    semaphore = asyncio.Semaphore(concurrency)

    async def run(item: Any) -> Any:
        async with semaphore:
            return await worker(item)

    if not items:
        return []
    return list(await asyncio.gather(*(run(item) for item in items)))


async def _fetch_hm02_materials_for_operations(
    settings: Settings,
    operations: Sequence[Mapping[str, Any]],
    *,
    client: httpx.AsyncClient,
    access_token: str,
    concurrency: int = PLANNING_IFS_CONCURRENCY,
) -> list[dict[str, Any]]:
    async def fetch_materials(operation: Mapping[str, Any]) -> list[dict[str, Any]]:
        return await fetch_operation_hm02_materials(
            settings,
            operation,
            client=client,
            access_token=access_token,
        )

    material_groups = await _gather_limited(
        list(operations),
        fetch_materials,
        concurrency=concurrency,
    )
    materials = [
        material
        for group in material_groups
        for material in group
        if str(material.get("PartNo") or "").strip()
    ]
    return _deduplicated_materials(materials)


async def fetch_used_hm02_materials(
    settings: Settings,
    *,
    client: httpx.AsyncClient | None = None,
    access_token: str | None = None,
) -> dict[str, Any]:
    """Fetch all active PET operation materials and build the used part set."""

    close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30.0)
    try:
        token = access_token or await obtain_access_token(settings, client=http_client)
        operations = await fetch_pet_ongoing_operations(
            settings,
            client=http_client,
            access_token=token,
        )
        operations = _deduplicated_operations(operations)
        used_materials = await _fetch_hm02_materials_for_operations(
            settings,
            operations,
            client=http_client,
            access_token=token,
        )

        used_parts = sorted(used_hm02_part_numbers(used_materials))
        return {
            "operation_count": len(operations),
            "used_material_count": len(used_materials),
            "used_part_count": len(used_parts),
            "used_parts": used_parts,
            "used_hm02_part_count": len(used_parts),
            "used_hm02_parts": used_parts,
            "used_materials": used_materials,
        }
    finally:
        if close_client:
            await http_client.aclose()


async def fetch_shop_order_operations(
    settings: Settings,
    order_no: str,
    *,
    client: httpx.AsyncClient | None = None,
    access_token: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch dispatch-list operations for one scheduled shop order."""

    _require_settings(
        settings,
        (
            ("ifs_base_url", "IFS_BASE_URL"),
            ("ifs_contract", "IFS_CONTRACT"),
            ("ifs_company_id", "IFS_COMPANY_ID"),
        ),
    )

    order_no = str(order_no or "").strip()
    if not order_no:
        return []

    close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30.0)
    try:
        token = access_token or await obtain_access_token(settings, client=http_client)
        headers = {"Authorization": f"Bearer {token}"}
        url = _projection_url(settings, _shop_order_operations_path(settings, order_no))
        params = {
            "$select": ",".join(OPERATION_SELECT_FIELDS),
            "$top": "1000",
        }
        return await _get_all(
            http_client,
            url,
            endpoint_category="planning-shop-order-operations",
            headers=headers,
            params=params,
        )
    finally:
        if close_client:
            await http_client.aclose()


async def fetch_shop_order_operation_actual_rows(
    settings: Settings,
    order_numbers: Sequence[str],
    *,
    client: httpx.AsyncClient | None = None,
    access_token: str | None = None,
    concurrency: int = PLANNING_IFS_CONCURRENCY,
) -> list[dict[str, Any]]:
    """Fetch full shop-order operation rows for production-loss actual timing.

    The production-loss report intentionally avoids a restrictive $select because
    IFS actual timing field names vary between versions and projections.
    """

    cleaned_order_numbers = list(
        dict.fromkeys(
            order_no
            for value in order_numbers
            if (order_no := str(value or "").strip()) and order_no != "0"
        )
    )

    _require_settings(
        settings,
        (
            ("ifs_base_url", "IFS_BASE_URL"),
            ("ifs_contract", "IFS_CONTRACT"),
            ("ifs_company_id", "IFS_COMPANY_ID"),
        ),
    )

    close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30.0)
    try:
        token = access_token or await obtain_access_token(settings, client=http_client)
        headers = {"Authorization": f"Bearer {token}"}

        async def fetch_order(order_no: str) -> list[dict[str, Any]]:
            url = _projection_url(settings, _shop_order_operations_path(settings, order_no))
            return await _get_all(
                http_client,
                url,
                endpoint_category="production-loss-operation-actuals",
                headers=headers,
                params={"$top": "1000"},
            )

        operation_groups = await _gather_limited(
            cleaned_order_numbers,
            fetch_order,
            concurrency=concurrency,
        )
        return _deduplicated_operations(
            [operation for group in operation_groups for operation in group]
        )
    finally:
        if close_client:
            await http_client.aclose()


async def fetch_operation_history_rows(
    settings: Settings,
    date_from: Any,
    date_to: Any,
    product_prefixes: Sequence[str] = DEFAULT_OPERATION_HISTORY_PRODUCT_PREFIXES,
    *,
    client: httpx.AsyncClient | None = None,
    access_token: str | None = None,
    page_size: int = 5000,
    window_padding_days: int = 1,
) -> list[dict[str, Any]]:
    """Fetch production operation history rows for caller-side local filtering.

    Reference_OperationHistory has been observed rejecting exact comparison
    filters in this IFS environment, so this fetches DateApplied month buckets
    and leaves exact TimeOfProduction filtering to the report service.
    """

    _require_settings(
        settings,
        (
            ("ifs_base_url", "IFS_BASE_URL"),
            ("ifs_contract", "IFS_CONTRACT"),
        ),
    )

    close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30.0)
    try:
        token = access_token or await obtain_access_token(settings, client=http_client)
        headers = {"Authorization": f"Bearer {token}"}
        url = _projection_url(
            settings,
            "ShopFloorWorkbenchHandling.svc/Reference_OperationHistory",
        )
        rows: list[dict[str, Any]] = []
        seen_transaction_ids: set[str] = set()
        for month_prefix in _operation_history_month_prefixes(
            settings,
            date_from,
            date_to,
            padding_days=window_padding_days,
        ):
            rows.extend(
                await _get_paged_by_top_skip(
                    http_client,
                    url,
                    endpoint_category="production-loss-operation-history",
                    headers=headers,
                    params={
                        "$filter": _operation_history_filter(
                            settings,
                            month_prefix,
                            product_prefixes,
                        ),
                        "$select": ",".join(OPERATION_HISTORY_SELECT_FIELDS),
                        "$orderby": "TransactionId asc",
                        "$count": "true",
                    },
                    page_size=page_size,
                    dedupe_field="TransactionId",
                    seen_values=seen_transaction_ids,
                )
            )
        return rows
    finally:
        if close_client:
            await http_client.aclose()


async def fetch_inventory_part_descriptions(
    settings: Settings,
    part_numbers: Sequence[str],
    *,
    client: httpx.AsyncClient | None = None,
    access_token: str | None = None,
    page_size: int = 1000,
    batch_size: int = 50,
) -> dict[str, str]:
    """Fetch InventoryPart descriptions keyed by PartNo."""

    cleaned_part_numbers = list(
        dict.fromkeys(
            part_no
            for value in part_numbers
            if (part_no := str(value or "").strip())
        )
    )
    if not cleaned_part_numbers:
        return {}

    _require_settings(
        settings,
        (
            ("ifs_base_url", "IFS_BASE_URL"),
            ("ifs_contract", "IFS_CONTRACT"),
        ),
    )

    close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30.0)
    try:
        token = access_token or await obtain_access_token(settings, client=http_client)
        headers = {"Authorization": f"Bearer {token}"}
        url = _projection_url(
            settings,
            "InventoryPartInStockHandling.svc/Reference_InventoryPart",
        )
        descriptions: dict[str, str] = {}
        for batch in _batched(cleaned_part_numbers, batch_size):
            part_filter = _part_no_equals_filter(batch)
            if not part_filter:
                continue
            rows = await _get_paged_by_top_skip(
                http_client,
                url,
                endpoint_category="inventory-part-descriptions",
                headers=headers,
                params={
                    "$filter": (
                        f"Contract eq {_odata_string(settings.ifs_contract)} "
                        f"and {part_filter}"
                    ),
                    "$select": ",".join(INVENTORY_PART_SELECT_FIELDS),
                    "$orderby": "PartNo asc",
                    "$count": "true",
                },
                page_size=page_size,
                dedupe_field="PartNo",
            )
            for row in rows:
                part_no = str(row.get("PartNo") or "").strip()
                description = str(row.get("Description") or "").strip()
                if part_no and description:
                    descriptions[part_no] = description
        return descriptions
    finally:
        if close_client:
            await http_client.aclose()


async def fetch_planning_used_hm02_materials(
    settings: Settings,
    order_numbers: Sequence[str],
    *,
    client: httpx.AsyncClient | None = None,
    access_token: str | None = None,
    concurrency: int = PLANNING_IFS_CONCURRENCY,
) -> dict[str, Any]:
    """Fetch configured material-prefix usage for visible planning shop orders."""

    cleaned_order_numbers = list(
        dict.fromkeys(
            order_no
            for value in order_numbers
            if (order_no := str(value or "").strip()) and order_no != "0"
        )
    )

    close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30.0)
    try:
        token = access_token or await obtain_access_token(settings, client=http_client)

        async def fetch_order_operations(order_no: str) -> list[dict[str, Any]]:
            return await fetch_shop_order_operations(
                settings,
                order_no,
                client=http_client,
                access_token=token,
            )

        operation_groups = await _gather_limited(
            cleaned_order_numbers,
            fetch_order_operations,
            concurrency=concurrency,
        )
        operations = _deduplicated_operations(
            [
                operation
                for group in operation_groups
                for operation in group
            ]
        )
        used_materials = await _fetch_hm02_materials_for_operations(
            settings,
            operations,
            client=http_client,
            access_token=token,
            concurrency=concurrency,
        )
        used_parts = sorted(used_hm02_part_numbers(used_materials))
        return {
            "planning_order_count": len(cleaned_order_numbers),
            "planning_operation_count": len(operations),
            "planning_used_material_count": len(used_materials),
            "planning_used_part_count": len(used_parts),
            "planning_used_parts": used_parts,
            "planning_used_hm02_part_count": len(used_parts),
            "planning_used_hm02_parts": used_parts,
            "planning_used_materials": used_materials,
        }
    finally:
        if close_client:
            await http_client.aclose()


async def find_u1_return_candidates(
    settings: Settings,
    *,
    client: httpx.AsyncClient | None = None,
    access_token: str | None = None,
) -> dict[str, Any]:
    """Find U1 configured-prefix stock rows not used by active or planned operations."""

    planning_path = resolve_planning_workbook(
        settings.production_planning_dir,
        settings.production_planning_path,
    )
    planning_orders = read_visible_planning_orders(planning_path)
    planning_order_numbers = [order.order_no for order in planning_orders]
    close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30.0)
    try:
        token = access_token or await obtain_access_token(settings, client=http_client)
        stock_rows, active_summary, planning_summary = await asyncio.gather(
            fetch_u1_hm02_stock(
                settings,
                client=http_client,
                access_token=token,
            ),
            fetch_used_hm02_materials(
                settings,
                client=http_client,
                access_token=token,
            ),
            fetch_planning_used_hm02_materials(
                settings,
                planning_order_numbers,
                client=http_client,
                access_token=token,
            ),
        )
        used_materials = _deduplicated_materials(
            [
                *active_summary["used_materials"],
                *planning_summary["planning_used_materials"],
            ]
        )
        used_hm02_parts = sorted(used_hm02_part_numbers(used_materials))
        used_parts = set(used_hm02_parts)
        candidates = list(return_candidate_stock_rows(stock_rows, used_parts))
        active_used_part_count = active_summary.get(
            "used_part_count",
            active_summary["used_hm02_part_count"],
        )
        planning_used_part_count = planning_summary.get(
            "planning_used_part_count",
            planning_summary["planning_used_hm02_part_count"],
        )
        return {
            "generated_at": _generated_at(settings),
            "planning_source_path": str(planning_path),
            "planning_source_name": planning_path.name,
            "stock_count": len(stock_rows),
            "operation_count": active_summary["operation_count"],
            "active_used_material_count": active_summary["used_material_count"],
            "active_used_part_count": active_used_part_count,
            "active_used_hm02_part_count": active_summary["used_hm02_part_count"],
            "planning_order_count": planning_summary["planning_order_count"],
            "planning_operation_count": planning_summary["planning_operation_count"],
            "planning_used_material_count": planning_summary[
                "planning_used_material_count"
            ],
            "planning_used_part_count": planning_used_part_count,
            "planning_used_hm02_part_count": planning_summary[
                "planning_used_hm02_part_count"
            ],
            "used_material_count": len(used_materials),
            "used_part_count": len(used_hm02_parts),
            "used_hm02_part_count": len(used_hm02_parts),
            "return_candidate_count": len(candidates),
            "return_candidates": candidates,
            "used_parts": used_hm02_parts,
            "used_hm02_parts": used_hm02_parts,
            "used_materials": used_materials,
        }
    finally:
        if close_client:
            await http_client.aclose()


def serialize_stock_row(row: Mapping[str, Any]) -> dict[str, Any]:
    payload = {
        output_name: row.get(source_name)
        for source_name, output_name in STOCK_FIELD_MAP.items()
    }
    part_ref = row.get("PartNoRef")
    payload["material_name"] = (
        part_ref.get("Description") if isinstance(part_ref, Mapping) else None
    )
    return payload


def serialize_operation_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        output_name: row.get(source_name)
        for source_name, output_name in OPERATION_FIELD_MAP.items()
    }


def serialize_material_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        output_name: row.get(source_name)
        for source_name, output_name in MATERIAL_FIELD_MAP.items()
    }
