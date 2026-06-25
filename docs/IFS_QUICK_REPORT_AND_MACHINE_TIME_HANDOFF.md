# IFS Quick Report And Machine Time Handoff

This note is for a follow-up Codex session. It summarizes the production-loss
workflow, the confirmed IFS quick report endpoint, and the IFS endpoint that
returns machine real start/finish timing.

## User Workflow

The plant currently uses IFS and shift-manager entries together:

1. IFS has a Quick Report for daily production amounts by date, material,
   machine, and shift.
2. Shift managers manually write production amounts for each machine across
   three shifts.
3. The team compares the IFS Quick Report result with the shift-manager written
   amounts to validate production quantities. The Quick Report is not intended
   to automatically replace the shift-manager quantities in the production-loss
   report.
4. After production data is validated, the team creates a production loss
   report.
5. The production loss report uses production amounts and job-order cycle times.
   Current optimum calculation is based on a full shift:

   ```text
   optimum production = 28800 / realized_cycle_time_seconds * active_cavity
   loss percent = (produced_amount - optimum_amount) * 100
   ```

6. If production loss is greater than 3 percent, the team investigates the loss
   reason. If it is below 3 percent, the result is accepted.
7. Loss reasons currently come from paper forms on each machine where workers
   write stop times and stop reasons.
8. Current report logic assumes a machine worked the whole shift. That is not
   always true. The next improvement is to incorporate real IFS machine working
   time instead of assuming the full 8-hour shift.

## Why These Endpoints Matter

The Quick Report endpoint is needed to fetch IFS production quantities in a
repeatable way instead of relying on the browser UI. These quantities can be
compared against shift-manager entries to validate production data before loss
reporting. If Quick Report and shift-manager quantities disagree, the report
should mark the mismatch for investigation; the team decides the correct value
after checking the problem.

The Quick Report endpoint does not provide machine real start/finish timing. To
replace the current full-shift assumption, the report also needs exact machine
clocking intervals and downtime. The preferred timing source is now
`ShopFloorWorkbenchHandling.svc/Reference_ShopOperClocking`, because it provides
exact `ResourceId`, `StartTime`, and `FinishTime`. Use
`OperationStatisticsHandling.svc/OperationStatistics` as the operation context
and `InterruptionTime` source. The older custom
`QueryProjectionPRODUCTIONLOSS.svc/PRODUCTIONLOSSSet` remains historical
evidence, but it is not required if the standard timing endpoints continue to
work.

## Confirmed Quick Report URL

The user supplied the IFS UI URL:

```text
https://ifs.simsekplastik.com/main/ifsapplications/web/quickreport/454105;path=0.1656053651.1494445447.169839528.1742020729.eyJmIjoiL1JlcG9ydCIsImciOiI0NTQxMDUiLCJpIjp7fSwiYSI6InZpcnR1YWwtMSIsImIiOiIxNzQyMDIwNzI5IiwiZSI6IkhpemxpIFJhcG9yLTogVVJUMDMtVmFyZGl5YSBCYXpsxLEgR8O8bmzDvGsgw5xyZXRpbSBNaWt0YXIgUmFwb3J1IiwiZCI6dHJ1ZSwiYyI6ZmFsc2V9
```

The report id is:

```text
454105
```

The HAR file inspected was:

```text
C:\Users\Ercan ÖZKAN\Desktop\Process Project\Quick report.har
```

The HAR confirms the data request:

```http
GET https://ifs.simsekplastik.com/main/ifsapplications/projection/v1/QuickReports.svc/QuickReport_454105(BASLANGIC_TARIHI='24.06.2026',BITIS_TARIHI='24.06.2026')?$skip=0&$top=35
```

Use `DD.MM.YYYY` date strings in both parameters:

```http
GET https://ifs.simsekplastik.com/main/ifsapplications/projection/v1/QuickReports.svc/QuickReport_454105(BASLANGIC_TARIHI='25.06.2026',BITIS_TARIHI='25.06.2026')?$skip=0&$top=1000
```

## Quick Report Column Metadata Endpoint

The HAR also confirms the column metadata request:

```http
GET https://ifs.simsekplastik.com/main/ifsapplications/projection/v1/QuickReports.svc/GetColumnNames(ReportId='454105')
```

Returned columns:

```text
C1_TARIH              -> Tarih
C2_MALZEME_NO         -> Malzeme No
C3_MAKINE_NO          -> Makine No
C4_VARDIYA_1_URETIM   -> Vardiya 1 Uretim
C5_VARDIYA_2_URETIM   -> Vardiya 2 Uretim
C6_VARDIYA_3_URETIM   -> Vardiya 3 Uretim
C7_TOPLAM_URETIM      -> Toplam Uretim
```

The HAR response type for the report data was:

```text
IfsApp.QuickReports.Structure_454105
```

The captured example request returned 34 rows for `24.06.2026`.

## Quick Report Headers Observed In HAR

Useful non-secret request headers:

```text
accept: application/json;odata.metadata=full;IEEE754Compatible=true
prefer: wait=99999
x-requested-with: XMLHttpRequest
```

Do not copy cookies, authorization headers, or other session-specific values
from the HAR into source code or documentation.

## Machine Real Start / Finish / Runtime Endpoint

### Preferred Accessible Timing Endpoint

Endpoint discovery on 2026-06-25 found an accessible standard IFS projection
that provides the real timing fields needed for machine-minute allocation:

```http
GET https://ifs.simsekplastik.com/main/ifsapplications/projection/v1/OperationStatisticsHandling.svc/OperationStatistics
```

Metadata status:

```text
OperationStatisticsHandling.svc/$metadata -> HTTP 200
OperationStatisticsHandling.svc/OperationStatistics -> HTTP 200 with rows
```

Recommended query shape:

```http
GET https://ifs.simsekplastik.com/main/ifsapplications/projection/v1/OperationStatisticsHandling.svc/OperationStatistics?$select=StatisticId,Contract,OrderNo,ReleaseNo,SequenceNo,OperationNo,PartNo,PartDescription,WorkCenterNo,WorkCenterDesc,OperationDesc,OperStatusCode,PlanStart,RealStart,PlanFinished,RealFinished,RealMachRunTime,InterruptionTime,PercentInterruptionTime,ReportedQty,RemainingQty,PlanQty,ManualOperationQty&$filter=Contract eq 'S01' and RealStart ge 2026-06-01T00:00:00Z&$top=1000
```

Important fields:

```text
StatisticId               -> unique operation-statistics row id
Contract                  -> site/contract
OrderNo                   -> IFS shop/job order number
ReleaseNo                 -> release number
SequenceNo                -> sequence number
OperationNo               -> operation number
PartNo                    -> material/part number
PartDescription           -> product description
WorkCenterNo              -> work center, not always exact machine number
WorkCenterDesc            -> work center description; may include machine range
OperationDesc             -> operation description
OperStatusCode            -> operation status
PlanStart                 -> planned operation start timestamp
RealStart                 -> actual operation start timestamp
PlanFinished              -> planned operation finish timestamp
RealFinished              -> actual operation finish timestamp, nullable
RealMachRunTime           -> real machine run time; observed as decimal value
InterruptionTime          -> IFS interruption/downtime value
PercentInterruptionTime   -> interruption percentage
ReportedQty               -> reported quantity
RemainingQty              -> remaining quantity
PlanQty                   -> planned quantity
ManualOperationQty        -> whether quantity is manual
```

Observed examples:

```text
OrderNo 2530 returned two OperationStatistics rows:
- StatisticId 10076, OperationNo 1, WorkCenterNo PKT,
  RealStart 2026-05-21T04:39:57Z,
  RealFinished 2026-06-05T11:20:41Z,
  RealMachRunTime 0, InterruptionTime 0
- StatisticId 10077, OperationNo 20, WorkCenterNo T2530,
  RealStart 2026-05-21T04:13:15Z,
  RealFinished 2026-06-05T11:20:41Z,
  RealMachRunTime 53.4333333333333,
  InterruptionTime 285.9333333333333
```

```text
OrderNo 2580 returned unfinished rows:
- OperationNo 10, WorkCenterNo 70DPH,
  RealStart 2026-06-16T05:03:55Z,
  RealFinished null,
  RealMachRunTime 21.0666666666667,
  InterruptionTime 128.1166666666667,
  OperStatusCode InProcess
```

This endpoint should be used for operation-level context, validation, and
`InterruptionTime`. It should not be the only source for machine-level timing
when exact `ResourceId` clocking rows are available.

Machine requirement: exact machine number is required. `OperationStatistics`
exposes `WorkCenterNo` and `WorkCenterDesc`, but the `OperationStatistic` entity
did not expose a direct `ResourceId`, `PreferredResourceId`, or `MachineNo`
property in metadata. For example, Quick Report has exact machine numbers such
as `173`, while `OperationStatistics` may show `WorkCenterNo=70DPH` and
`WorkCenterDesc=70DPH_(171-172-....177)`.

### Exact Machine Timing Endpoint

Endpoint discovery on 2026-06-25 found a better exact-machine timing companion:

```http
GET https://ifs.simsekplastik.com/main/ifsapplications/projection/v1/ShopFloorWorkbenchHandling.svc/Reference_ShopOperClocking
```

This endpoint provides exact `ResourceId` plus `StartTime` and `FinishTime`, so
machine minutes can be calculated directly per machine instead of distributing a
work-center-level timing row.

Recommended selected fields:

```text
OrderNo,ReleaseNo,SequenceNo,OperationNo,ClockingSeq,StartTime,FinishTime,Contract,WorkCenterNo,ResourceId
```

Real example for `OrderNo=2869`, `OperationNo=10`, machine `173`:

```text
ClockingSeq 7921: 2026-06-24T18:46:00Z -> 2026-06-24T21:39:00Z, ResourceId 173
ClockingSeq 7923: 2026-06-24T23:17:00Z -> 2026-06-25T00:36:00Z, ResourceId 173
ClockingSeq 7927: 2026-06-25T00:36:00Z -> 2026-06-25T01:13:00Z, ResourceId 173
ClockingSeq 7931: 2026-06-25T01:13:00Z -> 2026-06-25T04:25:00Z, ResourceId 173
ClockingSeq 7934: 2026-06-25T04:25:00Z -> null, ResourceId 173
```

Real example for a multi-machine operation, `OrderNo=16152`, `ReleaseNo=5`,
`SequenceNo=2`, `OperationNo=10`:

```text
OperationStatistics has one work-center timing row:
StatisticId 267
WorkCenterNo 70DPH
RealStart 2025-11-03T00:11:38Z
RealFinished 2025-11-26T16:06:05Z
InterruptionTime 115

Reference_ShopOperClocking gives exact machine clocking:
ResourceId 177:
  2025-11-15T18:47:00Z -> 2025-11-16T00:13:00Z
  2025-11-16T01:57:00Z -> 2025-11-16T02:28:00Z
  2025-11-16T02:55:00Z -> 2025-11-16T07:31:00Z

ResourceId 176:
  2025-11-16T13:18:00Z -> 2025-11-20T13:20:00Z

ResourceId 172:
  2025-11-25T18:56:00Z -> 2025-11-26T16:06:00Z
```

For a one-day report, clip these exact machine clocking intervals to the
selected report day's shift windows. This avoids assigning or distributing the
same full work-center timing row across multiple machines.

Use `ShopFloorWorkbenchHandling.svc/Reference_OperationHistory` as an additional
companion source for exact machine/resource production events and quantity
verification. It does not provide continuous start/finish intervals, but it does
provide transaction events with `OrderNo`, `OperationNo`, `WorkCenterNo`,
`ResourceId`, `ResourceDescription`, `PartNo`, `TimeOfProduction`, and
quantities. Example observed for `OrderNo=2869`, `OperationNo=10`:

```text
Reference_OperationHistory row:
WorkCenterNo 70DPH
ResourceId 173
ResourceDescription 70DPH/173
PartNo MM-PET0210-03-028Y-040
TimeOfProduction 2026-06-25T13:33:24Z
```

The intended exact-machine timing design is:

1. Fetch operation context rows from
   `OperationStatisticsHandling.svc/OperationStatistics`.
2. Fetch exact machine clocking intervals from
   `ShopFloorWorkbenchHandling.svc/Reference_ShopOperClocking`.
3. Optionally fetch resource transaction rows from
   `ShopFloorWorkbenchHandling.svc/Reference_OperationHistory` for quantity and
   resource validation.
4. Match by at least `Contract`, `OrderNo`, `ReleaseNo`, `SequenceNo`,
   `OperationNo`, `PartNo`, `WorkCenterNo`, and selected report day/month.
5. Use `Reference_ShopOperClocking.ResourceId` as the exact machine number and
   calculate exact elapsed machine minutes from `StartTime`/`FinishTime`.
6. Match that exact machine number to Quick Report `C3_MAKINE_NO`.

Real example:

```text
OperationStatistics:
StatisticId 11335
OrderNo 2869
OperationNo 10
PartNo MM-PET0210-03-028Y-040
WorkCenterNo 70DPH
RealStart 2026-06-24T18:46:13Z
RealFinished null
InterruptionTime 3.2

Reference_OperationHistory:
OrderNo 2869
OperationNo 10
PartNo MM-PET0210-03-028Y-040
WorkCenterNo 70DPH
ResourceId 173
ResourceDescription 70DPH/173

Quick Report:
C2_MALZEME_NO MM-PET0210-03-028Y-040
C3_MAKINE_NO 173
```

Therefore this timing row should be assigned to exact machine `173`, not just
work center `70DPH`.

### Blocked Custom Timing Endpoint

The existing project previously identified and used this custom IFS projection
for machine actual timing:

```http
GET https://ifs.simsekplastik.com/main/ifsapplications/projection/v1/QueryProjectionPRODUCTIONLOSS.svc/PRODUCTIONLOSSSet
```

Recommended query shape:

```http
GET https://ifs.simsekplastik.com/main/ifsapplications/projection/v1/QueryProjectionPRODUCTIONLOSS.svc/PRODUCTIONLOSSSet?$select=OrderNo,PartDescription,RealStart,RealFinished,RealMachRunTime,InterruptionTime&$filter=RealStart ge 2026-06-01T00:00:00Z and (OrderNo eq '2579' or OrderNo eq '2580')&$top=1000
```

Important fields:

```text
OrderNo           -> IFS shop/job order number
PartDescription   -> product description
RealStart         -> actual machine/order start timestamp
RealFinished      -> actual machine/order finish timestamp
RealMachRunTime   -> real machine run time, treated by current code as minutes
InterruptionTime  -> IFS interruption time, if populated
```

The current app code treats `RealMachRunTime` directly as minutes. It also uses
`RealStart` and `RealFinished` to calculate overlap with shift windows. If
`RealFinished` is null, the existing report logic treats the operation as still
continuing and handles it cautiously by shift.

Current status: this custom projection is not accessible with the current OAuth
context. On 2026-06-25, both `PRODUCTIONLOSSSet` and `$metadata` returned HTTP
404 `MI_METADATA_NOTFOUND`. Keep the saved 2026-06-22 response as historical
evidence, but prefer `OperationStatisticsHandling.svc/OperationStatistics` for
new implementation unless access to the custom projection is restored.

## Clarified Machine Time And Downtime Allocation Requirement

The next calculation should not assume every machine worked a full 8-hour shift.
For each given report day and job/order, first calculate how many elapsed
machine minutes belong to each shift by intersecting the machine actual time
range with that selected report day's shift windows. A report day is capped at
24 hours; if a machine/order has been running for many days, do not count the
whole multi-day interval for a one-day report. Clip the interval to the selected
report day first, then split that clipped interval into shifts.

Then distribute `InterruptionTime` downtime from IFS across those same shift
buckets in proportion to the elapsed machine minutes.

The user confirmed the daily shift windows are exactly:

```text
Shift 1: 00:00-08:00
Shift 2: 08:00-16:00
Shift 3: 16:00-24:00
```

Use the selected report day in plant local time when applying these shift
boundaries. The current project timezone setting is `Europe/Istanbul`.

The user originally described the rule with machine `RealStart` and
`RealFinished`. For the exact-machine implementation, read those as
`Reference_ShopOperClocking.StartTime` and `Reference_ShopOperClocking.FinishTime`
for the exact `ResourceId`. `OperationStatistics.RealStart` and
`OperationStatistics.RealFinished` remain useful for operation-level validation
or fallback, but they are not exact machine intervals.

### Finished Exact Machine Clocking Interval

If an exact machine/order clocking interval has both `StartTime` and
`FinishTime` for the report day:

1. Clip the actual interval to the report day's shift windows.
2. Calculate gross elapsed machine minutes per shift from the overlap.
3. Sum the shift minutes to get total elapsed machine minutes.
4. Allocate downtime proportionally:

   ```text
   shift_downtime_minutes =
     total_downtime_minutes * shift_elapsed_machine_minutes / total_elapsed_machine_minutes
   ```

5. Net machine minutes for optimum production should then be:

   ```text
   shift_net_machine_minutes = shift_elapsed_machine_minutes - shift_downtime_minutes
   ```

Example supplied by the user:

```text
RealStart:    01.01.2000 02:00
RealFinished: 01.01.2000 21:00

Shift 1 elapsed machine minutes: 02:00-08:00 = 360
Shift 2 elapsed machine minutes: 08:00-16:00 = 480
Shift 3 elapsed machine minutes: 16:00-21:00 = 300
Total elapsed machine minutes: 1140

If total downtime is 70 minutes:
Shift 1 downtime = 70 * 360 / 1140
Shift 2 downtime = 70 * 480 / 1140
Shift 3 downtime = 70 * 300 / 1140
```

### Unfinished Exact Machine Clocking Interval

If an exact machine/order clocking interval has `StartTime` but no `FinishTime`,
treat the operation as still running through the end of the selected report day.
The user explicitly confirmed that unfinished production should be capped at the
end of the selected report day, not at the current computer/report run time.

Expected behavior:

1. Start from `StartTime`.
2. For the shift containing `StartTime`, calculate only from `StartTime` to the
   end of that shift, capped by the selected report day.
3. Any fully elapsed shifts after that are counted as full 480-minute shifts.
4. For the selected report day, do not count before 00:00 or after 24:00.
5. Distribute downtime using the same proportional formula:

   ```text
   shift_downtime_minutes =
     InterruptionTime * shift_elapsed_machine_minutes / total_elapsed_machine_minutes
   ```

Example interpretation:

```text
If production has started, has not finished yet, and has 80 minutes
`InterruptionTime`, distribute those 80 minutes across the selected report day's
shift buckets according to:

shift elapsed machine minutes / total elapsed machine minutes in the selected report day
```

Round each shift's calculated time to whole minutes for the report.

## Endpoint Data Observations For Duplicate Rows

The user asked for examples before deciding how to handle multiple IFS timing
rows for the same order.

Live endpoint status checked on 2026-06-25:

```text
OAuth token request succeeded, but the production-loss projection returned:
HTTP 404 MI_METADATA_NOTFOUND
```

Retried on 2026-06-25 with the current local `.env` OAuth settings:

```text
Token request: OK
QuickReports.svc/GetColumnNames(ReportId='454105'): HTTP 200
QuickReports.svc/QuickReport_454105(...): HTTP 200
QueryProjectionPRODUCTIONLOSS.svc/PRODUCTIONLOSSSet: HTTP 404 MI_METADATA_NOTFOUND
QueryProjectionPRODUCTIONLOSS.svc/$metadata: HTTP 404 MI_METADATA_NOTFOUND
Common case variants of QueryProjectionPRODUCTIONLOSS: HTTP 404 MI_METADATA_NOTFOUND
```

Interpretation: the current OAuth credentials can authenticate and can read the
Quick Report projection, so the failure is not a general network/token problem.
It is specific to the custom `QueryProjectionPRODUCTIONLOSS` projection not
being visible or available to the current OAuth context. Likely causes are IFS
permission/profile changes, a projection publication/deployment change, or a
different user/session having been used when the saved successful response was
captured.

Because the live projection was not accessible with the current local
configuration, the examples below come from the saved endpoint response:

```text
outputs/production_loss_20260622/production_loss_raw.json
Fetched at: 2026-06-22T15:28:29.7396453+03:00
Endpoint: QueryProjectionPRODUCTIONLOSS.svc/PRODUCTIONLOSSSet
Data status: HTTP 200
Rows: 2627
```

That captured endpoint data shows `OrderNo` is not unique by itself:

```text
Order numbers with multiple rows: 67
Top repeated orders: 16153:9, 16226:8, 16152:6, 16280:6, 15906:5, 16154:5
```

Important examples:

```text
OrderNo 16153 appears 9 times. Rows have different PartDescription values and
different intervals, for example:
- PET0115-01..., RealStart 2025-11-03T00:09:10Z,
  RealFinished 2025-11-26T16:26:42Z, RealMachRunTime 55.9667,
  InterruptionTime 320.3167
- PET0026-01..., RealStart 2025-11-26T16:53:38Z,
  RealFinished 2025-11-26T16:53:38Z, RealMachRunTime 0,
  InterruptionTime 0
```

```text
OrderNo 16280 appears 6 times. Several rows share the same PartDescription and
operation but have separate or overlapping intervals, for example:
- RealStart 2025-11-02T23:59:43Z,
  RealFinished 2025-11-06T22:07:35Z, RealMachRunTime 825.552,
  InterruptionTime 0
- RealStart 2025-11-06T12:08:12Z,
  RealFinished 2025-11-11T11:35:39Z, RealMachRunTime 356.3977,
  InterruptionTime 0
- RealStart 2025-11-06T19:51:36Z,
  RealFinished 2025-11-07T16:35:40Z, RealMachRunTime 19.7333,
  InterruptionTime 0
```

Unfinished rows also exist:

```text
OrderNo 2635, RealStart 2026-06-03T01:29:46Z, RealFinished null,
RealMachRunTime 242.1833, InterruptionTime 49.7333

OrderNo 2758, RealStart 2026-06-13T05:02:57Z, RealFinished null,
RealMachRunTime 112, InterruptionTime 8.0333
```

Implementation implication: do not merge timing rows by `OrderNo` alone. Treat
each endpoint row as a candidate timing interval unless a stronger key is
available, such as `QueryKey`, operation, product, machine/resource, or another
IFS operation identifier. If final reporting needs one row per order/machine/day
bucket, calculate shift minutes and proportional downtime per endpoint row first,
then aggregate the resulting shift totals into the report bucket.

## Local Code References

Quick Report was confirmed from:

```text
C:\Users\Ercan ÖZKAN\Desktop\Process Project\Quick report.har
```

Machine timing endpoint references:

```text
app/integrations/ifs/client.py
  PRODUCTION_LOSS_QUERY_SELECT_FIELDS
  fetch_shop_order_operation_actual_rows()
  QueryProjectionPRODUCTIONLOSS.svc/PRODUCTIONLOSSSet

app/features/production_loss/service.py
  NET_MACHINE_DURATION_FIELDS
  RealMachRunTime handling
  shift overlap logic using actual start/finish

tests/test_ifs_client.py
  test_fetch_shop_order_operation_actual_rows_uses_production_loss_query_projection

docs/IFS_LABEL_BASED_PRODUCTION_LOSS_WORKFLOW.md
  documents QueryProjectionPRODUCTIONLOSS.svc/PRODUCTIONLOSSSet
```

## Implementation Guidance For Next Session

Use the Quick Report endpoint as the IFS production quantity source for the
shift-manager comparison. It is for validation/comparison only; it should not
automatically overwrite shift-manager production quantities. If the values
disagree, mark the mismatch for investigation and let the team decide the
correct production value.

Use `ShopFloorWorkbenchHandling.svc/Reference_ShopOperClocking` to calculate
exact elapsed machine minutes for each job order, exact `ResourceId`, and shift.
Use `OperationStatisticsHandling.svc/OperationStatistics` for operation context
and the IFS `InterruptionTime` downtime total. The likely replacement for the
full-shift assumption is:

```text
optimum production = (real_machine_minutes * 60) / realized_cycle_time_seconds * active_cavity
```

Where `real_machine_minutes` should be the net per-shift machine minutes after
proportional downtime allocation:

```text
real_machine_minutes = shift_elapsed_machine_minutes - shift_downtime_minutes
```

Use overlap minutes calculated from exact clocking `StartTime` and `FinishTime`
against each shift window for finished clocking rows. For unfinished clocking
rows where `FinishTime=null`, use `StartTime` through the end of the selected
report day.

`RealMachRunTime`, `RealStart`, and `RealFinished` from `OperationStatistics`
may still be useful for validation, but the primary machine-level shift
allocation should be calculated from exact `Reference_ShopOperClocking`
`StartTime`/`FinishTime` rows and clipped against the selected report day's
shift windows.

Exact machine timing should come from
`ShopFloorWorkbenchHandling.svc/Reference_ShopOperClocking.ResourceId` plus
`StartTime`/`FinishTime`, then be matched to Quick Report `C3_MAKINE_NO`. Do
not use `WorkCenterNo` alone as the machine key when building the final
machine-level report. `Reference_OperationHistory.ResourceId` remains useful as
a production-event validation source.

Keep the 3 percent investigation threshold unchanged unless the user asks to
change it.

## Open Points

The Quick Report data endpoint exposes exact machine number in `C3_MAKINE_NO`.
`OperationStatisticsHandling.svc/OperationStatistics` exposes `WorkCenterNo` and
`WorkCenterDesc`, but not exact `ResourceId`/machine number. The user confirmed
exact machine matching is required, so final implementation should use
`ShopFloorWorkbenchHandling.svc/Reference_ShopOperClocking` for exact machine
clocking intervals and use `Reference_OperationHistory` for production-event
validation.

Quick Report OAuth access is confirmed with the current local settings:
`QuickReports.svc/GetColumnNames(ReportId='454105')` and
`QuickReports.svc/QuickReport_454105(...)` both returned HTTP 200 on
2026-06-25.

The old custom timing projection access is not currently working with the same
OAuth context:
`QueryProjectionPRODUCTIONLOSS.svc/PRODUCTIONLOSSSet` and its `$metadata` URL
returned HTTP 404 `MI_METADATA_NOTFOUND` on 2026-06-25. It can be ignored for
now because `OperationStatisticsHandling.svc/OperationStatistics` is accessible
and provides `RealStart`, `RealFinished`, `RealMachRunTime`, and
`InterruptionTime`.

Downtime handling remains the main open decision. The options to clarify are:
use gaps between exact `Reference_ShopOperClocking` rows as exact stop windows,
or use `OperationStatistics.InterruptionTime` as the downtime total or
validation value. Also verify the exact unit and scope of `InterruptionTime`
before final implementation.

The user confirmed cross-day intervals should be clipped to the selected report
day. For example, if a machine/order spans 97 hours and the report is for one
day, the report should treat that day as 24 hours maximum, split across the
three 8-hour shifts.

The user confirmed each shift time should be rounded to whole minutes. Final
implementation still needs a balancing rule if independently rounded shift
downtime values do not sum exactly to rounded total `InterruptionTime`.

Clarify duplicate-row handling after reviewing endpoint examples with the user.
The current recommendation is to calculate each endpoint row separately, then
aggregate the calculated shift values into the final report bucket. This avoids
incorrectly merging different products/operations that share the same `OrderNo`.

Verify that `Reference_ShopOperClocking` is the authoritative exact machine
runtime source for the report. It avoids distributing work-center time across
machines because it provides exact `ResourceId`, `StartTime`, and `FinishTime`.
If a clocking row has `FinishTime=null`, cap it at the selected report day's end
for unfinished production, matching the user's confirmed rule.

Remaining downtime question: should the report use gaps between exact clocking
rows as exact downtime windows, or should it use
`OperationStatistics.InterruptionTime` as the downtime total or validation value?
