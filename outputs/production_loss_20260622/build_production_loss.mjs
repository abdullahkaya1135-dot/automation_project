import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const __filename = fileURLToPath(import.meta.url);
const outputDir = path.dirname(__filename);
const rawPath = path.join(outputDir, "production_loss_raw.json");
const xlsxPath = path.join(outputDir, "production_loss.xlsx");

const rawText = (await fs.readFile(rawPath, "utf8")).replace(/^\uFEFF/, "");
const payload = JSON.parse(rawText);
const rows = Array.isArray(payload.data) ? payload.data : [];
const meta = payload.meta ?? {};

const headers = [
  "OrderNo",
  "PartDescription",
  "RealFinished",
  "RealMachRunTime",
  "RealStart",
  "InterruptionTime",
  "OperationDesc",
  "keyref",
  "QueryKey",
  "luname",
];

function maybeDate(value) {
  if (typeof value !== "string") return value ?? null;
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(value)) return value;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed;
}

function rowToValues(row) {
  return headers.map((header) => {
    const value = row?.[header];
    if (header === "RealFinished" || header === "RealStart") return maybeDate(value);
    return value ?? null;
  });
}

function colLetter(index) {
  let n = index + 1;
  let s = "";
  while (n > 0) {
    const r = (n - 1) % 26;
    s = String.fromCharCode(65 + r) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

const workbook = Workbook.create();
workbook.comments.setSelf({ displayName: "User" });

const summary = workbook.worksheets.add("Summary");
const dataSheet = workbook.worksheets.add("Production Loss");
summary.showGridLines = false;
dataSheet.showGridLines = false;

summary.getRange("A1:F1").merge();
summary.getRange("A1").values = [["Production Loss Export"]];
summary.getRange("A1").format = {
  fill: "#17324D",
  font: { bold: true, color: "#FFFFFF", size: 16 },
};
summary.getRange("A1").format.rowHeight = 32;

summary.getRange("A3:B13").values = [
  ["Rows returned", meta.rowCount ?? rows.length],
  ["Data request elapsed (ms)", meta.dataElapsedMs ?? null],
  ["Token request elapsed (ms)", meta.tokenElapsedMs ?? null],
  ["Total elapsed (ms)", meta.totalElapsedMs ?? null],
  ["Payload bytes", meta.bytes ?? null],
  ["IFS request ID", meta.ifsRequestId ?? ""],
  ["Fetched at", maybeDate(meta.fetchedAt) ?? ""],
  ["Status code", meta.dataStatusCode ?? ""],
  ["Has next link", meta.hasNextLink ? "Yes" : "No"],
  ["Endpoint", meta.endpoint ?? ""],
  ["Next link", meta.nextLink ?? ""],
];
summary.getRange("A3:A13").format = {
  fill: "#E8EEF4",
  font: { bold: true, color: "#17324D" },
};
summary.getRange("A3:B13").format.borders = {
  preset: "inside",
  style: "thin",
  color: "#C7D2DE",
};
summary.getRange("A3:B13").format.borders = {
  preset: "outside",
  style: "thin",
  color: "#8EA4B8",
};
summary.getRange("B3").format.numberFormat = "#,##0";
summary.getRange("B4:B6").format.numberFormat = "0.00";
summary.getRange("B7").format.numberFormat = "#,##0";
summary.getRange("B9").format.numberFormat = "yyyy-mm-dd hh:mm";
summary.getRange("B10").format.numberFormat = "0";
summary.getRange("B3:B10").format = { horizontalAlignment: "right" };
summary.getRange("A16:F16").merge();
summary.getRange("A16").values = [["The Production Loss sheet contains the full OData result as a filterable Excel table."]];
summary.getRange("A16").format = {
  fill: "#F7F9FB",
  font: { color: "#334155" },
  wrapText: true,
};
summary.getRange("A:A").format.columnWidth = 28;
summary.getRange("B:B").format.columnWidth = 96;
summary.freezePanes.freezeRows(1);

const matrix = [headers, ...rows.map(rowToValues)];
const lastRow = Math.max(matrix.length, 1);
const lastCol = headers.length;
const lastColumnLetter = colLetter(lastCol - 1);

dataSheet.getRangeByIndexes(0, 0, matrix.length, lastCol).values = matrix;
dataSheet.getRange(`A1:${lastColumnLetter}1`).format = {
  fill: "#17324D",
  font: { bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
};

if (rows.length > 0) {
  const tableRange = `A1:${lastColumnLetter}${lastRow}`;
  const table = dataSheet.tables.add(tableRange, true, "ProductionLossTable");
  table.style = "TableStyleMedium2";
  table.showFilterButton = true;
  table.showBandedRows = true;
  dataSheet.getRange(`C2:C${lastRow}`).format.numberFormat = "yyyy-mm-dd hh:mm";
  dataSheet.getRange(`E2:E${lastRow}`).format.numberFormat = "yyyy-mm-dd hh:mm";
  dataSheet.getRange(`D2:D${lastRow}`).format.numberFormat = "0.00";
  dataSheet.getRange(`F2:F${lastRow}`).format.numberFormat = "0.00";
  dataSheet.getRange(`A2:A${lastRow}`).format.numberFormat = "@";
  dataSheet.getRange(`I2:I${lastRow}`).format.numberFormat = "@";
}

dataSheet.freezePanes.freezeRows(1);
dataSheet.getRange("A:A").format.columnWidth = 13;
dataSheet.getRange("B:B").format.columnWidth = 48;
dataSheet.getRange("C:C").format.columnWidth = 19;
dataSheet.getRange("D:D").format.columnWidth = 17;
dataSheet.getRange("E:E").format.columnWidth = 19;
dataSheet.getRange("F:F").format.columnWidth = 16;
dataSheet.getRange("G:G").format.columnWidth = 28;
dataSheet.getRange("H:H").format.columnWidth = 42;
dataSheet.getRange("I:I").format.columnWidth = 16;
dataSheet.getRange("J:J").format.columnWidth = 13;
dataSheet.getRange(`A1:${lastColumnLetter}${Math.min(lastRow, 100)}`).format.wrapText = false;

const sourceThread = workbook.comments.addThread(
  { cell: summary.getRange("B12") },
  `Source URL: ${meta.endpoint ?? ""}`,
);
sourceThread.resolve();

const overview = await workbook.inspect({
  kind: "workbook,sheet,table",
  maxChars: 4000,
  tableMaxRows: 3,
  tableMaxCols: 10,
});
console.log(overview.ndjson);

const formulaErrors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
  maxChars: 2000,
});
console.log(formulaErrors.ndjson);

const summaryPreview = await workbook.render({
  sheetName: "Summary",
  autoCrop: "all",
  scale: 1,
  format: "png",
});
await fs.writeFile(
  path.join(outputDir, "summary_preview.png"),
  new Uint8Array(await summaryPreview.arrayBuffer()),
);

const dataPreview = await workbook.render({
  sheetName: "Production Loss",
  range: "A1:J25",
  scale: 1,
  format: "png",
});
await fs.writeFile(
  path.join(outputDir, "production_loss_preview.png"),
  new Uint8Array(await dataPreview.arrayBuffer()),
);

await fs.mkdir(outputDir, { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(xlsxPath);
console.log(`Saved ${xlsxPath}`);
