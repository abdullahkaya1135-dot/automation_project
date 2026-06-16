from typing import TypedDict

from openpyxl.utils import get_column_letter

AUXILIARY_COLUMN_COUNT = 9
AUXILIARY_HEADER_ROW = 1
AUXILIARY_COLUMN_LETTERS = tuple(
    get_column_letter(column_index)
    for column_index in range(1, AUXILIARY_COLUMN_COUNT + 1)
)
AUXILIARY_MEASUREMENT_FIELD_NAMES = (
    "tower_frequency",
    "tower_set_pressure",
    "tower_feedback_pressure",
    "chiller_motor_frequency",
    "chiller_motor_set_pressure",
    "chiller_motor_feedback_pressure",
    "termokar_chiller_1_temp_set",
    "termokar_chiller_1_inlet_temp",
    "termokar_chiller_1_outlet_temp",
    "termokar_chiller_2_temp_set",
    "termokar_chiller_2_inlet_temp",
    "termokar_chiller_2_outlet_temp",
    "planer_temp_set",
    "planer_inlet_temp",
    "planer_outlet_temp",
    "itech_temp_set",
    "itech_current_temp",
    "compressor_high_708_pressure",
    "compressor_high_709_pressure",
    "compressor_high_710_pressure",
    "compressor_high_711_pressure",
    "compressor_low_712_pressure",
    "compressor_low_713_pressure",
    "compressor_low_714_pressure",
    "compressor_low_715_pressure",
    "compressor_low_716_pressure",
)
AUXILIARY_CHECK_FIELD_NAMES = (
    "oil_cooling_water_tank_checked",
    "chiller_water_tank_checked",
    "air_tank_1_drained",
    "air_tank_2_drained",
    "cleanliness_checked",
)
AUXILIARY_FIELD_NAMES = (
    *AUXILIARY_MEASUREMENT_FIELD_NAMES,
    *AUXILIARY_CHECK_FIELD_NAMES,
)


class AuxiliaryRowSpec(TypedDict):
    machine: str
    fields: dict[str, str]


AUXILIARY_ROW_SPECS: tuple[AuxiliaryRowSpec, ...] = (
    {
        "machine": "1- ELEKTROMOTOR (KULE)",
        "fields": {
            "C": "tower_frequency",
            "D": "tower_set_pressure",
            "E": "tower_feedback_pressure",
        },
    },
    {
        "machine": "2- ELEKTROMOTOR (CHİLLER)",
        "fields": {
            "C": "chiller_motor_frequency",
            "D": "chiller_motor_set_pressure",
            "E": "chiller_motor_feedback_pressure",
        },
    },
    {
        "machine": "TERMOKAR CHİLLER - 1",
        "fields": {
            "F": "termokar_chiller_1_temp_set",
            "G": "termokar_chiller_1_inlet_temp",
            "H": "termokar_chiller_1_outlet_temp",
        },
    },
    {
        "machine": "TERMOKAR CHİLLER - 2",
        "fields": {
            "F": "termokar_chiller_2_temp_set",
            "G": "termokar_chiller_2_inlet_temp",
            "H": "termokar_chiller_2_outlet_temp",
        },
    },
    {
        "machine": "PLANER SOĞUTUCU",
        "fields": {
            "F": "planer_temp_set",
            "G": "planer_inlet_temp",
            "H": "planer_outlet_temp",
        },
    },
    {
        "machine": "ITECH SOĞUTUCU",
        "fields": {
            "F": "itech_temp_set",
            "G": "itech_current_temp",
        },
    },
    {
        "machine": "YÜKSEK BASINÇ 708",
        "fields": {"I": "compressor_high_708_pressure"},
    },
    {
        "machine": "YÜKSEK BASINÇ 709",
        "fields": {"I": "compressor_high_709_pressure"},
    },
    {
        "machine": "YÜKSEK BASINÇ 710",
        "fields": {"I": "compressor_high_710_pressure"},
    },
    {
        "machine": "YÜKSEK BASINÇ 711",
        "fields": {"I": "compressor_high_711_pressure"},
    },
    {
        "machine": "ALÇAK BASINÇ 712",
        "fields": {"I": "compressor_low_712_pressure"},
    },
    {
        "machine": "ALÇAK BASINÇ 713",
        "fields": {"I": "compressor_low_713_pressure"},
    },
    {
        "machine": "ALÇAK BASINÇ 714",
        "fields": {"I": "compressor_low_714_pressure"},
    },
    {
        "machine": "ALÇAK BASINÇ 715 (150 ÖZEN)",
        "fields": {"I": "compressor_low_715_pressure"},
    },
    {
        "machine": "ALÇAK BASINÇ 716 (ATLAS)",
        "fields": {"I": "compressor_low_716_pressure"},
    },
)
AUXILIARY_HEADER_KEYWORDS_BY_COLUMN = {
    "A": ("tarih",),
    "B": ("makine",),
    "C": ("cikis frekansi", "frekans"),
    "D": ("set degeri",),
    "E": ("geri besleme",),
    "F": ("isi set",),
    "G": ("giris isisi", "giris isi"),
    "H": ("cikis isisi", "cikis isi"),
    "I": ("komp basinc", "basinc degeri"),
}
