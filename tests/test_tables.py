"""Table extraction is deterministic and generic. These tests use synthetic grids
(no PDF, no demo tables) to check header resolution, spanning headers, row-label
inheritance, missing-context rejection, and grounding."""

from factledger.tables import table_to_claims, _is_number, _header_row_count
from factledger.compare import compare, RECONCILED_BY_CONTEXT

span = lambda r, c, v: (0, len(v))          # every value is grounded
nowhere = lambda r, c, v: None              # nothing is grounded


def build(rows, caption="Acme Industries Limited", locate=span):
    return table_to_claims(rows, caption, locate, doc_id="d", page=1)


def test_single_level_header():
    claims, rej = build([["Particulars", "FY2024"], ["Revenue", "100"]])
    assert len(claims) == 1 and not rej
    assert claims[0].measure == "Revenue"
    assert claims[0].qualifiers.period == "FY2024"


def test_spanning_two_level_header_splits_scope():
    rows = [
        ["Particulars", "Standalone", "", "Consolidated", ""],
        ["", "FY2024", "FY2023", "FY2024", "FY2023"],
        ["Revenue from operations", "74,540.82", "70,000", "81,415.38", "78,000"],
    ]
    claims, _ = build(rows)
    assert len(claims) == 4
    by_col = {c.qualifiers.scope + "/" + c.qualifiers.period: c for c in claims}
    assert by_col["standalone/FY2024"].value_raw == "74,540.82"
    assert by_col["consolidated/FY2024"].value_raw == "81,415.38"


def test_missing_column_header_is_rejected():
    claims, rej = build([["Revenue", "100"]])  # first row already numeric -> no header
    assert claims == []
    assert rej[0].reason == "table cell without column header"


def test_missing_row_label_is_rejected():
    claims, rej = build([["", "FY2024"], ["", "100"]])
    assert claims == []
    assert rej[0].reason == "table cell without row label"


def test_row_label_is_inherited_from_the_row_above():
    rows = [["Particulars", "FY2024"], ["Revenue", "100"], ["", "50"]]
    claims, _ = build(rows)
    assert [c.measure for c in claims] == ["Revenue", "Revenue"]
    assert [c.value_raw for c in claims] == ["100", "50"]


def test_magnitude_and_currency_read_from_header_legend():
    rows = [["₹ Cr", "FY2024"], ["Revenue", "1,860"]]
    claims, _ = build(rows)
    assert claims[0].value_raw == "₹ 1,860 cr"


def test_ungrounded_value_is_rejected():
    claims, rej = build([["Particulars", "FY2024"], ["Revenue", "100"]], locate=nowhere)
    assert claims == []
    assert rej[0].reason == "table value not grounded in a single block"


def test_number_detection_ignores_dates_and_text():
    assert _is_number("1,860") and _is_number("(1,679.68)") and _is_number("40%")
    assert not _is_number("March 31, 2024") and not _is_number("Particulars") and not _is_number("")


def test_header_row_count_handles_multi_level():
    rows = [["", "Standalone", "Consolidated"], ["", "FY2024", "FY2024"], ["Revenue", "1", "2"]]
    assert _header_row_count(rows) == 2


def test_columns_that_differ_by_something_other_than_period_do_not_contradict():
    """Two columns can be two regions, segments or series under one period. Dropping
    what the column stood for would make their different values look like a
    contradiction, which is the failure this system exists to avoid."""
    rows = [
        ["Metric", "North Region", "South Region"],
        ["", "FY2024", "FY2024"],
        ["Revenue", "100", "150"],
    ]
    claims, _ = build(rows)
    assert [c.qualifiers.column_label for c in claims] == ["North Region", "South Region"]
    result = compare(claims[0], claims[1], reconcile=lambda **kw: "unknown")
    assert result.verdict != "CONTRADICTED"


def test_column_label_drops_parts_already_read_as_scope_or_period():
    rows = [
        ["Particulars", "Standalone", "Consolidated"],
        ["", "FY2024", "FY2024"],
        ["Revenue", "1", "2"],
    ]
    claims, _ = build(rows)
    assert all(c.qualifiers.column_label is None for c in claims)


def test_scope_difference_reconciles_end_to_end():
    rows = [
        ["Particulars", "Standalone", "Consolidated"],
        ["", "FY2024", "FY2024"],
        ["Revenue from operations", "74,540.82", "81,415.38"],
    ]
    claims, _ = build(rows)
    standalone = next(c for c in claims if c.qualifiers.scope == "standalone")
    consolidated = next(c for c in claims if c.qualifiers.scope == "consolidated")
    result = compare(standalone, consolidated, reconcile=lambda **kw: "yes")
    assert result.verdict == RECONCILED_BY_CONTEXT
    assert result.reconciling_dimension == "scope"
