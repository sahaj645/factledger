"""Resolve a raw subject mention to a canonical entity.

Conservative on purpose: two mentions map to the same entity only when their
normalized surface forms are identical. Similar names are left distinct, because a
parent, a subsidiary and an acquired company can all read alike. A bare or
anaphoric mention ("the Company", "it") carries no identity of its own and is left
unresolved, which downstream forces NOT_COMPARABLE rather than a false contradiction.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_LEXICON = Path(__file__).resolve().parent / "lexicon"
_ANAPHORA = set(json.loads((_LEXICON / "anaphora.json").read_text(encoding="utf-8")))
_MARKERS = set(json.loads((_LEXICON / "entity_markers.json").read_text(encoding="utf-8")))
_PUNCT = ".,;:()[]" + chr(39) + chr(8217) + chr(34)


@dataclass(frozen=True)
class Entity:
    id: str          # canonical key; empty when unresolved
    surface: str     # the mention as extracted
    confidence: float
    resolved: bool


def resolve_entity(subject: str) -> Entity:
    surface = (subject or "").strip()
    key = _normalize(surface)
    if not key or key in _ANAPHORA:
        return Entity(id="", surface=surface, confidence=0.0, resolved=False)
    return Entity(id=key, surface=surface, confidence=1.0, resolved=True)


def _normalize(surface: str) -> str:
    collapsed = re.sub(r"\s+", " ", surface.lower()).strip()
    return collapsed.strip(".,;:")


def entity_in_text(text: Optional[str]) -> Optional[str]:
    """The name of an entity stated in this text, or None.

    A name is recognised by its legal form — the markers in the lexicon — with the
    capitalised words that run up to it. This is deliberately narrow: it answers only
    when the text itself names an entity, so a caller can tell the difference between
    evidence and absence. When it returns None the subject stays unresolved. It must
    never be replaced by whichever entity the surrounding document is mostly about,
    because a table can belong to a subsidiary or an acquired company while the
    document is about the parent.
    """
    if not text:
        return None
    tokens = text.split()
    for i, token in enumerate(tokens):
        if token.strip(_PUNCT).lower() not in _MARKERS:
            continue
        start = i
        while start > 0 and _is_name_word(tokens[start - 1]):
            start -= 1
        if start == i:  # a legal form with no name in front of it names nothing
            continue
        return " ".join(tokens[start:i + 1]).strip(_PUNCT) or None
    return None


def _is_name_word(token: str) -> bool:
    core = token.strip(_PUNCT)
    return bool(core) and core[0].isupper() and any(c.isalpha() for c in core)
