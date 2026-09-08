"""The API's job is to serve claims and prove their grounding. The source endpoint
must return page text in which the claim's stored span quotes the snippet back
exactly, and compare must return a verdict."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from factledger.parse import parse_pdf
from factledger.extract import Claim, Evidence, Qualifiers
from factledger import store
from factledger.api import app

DEV = Path(__file__).resolve().parent.parent / "data" / "dev"


def numeric(doc_id, measure, value, page, snippet, span):
    return Claim(
        subject="Acme Foods Limited", measure=measure, kind="numeric", value_raw=value,
        qualifiers=Qualifiers(period="FY2024", scope="consolidated"),
        evidence=Evidence(doc_id=doc_id, page=page, snippet=snippet, char_span=span),
    )


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FACTLEDGER_DB", str(tmp_path / "t.db"))
    monkeypatch.setenv("FACTLEDGER_UPLOADS", str(tmp_path / "uploads"))
    conn = store.connect(str(tmp_path / "t.db"))

    path = str(DEV / "delhivery-prospectus-2022.pdf")
    doc = parse_pdf(path)
    page = next(p for p in doc.pages if any(len(b.text) > 40 for b in p.blocks))
    block = next(b for b in page.blocks if len(b.text) > 40)
    snippet = block.text[:20]
    span = (block.char_start, block.char_start + 20)

    store.store_document(conn, doc.doc_id, path)
    store.store_claims(conn, [
        numeric(doc.doc_id, "revenue from operations", "100 crore", page.number, snippet, span),
        numeric(doc.doc_id, "revenue from operations", "150 crore", page.number, snippet, span),
    ])
    ids = [r["id"] for r in store.load_claim_rows(conn)]
    return TestClient(app), doc.doc_id, page.number, snippet, span, ids


def test_documents_and_claims_are_listed(client):
    c, doc_id, *_ = client
    assert any(d["doc_id"] == doc_id for d in c.get("/api/documents").json())
    assert len(c.get(f"/api/claims?doc_id={doc_id}").json()) == 2


def test_source_span_quotes_the_snippet_back(client):
    c, doc_id, page, snippet, span, _ = client
    body = c.get(f"/api/source?doc_id={doc_id}&page={page}").json()
    assert body["text"][span[0]:span[1]] == snippet


def test_claim_detail_and_missing_claim(client):
    c, _, _, _, _, ids = client
    assert c.get(f"/api/claims/{ids[0]}").json()["id"] == ids[0]
    assert c.get("/api/claims/999999").status_code == 404


def test_compare_endpoint_returns_a_verdict(client):
    c, _, _, _, _, ids = client
    body = c.get(f"/api/compare?a={ids[0]}&b={ids[1]}").json()
    assert body["verdict"] == "CONTRADICTED"
    assert body["explanation"]


def test_upload_saves_file_and_ingests(client, tmp_path, monkeypatch):
    c = client[0]
    import run
    monkeypatch.setattr(run, "ingest_document",
                        lambda conn, path, **kw: {"doc_id": "uploaded", "claims": 1,
                                                  "rejected": 0, "skipped": False})
    resp = c.post("/api/upload", files={"file": ("x.pdf", b"%PDF-1.4 test", "application/pdf")})
    assert resp.json()["doc_id"] == "uploaded"
    assert (tmp_path / "uploads" / "x.pdf").read_bytes() == b"%PDF-1.4 test"
