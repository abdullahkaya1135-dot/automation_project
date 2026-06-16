from app.domain.entry_temperature import (
    expand_temperature_shorthand,
    expand_temperature_shorthand_fields,
)


def test_expand_temperature_shorthand_repeats_numeric_tokens():
    assert expand_temperature_shorthand("99x2") == "99-99"
    assert expand_temperature_shorthand("270x3,276x2,275") == (
        "270-270-270-276-276-275"
    )
    assert expand_temperature_shorthand("-1.5X2,+3") == "-1.5--1.5-+3"


def test_expand_temperature_shorthand_leaves_unsupported_values_unchanged():
    assert expand_temperature_shorthand(None) is None
    assert expand_temperature_shorthand("99-99") == "99-99"
    assert expand_temperature_shorthand("99x0") == "99x0"
    assert expand_temperature_shorthand("99x201") == "99x201"
    assert expand_temperature_shorthand("99x2,bad") == "99x2,bad"


def test_expand_temperature_shorthand_fields_only_updates_repeat_columns():
    payload = {
        "col_r": "70x2",
        "col_s": "49x2",
        "col_t": "12x2",
        "col_x": "270x2",
        "col_y": None,
    }

    assert expand_temperature_shorthand_fields(payload) == {
        "col_r": "70-70",
        "col_s": "49-49",
        "col_t": "12x2",
        "col_x": "270-270",
        "col_y": None,
    }
