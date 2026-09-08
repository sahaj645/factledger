"""HTTP surface: upload a document, browse its claims, view a claim beside its
highlighted source, and compare two claims. The API reads and serves; the pipeline
lives in run.py and the engine in compare.py."""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from factledger import store
from factledger.parse import parse_pdf
from factledger.compare import compare

_UI = Path(__file__).resolve().parent.parent / "ui" / "index.html"

app = FastAPI(title="factledger")


def _db() -> str:
    return os.environ.get("FACTLEDGER_DB", "factledger.db")


def _uploads() -> Path:
    return Path(os.environ.get("FACTLEDGER_UPLOADS", "data/uploads"))


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _UI.read_text(encoding="utf-8")


@app.get("/api/documents")
def documents() -> list[dict]:
    return store.list_documents(store.connect(_db()))


@app.get("/api/claims")
def claims(doc_id: str | None = None) -> list[dict]:
    return store.load_claim_rows(store.connect(_db()), doc_id)


@app.get("/api/claims/{claim_id}")
def claim_detail(claim_id: int) -> dict:
    row = store.get_claim_row(store.connect(_db()), claim_id)
    if row is None:
        raise HTTPException(status_code=404, detail="claim not found")
    return row


@app.get("/api/source")
def source(doc_id: str, page: int) -> dict:
    path = store.document_path(store.connect(_db()), doc_id)
    if path is None:
        raise HTTPException(status_code=404, detail="document not found")
    doc = parse_pdf(path)
    for parsed in doc.pages:
        if parsed.number == page:
            return {"doc_id": doc_id, "page": page, "text": parsed.text}
    raise HTTPException(status_code=404, detail="page not found")


@app.get("/api/compare")
def compare_claims(a: int, b: int) -> dict:
    conn = store.connect(_db())
    ca, cb = store.get_claim(conn, a), store.get_claim(conn, b)
    if ca is None or cb is None:
        raise HTTPException(status_code=404, detail="claim not found")
    result = compare(ca, cb)
    return {
        "verdict": result.verdict,
        "explanation": result.explanation,
        "reconciling_dimension": result.reconciling_dimension,
    }


@app.post("/api/upload")
async def upload(file: UploadFile) -> dict:
    from run import ingest_document

    uploads = _uploads()
    uploads.mkdir(parents=True, exist_ok=True)
    dest = uploads / (file.filename or "upload.pdf")
    dest.write_bytes(await file.read())
    return ingest_document(store.connect(_db()), str(dest))
