"""Retrieve claims that may be about the same measure.

This stage only proposes: it groups claims whose measure descriptions overlap into
candidate clusters for the comparison stage to judge. The similarity used here is a
retrieval signal and never reaches a verdict. Whether two clustered claims are truly
about the same entity and quantity is decided later, not here.
"""

import re
from typing import Callable

from factledger.extract import Claim

_TOKEN = re.compile(r"[a-z0-9]+")


def cluster(
    claims: list[Claim],
    similarity: Callable[[str, str], float] = None,
    threshold: float = 0.5,
) -> list[list[Claim]]:
    """Group claims by measure similarity into connected components. Returns the
    clusters that hold at least two claims, i.e. the comparison candidates."""
    sim = similarity or lexical_similarity
    parent = list(range(len(claims)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(claims)):
        for j in range(i + 1, len(claims)):
            if sim(claims[i].measure, claims[j].measure) >= threshold:
                parent[find(i)] = find(j)

    groups: dict[int, list[Claim]] = {}
    for i, claim in enumerate(claims):
        groups.setdefault(find(i), []).append(claim)
    return [g for g in groups.values() if len(g) >= 2]


def lexical_similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))
