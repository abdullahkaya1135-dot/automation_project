import {
  formatTimestamp,
  uniqueSorted,
} from "../utils.js?v=20260612-refactor";

export function updateShopOrderSourceStatus(source, pairs) {
  const status = document.querySelector("#shop-order-source-status");
  if (!status) {
    return;
  }

  status.classList.remove(
    "status-muted",
    "status-success",
    "status-warning",
    "status-error",
  );
  if (pairs.length > 0) {
    const orderCount = source?.order_count
      || uniqueSorted(pairs.map((pair) => pair.orderNo)).length;
    const machineCount = source?.resource_count
      || uniqueSorted(pairs.map((pair) => pair.resourceId)).length;
    const sourceLabel = source?.source === "ifs" ? "IFS" : "Dosya";
    if (source?.offline_cached_at) {
      status.textContent = `${orderCount} i\u015f emri (offline)`;
      status.title = `${sourceLabel}: ${machineCount} makine / ${pairs.length} e\u015fle\u015fme / ${formatTimestamp(source.offline_cached_at)}`;
      status.classList.add("status-warning");
      return;
    }
    status.textContent = `${orderCount} i\u015f emri`;
    status.title = `${sourceLabel}: ${machineCount} makine / ${pairs.length} e\u015fle\u015fme`;
    status.classList.add("status-success");
    return;
  }

  status.textContent = source?.source === "ifs"
    ? "IFS i\u015f emri yok"
    : "\u0130\u015f emri listesi yok";
  status.title = source?.last_error || "";
  status.classList.add("status-warning");
}
