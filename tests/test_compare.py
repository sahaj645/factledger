"""Every verdict must be reachable and must carry an explanation. The reconciliation
question is injected so these are deterministic and never touch a model."""

from factledger.extract import Claim, Evidence, Qualifiers
from factledger.compare import (
    compare, CORROBORATED, CONTRADICTED, RECONCILED_BY_CONTEXT, UNCERTAIN, NOT_COMPARABLE,
)


def claim(measure, value, *, subject="Acme Foods Limited", kind="numeric",
          period=None, scope=None, basis=None, as_of=None, snippet="x"):
    return Claim(
        subject=subject, measure=measure, kind=kind, value_raw=value,
        qualifiers=Qualifiers(period=period, scope=scope, basis=basis, as_of=as_of),
        evidence=Evidence(doc_id="d", page=1, snippet=snippet, char_span=(0, 1)),
    )


yes = lambda **kw: "yes"
no = lambda **kw: "no"


def test_corroborated_across_units():
    a = claim("adjusted ebitda", "757.86 million", period="FY2024", scope="consolidated")
    b = claim("adjusted ebitda", "76 crore", period="FY2024", scope="consolidated")
    r = compare(a, b, reconcile=no)
    assert r.verdict == CORROBORATED and r.explanation


def test_contradicted_same_coordinate_different_value():
    a = claim("revenue from operations", "100 crore", period="FY2024", scope="consolidated")
    b = claim("revenue from operations", "150 crore", period="FY2024", scope="consolidated")
    r = compare(a, b, reconcile=no)
    assert r.verdict == CONTRADICTED and r.explanation


def test_reconciled_when_one_qualifier_explains_the_gap():
    a = claim("revenue from operations", "74,540.82 million", period="FY2024", scope="standalone")
    b = claim("revenue from operations", "81,415.38 million", period="FY2024", scope="consolidated")
    r = compare(a, b, reconcile=yes)
    assert r.verdict == RECONCILED_BY_CONTEXT
    assert r.reconciling_dimension == "scope"


def test_uncertain_when_difference_does_not_explain_gap():
    a = claim("revenue from operations", "74,540 million", period="FY2024", scope="standalone")
    b = claim("revenue from operations", "20,000 million", period="FY2024", scope="consolidated")
    r = compare(a, b, reconcile=no)
    assert r.verdict == UNCERTAIN


def test_uncertain_when_period_missing():
    a = claim("revenue from operations", "100 crore", scope="consolidated")
    b = claim("revenue from operations", "100 crore", period="FY2024", scope="consolidated")
    r = compare(a, b, reconcile=no)
    assert r.verdict == UNCERTAIN and "period" in r.explanation


def test_uncertain_when_a_scale_is_stated_on_only_one_side():
    """A bare figure may be in the same scale with its unit unrecorded, so it cannot
    be read as disagreeing with a figure that states one."""
    a = claim("revenue from operations", "100 crore", period="FY2024", scope="consolidated")
    b = claim("revenue from operations", "100", period="FY2024", scope="consolidated")
    assert compare(a, b, reconcile=no).verdict == UNCERTAIN


def test_equivalent_scales_still_corroborate():
    a = claim("revenue from operations", "100 crore", period="FY2024", scope="consolidated")
    b = claim("revenue from operations", "1,000 million", period="FY2024", scope="consolidated")
    assert compare(a, b, reconcile=no).verdict == CORROBORATED


def test_not_comparable_different_entity():
    a = claim("revenue from operations", "100 crore", subject="Acme Foods Limited",
              period="FY2024", scope="consolidated")
    b = claim("revenue from operations", "100 crore", subject="Globex Corporation",
              period="FY2024", scope="consolidated")
    assert compare(a, b, reconcile=no).verdict == NOT_COMPARABLE


def test_not_comparable_percentage_vs_absolute():
    a = claim("adjusted ebitda", "0.93%", period="FY2024", scope="consolidated")
    b = claim("adjusted ebitda", "757.86 million", period="FY2024", scope="consolidated")
    assert compare(a, b, reconcile=no).verdict == NOT_COMPARABLE


def test_not_comparable_same_value_different_period():
    a = claim("pin codes served", "18000", period="FY2023")
    b = claim("pin codes served", "18000", period="FY2024")
    assert compare(a, b, reconcile=no).verdict == NOT_COMPARABLE


def test_state_transition_reconciles_by_time():
    a = claim("role: director", "active", kind="entity_state", as_of="2023-03-31")
    b = claim("role: director", "resigned", kind="entity_state", as_of="2024-07-01")
    r = compare(a, b, reconcile=no)
    assert r.verdict == RECONCILED_BY_CONTEXT and r.reconciling_dimension == "as_of"


def test_state_contradiction_same_time():
    a = claim("role: director", "active", kind="entity_state", as_of="2024-03-31")
    b = claim("role: director", "resigned", kind="entity_state", as_of="2024-03-31")
    assert compare(a, b, reconcile=no).verdict == CONTRADICTED
