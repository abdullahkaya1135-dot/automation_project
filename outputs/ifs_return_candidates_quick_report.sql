/*
IFS Quick Report SQL: U1 iade adaylari

Purpose
-------
Return HM-02/HM-03/HM-04 stock rows in U1 that are not used by the current
planning workbook order list.

Endpoint discovery on 2026-06-29 showed:
- Latest planning workbook: 28.06.2026 CIZELGE 2.xlsx
- Visible planning orders: 71
- Shop-order lookup through ShopFloorWorkbenchHandling.GetOperations found
  operations for 71/71 Excel orders, including orders that are not active.
- 70/71 orders had HM-02/HM-03/HM-04 material lines. Order 2906 had no matching
  configured-prefix materials because it resolves to a nonstandard NMN-PET item.

Refresh instructions
--------------------
IFS Quick Report SQL cannot read the external Excel workbook directly. Refresh
the planning_orders CTE below from the visible job orders in the current planning
Excel before running the report, unless a permanent staging table is created.

View assumptions
----------------
The live OData metadata/rows map to these IFS logical units:
- InventoryPartInStock  -> INVENTORY_PART_IN_STOCK
- InventoryPart         -> INVENTORY_PART
- ShopOrderOperation    -> SHOP_ORDER_OPERATION
- ShopMaterialAlloc     -> SHOP_MATERIAL_ALLOC

If this tenant exposes an exact stock availability expression/column in Quick
Report SQL, replace the available_qty expression below with that value. The
portable fallback used here is qty_onhand - qty_reserved.
*/

WITH
planning_orders AS (
    SELECT '2840' AS order_no FROM dual UNION ALL
    SELECT '2761' AS order_no FROM dual UNION ALL
    SELECT '2769' AS order_no FROM dual UNION ALL
    SELECT '2599' AS order_no FROM dual UNION ALL
    SELECT '2813' AS order_no FROM dual UNION ALL
    SELECT '2852' AS order_no FROM dual UNION ALL
    SELECT '2606' AS order_no FROM dual UNION ALL
    SELECT '2881' AS order_no FROM dual UNION ALL
    SELECT '2697' AS order_no FROM dual UNION ALL
    SELECT '2544' AS order_no FROM dual UNION ALL
    SELECT '2464' AS order_no FROM dual UNION ALL
    SELECT '2892' AS order_no FROM dual UNION ALL
    SELECT '2826' AS order_no FROM dual UNION ALL
    SELECT '2906' AS order_no FROM dual UNION ALL
    SELECT '2854' AS order_no FROM dual UNION ALL
    SELECT '2633' AS order_no FROM dual UNION ALL
    SELECT '2911' AS order_no FROM dual UNION ALL
    SELECT '2814' AS order_no FROM dual UNION ALL
    SELECT '2937' AS order_no FROM dual UNION ALL
    SELECT '2936' AS order_no FROM dual UNION ALL
    SELECT '2812' AS order_no FROM dual UNION ALL
    SELECT '2921' AS order_no FROM dual UNION ALL
    SELECT '2829' AS order_no FROM dual UNION ALL
    SELECT '2790' AS order_no FROM dual UNION ALL
    SELECT '2820' AS order_no FROM dual UNION ALL
    SELECT '2821' AS order_no FROM dual UNION ALL
    SELECT '2780' AS order_no FROM dual UNION ALL
    SELECT '2853' AS order_no FROM dual UNION ALL
    SELECT '2822' AS order_no FROM dual UNION ALL
    SELECT '2860' AS order_no FROM dual UNION ALL
    SELECT '2912' AS order_no FROM dual UNION ALL
    SELECT '2933' AS order_no FROM dual UNION ALL
    SELECT '2874' AS order_no FROM dual UNION ALL
    SELECT '2913' AS order_no FROM dual UNION ALL
    SELECT '2841' AS order_no FROM dual UNION ALL
    SELECT '2923' AS order_no FROM dual UNION ALL
    SELECT '2925' AS order_no FROM dual UNION ALL
    SELECT '2815' AS order_no FROM dual UNION ALL
    SELECT '2938' AS order_no FROM dual UNION ALL
    SELECT '2893' AS order_no FROM dual UNION ALL
    SELECT '2816' AS order_no FROM dual UNION ALL
    SELECT '2929' AS order_no FROM dual UNION ALL
    SELECT '2823' AS order_no FROM dual UNION ALL
    SELECT '2935' AS order_no FROM dual UNION ALL
    SELECT '2808' AS order_no FROM dual UNION ALL
    SELECT '2915' AS order_no FROM dual UNION ALL
    SELECT '2747' AS order_no FROM dual UNION ALL
    SELECT '2930' AS order_no FROM dual UNION ALL
    SELECT '2931' AS order_no FROM dual UNION ALL
    SELECT '2910' AS order_no FROM dual UNION ALL
    SELECT '2914' AS order_no FROM dual UNION ALL
    SELECT '2636' AS order_no FROM dual UNION ALL
    SELECT '2638' AS order_no FROM dual UNION ALL
    SELECT '2637' AS order_no FROM dual UNION ALL
    SELECT '2740' AS order_no FROM dual UNION ALL
    SELECT '2873' AS order_no FROM dual UNION ALL
    SELECT '2932' AS order_no FROM dual UNION ALL
    SELECT '2907' AS order_no FROM dual UNION ALL
    SELECT '2882' AS order_no FROM dual UNION ALL
    SELECT '2722' AS order_no FROM dual UNION ALL
    SELECT '2553' AS order_no FROM dual UNION ALL
    SELECT '2630' AS order_no FROM dual UNION ALL
    SELECT '2758' AS order_no FROM dual UNION ALL
    SELECT '2904' AS order_no FROM dual UNION ALL
    SELECT '2934' AS order_no FROM dual UNION ALL
    SELECT '2456' AS order_no FROM dual UNION ALL
    SELECT '2802' AS order_no FROM dual UNION ALL
    SELECT '2704' AS order_no FROM dual UNION ALL
    SELECT '2027' AS order_no FROM dual UNION ALL
    SELECT '2635' AS order_no FROM dual UNION ALL
    SELECT '2647' AS order_no FROM dual
),
u1_stock AS (
    SELECT
        s.contract,
        s.part_no,
        ip.description AS material_name,
        s.location_no,
        s.lot_batch_no,
        s.serial_no,
        s.configuration_id,
        s.eng_chg_level,
        s.waiv_dev_rej_no,
        s.activity_seq,
        s.handling_unit_id,
        s.qty_onhand,
        s.qty_reserved,
        NVL(s.qty_onhand, 0) - NVL(s.qty_reserved, 0) AS available_qty,
        ip.unit_meas AS uom
    FROM inventory_part_in_stock s
    LEFT JOIN inventory_part ip
        ON ip.contract = s.contract
       AND ip.part_no = s.part_no
    WHERE s.contract = 'S01'
      AND s.location_no = 'U1'
      AND (
          s.part_no LIKE 'HM-02%'
          OR s.part_no LIKE 'HM-03%'
          OR s.part_no LIKE 'HM-04%'
      )
      AND NVL(s.qty_onhand, 0) - NVL(s.qty_reserved, 0) > 0
),
used_materials AS (
    SELECT DISTINCT
        sma.contract,
        sma.part_no,
        sma.order_no,
        sma.release_no,
        sma.sequence_no,
        sma.operation_no,
        sma.line_item_no,
        sma.issue_to_loc,
        sma.qty_required,
        sma.qty_assigned,
        sma.qty_issued,
        sma.qty_remaining_to_reserve,
        sma.qty_available,
        sma.print_unit,
        sma.so_part_no,
        soo.work_center_no,
        soo.preferred_resource_id
    FROM shop_material_alloc sma
    JOIN planning_orders po
        ON po.order_no = sma.order_no
    LEFT JOIN shop_order_operation soo
        ON soo.order_no = sma.order_no
       AND soo.release_no = sma.release_no
       AND soo.sequence_no = sma.sequence_no
       AND soo.operation_no = sma.operation_no
    WHERE sma.contract = 'S01'
      AND (
          sma.part_no LIKE 'HM-02%'
          OR sma.part_no LIKE 'HM-03%'
          OR sma.part_no LIKE 'HM-04%'
      )
)
SELECT
    s.contract,
    s.part_no,
    s.material_name,
    s.location_no,
    s.lot_batch_no,
    s.serial_no,
    s.configuration_id,
    s.eng_chg_level,
    s.waiv_dev_rej_no,
    s.activity_seq,
    s.handling_unit_id,
    s.qty_onhand,
    s.qty_reserved,
    s.available_qty,
    s.uom,
    'PLANNING_LIST_NOT_USED' AS candidate_reason
FROM u1_stock s
WHERE NOT EXISTS (
    SELECT 1
    FROM used_materials um
    WHERE um.contract = s.contract
      AND um.part_no = s.part_no
)
ORDER BY
    s.part_no,
    s.lot_batch_no,
    s.handling_unit_id
;
