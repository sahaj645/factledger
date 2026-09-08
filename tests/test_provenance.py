"""Provenance ranks sources without touching the verdict: a higher tier wins, then
recency; equal tier and equal period yields no preference."""

from factledger.provenance import classify_tier, preferred_source, Provenance


def test_tier_reads_the_highest_matching_cue():
    audited = classify_tier("... Independent Auditor's Report ... annual report ...")
    presentation = classify_tier("Q4 FY24 Earnings Presentation for investors")
    prospectus = classify_tier("This Red Herring Prospectus is dated ...")
    plain = classify_tier("a memo about the weather")
    assert audited.tier == "audited" and audited.rank == 4
    assert presentation.tier == "presentation"
    assert prospectus.tier == "prospectus"
    assert plain.tier == "other" and plain.rank == 0


def test_higher_tier_is_preferred():
    pref = preferred_source(
        "annual", Provenance("audited", 4), "FY2024",
        "deck", Provenance("presentation", 2), "FY2024",
    )
    assert pref.doc_id == "annual"
    assert "outranks" in pref.reason


def test_same_tier_prefers_more_recent_period():
    pref = preferred_source(
        "old", Provenance("annual_report", 3), "FY2022",
        "new", Provenance("annual_report", 3), "FY2024",
    )
    assert pref.doc_id == "new" and "recent" in pref.reason


def test_no_preference_when_tier_and_period_match():
    assert preferred_source(
        "a", Provenance("annual_report", 3), "FY2024",
        "b", Provenance("annual_report", 3), "FY2024",
    ) is None
