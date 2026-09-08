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

_ANAPHORA = set(
    json.loads(
        (Path(__file__).resolve().parent / "lexicon" / "anaphora.json").read_text(
            encoding="utf-8"
        )
    )
)


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
