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


def test_document_entity_is_the_name_used_most_not_the_first_seen():
    """A filing names the exchange it is submitted to once and its own subject many
    times. Taking the first legal-form name would attribute every figure to the
    exchange."""
    from factledger.entities import document_entity
    pages = ["Filed with BSE Limited by Acme Foods Limited",
             "Acme Foods Limited results", "Acme Foods Limited outlook"]
    assert document_entity(pages) == "Acme Foods Limited"
    assert document_entity(["nothing named here"]) is None


def test_effective_subject_fills_only_bare_or_anaphoric_mentions():
    from factledger.entities import effective_subject
    assert effective_subject("Company", "Acme Foods Limited") == "Acme Foods Limited"
    assert effective_subject("", "Acme Foods Limited") == "Acme Foods Limited"
    # a subject that names someone else is never overwritten
    assert effective_subject("Northwind Logistics Private Limited",
                             "Acme Foods Limited") == "Northwind Logistics Private Limited"
    assert effective_subject("Spoton", "Acme Foods Limited") == "Spoton"
