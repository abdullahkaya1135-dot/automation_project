# IFS Integration Implementation Guide

This document captures the confirmed IFS Cloud API integration needed to replace the
manual Excel export process for:

1. `Malzeme Stok Bilgisi` stock in location `U1`
2. `Tezgah Yukleme Listesi` active machine/order material usage

Goal:

```text
Find HM-02, HM-03, and HM-04 material stock that is physically/logically in U1, has available stock,
but is not currently used by any active machine/order in the PET dispatch list.
```

The final result is a list of U1 stock rows that should be returned to inventory.

## Current Implementation Status

The implementation has moved into the feature/integration layout:

```text
app/integrations/ifs/client.py      OAuth, OData requests, pagination, and comparison logic
app/features/ifs/api.py             Authenticated `/api/ifs/*` routes
app/features/ifs_checks/service.py  WhatsApp status and missing-production checks
app/features/bootstrap/api.py       Bootstrap-time IFS shop-order loading
```

The older import aliases have been retired; code and docs should use the paths
above.

## Confirmed IFS Environment

Base URL:

```text
https://ifs.simsekplastik.com
```

Projection API root:

```text
https://ifs.simsekplastik.com/main/ifsapplications/projection/v1
```

Confirmed working projections:

```text
InventoryPartInStockHandling
ShopFloorWorkbenchHandling
```

Confirmed dispatch filter:

```text
Contract: S01
CompanyId: C01
DispListFilterId: PET
DispListFilterDesc: Salon 4
Selection: Ongoing
DispatchRule: AsScheduled
WorkCenterCode: InternalWorkCenter
```

## Required IFS Permissions

Create or use a permission set for the integration app.

Grant these projections with read access:

```text
InventoryPartInStockHandling
ShopFloorWorkbenchHandling
```

The following child data was confirmed readable through `ShopFloorWorkbenchHandling`:

```text
DispatchListOperationSet(...)/OperationMaterialArray
```

These were tested and returned empty for the sample operation:

```text
DaComponentArray
ShopMaterialAllocGuideArray
```

They are not needed for the current configured raw-material prefix comparison.

Assign the permission set to the user used by the integration. For production, use a
dedicated integration/service user instead of a personal user account.

After changing permissions, the user/client should log in again or obtain a fresh
OAuth token before testing.

## Authentication Plan

Use OAuth for the app integration.

Current setup:

```text
Normal IFS user credentials
Dedicated IAM client
OAuth password grant
Bearer token on every IFS projection request
Read-only permission set assigned to the IFS user
```

Do not store browser cookies or HAR tokens in the app.

Suggested `.env` values:

```text
IFS_BASE_URL=https://ifs.simsekplastik.com
IFS_TOKEN_URL=https://ifs.simsekplastik.com/auth/realms/prod/protocol/openid-connect/token
IFS_CLIENT_ID=<store only in .env or a secret store; do not commit>
IFS_CLIENT_SECRET=<optional; store only in .env or a secret store; do not commit>
IFS_USERNAME=<store only in .env or a secret store; do not commit>
IFS_PASSWORD=<store only in .env or a secret store; do not commit>
IFS_CONTRACT=S01
IFS_COMPANY_ID=C01
IFS_DISPATCH_FILTER_ID=PET
IFS_PART_PREFIXES=HM-02,HM-03,HM-04
IFS_PART_PREFIX=HM-02
IFS_U1_LOCATION=U1
IFS_PRODUCTION_LOSS_QUERY_START_DATE=2026-06-01
```

Confirm the exact client ID spelling and case in `IAM Clients`. If the IFS
record uses normal Latin `I` instead of Turkish dotted `İ`, copy the value from
IFS exactly.

The client secret was intentionally not written into this Markdown document.
Store it only in local configuration such as `.env`, and keep `.env` out of
version control.

The OpenID discovery document was confirmed at:

```text
https://ifs.simsekplastik.com/auth/realms/prod/.well-known/openid-configuration
```

Confirmed OAuth details:
```text
issuer=https://ifs.simsekplastik.com/auth/realms/prod
authorization_endpoint=https://ifs.simsekplastik.com/auth/realms/prod/protocol/openid-connect/auth
token_endpoint=https://ifs.simsekplastik.com/auth/realms/prod/protocol/openid-connect/token
password grant is used by this app
client_secret_basic and client_secret_post are supported
```

Use `httpx` for HTTP calls. It already exists in `requirements.txt`.

## Data Source 1: U1 HM-02/HM-03/HM-04 Stock

Projection:

```text
InventoryPartInStockHandling.svc
```

Entity set:

```text
InventoryPartInStockSet
```

Purpose:

```text
Read all configured raw-material prefixes in U1 where AvailableQty > 0.
```

Confirmed working URL:

```text
https://ifs.simsekplastik.com/main/ifsapplications/projection/v1/InventoryPartInStockHandling.svc/InventoryPartInStockSet?$filter=Contract eq 'S01' and (startswith(PartNo,'HM-02') or startswith(PartNo,'HM-03') or startswith(PartNo,'HM-04')) and LocationNo eq 'U1' and AvailableQty gt 0&$select=Contract,PartNo,LocationNo,AvailableQty,QtyOnhand,UoM,LotBatchNo,ObjId&$top=5
```

Recommended query:

```text
GET /main/ifsapplications/projection/v1/InventoryPartInStockHandling.svc/InventoryPartInStockSet
```

Query parameters:

```text
$filter=Contract eq 'S01' and (startswith(PartNo,'HM-02') or startswith(PartNo,'HM-03') or startswith(PartNo,'HM-04')) and LocationNo eq 'U1' and AvailableQty gt 0
$select=Contract,PartNo,LocationNo,AvailableQty,QtyOnhand,UoM,LotBatchNo,ObjId,ConfigurationId,SerialNo,EngChgLevel,WaivDevRejNo,ActivitySeq,HandlingUnitId
$top=1000
```

Optional description expansion:

```text
$expand=PartNoRef($select=Description)
```

Use `LocationNo eq 'U1'`, not `startswith(LocationNo,'U1')`, unless locations like
`U10` should also be included.

Important fields:

```text
Contract
PartNo
LocationNo
LotBatchNo
AvailableQty
QtyOnhand
UoM
ObjId
ConfigurationId
SerialNo
EngChgLevel
WaivDevRejNo
ActivitySeq
HandlingUnitId
```

`PartNo` is the material code to compare against machine usage.

Stock rows are lot/batch-specific. There can be multiple rows for the same `PartNo`.
The comparison should usually keep all rows for an unused `PartNo`, not aggregate
them away, because return-to-inventory actions may require the lot/batch and `ObjId`.

## Data Source 2: PET Active And DURAN Stopped Machine Operations

Projection:

```text
ShopFloorWorkbenchHandling.svc
```

Function:

```text
GetOperations(...)
```

Purpose:

```text
Read active/ongoing shop floor operations from the PET predefined dispatch list.
```

First confirm the predefined filter:

```text
GET /main/ifsapplications/projection/v1/ShopFloorWorkbenchHandling.svc/Reference_DispatchListFilter
```

Query:

```text
$filter=Contract eq 'S01' and DispListFilterId eq 'PET'
$top=2
```

Confirmed response values:

```text
Contract: S01
DispListFilterId: PET
DispListFilterDesc: Salon 4
Selection: Ongoing
DispatchRule: AsScheduled
WorkCenterCode: InternalWorkCenter
MyAssignedOper: false
BaseIntervalOn: PlannedFinishTime
```

Confirmed working `GetOperations` URL:

```text
https://ifs.simsekplastik.com/main/ifsapplications/projection/v1/ShopFloorWorkbenchHandling.svc/GetOperations(Contract='S01',FilterBy=IfsApp.ShopFloorWorkbenchHandling.DispatchListFilterBy'PredefinedFilter',DispListFilterId='PET',Selection=IfsApp.ShopFloorWorkbenchHandling.DisListFilterSelection'Ongoing',DispatchRule=IfsApp.ShopFloorWorkbenchHandling.DispatchRule'AsScheduled',DepartmentList=null,WorkCenterList=null,WorkCenterCode=IfsApp.ShopFloorWorkbenchHandling.WorkCenterCodeShopFloor'InternalWorkCenter',ProductionLineList=null,ResourceList=null,LaborClassList=null,DateFrom=null,DateTo=null,BaseIntervalOn=IfsApp.ShopFloorWorkbenchHandling.DispListIntervalBasis'PlannedFinishTime',MyAssignedOper=false,BarcodeId=null,OrderNo=null,ReleaseNo=null,SequenceNo=null,ProgramId=null,ProjectId=null,SubProjectId=null,ActivityNo=null,ActivitySeq=null,CompanyId='C01',EmployeeId=null,TeamId=null)?$select=OrderNo,ReleaseNo,SequenceNo,OperationNo,Contract,WorkCenterNo,PartNo,PartNoDesc,PreferredResourceId,OperationNoDesc,RemainingQty&$top=5
```

Recommended selected fields:

```text
OrderNo
ReleaseNo
SequenceNo
OperationNo
Contract
WorkCenterNo
PartNo
PartNoDesc
PreferredResourceId
OperationNoDesc
RemainingQty
```

Important fields:

```text
OrderNo          = shop order number
ReleaseNo        = release, often "*"
SequenceNo       = sequence, often "*"
OperationNo      = operation number
WorkCenterNo     = work center/machine area
PreferredResourceId = preferred machine/resource id
PartNo           = produced product
PartNoDesc       = produced product description
RemainingQty     = remaining operation quantity
```

The `GetOperations` response does not directly contain raw-material/component
codes. Use each operation's keys to call `OperationMaterialArray`.

DURAN/stopped operations use the same projection, but with the stopped dispatch
list and an explicit IFS date window.

Window query:

```text
GetDatesForInterval(-30, 30)
```

Use the returned `DateFrom` and `DateTo` values in the stopped operation query:

```text
DispListFilterId: DURUS
Selection: Interrupted
WorkCenterCode: InternalWorkCenter
DateFrom: <GetDatesForInterval DateFrom>
DateTo: <GetDatesForInterval DateTo>
```

The stopped `GetOperations` query should otherwise use the same contract,
company, dispatch rule, interval basis, selected fields, and pagination behavior
as the ongoing PET operation query. Include these DURAN rows in the material
usage comparison before deciding that U1 stock is free to return.

## Data Source 3: HM-02/HM-03/HM-04 Materials Used By Operations

Projection:

```text
ShopFloorWorkbenchHandling.svc
```

Navigation entity:

```text
DispatchListOperationSet(...)/OperationMaterialArray
```

Purpose:

```text
For each active, DURAN stopped, or visible planning operation, read configured
raw-material/component lines.
```

Confirmed sample operation:

```text
OrderNo: 2615
ReleaseNo: *
SequenceNo: *
OperationNo: 10
```

Confirmed working URL:

```text
https://ifs.simsekplastik.com/main/ifsapplications/projection/v1/ShopFloorWorkbenchHandling.svc/DispatchListOperationSet(OrderNo='2615',ReleaseNo='%2A',SequenceNo='%2A',OperationNo=10)/OperationMaterialArray?$filter=(startswith(PartNo,'HM-02') or startswith(PartNo,'HM-03') or startswith(PartNo,'HM-04'))&$select=OrderNo,ReleaseNo,SequenceNo,LineItemNo,OperationNo,PartNo,IssueToLoc,QtyRequired,QtyAssigned,QtyIssued,QtyRemainingToReserve,QtyAvailable,PrintUnit,SoPartNo,Cf_Tercihedilenkaynak&$top=20
```

Important URL encoding detail:

```text
ReleaseNo='*'   -> ReleaseNo='%2A'
SequenceNo='*'  -> SequenceNo='%2A'
```

Recommended query per operation:

```text
GET /main/ifsapplications/projection/v1/ShopFloorWorkbenchHandling.svc/DispatchListOperationSet(OrderNo='<OrderNo>',ReleaseNo='<encoded ReleaseNo>',SequenceNo='<encoded SequenceNo>',OperationNo=<OperationNo>)/OperationMaterialArray
```

Query parameters:

```text
$filter=(startswith(PartNo,'HM-02') or startswith(PartNo,'HM-03') or startswith(PartNo,'HM-04'))
$select=OrderNo,ReleaseNo,SequenceNo,LineItemNo,OperationNo,PartNo,IssueToLoc,QtyRequired,QtyAssigned,QtyIssued,QtyRemainingToReserve,QtyAvailable,PrintUnit,SoPartNo,Cf_Tercihedilenkaynak
$top=1000
```

Confirmed sample result:

```text
OrderNo: 2615
ReleaseNo: *
SequenceNo: *
LineItemNo: 2
OperationNo: 10
PartNo: HM-02-01-01-525
IssueToLoc: U1
QtyRequired: 25.578
QtyAssigned: 0
QtyIssued: 0
QtyRemainingToReserve: 25.578
QtyAvailable: 100.72
PrintUnit: kg
SoPartNo: MM-PET0048-12-024Y-025
Cf_Tercihedilenkaynak: 135
```

Important fields:

```text
PartNo                 = configured raw-material/component code
IssueToLoc             = issue/source location, U1 in the confirmed sample
QtyRequired            = required material quantity
QtyRemainingToReserve  = remaining quantity to reserve
QtyAvailable           = available material quantity according to this material line
PrintUnit              = unit
SoPartNo               = produced product on the shop order
Cf_Tercihedilenkaynak  = preferred resource/machine id
OrderNo
OperationNo
LineItemNo
```

Use `PartNo` from `OperationMaterialArray` as the set of configured raw materials currently
used by active PET operations, DURAN stopped operations, or visible planning
workbook orders.

## Comparison Logic

High-level algorithm:

```text
1. Fetch all U1 HM-02/HM-03/HM-04 stock rows with AvailableQty > 0.
2. Fetch all ongoing PET operations.
3. Fetch DURAN stopped operations by calling GetDatesForInterval(-30, 30), then
   GetOperations with DispListFilterId='DURUS', Selection='Interrupted',
   WorkCenterCode='InternalWorkCenter', and the returned DateFrom/DateTo.
4. Read visible planning workbook orders and fetch their shop-order operations.
5. For each operation, fetch OperationMaterialArray filtered to the configured prefixes.
6. Build a set of used PartNo values from active, stopped, and planning material lines.
7. Return every U1 stock row whose PartNo is not in the used set.
```

Pseudo-code:

```python
stock_rows = fetch_u1_hm02_stock()
active_operations = fetch_pet_ongoing_operations()
date_window = fetch_get_dates_for_interval(-30, 30)
stopped_operations = fetch_pet_stopped_operations(
    disp_list_filter_id="DURUS",
    selection="Interrupted",
    date_from=date_window["DateFrom"],
    date_to=date_window["DateTo"],
)
planning_operations = fetch_visible_planning_order_operations()

used_parts = set()
material_usage = []

for operation in active_operations + stopped_operations + planning_operations:
    materials = fetch_hm02_operation_materials(operation)
    for material in materials:
        used_parts.add(material["PartNo"])
        material_usage.append({
            "part_no": material["PartNo"],
            "order_no": material["OrderNo"],
            "operation_no": material["OperationNo"],
            "machine": material.get("Cf_Tercihedilenkaynak"),
            "produced_part": material.get("SoPartNo"),
            "qty_required": material.get("QtyRequired"),
            "qty_remaining_to_reserve": material.get("QtyRemainingToReserve"),
        })

return_candidates = [
    row for row in stock_rows
    if row["PartNo"] not in used_parts
]
```

Recommended output shape:

```json
{
  "generated_at": "2026-06-09T00:00:00+03:00",
  "stock_count": 27,
  "operation_count": 31,
  "stopped_operation_count": 2,
  "stopped_used_material_count": 1,
  "stopped_used_part_count": 1,
  "stopped_used_hm02_part_count": 1,
  "used_hm02_part_count": 1,
  "return_candidate_count": 0,
  "return_candidates": [
    {
      "contract": "S01",
      "part_no": "HM-02-...",
      "location_no": "U1",
      "lot_batch_no": "...",
      "available_qty": 0,
      "qty_onhand": 0,
      "uom": "kg",
      "obj_id": "..."
    }
  ],
  "used_materials": [
    {
      "part_no": "HM-02-01-01-525",
      "order_no": "2615",
      "operation_no": 10,
      "machine": "135",
      "produced_part": "MM-PET0048-12-024Y-025",
      "qty_required": 25.578
    }
  ]
}
```

## Pagination

IFS OData responses can be paged.

Use one of these approaches:

1. Follow `@odata.nextLink` if present.
2. Otherwise use `$skip` and `$top`.

Recommended default:

```text
$top=1000
```

Loop until no `@odata.nextLink` is present or the returned `value` list is empty.

Pseudo-code:

```python
async def get_all(client, url, params):
    rows = []
    next_url = url
    next_params = params

    while next_url:
        response = await client.get(next_url, params=next_params)
        response.raise_for_status()
        payload = response.json()
        rows.extend(payload.get("value", []))

        next_url = payload.get("@odata.nextLink")
        next_params = None

    return rows
```

## Error Handling

Handle these cases explicitly:

```text
401 Unauthorized
```

Token missing, expired, or invalid.

```text
403 Forbidden
```

Permission set is missing the projection or the user/client did not get a fresh
session/token after permissions changed.

```text
404 Not Found
```

Wrong projection/entity/function path or malformed key.

```text
400 Bad Request
```

Usually malformed OData function parameters, invalid enum values, or incorrect
URL encoding for `*`.

```text
5xx
```

IFS/server-side issue. Retry with backoff for read calls.

Log the endpoint category, HTTP status, and response body snippet. Do not log
access tokens or client secrets.

## Current App Modules

IFS client logic lives in:

```text
app/integrations/ifs/client.py
```

Responsibilities:

```text
load IFS settings
obtain OAuth token
create authenticated httpx client
fetch stock rows
fetch PET operations
fetch DURAN stopped operations
fetch operation materials
compute return candidates
```

Current public functions include:

```python
async def fetch_u1_hm02_stock(settings) -> list[dict]:
    ...

async def fetch_pet_ongoing_operations(settings) -> list[dict]:
    ...

async def fetch_pet_stopped_operations(settings) -> list[dict]:
    ...

async def fetch_operation_hm02_materials(settings, operation) -> list[dict]:
    ...

async def find_u1_return_candidates(settings) -> dict:
    ...
```

IFS API routes live in:

```text
app/features/ifs/api.py
```

Implemented authenticated routes:

```text
GET /api/ifs/u1-hm02-stock
GET /api/ifs/pet-ongoing-operations
GET /api/ifs/used-hm02-materials
GET /api/ifs/u1-return-candidates
GET /api/ifs/missing-production-starts
GET /api/ifs/whatsapp-status-message
```

No standalone IFS diagnostics route is currently implemented. Keep ad hoc
diagnostic checks in authenticated developer tooling or tests, and do not expose
secrets in any diagnostic output.

## Implementation Notes For Existing App
The app calls `GetOperations` directly with a bearer token. It does not parse
saved browser payloads.

The `ShopOrderOption` model extracts live IFS operation fields:

```text
OrderNo
PreferredResourceId
WorkCenterNo
PartNoDesc
```

Map them as:

```text
OrderNo             -> order_no
PreferredResourceId -> resource_id
WorkCenterNo        -> work_center_no
PartNoDesc          -> part_description
```

The app only consumes the live IFS `PreferredResourceId` field.

## URL Builder Details

Build OData URLs with helper functions instead of string concatenation scattered
through the code.

Important:

```text
Single quotes must wrap OData string values.
The `*` value in entity keys should be URL encoded as `%2A`.
Query parameters should be URL encoded by httpx `params=...`.
```

Example key builder:

```python
from urllib.parse import quote

def odata_string(value: str) -> str:
    escaped = value.replace("'", "''")
    return f"'{quote(escaped, safe='')}'"
```

For this IFS key, the confirmed working representation is:

```text
ReleaseNo='%2A'
SequenceNo='%2A'
```

## Validation Checklist

Before merging the integration:

```text
[ ] OAuth token can be obtained without browser cookies.
[ ] Stock query returns U1 HM-02/HM-03/HM-04 rows.
[ ] Reference_DispatchListFilter returns PET / Salon 4.
[ ] GetOperations returns ongoing PET operations.
[ ] GetDatesForInterval(-30, 30) returns the DURAN stopped-operation date window.
[ ] GetOperations returns DURUS / Interrupted stopped operations with that date window.
[ ] OperationMaterialArray returns configured raw-material rows for at least one operation.
[ ] Pagination is handled for stock, operations, and materials.
[ ] Return-candidate comparison keeps lot/batch-level stock rows.
[ ] 401/403/400 errors produce clear messages.
[ ] Secrets are not logged.
[ ] Unit tests cover comparison logic.
[ ] Integration can be disabled or fails gracefully if IFS is unreachable.
```

## Minimal Unit Tests

Test comparison logic without calling IFS:

```python
def test_return_candidates_exclude_used_parts():
    stock_rows = [
        {"PartNo": "HM-02-A", "LotBatchNo": "L1"},
        {"PartNo": "HM-03-B", "LotBatchNo": "L2"},
        {"PartNo": "HM-04-C", "LotBatchNo": "L3"},
    ]
    used_parts = {"HM-02-A"}

    candidates = [row for row in stock_rows if row["PartNo"] not in used_parts]

    assert candidates == [
        {"PartNo": "HM-03-B", "LotBatchNo": "L2"},
        {"PartNo": "HM-04-C", "LotBatchNo": "L3"},
    ]
```

Test duplicate stock lots are retained:

```python
def test_unused_part_keeps_all_lots():
    stock_rows = [
        {"PartNo": "HM-03-B", "LotBatchNo": "L1"},
        {"PartNo": "HM-03-B", "LotBatchNo": "L2"},
    ]
    used_parts = set()

    candidates = [row for row in stock_rows if row["PartNo"] not in used_parts]

    assert len(candidates) == 2
```

## Official Documentation References

IFS API usage policy:

```text
https://docs.ifs.com/policy/APIUsageCloud.pdf
```

IFS REST/OData technical docs:

```text
https://docs.ifs.com/techdocs/Foundation1/050_development/024_integration/010_restful_odata/default.htm
```

IFS API Explorer:

```text
https://docs.ifs.com/techdocs/Foundation1/045_administration_aurena/240_integration/020_api_explorer/
```

IFS projection permissions:

```text
https://docs.ifs.com/techdocs/25r2/030_administration/010_security/020_permission_sets/004_permission_set_overview/010_projections/
```

IFS IAM clients:

```text
https://docs.ifs.com/techdocs/25R1/070_remote_deploy/400_installation_options/003_security/030_setup_iam_clients/
```
