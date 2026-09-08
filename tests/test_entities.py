"""Entity resolution must be conservative: identical surfaces unify, similar-but-
different names stay apart, and bare or anaphoric mentions resolve to nothing."""

from factledger.entities import resolve_entity


def test_named_entity_resolves_with_a_stable_id():
    a = resolve_entity("Acme Foods Limited")
    b = resolve_entity("  ACME   Foods Limited ")
    assert a.resolved and a.confidence == 1.0
    assert a.id == b.id  # case and whitespace do not create a new entity


def test_similar_names_are_not_merged():
    parent = resolve_entity("Acme Foods Limited")
    other = resolve_entity("Acme Foods")
    subsidiary = resolve_entity("Northwind Logistics Private Limited")
    assert parent.id != other.id != subsidiary.id
    assert parent.id != subsidiary.id


def test_anaphoric_and_bare_mentions_are_unresolved():
    for mention in ["the Company", "the group", "it", "They", ""]:
        e = resolve_entity(mention)
        assert e.resolved is False
        assert e.confidence == 0.0
        assert e.id == ""
