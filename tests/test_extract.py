"""The extraction gate is deterministic and is tested without a model: a fake
completion feeds candidates in, and only those whose snippet (and, for numbers,
whose value) is grounded in the block survive."""

import json

from factledger.parse import Block
from factledger.extract import extract_from_block

BLOCK = Block(
    index=0,
    text="Acme Foods Limited reported net sales of 1,240.5 million for FY2023.",
    char_start=100,
    char_end=100 + len("Acme Foods Limited reported net sales of 1,240.5 million for FY2023."),
    bbox=(0.0, 0.0, 0.0, 0.0),
)


def fake(claims):
    return lambda prompt, system: json.dumps({"claims": claims})


def test_grounded_numeric_claim_is_kept_with_correct_span():
    snippet = "net sales of 1,240.5 million"
    claims, rejections = extract_from_block(
        BLOCK, page=3, doc_id="doc",
        complete=fake([{
            "subject": "Acme Foods Limited", "measure": "net sales", "kind": "numeric",
            "value": "1,240.5 million", "period": "FY2023", "scope": None,
            "basis": None, "as_of": None, "snippet": snippet,
        }]),
    )
    assert len(claims) == 1
    assert not rejections
    claim = claims[0]
    start, end = claim.evidence.char_span
    local = BLOCK.text.find(snippet)
    assert (start, end) == (BLOCK.char_start + local, BLOCK.char_start + local + len(snippet))
    assert claim.evidence.page == 3
    assert claim.qualifiers.period == "FY2023"
    assert claim.qualifiers.scope is None


def test_hallucinated_snippet_is_rejected():
    claims, rejections = extract_from_block(
        BLOCK, page=1, doc_id="doc",
        complete=fake([{
            "subject": "Acme Foods Limited", "measure": "net sales", "kind": "numeric",
            "value": "1,240.5 million", "snippet": "net sales of 9,999 million",
        }]),
    )
    assert claims == []
    assert rejections[0].reason == "snippet not a verbatim substring of block"


def test_numeric_value_not_in_snippet_is_rejected():
    claims, rejections = extract_from_block(
        BLOCK, page=1, doc_id="doc",
        complete=fake([{
            "subject": "Acme Foods Limited", "measure": "net sales", "kind": "numeric",
            "value": "2,500 million", "snippet": "reported net sales of 1,240.5 million",
        }]),
    )
    assert claims == []
    assert rejections[0].reason == "value not found inside snippet"


def test_entity_state_claim_without_value_is_kept():
    snippet = "Acme Foods Limited reported"
    claims, _ = extract_from_block(
        BLOCK, page=1, doc_id="doc",
        complete=fake([{
            "subject": "Acme Foods Limited", "measure": "status: reporting",
            "kind": "entity_state", "value": None, "snippet": snippet,
        }]),
    )
    assert len(claims) == 1
    assert claims[0].value_raw is None


def test_missing_snippet_and_bad_kind_are_rejected():
    claims, rejections = extract_from_block(
        BLOCK, page=1, doc_id="doc",
        complete=fake([
            {"subject": "A", "measure": "m", "kind": "numeric", "value": "1"},
            {"subject": "A", "measure": "m", "kind": "opinion", "snippet": "Acme"},
        ]),
    )
    assert claims == []
    assert {r.reason for r in rejections} == {"missing snippet", "kind not in schema"}


def test_malformed_model_output_yields_nothing():
    claims, rejections = extract_from_block(
        BLOCK, page=1, doc_id="doc", complete=lambda p, s: "not json at all",
    )
    assert claims == [] and rejections == []
