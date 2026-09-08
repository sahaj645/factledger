"""Retrieval must pull claims about the same measure together across documents and
leave unrelated measures apart, without deciding anything about them."""

from factledger.extract import Claim, Evidence, Qualifiers
from factledger.resolve import cluster, lexical_similarity


def claim(measure, doc_id, value="1"):
    return Claim(
        subject="Acme Foods Limited", measure=measure, kind="numeric", value_raw=value,
        qualifiers=Qualifiers(),
        evidence=Evidence(doc_id=doc_id, page=1, snippet=value, char_span=(0, 1)),
    )


def test_same_measure_groups_across_three_documents():
    claims = [
        claim("revenue from operations", "annual"),
        claim("revenue from operations", "earnings"),
        claim("revenue from operations", "prospectus"),
        claim("total income", "annual"),
    ]
    clusters = cluster(claims)
    assert len(clusters) == 1
    grouped = clusters[0]
    assert {c.evidence.doc_id for c in grouped} == {"annual", "earnings", "prospectus"}
    assert all(c.measure == "revenue from operations" for c in grouped)


def test_unrelated_measures_do_not_cluster():
    claims = [claim("total income", "a"), claim("headcount", "b")]
    assert cluster(claims) == []


def test_near_measures_cluster_and_leave_singletons_out():
    claims = [
        claim("pin codes served", "prospectus"),
        claim("pin codes served", "annual"),
        claim("adjusted ebitda", "annual"),
    ]
    clusters = cluster(claims)
    assert len(clusters) == 1
    assert {c.measure for c in clusters[0]} == {"pin codes served"}


def test_lexical_similarity_is_symmetric_and_bounded():
    assert lexical_similarity("revenue", "revenue") == 1.0
    assert lexical_similarity("revenue", "") == 0.0
    assert lexical_similarity("a b", "b a") == lexical_similarity("b a", "a b") == 1.0
