"""Run the adversarial fixture set.

eval/cases.json is a read-only fixture: each case is a pair of claims, the verdict the
working agreement says the system should reach, and why. Nothing under factledger/
reads it. The bounded reconciliation answer is supplied by the fixture so a case is
deterministic and never depends on a model being installed.
"""

import json
from pathlib import Path

import pytest

from factledger.extract import Claim, Evidence, Qualifiers
from factledger.compare import compare

CASES = json.loads(
    (Path(__file__).resolve().parent.parent / "eval" / "cases.json").read_text(encoding="utf-8")
)


def build(spec: dict) -> Claim:
    value = spec.get("value")
    return Claim(
        subject=spec.get("subject", ""),
        measure=spec["measure"],
        kind=spec.get("kind", "numeric"),
        value_raw=value,
        qualifiers=Qualifiers(
            period=spec.get("period"), scope=spec.get("scope"),
            basis=spec.get("basis"), as_of=spec.get("as_of"),
            column_label=spec.get("column_label"),
        ),
        evidence=Evidence(doc_id=spec.get("doc_id", "d"), page=1,
                          snippet=value or spec["measure"], char_span=(0, 1)),
    )


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_case(case):
    answer = case.get("reconcile", "unknown")
    result = compare(build(case["a"]), build(case["b"]), reconcile=lambda **kw: answer)
    assert result.verdict == case["expect"], (
        f"{case['name']}: expected {case['expect']}, got {result.verdict} "
        f"({result.explanation}). Rationale: {case['why']}"
    )
