from app.features.process_entries.normalization import (
    normalize_production_engineer_name,
)


def test_normalize_production_engineer_name_known_variants():
    assert normalize_production_engineer_name("BARIŞ ÇETİK") == "Barış Çetik"
    assert normalize_production_engineer_name("Barış Çetik") == "Barış Çetik"
    assert normalize_production_engineer_name("ABDULLAH KAYA") == "Abdullah Kaya"
    assert normalize_production_engineer_name("FEVZİ KILINÇ") == "Fevzi Kılınç"
    assert normalize_production_engineer_name("FEVZİ KILNÇ") == "Fevzi Kılınç"
