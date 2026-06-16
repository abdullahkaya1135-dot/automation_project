from openpyxl.utils import get_column_letter

from ...domain.entry_fields import EXCEL_FIELD_NAME_BY_COLUMN

EXCEL_COLUMN_COUNT = 25
HEADER_ROW = 1
EXCEL_COLUMN_LETTERS = tuple(
    get_column_letter(column_index)
    for column_index in range(1, EXCEL_COLUMN_COUNT + 1)
)
NUMERIC_COLUMN_LETTERS = frozenset(
    {
        "B",
        "J",
        "K",
        "L",
        "M",
        "N",
        "O",
        "P",
        "Q",
        "R",
        "S",
        "T",
        "U",
        "V",
        "W",
        "X",
        "Y",
    }
)
HEADER_KEYWORDS_BY_COLUMN = {
    "A": ("date", "tarih"),
    "B": ("ambient", "ortam"),
    "C": ("production", "engineer", "uretim", "muh"),
    "D": ("shift chief", "vardiya amiri"),
    "E": ("shift", "vardiya"),
    "F": ("machine", "makine"),
    "G": ("product", "urun"),
    "H": ("work order", "is emri"),
    "I": ("raw material", "hammadde"),
    "J": ("total", "toplam"),
    "K": ("working", "active", "calisan"),
    "L": ("cycle", "cevrim"),
    "M": ("cooling", "sogutma"),
    "N": ("injection", "enjeksiyon"),
    "O": ("blow", "ufleme", "sisirme"),
    "P": ("conditioner", "sartlandirici"),
    "Q": ("dryer", "kurutucu"),
    "R": ("pressure", "basinc"),
    "S": ("speed", "hiz"),
    "T": ("holding", "utuleme", "zaman"),
    "U": ("holding", "utuleme", "hiz"),
    "V": ("holding", "utuleme", "basinc"),
    "W": ("clamp", "mengene"),
    "X": ("oven", "barrel", "ocak"),
    "Y": ("mold", "kalip"),
}
PROCESS_ENTRY_ATTRIBUTE_BY_COLUMN = {
    "A": "date",
    "B": "ambient_temp",
    "C": "production_engineer",
    "D": "shift_chief",
    "E": "shift",
    "F": "machine",
    "G": "product",
    "H": "work_order",
    "I": "raw_material",
    "J": "total_cavity_count",
    "K": "active_cavity_count",
    "L": "cycle_time",
    "M": "cooling_time",
    "N": "injection_time",
    "O": "blow_time",
    "P": "conditioner_temp",
    "Q": "dryer_temp",
    "R": "injection_pressures",
    "S": "injection_speeds",
    "T": "holding_time",
    "U": "holding_speed",
    "V": "holding_pressure",
    "W": "clamp_force",
    "X": "oven_temps",
    "Y": "mold_temps",
}
PAYLOAD_FIELD_BY_ATTRIBUTE = {
    attribute: EXCEL_FIELD_NAME_BY_COLUMN[column_letter]
    for column_letter, attribute in PROCESS_ENTRY_ATTRIBUTE_BY_COLUMN.items()
}

__all__ = [
    "EXCEL_COLUMN_COUNT",
    "EXCEL_COLUMN_LETTERS",
    "HEADER_KEYWORDS_BY_COLUMN",
    "HEADER_ROW",
    "NUMERIC_COLUMN_LETTERS",
    "PAYLOAD_FIELD_BY_ATTRIBUTE",
    "PROCESS_ENTRY_ATTRIBUTE_BY_COLUMN",
]
