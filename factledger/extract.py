"""Blocks -> candidate claims, snippet-enforced.

The model proposes claims and copies a verbatim snippet for each. It never supplies
a page, a span, or a document id: those are attached here from the parsed block. A
candidate is kept only if its snippet is an exact substring of the block, and, for a
numeric claim, only if the stated value also appears inside that snippet. Everything
else is rejected with a recorded reason so the failure audit can count it.
"""

import json
from dataclasses import dataclass
from typing import Callable, Optional

from factledger.parse import Block
from factledger import llm

KINDS = ("numeric", "entity_state", "relational")


@dataclass(frozen=True)
class Qualifiers:
    period: Optional[str] = None
    scope: Optional[str] = None
    basis: Optional[str] = None
    as_of: Optional[str] = None
    # What the claim's column said beyond its period and scope — the entity, segment,
    # scenario or series a table column stands for. Two cells that differ only in this
    # are not the same fact, so it has to travel with the claim.
    column_label: Optional[str] = None


@dataclass(frozen=True)
class Evidence:
    doc_id: str
    page: int
    snippet: str
    char_span: tuple[int, int]  # into the page text


@dataclass(frozen=True)
class Claim:
    subject: str
    measure: str
    kind: str
    value_raw: Optional[str]
    qualifiers: Qualifiers
    evidence: Evidence


@dataclass(frozen=True)
class Rejection:
    reason: str
    candidate: dict


SYSTEM = (
    "You extract factual claims from one block of text taken from a document. "
    "A claim is a numeric measurement, a statement about an entity's state, or a "
    "relationship between entities. Return strict JSON only.\n"
    "Rules:\n"
    "- Copy 'snippet' character-for-character from the text. Do not paraphrase, "
    "reorder, correct spelling, or change punctuation or spacing.\n"
    "- For a numeric claim, 'value' must appear inside 'snippet' exactly as written "
    "in the text.\n"
    "- Fill period, scope, basis, as_of only if the text states them; otherwise use "
    "null. Never guess a qualifier.\n"
    "- Extract only what the text supports. If the block contains no claim, return an "
    "empty list."
)

SCHEMA_HINT = (
    '{"claims": [{"subject": str, "measure": str, "kind": '
    '"numeric|entity_state|relational", "value": str or null, "period": str or null, '
    '"scope": str or null, "basis": str or null, "as_of": str or null, '
    '"snippet": str}]}'
)

# Few-shot drawn from invented, out-of-corpus text so nothing is tuned to the cases
# being demonstrated.
EXAMPLES = (
    "TEXT:\n"
    "Acme Foods Limited reported net sales of 1,240.5 million on a consolidated "
    "basis for the year ended 31 March 2023. Priya Rao was appointed Chief "
    "Financial Officer with effect from 1 June 2023.\n"
    "JSON:\n"
    '{"claims": [{"subject": "Acme Foods Limited", "measure": "net sales", '
    '"kind": "numeric", "value": "1,240.5 million", "period": "year ended 31 March '
    '2023", "scope": "consolidated", "basis": null, "as_of": null, '
    '"snippet": "net sales of 1,240.5 million on a consolidated basis for the year '
    'ended 31 March 2023"}, '
    '{"subject": "Priya Rao", "measure": "role: Chief Financial Officer", '
    '"kind": "entity_state", "value": null, "period": null, "scope": null, '
    '"basis": null, "as_of": "1 June 2023", '
    '"snippet": "Priya Rao was appointed Chief Financial Officer with effect from 1 '
    'June 2023"}]}'
)


def extract_from_block(
    block: Block,
    page: int,
    doc_id: str,
    complete: Callable[[str, str], str] = llm.complete,
) -> tuple[list[Claim], list[Rejection]]:
    if not block.text.strip():
        return [], []
    raw = complete(_build_prompt(block.text), SYSTEM)
    candidates = _parse_candidates(raw)
    claims: list[Claim] = []
    rejections: list[Rejection] = []
    for cand in candidates:
        claim, reason = _validate(cand, block, page, doc_id)
        if claim is not None:
            claims.append(claim)
        else:
            rejections.append(Rejection(reason=reason, candidate=cand))
    return claims, rejections


def _build_prompt(text: str) -> str:
    return (
        f"Return JSON matching this shape:\n{SCHEMA_HINT}\n\n"
        f"Example:\n{EXAMPLES}\n\n"
        f"TEXT:\n{text}\nJSON:"
    )


def _parse_candidates(raw: str) -> list[dict]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    claims = data.get("claims") if isinstance(data, dict) else None
    return [c for c in claims if isinstance(c, dict)] if isinstance(claims, list) else []


def _validate(
    cand: dict, block: Block, page: int, doc_id: str
) -> tuple[Optional[Claim], str]:
    kind = cand.get("kind")
    if kind not in KINDS:
        return None, "kind not in schema"

    subject = _clean(cand.get("subject"))
    measure = _clean(cand.get("measure"))
    if not subject or not measure:
        return None, "missing subject or measure"

    snippet = cand.get("snippet")
    if not isinstance(snippet, str) or not snippet:
        return None, "missing snippet"

    local = block.text.find(snippet)
    if local < 0:
        return None, "snippet not a verbatim substring of block"

    value = _clean(cand.get("value"))
    if kind == "numeric":
        if not value:
            return None, "numeric claim without value"
        if value not in snippet:
            return None, "value not found inside snippet"

    span = (block.char_start + local, block.char_start + local + len(snippet))
    claim = Claim(
        subject=subject,
        measure=measure,
        kind=kind,
        value_raw=value,
        qualifiers=Qualifiers(
            period=_clean(cand.get("period")),
            scope=_clean(cand.get("scope")),
            basis=_clean(cand.get("basis")),
            as_of=_clean(cand.get("as_of")),
        ),
        evidence=Evidence(doc_id=doc_id, page=page, snippet=snippet, char_span=span),
    )
    return claim, ""


def _clean(value) -> Optional[str]:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
