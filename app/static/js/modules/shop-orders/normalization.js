import {
  cleanOptional,
  compareOptionText,
} from "../utils.js?v=20260612-refactor";

export function normalizeShopOrderPairs(options) {
  if (!Array.isArray(options)) {
    return [];
  }

  const seen = new Set();
  const pairs = [];
  for (const option of options) {
    const orderNo = cleanOptional(option?.order_no);
    const resourceId = cleanOptional(option?.resource_id);
    if (!orderNo || !resourceId) {
      continue;
    }

    const releaseNo = cleanOptional(option?.release_no) || "*";
    const sequenceNo = cleanOptional(option?.sequence_no) || "*";
    const rawOperationNo = option?.operation_no == null
      ? null
      : Number(option.operation_no);
    const operationNo = Number.isFinite(rawOperationNo) ? rawOperationNo : null;
    const partNo = cleanOptional(option?.part_no);
    const partDescription = cleanOptional(option?.part_description);
    const key = `${orderNo}\u0000${resourceId}\u0000${releaseNo}\u0000${sequenceNo}\u0000${operationNo ?? ""}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    pairs.push({
      key,
      orderNo,
      resourceId,
      releaseNo,
      sequenceNo,
      operationNo,
      partNo,
      partDescription,
    });
  }

  pairs.sort((left, right) => {
    const machineComparison = compareOptionText(left.resourceId, right.resourceId);
    if (machineComparison) {
      return machineComparison;
    }
    const orderComparison = compareOptionText(left.orderNo, right.orderNo);
    if (orderComparison) {
      return orderComparison;
    }
    return (left.operationNo || 0) - (right.operationNo || 0);
  });
  return pairs;
}
