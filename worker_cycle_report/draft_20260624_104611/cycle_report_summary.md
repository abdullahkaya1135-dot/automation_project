# Cycle-Time Analysis Draft

Source workbook: `\\fileserver\PRODUCTION\ÜRETİM RAPOR FK\PROSES-YARDIMCI SİSTEMLER\PROSES 2026_FK.xlsx`
Requested rows: `1498:1867` (370 rows), columns `F, G, J, K, L`.

## Workbook Availability

| Sheet | Max row | Max column | Requested row start present? | Requested row end present? |
|---|---:|---:|---|---|
| FK_ÜRÜN_ÇEVRİM _DETAY | 90 | 31 | no | no |
| PROSES ENJEKSİYON | 83 | 25 | no | no |
| FK_ÜRÜN_ÇEVRİM | 47 | 19 | no | no |
| salon 2 | 23 | 19 | no | no |
| salon 1 | 24 | 19 | no | no |
| FK_ÇEVRİM  | 46 | 12 | no | no |
| ESKİ | 1482 | 26 | no | no |
| Form | 46 | 19 | no | no |
| Sayfa1 | 4 | 2 | no | no |
| Sayfa2 | 135 | 12 | no | no |

## Scope Result

- Requested range nonblank rows found: 0.
- No worksheet in this workbook reaches row 1867; the largest sheet is `ESKİ` at row 1482.
- Candidate fallback analyzed here: `ESKİ!1113:1482`. This is the latest 370 rows on the largest sheet and is labeled as fallback, not as a silent replacement.
- Schema-match fallback analyzed here: `PROSES ENJEKSİYON`. This is the only sheet where column F/G/J/K/L match the requested machine/product/cycle schema and column G contains both `MM` and `GR`.

## Candidate Data Profile

- Candidate rows with any requested-column data: 352.
- Rows with machine code plus parsed agiz_mm and gramaj_gr: 0.
- Numeric observations across J/K/L: 1056.
- Numeric observations in L only: 352.
- Groups produced from J/K/L: 0.
- Groups produced from L only: 0.

Schema-match fallback profile:

- Rows with any requested-column data: 82.
- Rows with machine code plus parsed agiz_mm and gramaj_gr: 81.
- Numeric observations across J/K/L: 242.
- Numeric observations in L only: 81.
- Groups produced from J/K/L: 38.
- Groups produced from L only: 38.

Parse status counts:

| Parse status | Rows |
|---|---:|
| missing_agiz_mm_gramaj_gr | 199 |
| missing_gramaj_gr | 152 |
| missing_agiz_mm | 1 |

## Method

- Product text in column G is parsed with regex patterns for `<number>MM` and `<number>GR`; comma decimals such as `5,5GR` are normalized to `5.5`.
- Rows are grouped by machine code from F plus parsed agiz_mm and gramaj_gr.
- Numeric positive values are converted from the selected observation columns.
- For each group, outliers are removed with a Tukey IQR 1.5x filter when sample size is at least 4 and IQR is nonzero. If IQR cannot estimate spread, a MAD-based 3-sigma filter is used. For small samples, no outlier filter is applied.
- The recommended cycle is the median of the cleaned observations, with raw and clean sample sizes and supporting min/max/median/mean/stdev retained.

## Data-Quality Notes

- The exact requested row range is absent from the source workbook. Treat this draft as a range-audit plus fallback candidate, not a final production output.
- In the fallback sheet, row 1 headers for J/K/L are: J=`Toplam Göz Sayısı (ad)`, K=`Çalışan Göz Sayısı (ad)`, L=`Çevrim Süresi (sn)`.
- Those headers indicate L is the true cycle-time field in the populated fallback sheets, while J and K are cavity/eye counts. The all-J/K/L stats are included to mirror the requested columns, but the L-only stats are the more usable cycle recommendation for these fallback scopes.
- Rows missing either `MM` or `GR` in product text cannot be grouped by agiz and gramaj and are excluded from group stats.
- Groups with small raw sample sizes are reported, but their recommendations have limited robustness because no outlier filter can be defended with n < 4.
