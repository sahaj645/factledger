"""One command: ingest PDFs into the store, then serve the API.

    python run.py ingest data/dev/*.pdf
    python run.py serve
    python run.py            # ingest data/dev, then serve
"""

import glob
import os
import sys
from dataclasses import replace
from typing import Callable

from factledger import llm
from factledger.parse import parse_pdf, Page
from factledger.extract import extract_from_block, Claim, Rejection
from factledger.tables import build_table_claims, in_table
from factledger.entities import document_entity, effective_subject
from factledger import store

DB_PATH = os.environ.get("FACTLEDGER_DB", "factledger.db")
ENTITY_SCAN_PAGES = 10  # enough to see who a document is about without reading it all


def extract_page(page: Page, doc_id: str,
                 complete: Callable[[str, str], str] = llm.complete
                 ) -> tuple[list[Claim], list[Rejection]]:
    """Table cells deterministically, narrative blocks via the model. Blocks that
    fall inside a table are left to the deterministic path, not read by the model."""
    claims, rejections = build_table_claims(page, doc_id)
    for block in page.blocks:
        if in_table(block, page.tables):
            continue
        kept, dropped = extract_from_block(block, page.number, doc_id, complete)
        claims.extend(kept)
        rejections.extend(dropped)
    return claims, rejections


def ingest_document(conn, path: str, complete: Callable[[str, str], str] = llm.complete) -> dict:
    doc = parse_pdf(path)
    if not store.ingest_needed(conn, path):
        return {"doc_id": doc.doc_id, "claims": 0, "rejected": 0, "skipped": True}

    store.store_document(conn, doc.doc_id, path)
    # The entity this document is about, read from the document itself. Used only to
    # fill in a subject that its own context left bare or anaphoric.
    entity = document_entity([p.text for p in doc.pages[:ENTITY_SCAN_PAGES]])
    claims, rejected = [], 0
    for page in doc.pages:
        kept, dropped = extract_page(page, doc.doc_id, complete)
        claims.extend(replace(c, subject=effective_subject(c.subject, entity)) for c in kept)
        rejected += len(dropped)
    store.store_claims(conn, claims)
    return {"doc_id": doc.doc_id, "claims": len(claims), "rejected": rejected, "skipped": False}


def ingest_paths(paths: list[str], db_path: str = DB_PATH) -> list[dict]:
    conn = store.connect(db_path)
    results = []
    for path in paths:
        result = ingest_document(conn, path)
        results.append(result)
        print(f"{result['doc_id']}: {result['claims']} claims, "
              f"{result['rejected']} rejected" + (" (skipped)" if result["skipped"] else ""))
    return results


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn
    uvicorn.run("factledger.api:app", host=host, port=port)


def main(argv: list[str]) -> None:
    command = argv[0] if argv else "all"
    if command == "ingest":
        paths = _expand(argv[1:]) or _expand(["data/dev/*.pdf"])
        ingest_paths(paths)
    elif command == "serve":
        serve()
    elif command == "all":
        ingest_paths(_expand(["data/dev/*.pdf"]))
        serve()
    else:
        print(__doc__)


def _expand(patterns: list[str]) -> list[str]:
    return [p for pattern in patterns for p in glob.glob(pattern)]


if __name__ == "__main__":
    main(sys.argv[1:])
