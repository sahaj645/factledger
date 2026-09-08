"""One command: ingest PDFs into the store, then serve the API.

    python run.py ingest data/dev/*.pdf
    python run.py serve
    python run.py            # ingest data/dev, then serve
"""

import glob
import os
import sys
from typing import Callable

from factledger import llm
from factledger.parse import parse_pdf
from factledger.extract import extract_from_block
from factledger import store

DB_PATH = os.environ.get("FACTLEDGER_DB", "factledger.db")


def ingest_document(conn, path: str, complete: Callable[[str, str], str] = llm.complete) -> dict:
    doc = parse_pdf(path)
    if not store.ingest_needed(conn, path):
        return {"doc_id": doc.doc_id, "claims": 0, "rejected": 0, "skipped": True}

    store.store_document(conn, doc.doc_id, path)
    claims, rejected = [], 0
    for page in doc.pages:
        for block in page.blocks:
            kept, dropped = extract_from_block(block, page.number, doc.doc_id, complete)
            claims.extend(kept)
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
