# IFS Label-Based Production-Loss Workflow

This document defines the docs-only target model for measuring production loss from
IFS package labels. It does not change app code.

## Core Model

Use the IFS inventory part barcode label as the production unit:

```text
One valid label = one physical package.
PackageCount = COUNT(DISTINCT PackageLabelId)
ProducedQty = SUM(QtyPerPackage)
```

If the label record does not store actual package quantity, use:

```text
ProducedQty = COUNT(DISTINCT PackageLabelId) * StandardPackSize
```

Use the fallback only when the package size is uniform for the grouped
machine/product/shift and partial labels are excluded or corrected. If IFS stores
actual label quantity, `QtyPerPackage` is the authoritative quantity.

Production loss is then:

```text
ExpectedQty = planned runtime minutes * expected rate per minute
LossQty = ExpectedQty - ProducedQty
LossPercent = LossQty / ExpectedQty * 100
```

Negative `LossQty` means over-production or an expected-rate/shift mapping problem;
do not silently clamp it unless the reporting requirement explicitly says to hide
over-production.

## Public Source Status

Public IFS sources confirm the workflow concept but not every tenant field name.
Exact projection names, entity sets, action/function names, keys, enum literals,
and field names must be confirmed in the tenant with API Explorer, `$metadata`, or
`$openapi`.

Confirmed publicly:

- IFS Cloud exposes OData projection APIs and documents API classes through API
  Explorer/OpenAPI.
- IFS "Print Shop Order Barcode Labels" creates one Inventory Part Barcode
  Analysis line for each printed barcode label and uses Standard Pack Size to
  calculate label count.
- IFS MES docs list Shop Floor Connector APIs for operation reporting, receiving,
  operation info, and shop order operation information.
- IFS MES docs list `InventoryPartService` `GetPartInformation` and
  `ManufacturingPartService` `GetParts` for part/master-data integration.
- IFS Community posts identify `InventoryPartBarcodeRep`,
  `InventoryPartBarcode`, `ReportArchive`, `ArchiveDocumentSet`, `PdfArchiveSet`,
  and `ReceiveShopOrderHandling` behavior.

Tenant-confirm before implementation:

- `InventoryPartBarcodeRep.svc/VirtualOrderReports` request schema.
- `InventoryPartBarcode.svc` entity set name and label fields.
- `ReportArchive.svc` key fields for archive and PDF access.
- `ShopFloorConnector.svc` exact `GetOperationInfo` and `GetOrderOperations`
  signatures.
- `InventoryPartService.svc` and `ManufacturingPartService.svc` request/response
  shapes.
- Optional handling-unit projection names and navigation paths.

## Confirming Tenant Metadata

Use the projection root for the tenant:

```text
https://<ifs-host>/main/ifsapplications/projection/v1
```

For each candidate projection:

```http
GET /main/ifsapplications/projection/v1/<ProjectionName>.svc/$metadata
GET /main/ifsapplications/projection/v1/<ProjectionName>.svc/$openapi
```

If the tenant exposes an integration route, confirm the same metadata through:

```http
GET /int/ifsapplications/projection/v1/<ProjectionName>.svc/$metadata
GET /int/ifsapplications/projection/v1/<ProjectionName>.svc/$openapi
```

On this tenant, plain `...svc/$openapi` returned JSON successfully. Version
query variants should be checked in API Explorer before using them in scripts.

Check these items in metadata before coding:

- Entity set names, primary keys, navigation properties, and ETags.
- Action/function names, HTTP method, parameter names, enum literals, and return
  type.
- Field names for label ID, quantity, standard pack size, status/cancel flag,
  print job, result key, shop order, operation, resource, work center, lot/batch,
  serial number, and handling unit.
- Whether date fields are UTC, tenant-local, date-only, or offset-aware.

## Tenant Check On 2026-06-22

A live read against the configured tenant confirmed these projection metadata
results with the current integration user:

| Projection | Route tested | Result |
| --- | --- | --- |
| `ReportArchive` | `/main/ifsapplications/projection/v1/ReportArchive.svc/$metadata` | 200, `ArchiveSet`, `ArchiveDocumentSet`, `PdfArchiveSet`, `XmlVirtualset`, and `GetXml` confirmed |
| `InventoryPartBarcodeRep` | `/main/ifsapplications/projection/v1/InventoryPartBarcodeRep.svc/$metadata` | 200, `VirtualOrderReports` confirmed |
| `HandlUnitContentLabelRep` | `/main/ifsapplications/projection/v1/HandlUnitContentLabelRep.svc/$metadata` | 200, `VirtualOrderReports` confirmed |
| `HandlingUnitHandling` | `/main/ifsapplications/projection/v1/HandlingUnitHandling.svc/$metadata` | 200, `HandlingUnitSet` confirmed |
| `InventoryPartInStockHandling` | `/main/ifsapplications/projection/v1/InventoryPartInStockHandling.svc/$metadata` | 200, `InventoryPartInStockSet` confirmed |
| `QueryProjectionPRODUCTIONLOSS` | `/main/ifsapplications/projection/v1/QueryProjectionPRODUCTIONLOSS.svc/PRODUCTIONLOSSSet` | 200 with user permission set, custom timing source confirmed |
| `InventoryPartService` | `/int/ifsapplications/projection/v1/InventoryPartService.svc/$metadata` | 200, `GetPartInformation` confirmed |
| `ShopFloorConnector` | `/main` and `/int` projection metadata routes | 404 with the current integration user |
| `ManufacturingPartService` | `/main` and `/int` projection metadata routes | 404 with the current integration user |
| `InventoryPartBarcode` / `InventoryPartBarcodeHandling` | tested projection/entity metadata candidates | 404 with the current integration user |

The current tenant already has a custom label archive path that returns usable
label data. A 7-day test for `SIMSEK_PALET_ETIKETI_REP` returned 47 archive
label rows. All 47 rows had non-empty values for `ResultKey`, `ReportId`,
`label_time`, `machine_code`, `job_order`, `part_no`, `product_description`,
`quantity`, `package_id`, and `lot_batch_no`.

The permission-set export from 2026-06-22 includes
`QueryProjectionPRODUCTIONLOSS` with read-only access. It does not show an
explicit label projection grant, so the current reporting path keeps using the
existing label stock/archive sources unless a direct package-label projection is
later granted.

## Endpoint And Field Mapping

All field names below are logical targets. Replace them with tenant metadata names.

| Source | Purpose | Candidate fields to confirm |
| --- | --- | --- |
| `QueryProjectionPRODUCTIONLOSS.svc/PRODUCTIONLOSSSet` | Realized production timing by order number. Current app fetches this instead of the broader operation-statistics projection. | `OrderNo`, `PartDescription`, `RealStart`, `RealFinished`, `RealMachRunTime`, `InterruptionTime` |
| `InventoryPartBarcodeRep.svc/VirtualOrderReports` | Order or trace inventory part barcode label reports. Tenant metadata confirms this is report-order metadata, not the analysis row itself. | `ReportId`, `ReportTitle`, `ResultKey`, `ReportPrinterId`, `LayoutName`, `ParamContract`, `ParamBarcodeId`, `ArchiveDocument`, `TimeZone`, `LangCode`, `Objkey` |
| `InventoryPartBarcode.svc` / Inventory Part Barcode Analysis | Desired primary label source if enabled as a projection/entity in the tenant. Current integration user did not get metadata for tested names, so API Explorer must locate the actual exposed entity or a custom projection. | `BarcodeId` or `PackageLabelId`, `Contract`, `PartNo`, `PartDescription`, `ShopOrderNo`, `ReleaseNo`, `SequenceNo`, `OperationNo`, `LineItemNo`, `QtyPerPackage`, `StandardPackSize`, `UoM`, `LotBatchNo`, `SerialNo`, `HandlingUnitId`, `PrintJobId`, `ResultKey`, `CreatedDate`, `CreatedBy`, `Status`, `Cancelled`, `Objid`, `Objversion` |
| `ReportArchive.svc/ArchiveSet` | Report run metadata and audit lookup. Existing custom label XML can be parsed from archive result keys. | `ResultKey`, `TimeZone`, `ReportId`, `Notes`, `ExecTime`, `LayoutName`, `Sender`, `Owner`, `Printed`, `ReportMode`, `Title` |
| `ReportArchive.svc/ArchiveDocumentSet` | Report document metadata and optional PDF route. | `ResultKey`, `Id`, `ReportTitle`, `LangCode`, `Pdf`, `PrintJobId`, `PdfSize`, `FileName`, `FileNameExt`, `Notes`, `MimetypePdf`, `TimeZone` |
| `ReportArchive.svc/PdfArchiveSet` | Base64 PDF retrieval where allowed. Watch payload limits. | `ResultKey`, `Id`, `PdfSize`, `Pdf`, `LayoutName`, `FileName`, `LangCode`, `PrintJobId`, `Notes`, `Created`, `ReportTitle`, `TimeZone` |
| `ShopFloorConnector.svc GetOperationInfo` | Operation and machine context by operation ID. | `OperationId`, `Contract`, `OrderNo`, `ReleaseNo`, `SequenceNo`, `OperationNo`, `PartNo`, `WorkCenterNo`, `ResourceId`, `MachineId`, `OperationStatus`, `PlannedStart`, `PlannedFinish`, `QtyComplete`, `QtyScrapped` |
| `ShopFloorConnector.svc GetOrderOperations` | Operation list for a shop order. Public docs call this "Get Shop Order Operations Information"; exact function name is tenant metadata-confirmed. | `Contract`, `OrderNo`, `ReleaseNo`, `SequenceNo`, `OperationNo`, `PartNo`, `WorkCenterNo`, `ResourceId`, `OperationId`, `PlannedStart`, `PlannedFinish`, `RemainingQty` |
| `InventoryPartService.svc GetPartInformation` | Inventory part master data and characteristics. Tenant route confirmed under `/int`. | Request `PartInfoParams` with `Site`, `PartNo`, `ChangedSinceNumberOfDays`; response includes `Contract`, `PartNo`, `Description`, `UnitMeas`, `ProductCode`, `ProductFamily`, `PartStatus`, `Characteristics` |
| `ManufacturingPartService.svc GetParts` | Manufacturing master data, routing, structures, recipe, effective dates. | `Contract`, `PartNo`, `RoutingRevision`, `StructureRevision`, `OperationNo`, `WorkCenterNo`, `ResourceId`, `RunFactor`, `CrewSize`, `PhaseInDate`, `PhaseOutDate` |
| `HandlingUnitHandling.svc/HandlingUnitSet` | Map package labels to pallet/container context if labels are packed into handling units. | `HandlingUnitId`, `ParentHandlingUnitId`, `TopParentHandlingUnitId`, `Sscc`, `AltHandlingUnitLabelId`, `HandlingUnitTypeId`, `Contract`, `LocationNo`, `SourceRef1`, `SourceRef2`, `SourceRef3`, `IsInStock`, `IsInTransit` |
| `InventoryPartInStockHandling.svc/InventoryPartInStockSet` | Optional stock/HU enrichment when labels are tied to inventory stock rows. | `Contract`, `PartNo`, `ConfigurationId`, `LocationNo`, `LotBatchNo`, `SerialNo`, `EngChgLevel`, `WaivDevRejNo`, `ActivitySeq`, `HandlingUnitId`, `QtyOnhand`, `AvailableQty`, `UoM`, `PartNoDesc`, `Sscc`, `AltHandlingUnitLabelId`, `TopParentHandlingUnitId`, `TopParentSscc`, `InvPartBarcodeExist`, `Cf_Palet_Ici_Miktar` |

## Sample API Requests

These samples show the desired shape. Adjust every field, entity set, key, action,
function, and enum name to tenant metadata before implementation.

### Production Loss Timing

```http
GET https://<ifs-host>/main/ifsapplications/projection/v1/QueryProjectionPRODUCTIONLOSS.svc/PRODUCTIONLOSSSet
  ?$select=OrderNo,PartDescription,RealStart,RealFinished,RealMachRunTime,InterruptionTime
  &$filter=RealStart ge 2026-06-01T00:00:00Z
  &$top=1000
```

For app reporting, the client adds an `OrderNo` batch filter to the configured
`IFS_PRODUCTION_LOSS_QUERY_START_DATE` lower bound. Rows where `RealFinished` is
empty are kept; completed shift windows are calculated up to the current local
time, while the current/incomplete shift is left uncalculated.

### Inventory Part Barcode Analysis

```http
# Field names and entity set must be adjusted to tenant $metadata.
GET https://<ifs-host>/main/ifsapplications/projection/v1/InventoryPartBarcode.svc/InventoryPartBarcodeSet
  ?$select=BarcodeId,Contract,PartNo,ShopOrderNo,ReleaseNo,SequenceNo,OperationNo,QtyPerPackage,StandardPackSize,UoM,LotBatchNo,SerialNo,HandlingUnitId,PrintJobId,ResultKey,CreatedDate,Status,Cancelled
  &$filter=Contract eq 'S01' and CreatedDate ge 2026-06-01T00:00:00Z and CreatedDate lt 2026-06-02T00:00:00Z and Cancelled eq false
  &$expand=PartNoRef($select=Description)
  &$top=1000
```

### Barcode Label Report Ordering

```http
# Confirm POST body in InventoryPartBarcodeRep.svc/$openapi.
POST https://<ifs-host>/main/ifsapplications/projection/v1/InventoryPartBarcodeRep.svc/VirtualOrderReports
Content-Type: application/json

{
  "ReportId": "INVENTORY_PART_BARCODE_REP",
  "LayoutName": "InventoryPartBarcodeStandard.rpl",
  "ArchiveDocument": true,
  "ParamContract": "S01",
  "ParamBarcodeId": "BARCODE-ID-FROM-ANALYSIS"
}
```

### Report Archive

```http
# Use for audit/reconciliation, or as the current custom label XML bridge.
GET https://<ifs-host>/main/ifsapplications/projection/v1/ReportArchive.svc/ArchiveSet
  ?$select=ResultKey,ReportId,Notes,ExecTime,Sender,Owner,Printed,Title,ReportMode
  &$filter=ReportId eq 'SIMSEK_PALET_ETIKETI_REP' and ExecTime ge 2026-06-01T00:00:00Z
    and ExecTime lt 2026-06-02T00:00:00Z
  &$orderby=ExecTime asc,ResultKey asc
  &$top=1000
```

```http
# Confirm ArchiveDocumentSet keys in tenant metadata.
GET https://<ifs-host>/main/ifsapplications/projection/v1/ReportArchive.svc/ArchiveDocumentSet
  ?$select=ResultKey,Id,ReportTitle,PrintJobId,FileName,FileNameExt,Notes,MimetypePdf,TimeZone
  &$filter=ResultKey eq 123456
```

```http
# PdfArchiveSet may return base64 and can hit payload limits for large PDFs.
GET https://<ifs-host>/main/ifsapplications/projection/v1/ReportArchive.svc/PdfArchiveSet
  ?$select=ResultKey,Id,Pdf
  &$filter=ResultKey eq 123456
```

```http
# Some tenants expose a streaming PDF navigation instead.
GET https://<ifs-host>/main/ifsapplications/projection/v1/ReportArchive.svc/ArchiveDocumentSet(ResultKey=123456,Id='00000000-0000-0000-0000-000000000000')/Pdf
```

### Shop Floor Connector

```http
# Confirm function/action syntax and enum names in ShopFloorConnector.svc/$metadata.
GET https://<ifs-host>/main/ifsapplications/projection/v1/ShopFloorConnector.svc/GetOperationInfo(OperationId='S01-2615-*-*-10')
  ?$select=OperationId,Contract,OrderNo,ReleaseNo,SequenceNo,OperationNo,PartNo,WorkCenterNo,ResourceId,PlannedStart,PlannedFinish,QtyComplete,QtyScrapped
```

```http
# Public docs describe shop order operation information; exact name may vary.
GET https://<ifs-host>/main/ifsapplications/projection/v1/ShopFloorConnector.svc/GetOrderOperations(Contract='S01',OrderNo='2615',ReleaseNo='*',SequenceNo='*')
  ?$select=Contract,OrderNo,ReleaseNo,SequenceNo,OperationNo,PartNo,WorkCenterNo,ResourceId,OperationId,PlannedStart,PlannedFinish,RemainingQty
```

### Part Master Data

```http
# Tenant metadata confirms this action under /int.
POST https://<ifs-host>/int/ifsapplications/projection/v1/InventoryPartService.svc/GetPartInformation
Content-Type: application/json

{
  "PartInfoParams": {
    "Site": "S01",
    "PartNo": "MM-PET0048-12-024Y-025",
    "ChangedSinceNumberOfDays": null
  }
}
```

The response structure contains `Description`, `UnitMeas`, `ProductCode`,
`ProductFamily`, `PartStatus`, and `Characteristics`.

```http
# ManufacturingPartService GetParts returns manufacturing master-data structures.
POST https://<ifs-host>/main/ifsapplications/projection/v1/ManufacturingPartService.svc/GetParts
Content-Type: application/json

{
  "Contract": "S01",
  "ChangedWithinDays": 30
}
```

## Extraction Pipeline To FACT_PACKAGE_LABEL

1. Read tenant metadata for all candidate projections and freeze a field map.
2. Preferred source: pull label rows from `InventoryPartBarcode`/Inventory Part
   Barcode Analysis for the extraction window after API Explorer locates the
   exposed projection/entity.
3. Current pilot source: use `ReportArchive.svc/ArchiveSet` plus `GetXml` for
   `SIMSEK_PALET_ETIKETI_REP`, because the live 7-day test returned complete
   label data for the required fields.
4. Filter to valid production labels: correct site, produced-part families,
   relevant report/layout if needed, not cancelled, not voided, and not
   replaced by a later valid label.
5. Normalize one source row into one `FACT_PACKAGE_LABEL` row keyed by
   `package_label_id`.
6. Dedupe by `package_label_id`. Never dedupe by print job, result key, order,
   product, lot, serial, or handling unit alone.
7. Enrich missing machine context from label fields first, then
   `ShopFloorConnector` operation data using shop order keys and operation/time
   if that premium projection is enabled for the tenant/user.
8. Enrich product description, UoM, standard pack size, characteristics, and
   routing data from `InventoryPartService` and `ManufacturingPartService`.
9. Optionally enrich handling-unit hierarchy if the label is packed into a
   pallet/container.
10. Resolve shift by matching `label_printed_at` or production completion time to
   the shift calendar. Prefer the time that best represents physical package
   creation.
11. Upsert `FACT_PACKAGE_LABEL` by `package_label_id`.
12. Aggregate by shift, machine, and product; compare produced quantity with
   expected quantity from expected-rate/shift plan tables.
13. Store `ReportArchive` result keys and document IDs for traceability only.

## SQL DDL

The DDL is database-neutral SQL. Adjust data types for the deployed database.

```sql
CREATE TABLE fact_package_label (
    package_label_id        VARCHAR(100) PRIMARY KEY,
    source_system           VARCHAR(50) NOT NULL DEFAULT 'IFS',
    contract                VARCHAR(20) NOT NULL,
    company_id              VARCHAR(20),
    part_no                 VARCHAR(100) NOT NULL,
    part_description        VARCHAR(500),
    shop_order_no           VARCHAR(100),
    release_no              VARCHAR(30),
    sequence_no             VARCHAR(30),
    operation_no            INTEGER,
    machine_id              VARCHAR(100),
    work_center_no          VARCHAR(100),
    resource_id             VARCHAR(100),
    shift_id                VARCHAR(100),
    shift_date              DATE,
    label_printed_at        TIMESTAMP NOT NULL,
    production_completed_at TIMESTAMP,
    qty_per_package         DECIMAL(18, 6),
    standard_pack_size      DECIMAL(18, 6),
    uom                     VARCHAR(30),
    label_status            VARCHAR(50),
    is_cancelled            BOOLEAN NOT NULL DEFAULT FALSE,
    is_reprint              BOOLEAN NOT NULL DEFAULT FALSE,
    original_package_label_id VARCHAR(100),
    print_job_id            VARCHAR(100),
    report_result_key       VARCHAR(100),
    archive_document_id     VARCHAR(100),
    handling_unit_id        VARCHAR(100),
    parent_handling_unit_id VARCHAR(100),
    lot_batch_no            VARCHAR(100),
    serial_no               VARCHAR(100),
    ifs_objid               VARCHAR(200),
    ifs_objversion          VARCHAR(200),
    raw_payload_json        TEXT,
    loaded_at               TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_fact_package_label_shift_machine_part
    ON fact_package_label (shift_date, shift_id, machine_id, part_no);

CREATE INDEX idx_fact_package_label_shop_order
    ON fact_package_label (contract, shop_order_no, release_no, sequence_no, operation_no);

CREATE TABLE dim_shift_calendar (
    shift_id       VARCHAR(100) PRIMARY KEY,
    shift_date     DATE NOT NULL,
    shift_code     VARCHAR(50) NOT NULL,
    starts_at      TIMESTAMP NOT NULL,
    ends_at        TIMESTAMP NOT NULL,
    planned_minutes INTEGER NOT NULL
);

CREATE TABLE dim_expected_production_rate (
    expected_rate_id      VARCHAR(100) PRIMARY KEY,
    contract              VARCHAR(20) NOT NULL,
    machine_id            VARCHAR(100) NOT NULL,
    part_no               VARCHAR(100) NOT NULL,
    effective_from        TIMESTAMP NOT NULL,
    effective_to          TIMESTAMP,
    expected_qty_per_hour DECIMAL(18, 6) NOT NULL,
    uom                   VARCHAR(30) NOT NULL
);

CREATE TABLE fact_shift_machine_plan (
    shift_id          VARCHAR(100) NOT NULL,
    contract          VARCHAR(20) NOT NULL,
    machine_id        VARCHAR(100) NOT NULL,
    part_no           VARCHAR(100) NOT NULL,
    planned_minutes   INTEGER NOT NULL,
    planned_qty       DECIMAL(18, 6),
    source_order_no   VARCHAR(100),
    PRIMARY KEY (shift_id, contract, machine_id, part_no)
);
```

## SQL Aggregations

### Package Count And Produced Quantity

```sql
WITH valid_labels AS (
    SELECT *
    FROM fact_package_label
    WHERE is_cancelled = FALSE
      AND package_label_id IS NOT NULL
),
label_rollup AS (
    SELECT
        shift_date,
        shift_id,
        contract,
        machine_id,
        part_no,
        COUNT(DISTINCT package_label_id) AS package_count,
        CASE
            WHEN SUM(CASE WHEN qty_per_package IS NULL THEN 1 ELSE 0 END) = 0
                THEN SUM(qty_per_package)
            ELSE COUNT(DISTINCT package_label_id) * MAX(standard_pack_size)
        END AS produced_qty
    FROM valid_labels
    GROUP BY shift_date, shift_id, contract, machine_id, part_no
)
SELECT *
FROM label_rollup;
```

### Expected Quantity From Shift Plan And Rate

```sql
SELECT
    p.shift_id,
    s.shift_date,
    p.contract,
    p.machine_id,
    p.part_no,
    COALESCE(
        p.planned_qty,
        p.planned_minutes * r.expected_qty_per_hour / 60.0
    ) AS expected_qty
FROM fact_shift_machine_plan p
JOIN dim_shift_calendar s
  ON s.shift_id = p.shift_id
JOIN dim_expected_production_rate r
  ON r.contract = p.contract
 AND r.machine_id = p.machine_id
 AND r.part_no = p.part_no
 AND s.starts_at >= r.effective_from
 AND (r.effective_to IS NULL OR s.starts_at < r.effective_to);
```

### Loss By Shift, Machine, And Product

```sql
WITH valid_labels AS (
    SELECT *
    FROM fact_package_label
    WHERE is_cancelled = FALSE
),
produced AS (
    SELECT
        shift_date,
        shift_id,
        contract,
        machine_id,
        part_no,
        COUNT(DISTINCT package_label_id) AS package_count,
        CASE
            WHEN SUM(CASE WHEN qty_per_package IS NULL THEN 1 ELSE 0 END) = 0
                THEN SUM(qty_per_package)
            ELSE COUNT(DISTINCT package_label_id) * MAX(standard_pack_size)
        END AS produced_qty
    FROM valid_labels
    GROUP BY shift_date, shift_id, contract, machine_id, part_no
),
expected AS (
    SELECT
        p.shift_id,
        s.shift_date,
        p.contract,
        p.machine_id,
        p.part_no,
        COALESCE(
            p.planned_qty,
            p.planned_minutes * r.expected_qty_per_hour / 60.0
        ) AS expected_qty
    FROM fact_shift_machine_plan p
    JOIN dim_shift_calendar s
      ON s.shift_id = p.shift_id
    JOIN dim_expected_production_rate r
      ON r.contract = p.contract
     AND r.machine_id = p.machine_id
     AND r.part_no = p.part_no
     AND s.starts_at >= r.effective_from
     AND (r.effective_to IS NULL OR s.starts_at < r.effective_to)
)
SELECT
    e.shift_date,
    e.shift_id,
    e.contract,
    e.machine_id,
    e.part_no,
    COALESCE(p.package_count, 0) AS package_count,
    COALESCE(p.produced_qty, 0) AS produced_qty,
    e.expected_qty,
    e.expected_qty - COALESCE(p.produced_qty, 0) AS loss_qty,
    CASE
        WHEN e.expected_qty = 0 THEN NULL
        ELSE (e.expected_qty - COALESCE(p.produced_qty, 0)) * 100.0 / e.expected_qty
    END AS loss_percent
FROM expected e
LEFT JOIN produced p
  ON p.shift_id = e.shift_id
 AND p.contract = e.contract
 AND p.machine_id = e.machine_id
 AND p.part_no = e.part_no
ORDER BY e.shift_date, e.shift_id, e.machine_id, e.part_no;
```

## Key Risks And Controls

- Reprints: IFS Community reports that printing from shop order can generate a
  new barcode ID for the same serial/part, while reprinting from Inventory Part
  Barcode Analysis may reuse the existing barcode. Classify reprints and count
  only the valid physical package label.
- Cancelled or voided labels: exclude rows marked cancelled, voided, replaced, or
  otherwise invalid in tenant metadata.
- Multiple labels in one print job: a print job/result key is not a package. It
  can contain many labels, so count distinct label IDs.
- Missing machine context: label rows may not carry machine/resource. Enrich from
  operation metadata by order/release/sequence/operation and timestamp; keep
  unresolved records with `machine_id = 'UNKNOWN'` rather than dropping them.
- Partial packages: if actual `QtyPerPackage` exists, sum it. If only
  `StandardPackSize` exists, ensure partial packages and manual edits are handled
  before applying the count-times-pack-size fallback.
- Handling units: a handling unit may contain multiple package labels or a package
  label may later be attached to a parent handling unit. Do not count handling
  units as packages unless tenant process confirms one-to-one usage.
- Report archive PDFs: useful audit evidence, but PDF archive data is not the
  production-count system of record and can hit payload limits.
- ReceiveShopOrderHandling: do not use it as the main source. IFS Community
  explains it is built for assistant/workflow staging; successful HTTP status can
  indicate staging activity rather than a committed receipt. For transactional
  shop order receipts, IFS points newer releases to the premium
  `ShopFloorConnector` `ReceiveOrder` API. For this workflow, the main source is
  label history, not receipt assistant state.

## Public References

- IFS API Usage policy: https://docs.ifs.com/policy/APIUsageCloud.pdf
- IFS API Explorer and `$openapi` community example:
  https://community.ifs.com/framework-experience-infrastructure-cloud-integration-dev-tools-50/how-do-i-view-the-ifs-api-documentation-12766
- IFS MES integration docs:
  https://docs.ifs.com/ifsclouddocs/25r2/Manufacturing/AboutManufacturingExecutionSystemIntegration.htm
- IFS Print Shop Order Barcode Labels:
  https://docs.ifs.com/ifsclouddocs/25r2/Manufacturing/ActivityPrintShopOrderBarcodeLabels.htm
- IFS Inventory Part Barcode report community:
  https://community.ifs.com/products-manufacturing-products-engineering-40/inventory-part-barcode-report-label-has-no-description-how-to-print-a-picture-13830
- IFS barcode scanning community:
  https://community.ifs.com/supply-chain-251/barcode-scanning-function-with-non-wadaco-customized-screen-36031
- IFS barcode reprint behavior community:
  https://community.ifs.com/products-manufacturing-products-engineering-40/two-barcodes-are-generated-for-the-same-serial-part-16239
- IFS ReportArchive PDF community:
  https://community.ifs.com/framework-experience-infrastructure-cloud-integration-dev-tools-50/report-archive-api-for-displaying-pdf-invoices-in-external-application-42326
- IFS ReportArchive matching community:
  https://community.ifs.com/framework-experience-infrastructure-cloud-integration-dev-tools-50/finding-the-correct-item-from-the-report-archive-44327
- IFS ReceiveShopOrderHandling community:
  https://community.ifs.com/framework-experience-infrastructure-cloud-integration-dev-tools-50/receiving-shop-order-using-rest-api-27071
- IFS Receive Shop Order API community:
  https://community.ifs.com/framework-experience-infrastructure-cloud-integration-dev-tools-50/receive-shop-order-ifs-rest-api-63821
