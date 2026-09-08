"""Normalization has to make figures written in different units and fiscal
notations line up. The headline check is case 1: the same amount stated in million
and in crore must reduce to the same number."""

from factledger.normalize import normalize_value, normalize_period, normalize_scope


def to_crore(v):
    return round(v.number / 10_000_000)


def test_million_and_crore_reduce_to_the_same_amount():
    million = normalize_value("₹757.86 million")
    crore = normalize_value("76 crore")
    assert million.unit == "INR"
    assert to_crore(million) == to_crore(crore) == 76


def test_total_income_million_matches_crore():
    million = normalize_value("₹85,942.34 million")
    crore = normalize_value("8,594 crore")
    assert to_crore(million) == to_crore(crore) == 8594


def test_plain_value_has_no_unit_or_magnitude():
    v = normalize_value("74,540.82")
    assert v.number == 74540.82
    assert v.unit is None and v.magnitude is None


def test_magnitude_words_apply_the_right_factor():
    assert normalize_value("2 lakh").number == 200000
    assert normalize_value("3 billion").number == 3_000_000_000
    assert normalize_value("8,594 crore").number == 85_940_000_000


def test_bracketed_figures_are_negative():
    """Accounting writes a negative in brackets. Reading it as positive would make a
    loss corroborate a profit of the same size."""
    assert normalize_value("(1,679.68)").number == -1679.68
    assert normalize_value("(5.4%)").number == -5.4
    assert normalize_value("₹ (1,679.68) million").number == -1_679_680_000
    assert normalize_value("-1,679.68").number == -1679.68


def test_brackets_that_are_not_around_the_number_do_not_negate():
    assert normalize_value("Revenue (net) 1,234").number == 1234
    assert normalize_value("EBITDA (in million) 250").number == 250_000_000


def test_value_with_no_number_is_none():
    assert normalize_value("consolidated basis") is None


def test_fiscal_periods_canonicalize():
    assert normalize_period("FY24") == "FY2024"
    assert normalize_period("FY2024") == "FY2024"
    assert normalize_period("for the year ended 31 March 2024") == "FY2024"
    assert normalize_period("fiscal 2023") == "FY2023"
    assert normalize_period("as at 31 December 2021") is None


def test_scope_words_canonicalize():
    assert normalize_scope("on a standalone basis") == "standalone"
    assert normalize_scope("Consolidated") == "consolidated"
    assert normalize_scope("group level") is None
