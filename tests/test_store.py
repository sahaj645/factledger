"""Storage has to round-trip a claim without losing its evidence, and it has to
recognise a document it has already seen so re-ingestion does no work."""

from factledger.extract import Claim, Evidence, Qualifiers
from factledger import store


def make_pdf(tmp_path, name, content):
    p = tmp_path / name
    p.write_bytes(content)
    return str(p)


def sample_claim(doc_id="docA"):
    return Claim(
        subject="Acme Foods Limited", measure="net sales", kind="numeric",
        value_raw="1,240.5 million",
        qualifiers=Qualifiers(period="FY2023", scope="consolidated", basis=None, as_of=None),
        evidence=Evidence(doc_id=doc_id, page=7, snippet="net sales of 1,240.5 million",
                          char_span=(120, 148)),
    )


def test_claim_round_trips_with_its_evidence(tmp_path):
    conn = store.connect(str(tmp_path / "f.db"))
    store.store_document(conn, "docA", make_pdf(tmp_path, "a.pdf", b"%PDF-a"))
    store.store_claims(conn, [sample_claim()])

    loaded = store.load_claims(conn, "docA")
    assert len(loaded) == 1
    c = loaded[0]
    assert c.subject == "Acme Foods Limited"
    assert c.qualifiers.scope == "consolidated"
    assert c.evidence.char_span == (120, 148)
    assert c.evidence.snippet == "net sales of 1,240.5 million"


def test_reingest_is_refused_for_unchanged_content(tmp_path):
    conn = store.connect(str(tmp_path / "f.db"))
    pdf = make_pdf(tmp_path, "a.pdf", b"%PDF-identical-bytes")
    assert store.ingest_needed(conn, pdf) is True
    store.store_document(conn, "docA", pdf)
    assert store.ingest_needed(conn, pdf) is False


def test_changed_content_needs_ingest(tmp_path):
    conn = store.connect(str(tmp_path / "f.db"))
    first = make_pdf(tmp_path, "a.pdf", b"%PDF-one")
    store.store_document(conn, "docA", first)
    second = make_pdf(tmp_path, "b.pdf", b"%PDF-two")
    assert store.ingest_needed(conn, second) is True


def test_load_filters_by_document(tmp_path):
    conn = store.connect(str(tmp_path / "f.db"))
    store.store_document(conn, "docA", make_pdf(tmp_path, "a.pdf", b"%PDF-a"))
    store.store_document(conn, "docB", make_pdf(tmp_path, "b.pdf", b"%PDF-b"))
    store.store_claims(conn, [sample_claim("docA"), sample_claim("docB"), sample_claim("docB")])
    assert len(store.load_claims(conn, "docA")) == 1
    assert len(store.load_claims(conn, "docB")) == 2
    assert len(store.load_claims(conn)) == 3
