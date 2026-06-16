import { downloadTextFile } from "../utils.js?v=20260612-refactor";
import { getAllOfflineRecords } from "./outbox-db.js?v=20260616-offline-split";

export async function exportOfflineOutbox(format) {
  const records = await getAllOfflineRecords();
  if (format === "csv") {
    downloadTextFile("telefon-bekleyen-kayitlar.csv", offlineRecordsCsv(records), "text/csv");
    return;
  }
  downloadTextFile(
    "telefon-bekleyen-kayitlar.json",
    JSON.stringify(records, null, 2),
    "application/json",
  );
}

function offlineRecordsCsv(records) {
  const rows = [
    [
      "client_request_id",
      "type",
      "status",
      "attempt_count",
      "server_id",
      "created_at",
      "updated_at",
      "last_error",
      "body_json",
    ],
    ...records.map((record) => [
      record.client_request_id,
      record.type,
      record.status,
      record.attempt_count,
      record.server_id,
      record.created_at,
      record.updated_at,
      record.last_error,
      JSON.stringify(record.body || {}),
    ]),
  ];
  return rows.map((row) => row.map(csvCell).join(",")).join("\n");
}

function csvCell(value) {
  const text = value == null ? "" : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}
