import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const exportDir = path.resolve(scriptDir, "..");
const dataPath = path.resolve(exportDir, "ifs_inventory_shopfloor_join.json");
const desktopPath = path.join(
  process.env.USERPROFILE ?? "C:/Users/Ercan ÖZKAN",
  "Desktop",
);
const selectedJoinedColumns = [
  "MachineCode",
  "WorkCenterNo",
  "inv_DateTimeCreated",
  "inv_HandlingUnit",
  "inv_PartNo",
  "inv_PartDescription",
  "inv_LocationNo",
  "inv_Quantity",
  "inv_TransactionCodeDesc",
  "shop_OrderNo",
  "shop_QtyComplete",
  "inv_DateTimeMinuteCreated",
];

function dateSlug(summary) {
  const match = /^(\d{4}-\d{2}-\d{2}) through (\d{4}-\d{2}-\d{2})$/.exec(
    summary?.export_window ?? "",
  );
  if (!match) return "export";
  return match[1] === match[2] ? match[1] : `${match[1]}_to_${match[2]}`;
}

function columnLetter(colIndexZeroBased) {
  let n = colIndexZeroBased + 1;
  let result = "";
  while (n > 0) {
    const rem = (n - 1) % 26;
    result = String.fromCharCode(65 + rem) + result;
    n = Math.floor((n - 1) / 26);
  }
  return result;
}

function normalizeColumns(columns, priority = []) {
  const seen = new Set();
  const ordered = [];
  for (const col of priority) {
    if (columns.includes(col) && !seen.has(col)) {
      ordered.push(col);
      seen.add(col);
    }
  }
  for (const col of columns) {
    if (!seen.has(col)) {
      ordered.push(col);
      seen.add(col);
    }
  }
  return ordered;
}

function asCellValue(value, columnName) {
  if (value === undefined || value === null) return null;
  const text = String(value);
  if (
    /Date|Time|Dated|Created|Production/i.test(columnName) &&
    /^\d{4}-\d{2}-\d{2}(T.*)?/.test(text)
  ) {
    const parsed = new Date(text.includes("T") ? text : `${text}T00:00:00`);
    if (!Number.isNaN(parsed.getTime())) return parsed;
  }
  return value;
}

function matrixFromRows(rows, columns) {
  return [
    columns,
    ...rows.map((row) => columns.map((column) => asCellValue(row[column], column))),
  ];
}

function safeSheetName(name) {
  return name.slice(0, 31);
}

function writeTableSheet(workbook, sheetName, rows, columns, tableName, priority = []) {
  const sheet = workbook.worksheets.add(safeSheetName(sheetName));
  sheet.showGridLines = false;

  const orderedColumns = normalizeColumns(columns, priority);
  const matrix = rows.length ? matrixFromRows(rows, orderedColumns) : [orderedColumns];
  const rowCount = matrix.length;
  const colCount = orderedColumns.length;
  const lastCell = `${columnLetter(colCount - 1)}${rowCount}`;

  sheet.getRangeByIndexes(0, 0, rowCount, colCount).values = matrix;
  const used = sheet.getRange(`A1:${lastCell}`);
  used.format.font = { name: "Aptos", size: 10 };
  sheet.getRange(`A1:${columnLetter(colCount - 1)}1`).format = {
    fill: "#1F4E79",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
  };
  sheet.getRange(`A1:${lastCell}`).format.borders = {
    preset: "inside",
    style: "thin",
    color: "#E5E7EB",
  };
  sheet.freezePanes.freezeRows(1);

  const table = sheet.tables.add(`A1:${lastCell}`, true, tableName);
  table.style = "TableStyleMedium2";
  table.showFilterButton = true;

  for (let i = 0; i < colCount; i += 1) {
    const colName = orderedColumns[i];
    const colLetter = columnLetter(i);
    const range = sheet.getRange(`${colLetter}1:${colLetter}${rowCount}`);
    if (/Quantity|Qty|Cost|Count|Delta|Hours|Time|Id$/i.test(colName)) {
      range.format.numberFormat = "#,##0.000";
    }
    if (/DateApplied|DateCreated|Dated$/i.test(colName)) {
      range.format.numberFormat = "yyyy-mm-dd";
    }
    if (/DateTime|TimeOfProduction|TransactionDate/i.test(colName)) {
      range.format.numberFormat = "yyyy-mm-dd hh:mm";
    }
  }

  const widthByName = (name) => {
    if (/TransactionCodeDesc/i.test(name)) return 30;
    if (/DateTimeMinuteCreated/i.test(name)) return 24;
    if (/HandlingUnit/i.test(name)) return 16;
    if (/Description|JoinStatus|Source/i.test(name)) return 28;
    if (/DateTime|TimeOfProduction/i.test(name)) return 20;
    if (/PartNo|PartDescription/i.test(name)) return name.includes("Description") ? 42 : 24;
    if (/TransactionCode|WorkCenter|Resource/i.test(name)) return 18;
    return 14;
  };
  for (let i = 0; i < colCount; i += 1) {
    sheet.getRange(`${columnLetter(i)}1:${columnLetter(i)}${rowCount}`).format.columnWidth =
      widthByName(orderedColumns[i]);
  }

  return sheet;
}

function writeSummary(workbook, summary) {
  const sheet = workbook.worksheets.add("Summary");
  sheet.showGridLines = false;
  sheet.getRange("A1:H1").merge();
  sheet.getRange("A1").values = [["IFS MM Inventory Transactions With Machine Code"]];
  sheet.getRange("A1").format = {
    fill: "#17365D",
    font: { bold: true, color: "#FFFFFF", size: 16 },
  };

  const rows = [
    ["Export window", summary.export_window],
    ["Contract", summary.contract],
    ["Inventory rows", summary.inventory_row_count],
    ["Shop-floor rows", summary.shopfloor_row_count],
    ["Joined rows", summary.joined_row_count],
    ["Matched with machine/resource", summary.matched_with_resource_count],
    ["Unmatched inventory rows", summary.unmatched_count],
    ["Export started", summary.export_started_at],
    ["Inventory source", `${summary.inventory_projection}.svc/${summary.inventory_entity}`],
    ["Shop-floor source", `${summary.shop_projection}.svc/${summary.shop_entity}`],
  ];
  sheet.getRange(`A3:B${rows.length + 2}`).values = rows;
  sheet.getRange("A3:A12").format = {
    fill: "#D9EAF7",
    font: { bold: true },
  };
  sheet.getRange("B3:B12").format = { fill: "#F8FBFD" };
  sheet.getRange("A3:B12").format.borders = {
    preset: "all",
    style: "thin",
    color: "#CBD5E1",
  };
  sheet.getRange("A14:H14").merge();
  sheet.getRange("A14").values = [["Join rule"]];
  sheet.getRange("A14").format = {
    fill: "#1F4E79",
    font: { bold: true, color: "#FFFFFF" },
  };
  sheet.getRange("A15:H17").merge();
  sheet.getRange("A15").values = [[summary.join_rule]];
  sheet.getRange("A15").format = { wrapText: true, fill: "#F8FBFD" };
  sheet.getRange("A15:H17").format.borders = {
    preset: "outside",
    style: "thin",
    color: "#CBD5E1",
  };
  sheet.getRange("A19:H19").merge();
  sheet.getRange("A19").values = [[
    "Rows are filtered at source to inv_PartNo starting MM-. The joined sheet includes the selected inventory and shop-floor columns requested for the machine-code view.",
  ]];
  sheet.getRange("A19").format = { wrapText: true, fill: "#FFF7ED" };
  sheet.getRange("B10").format.numberFormat = "yyyy-mm-dd hh:mm";
  sheet.getRange("A:A").format.columnWidth = 30;
  sheet.getRange("B:B").format.columnWidth = 58;
  sheet.getRange("C:H").format.columnWidth = 18;
}

const raw = JSON.parse(await fs.readFile(dataPath, "utf8"));
const outputPath = path.join(
  desktopPath,
  `IFS_MM_Inventory_Transactions_With_Machine_${dateSlug(raw.summary)}.xlsx`,
);
const workbook = Workbook.create();

writeSummary(workbook, raw.summary);
writeTableSheet(
  workbook,
  "Joined Inventory History",
  raw.joined_rows,
  selectedJoinedColumns,
  "JoinedInventoryHistory",
  selectedJoinedColumns,
);

const sheetInspect = await workbook.inspect({
  kind: "sheet",
  maxChars: 2000,
});
console.log(sheetInspect.ndjson);

const regionInspect = await workbook.inspect({
  kind: "region",
  sheetId: "Joined Inventory History",
  range: "A1:L5",
  maxChars: 3000,
});
console.log(regionInspect.ndjson);

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 50 },
  summary: "formula error scan",
});
console.log(errors.ndjson);

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
let savedPath = outputPath;
try {
  await xlsx.save(savedPath);
} catch (error) {
  if (!["EBUSY", "EPERM"].includes(error?.code)) {
    throw error;
  }
  savedPath = outputPath.replace(/\.xlsx$/i, "_updated.xlsx");
  await xlsx.save(savedPath);
}
console.log(`Saved ${savedPath}`);
