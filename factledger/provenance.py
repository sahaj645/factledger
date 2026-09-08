"""Which source to believe when two claims genuinely conflict.

This is a separate output from the verdict. A conflict stays a conflict; provenance
only says which side is the more authoritative source and why. A lower-authority
source is never marked false, and authority never changes a verdict. Tier is read
from general document-type cues in the lexicon, so it works on unseen documents.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_P = json.loads(
    (Path(__file__).resolve().parent / "lexicon" / "provenance.json").read_text(encoding="utf-8")
)
_YEAR = re.compile(r"(\d{4})")


@dataclass(frozen=True)
class Provenance:
    tier: str
    rank: int


@dataclass(frozen=True)
class PreferredSource:
    doc_id: str
    reason: str


def classify_tier(document_text: str) -> Provenance:
    lowered = document_text.lower()
    best = Provenance(_P["default"]["name"], _P["default"]["rank"])
    for tier in _P["tiers"]:
        if tier["rank"] > best.rank and any(cue in lowered for cue in tier["cues"]):
            best = Provenance(tier["name"], tier["rank"])
    return best


def preferred_source(
    doc_a: str, prov_a: Provenance, temporal_a: Optional[str],
    doc_b: str, prov_b: Provenance, temporal_b: Optional[str],
) -> Optional[PreferredSource]:
    if prov_a.rank != prov_b.rank:
        if prov_a.rank > prov_b.rank:
            return PreferredSource(doc_a, f"{prov_a.tier} outranks {prov_b.tier}")
        return PreferredSource(doc_b, f"{prov_b.tier} outranks {prov_a.tier}")

    ya, yb = _year(temporal_a), _year(temporal_b)
    if ya and yb and ya != yb:
        return (PreferredSource(doc_a, "more recent reporting period")
                if ya > yb else PreferredSource(doc_b, "more recent reporting period"))
    return None


def _year(temporal: Optional[str]) -> Optional[int]:
    if not temporal:
        return None
    match = _YEAR.search(temporal)
    return int(match.group(1)) if match else None
