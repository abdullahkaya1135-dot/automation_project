import {
  cleanOptional,
  compareOptionText,
  uniqueSorted,
} from "./utils.js?v=20260629-label-material-availability-v1";

export function machineOptionsFromBootstrap(machines, shopOrderSource) {
  let machineOptions = normalizeMachineOptions(machines);
  if (!machineOptions.length) {
    machineOptions = uniqueSorted(
      normalizeShopOrderOptions(shopOrderSource?.options).map(
        (option) => option.resourceId,
      ),
    ).map((machineCode) => ({ machineCode, label: machineCode }));
  }
  machineOptions.sort((left, right) => (
    compareOptionText(left.machineCode, right.machineCode)
  ));
  return machineOptions;
}

export function normalizeMachineOptions(machines) {
  if (!Array.isArray(machines)) {
    return [];
  }
  const seen = new Set();
  const normalized = [];
  for (const machine of machines) {
    const machineCode = cleanOptional(machine?.machine_code);
    if (!machineCode || seen.has(machineCode)) {
      continue;
    }
    seen.add(machineCode);
    const hallName = cleanOptional(machine?.hall_name);
    normalized.push({
      machineCode,
      label: hallName ? `${machineCode} / ${hallName}` : machineCode,
    });
  }
  return normalized;
}

export function normalizeShopOrderOptions(options) {
  if (!Array.isArray(options)) {
    return [];
  }
  const seen = new Set();
  const normalized = [];
  for (const option of options) {
    const orderNo = cleanOptional(option?.order_no);
    const resourceId = cleanOptional(option?.resource_id);
    if (!orderNo || !resourceId) {
      continue;
    }
    const releaseNo = cleanOptional(option?.release_no) || "*";
    const sequenceNo = cleanOptional(option?.sequence_no) || "*";
    const rawOperationNo = option?.operation_no == null ? null : Number(option.operation_no);
    const operationNo = Number.isFinite(rawOperationNo) ? rawOperationNo : null;
    const key = `${resourceId}\u0000${orderNo}\u0000${releaseNo}\u0000${sequenceNo}\u0000${operationNo ?? ""}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    normalized.push({
      key,
      orderNo,
      resourceId,
      releaseNo,
      sequenceNo,
      operationNo,
      partNo: cleanOptional(option?.part_no),
      partDescription: cleanOptional(option?.part_description),
    });
  }
  normalized.sort((left, right) => {
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
  return normalized;
}

export function shopOrderProductText(option) {
  if (!option) {
    return "";
  }
  if (option.partNo && option.partDescription?.startsWith(option.partNo)) {
    return option.partDescription;
  }
  return [option.partNo, option.partDescription].filter(Boolean).join(" - ");
}
