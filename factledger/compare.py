"""Decide the relationship between two claims.

The decision is deterministic. Two claims are only comparable when they share a
coordinate system: same entity, same measure, same kind of value, a temporal
coordinate on both sides, and matching scope. Within a shared coordinate system,
equal values corroborate and unequal values contradict. When a qualifier differs,
the difference is a candidate explanation and the verdict is provisionally
reconciled; a bounded model question may only pull that back to uncertain, never
push it toward confidence. Explanations are written from the signals here, so the
same pair always yields the same words.
"""

import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from factledger.extract import Claim
from factledger.entities import resolve_entity
from factledger.normalize import normalize_value, normalize_period, normalize_scope, NormalizedValue
from factledger.resolve import lexical_similarity
from factledger import llm

CORROBORATED = "CORROBORATED"
CONTRADICTED = "CONTRADICTED"
RECONCILED_BY_CONTEXT = "RECONCILED_BY_CONTEXT"
UNCERTAIN = "UNCERTAIN"
NOT_COMPARABLE = "NOT_COMPARABLE"

MEASURE_THRESHOLD = 0.6
_NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


@dataclass(frozen=True)
class Comparison:
    verdict: str
    explanation: str
    reconciling_dimension: Optional[str] = None


def compare(a: Claim, b: Claim, reconcile: Callable[..., str] = None) -> Comparison:
    reconcile = reconcile or _llm_reconcile

    ea, eb = resolve_entity(a.subject), resolve_entity(b.subject)
    if not ea.resolved or not eb.resolved:
        return Comparison(NOT_COMPARABLE,
                          f"entity unresolved on one side: '{a.subject}' / '{b.subject}'")
    if ea.id != eb.id:
        return Comparison(NOT_COMPARABLE,
                          f"different entities: '{a.subject}' vs '{b.subject}'")
    if lexical_similarity(a.measure, b.measure) < MEASURE_THRESHOLD:
        return Comparison(NOT_COMPARABLE,
                          f"different measures: '{a.measure}' vs '{b.measure}'")

    if a.kind == "entity_state" and b.kind == "entity_state":
        return _compare_state(a, b)
    return _compare_numeric(a, b, reconcile)


def _compare_numeric(a: Claim, b: Claim, reconcile: Callable[..., str]) -> Comparison:
    va, vb = normalize_value(a.value_raw), normalize_value(b.value_raw)
    if va is None or vb is None:
        return Comparison(UNCERTAIN, "a value could not be read as a number")
    if _is_percent(a.value_raw) != _is_percent(b.value_raw):
        return Comparison(NOT_COMPARABLE, "one value is a percentage, the other absolute")
    if va.unit and vb.unit and va.unit != vb.unit:
        return Comparison(NOT_COMPARABLE, f"different units: {va.unit} vs {vb.unit}")
    if bool(va.unit or va.magnitude) != bool(vb.unit or vb.magnitude):
        # One side states a scale and the other states none. The bare figure may be in
        # the same scale with its unit unrecorded, so the gap cannot be read as
        # disagreement.
        return Comparison(UNCERTAIN, "a unit or magnitude is stated on only one side")

    ta, tb = _temporal(a), _temporal(b)
    if ta is None or tb is None:
        return Comparison(UNCERTAIN, "missing reporting period or as-of date on at least one claim")

    sa, sb = normalize_scope(a.qualifiers.scope), normalize_scope(b.qualifiers.scope)
    if (sa is None) != (sb is None):
        return Comparison(UNCERTAIN, "scope is stated on only one side")

    diffs = _qualifier_diffs(ta, tb, sa, sb, a.qualifiers.basis, b.qualifiers.basis,
                             a.qualifiers.column_label, b.qualifiers.column_label)
    values_equal = _values_equal(a.value_raw, va, b.value_raw, vb)

    if not diffs:
        if values_equal:
            return Comparison(CORROBORATED,
                              f"same {a.measure} under matching context ({_ctx(ta, sa)}); "
                              f"{a.value_raw} equals {b.value_raw} after normalization")
        return Comparison(CONTRADICTED,
                          f"same {a.measure} under matching context ({_ctx(ta, sa)}); "
                          f"{a.value_raw} and {b.value_raw} disagree")

    if values_equal:
        return Comparison(NOT_COMPARABLE,
                          f"differ in {', '.join(diffs)}; an equal value across a different "
                          f"{diffs[0]} is not corroboration")

    dimension = ", ".join(diffs)
    answer = reconcile(dimension=dimension, value_a=a.value_raw, value_b=b.value_raw,
                       context_a=_ctx(ta, sa), context_b=_ctx(tb, sb))
    if answer == "yes":
        return Comparison(RECONCILED_BY_CONTEXT,
                          f"{a.value_raw} vs {b.value_raw} differ, and the {dimension} "
                          f"difference ({_ctx(ta, sa)} vs {_ctx(tb, sb)}) accounts for it",
                          reconciling_dimension=dimension)
    return Comparison(UNCERTAIN,
                      f"{a.value_raw} vs {b.value_raw} differ across {dimension}, and the "
                      f"difference does not account for the gap")


def _compare_state(a: Claim, b: Claim) -> Comparison:
    ta, tb = _temporal(a), _temporal(b)
    state_a = (a.value_raw or a.evidence.snippet).strip().lower()
    state_b = (b.value_raw or b.evidence.snippet).strip().lower()
    if state_a == state_b:
        return Comparison(CORROBORATED, f"same state for {a.subject}: {a.value_raw or a.measure}")
    if ta is None or tb is None:
        return Comparison(UNCERTAIN, "states differ but at least one has no effective date")
    if ta == tb:
        return Comparison(CONTRADICTED,
                          f"incompatible states for {a.subject} at {ta}: "
                          f"{a.value_raw} vs {b.value_raw}")
    return Comparison(RECONCILED_BY_CONTEXT,
                      f"state transition for {a.subject}: {a.value_raw} at {ta} then "
                      f"{b.value_raw} at {tb}",
                      reconciling_dimension="as_of")


def _temporal(claim: Claim) -> Optional[str]:
    return normalize_period(claim.qualifiers.period) or (claim.qualifiers.as_of or None)


def _qualifier_diffs(ta, tb, sa, sb, ba, bb, ca=None, cb=None) -> list[str]:
    diffs = []
    if ta != tb:
        diffs.append("period")
    if sa != sb:
        diffs.append("scope")
    if ba and bb and ba.strip().lower() != bb.strip().lower():
        diffs.append("basis")
    if (ca or "").strip().lower() != (cb or "").strip().lower():
        diffs.append("column")
    return diffs


def _values_equal(raw_a: str, va: NormalizedValue, raw_b: str, vb: NormalizedValue) -> bool:
    """Compare at the precision of the less precise figure. A value rounded to crore
    and the same amount stated to two decimals in million agree; two figures that
    differ in their last stated digit, like 6.5 and 6.6 per cent, do not."""
    step = max(_granularity(raw_a, va), _granularity(raw_b, vb))
    if step <= 0:
        return va.number == vb.number
    return round(va.number / step) == round(vb.number / step)


def _granularity(raw: str, nv: NormalizedValue) -> float:
    match = _NUMBER.search(raw)
    digits = match.group(0).replace(",", "")
    place = 10 ** -len(digits.split(".")[1]) if "." in digits else 1.0
    raw_number = float(digits)
    factor = nv.number / raw_number if raw_number else 1.0
    return place * factor


def _is_percent(raw: Optional[str]) -> bool:
    return bool(raw) and ("%" in raw or re.search(r"(?i)per\s?cent", raw) is not None)


def _ctx(temporal: Optional[str], scope: Optional[str]) -> str:
    parts = [p for p in (temporal, scope) if p]
    return ", ".join(parts) if parts else "unqualified"


def _llm_reconcile(dimension: str, value_a: str, value_b: str,
                   context_a: str, context_b: str) -> str:
    prompt = (
        f"A value is {value_a} in context ({context_a}) and {value_b} in context "
        f"({context_b}). The contexts differ in: {dimension}.\n"
        f"Does that {dimension} difference plausibly account for the difference between "
        f"the two values, in direction and rough magnitude?\n"
        'Answer strict JSON: {"answer": "yes|no|unknown", "reason": "one sentence"}'
    )
    system = ("You judge whether a stated contextual difference explains a difference "
              "between two values. Be conservative: answer yes only when the direction "
              "and rough size of the gap follow from the difference.")
    import json
    try:
        data = json.loads(llm.complete(prompt, system))
    except (json.JSONDecodeError, KeyError):
        return "unknown"
    answer = data.get("answer")
    return answer if answer in ("yes", "no", "unknown") else "unknown"
