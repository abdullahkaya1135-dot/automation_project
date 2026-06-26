import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const dataPath = path.join(__dirname, "cycle_time_analysis_data.json");
const outputPath = "C:\\Users\\Ercan ÖZKAN\\Desktop\\cycle time analysis.xlsx";
const fallbackOutputPath = "C:\\Users\\Ercan ÖZKAN\\Desktop\\cycle time analysis db included.xlsx";
const previewDir = path.join(__dirname, "previews");

const payload = JSON.parse(await fs.readFile(dataPath, "utf8"));

function colName(index) {
  let n = index + 1;
  let name = "";
  while (n > 0) {
    const rem = (n - 1) % 26;
    name = String.fromCharCode(65 + rem) + name;
    n = Math.floor((n - 1) / 26);
  }
  return name;
}

function rangeAddress(rowCount, colCount) {
  return `A1:${colName(colCount - 1)}${rowCount}`;
}

function writeTable(sheet, headers, rows, tableName, widths = []) {
  const matrix = [headers, ...rows];
  sheet.getRange(rangeAddress(matrix.length, headers.length)).values = matrix;
  const headerRange = sheet.getRange(`A1:${colName(headers.length - 1)}1`);
  headerRange.format = {
    fill: "#174A5C",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
    verticalAlignment: "center",
  };
  headerRange.format.borders = { preset: "outside", style: "thin", color: "#0F3340" };
  const bodyRange = sheet.getRange(`A2:${colName(headers.length - 1)}${matrix.length}`);
  bodyRange.format = {
    font: { color: "#111827" },
    wrapText: false,
  };
  bodyRange.format.borders = {
    insideHorizontal: { style: "thin", color: "#E5E7EB" },
    top: { style: "thin", color: "#CBD5E1" },
    bottom: { style: "thin", color: "#CBD5E1" },
  };
  sheet.tables.add(rangeAddress(matrix.length, headers.length), true, tableName);
  sheet.freezePanes.freezeRows(1);
  sheet.showGridLines = false;
  widths.forEach((width, idx) => {
    if (width) {
      sheet.getRangeByIndexes(0, idx, matrix.length, 1).format.columnWidth = width;
    }
  });
  return matrix.length;
}

function roundOrBlank(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return "";
  if (typeof value !== "number") return value;
  return Number(value.toFixed(digits));
}

function numberFormat(sheet, colIndex, rowCount, format) {
  if (rowCount < 2) return;
  sheet.getRangeByIndexes(1, colIndex, rowCount - 1, 1).format.numberFormat = format;
}

function text(value) {
  return value === null || value === undefined ? "" : String(value);
}

function mouth(row) {
  return row["Ağız"] ?? row["ağız"] ?? "";
}

function countUsable(sourceType) {
  return payload.observations.filter((row) => row.source_type === sourceType && row.status === "Usable").length;
}

const workbook = Workbook.create();

const readme = workbook.worksheets.add("Read Me");
readme.showGridLines = false;
readme.getRange("A1:H1").merge();
readme.getRange("A1").values = [["Cycle Time Analysis"]];
readme.getRange("A1").format = {
  fill: "#174A5C",
  font: { bold: true, color: "#FFFFFF", size: 16 },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
readme.getRange("A1").format.rowHeight = 28;

const readmeRows = [
  ["Original source", payload.metadata.original_source_path],
  ["Working copy", payload.metadata.source_path],
  ["Process DB", payload.metadata.database_path],
  ["Requested rows", payload.metadata.requested_rows],
  ["Selected source sheet", payload.metadata.source_sheet],
  ["Old workbook observations", payload.metadata.workbook_observation_count],
  ["Process DB observations", payload.metadata.database_observation_count],
  ["Total observations", payload.metadata.observation_count],
  ["Machine/Ağız/Gramaj groups", payload.metadata.group_count],
  ["Current DB optimum rows", payload.metadata.cycle_table_row_count ?? ""],
  ["Exact DB optimum matches", payload.metadata.db_optimum_exact_match_count ?? ""],
  ["Ambiguous exact DB matches", payload.metadata.db_optimum_exact_ambiguous_count ?? ""],
  ["No exact DB match", payload.metadata.db_optimum_no_exact_match_count ?? ""],
  ["Missing machine group", payload.metadata.db_optimum_machine_group_missing_count ?? ""],
  ["Cycle column", "L = Çevrim Süresi (sn). Columns/fields J and K are total/active cavity counts."],
  [
    "Row-range note",
    `Requested rows ${payload.metadata.requested_rows} are not present in this saved workbook. Largest sheet ends at row ${payload.metadata.max_workbook_row}; analysis uses the sheet where columns F/G/J/K/L match the requested fields, plus process rows from the SQLite DB.`,
  ],
  [
    "Parsing",
    "Ağız is parsed from the first number before MM in product text. Gramaj is parsed from the first number before GR.",
  ],
  ["Recommendation method", payload.metadata.method],
  [
    "Outlier bounds",
    `Global robust cycle range used before group checks: ${payload.metadata.global_outlier_lower} to ${payload.metadata.global_outlier_upper} seconds.`,
  ],
  [
    "Confidence",
    "High = usable n >= 4 and CV <= 5%; Medium = usable n >= 3 and CV <= 10%; otherwise Low.",
  ],
];
readme.getRange(`A3:B${readmeRows.length + 2}`).values = readmeRows;
readme.getRange(`A3:A${readmeRows.length + 2}`).format = {
  fill: "#E7F1F5",
  font: { bold: true, color: "#153947" },
  wrapText: true,
};
readme.getRange(`B3:B${readmeRows.length + 2}`).format = {
  wrapText: true,
  verticalAlignment: "top",
};
readme.getRange(`A3:B${readmeRows.length + 2}`).format.borders = {
  preset: "all",
  style: "thin",
  color: "#D8E3E8",
};
readme.getRange("A:A").format.columnWidth = 28;
readme.getRange("B:B").format.columnWidth = 118;

const recSheet = workbook.worksheets.add("Recommendations");
const recommendationHeaders = [
  "Machine Code",
  "Machine Group",
  "Ağız (mm)",
  "Gramaj (gr)",
  "Recommended Cycle (sec)",
  "DB Optimum Cycle (sec)",
  "Recommended - DB Optimum (sec)",
  "Recommended vs DB Optimum %",
  "DB Match Status",
  "DB Source Rows",
  "Diagnostic Optimum (sec)",
  "Diagnostic Status",
  "Raw n",
  "Usable n",
  "Removed n",
  "Workbook n",
  "DB n",
  "Confidence",
  "Raw Min",
  "Raw Median",
  "Raw Mean",
  "Raw Max",
  "Usable Min",
  "Usable Mean",
  "Usable Max",
  "Usable Stdev",
  "Usable CV",
  "Source Refs",
  "Note",
  "Products Observed",
];
const recommendationRows = payload.summaries.map((row) => [
  row.machine_code,
  row.machine_group,
  mouth(row),
  row.gramaj,
  roundOrBlank(row.recommended_cycle_sec),
  roundOrBlank(row.db_optimum_cycle_sec),
  roundOrBlank(row.db_optimum_delta_sec),
  row.db_optimum_delta_percent ?? "",
  row.db_optimum_match_status,
  row.db_optimum_source_rows,
  roundOrBlank(row.diagnostic_optimum_cycle_sec),
  row.diagnostic_match_status,
  row.raw_sample_size,
  row.usable_sample_size,
  row.removed_sample_size,
  row.workbook_sample_size,
  row.database_sample_size,
  row.confidence,
  roundOrBlank(row.raw_min),
  roundOrBlank(row.raw_median),
  roundOrBlank(row.raw_mean),
  roundOrBlank(row.raw_max),
  roundOrBlank(row.usable_min),
  roundOrBlank(row.usable_mean),
  roundOrBlank(row.usable_max),
  roundOrBlank(row.usable_stdev),
  roundOrBlank(row.usable_cv, 4),
  row.source_rows,
  row.note,
  row.products_observed,
]);
const recRows = writeTable(
  recSheet,
  recommendationHeaders,
  recommendationRows,
  "RecommendationsTable",
  [13, 15, 10, 11, 18, 18, 22, 18, 18, 46, 18, 22, 9, 10, 10, 11, 9, 12, 10, 12, 11, 10, 11, 12, 11, 12, 10, 34, 22, 64],
);
for (const col of [4, 5, 6, 10, 18, 19, 20, 21, 22, 23, 24, 25]) numberFormat(recSheet, col, recRows, "0.00");
for (const col of [7, 26]) numberFormat(recSheet, col, recRows, "0.0%");
recSheet.getRangeByIndexes(1, 8, Math.max(recRows - 1, 1), 4).format.wrapText = true;
recSheet.getRangeByIndexes(1, 27, Math.max(recRows - 1, 1), 3).format.wrapText = true;

const dbCompareSheet = workbook.worksheets.add("DB Optimum Comparison");
const dbCompareHeaders = [
  "Machine Group",
  "Machine Code",
  "Ağız (mm)",
  "Gramaj (gr)",
  "Recommended Cycle (sec)",
  "DB Optimum Cycle (sec)",
  "Delta (sec)",
  "Delta %",
  "Match Status",
  "Diagnostic Optimum (sec)",
  "Diagnostic Status",
  "Confidence",
  "Usable n",
  "Note",
  "Products Observed",
];
const dbCompareRows = payload.summaries.map((row) => [
  row.machine_group,
  row.machine_code,
  mouth(row),
  row.gramaj,
  roundOrBlank(row.recommended_cycle_sec),
  roundOrBlank(row.db_optimum_cycle_sec),
  roundOrBlank(row.db_optimum_delta_sec),
  row.db_optimum_delta_percent ?? "",
  row.db_optimum_match_status,
  roundOrBlank(row.diagnostic_optimum_cycle_sec),
  row.diagnostic_match_status,
  row.confidence,
  row.usable_sample_size,
  row.note,
  row.products_observed,
]);
const dbCompareRowCount = writeTable(
  dbCompareSheet,
  dbCompareHeaders,
  dbCompareRows,
  "DbOptimumComparisonTable",
  [15, 13, 10, 11, 18, 18, 12, 11, 20, 18, 22, 12, 10, 22, 64],
);
for (const col of [4, 5, 6, 9]) numberFormat(dbCompareSheet, col, dbCompareRowCount, "0.00");
numberFormat(dbCompareSheet, 7, dbCompareRowCount, "0.0%");
dbCompareSheet.getRangeByIndexes(1, 8, Math.max(dbCompareRowCount - 1, 1), 7).format.wrapText = true;

const obsSheet = workbook.worksheets.add("Observations");
const observationHeaders = [
  "Source Type",
  "Source Sheet",
  "Source Row / DB ID",
  "Process Date",
  "Work Order",
  "Machine Code",
  "Product",
  "Ağız (mm)",
  "Gramaj (gr)",
  "Total Cavities",
  "Active Cavities",
  "Cycle Time (sec)",
  "Status",
  "Flag Reason",
  "Group Key",
];
const observationRows = payload.observations.map((row) => [
  row.source_type,
  row.source_sheet,
  row.source_row,
  row.process_date,
  row.work_order,
  row.machine_code,
  row.product,
  mouth(row),
  row.gramaj,
  row.total_cavities,
  row.active_cavities,
  roundOrBlank(row.cycle_time_sec),
  row.status,
  row.flag_reason,
  row.group_key,
]);
const obsRows = writeTable(
  obsSheet,
  observationHeaders,
  observationRows,
  "ObservationsTable",
  [15, 18, 15, 12, 12, 13, 66, 10, 11, 13, 13, 15, 12, 48, 24],
);
numberFormat(obsSheet, 11, obsRows, "0.00");
obsSheet.getRange(`G2:G${obsRows}`).format.wrapText = true;
obsSheet.getRange(`N2:N${obsRows}`).format.wrapText = true;

const issueSheet = workbook.worksheets.add("Data Issues");
const issueHeaders = [
  "Issue Type",
  "Source Type",
  "Source Sheet",
  "Source Row / DB ID",
  "Process Date",
  "Work Order",
  "Machine Code",
  "Ağız (mm)",
  "Gramaj (gr)",
  "Cycle Time (sec)",
  "Reason",
  "Product",
];
const issueRows = payload.issues.map((row) => [
  row.issue_type,
  text(row.source_type),
  text(row.source_sheet),
  text(row.source_row),
  text(row.process_date),
  text(row.work_order),
  text(row.machine_code),
  mouth(row),
  row.gramaj ?? "",
  roundOrBlank(row.cycle_time_sec),
  row.reason,
  row.product ?? "",
]);
const issueRowCount = writeTable(
  issueSheet,
  issueHeaders,
  issueRows,
  "DataIssuesTable",
  [26, 14, 18, 15, 12, 12, 13, 10, 11, 15, 72, 64],
);
numberFormat(issueSheet, 9, issueRowCount, "0.00");
issueSheet.getRange(`K2:L${issueRowCount}`).format.wrapText = true;

const issueCount = Math.max(0, payload.issues.length - 1);
const summary = workbook.worksheets.add("Summary");
summary.showGridLines = false;
summary.getRange("A1:H1").merge();
summary.getRange("A1").values = [["Cycle Time Summary"]];
summary.getRange("A1").format = {
  fill: "#174A5C",
  font: { bold: true, color: "#FFFFFF", size: 15 },
  horizontalAlignment: "center",
};
const summaryRows = [
  ["Usable observations", payload.observations.filter((row) => row.status === "Usable").length],
  ["Excluded observations", payload.observations.filter((row) => row.status === "Excluded").length],
  ["Old workbook usable", countUsable("Old Workbook")],
  ["Process DB usable", countUsable("Process DB")],
  ["Recommendation groups", payload.summaries.length],
  ["Groups needing verification", payload.summaries.filter((row) => row.confidence === "Low").length],
  ["Exact DB optimum matches", payload.metadata.db_optimum_exact_match_count ?? 0],
  ["Ambiguous exact DB matches", payload.metadata.db_optimum_exact_ambiguous_count ?? 0],
  ["No exact DB match", payload.metadata.db_optimum_no_exact_match_count ?? 0],
  ["Missing machine group", payload.metadata.db_optimum_machine_group_missing_count ?? 0],
  ["Data issue rows listed", issueCount],
];
const summaryEndRow = summaryRows.length + 2;
summary.getRange(`A3:B${summaryEndRow}`).values = summaryRows;
summary.getRange(`A3:A${summaryEndRow}`).format = { fill: "#E7F1F5", font: { bold: true, color: "#153947" } };
summary.getRange(`B3:B${summaryEndRow}`).format.numberFormat = "#,##0";
summary.getRange(`A3:B${summaryEndRow}`).format.borders = { preset: "all", style: "thin", color: "#D8E3E8" };
summary.getRange("D3:F3").values = [["Confidence", "Groups", "Share"]];
const confidenceLevels = ["High", "Medium", "Low"];
const confidenceRows = confidenceLevels.map((level) => {
  const count = payload.summaries.filter((row) => row.confidence === level).length;
  return [level, count, payload.summaries.length ? count / payload.summaries.length : 0];
});
summary.getRange("D4:F6").values = confidenceRows;
summary.getRange("D3:F3").format = { fill: "#174A5C", font: { bold: true, color: "#FFFFFF" } };
summary.getRange("F4:F6").format.numberFormat = "0.0%";
summary.getRange("D3:F6").format.borders = { preset: "all", style: "thin", color: "#D8E3E8" };
summary.getRange("A:A").format.columnWidth = 28;
summary.getRange("B:B").format.columnWidth = 14;
summary.getRange("D:D").format.columnWidth = 14;
summary.getRange("E:F").format.columnWidth = 12;

await fs.mkdir(previewDir, { recursive: true });
const previewSpecs = [
  ["Summary", undefined],
  ["Read Me", undefined],
  ["Recommendations", `A1:AD${Math.min(recRows, 60)}`],
  ["DB Optimum Comparison", `A1:O${Math.min(dbCompareRowCount, 80)}`],
  ["Observations", `A1:O${Math.min(obsRows, 80)}`],
  ["Data Issues", `A1:L${Math.min(issueRowCount, 80)}`],
];
for (const [sheetName, range] of previewSpecs) {
  const preview = await workbook.render({
    sheetName,
    range,
    autoCrop: "all",
    scale: 1,
    format: "png",
  });
  const safeName = sheetName.replace(/[^a-z0-9]+/gi, "_").toLowerCase();
  await fs.writeFile(path.join(previewDir, `${safeName}.png`), new Uint8Array(await preview.arrayBuffer()));
}

const inspect = await workbook.inspect({
  kind: "table",
  range: "Recommendations!A1:AD12",
  include: "values",
  tableMaxRows: 12,
  tableMaxCols: 30,
  maxChars: 10000,
});
await fs.writeFile(path.join(__dirname, "recommendations_inspect.ndjson"), inspect.ndjson, "utf8");

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
});
await fs.writeFile(path.join(__dirname, "formula_error_scan.ndjson"), errors.ndjson, "utf8");

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
let savedPath = outputPath;
try {
  await xlsx.save(outputPath);
} catch (error) {
  if (error?.code !== "EBUSY") {
    throw error;
  }
  savedPath = fallbackOutputPath;
  await xlsx.save(fallbackOutputPath);
}

console.log(JSON.stringify({
  outputPath: savedPath,
  previewDir,
  recommendations: payload.summaries.length,
  observations: payload.observations.length,
  databaseObservations: payload.metadata.database_observation_count,
  exactDbOptimumMatches: payload.metadata.db_optimum_exact_match_count,
  noExactDbOptimumMatches: payload.metadata.db_optimum_no_exact_match_count,
}, null, 2));
