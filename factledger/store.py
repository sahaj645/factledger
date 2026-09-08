"""SQLite persistence for documents and their claims.

A document is keyed by the sha256 of its file bytes. Ingesting the same content
again is refused by ingest_needed, so parsing and extraction never run twice for a
file that has not changed.
"""

import hashlib
import sqlite3
from pathlib import Path

from factledger.extract import Claim, Evidence, Qualifiers

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id       TEXT PRIMARY KEY,
    path         TEXT NOT NULL,
    content_hash TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS claims (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id     TEXT NOT NULL REFERENCES documents(doc_id),
    subject    TEXT NOT NULL,
    measure    TEXT NOT NULL,
    kind       TEXT NOT NULL,
    value_raw  TEXT,
    period     TEXT,
    scope      TEXT,
    basis      TEXT,
    as_of      TEXT,
    column_label TEXT,
    page       INTEGER NOT NULL,
    snippet    TEXT NOT NULL,
    char_start INTEGER NOT NULL,
    char_end   INTEGER NOT NULL
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA)
    return conn


def content_hash(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ingest_needed(conn: sqlite3.Connection, path: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM documents WHERE content_hash = ?", (content_hash(path),)
    ).fetchone()
    return row is None


def store_document(conn: sqlite3.Connection, doc_id: str, path: str) -> None:
    conn.execute(
        "INSERT INTO documents (doc_id, path, content_hash) VALUES (?, ?, ?)",
        (doc_id, str(path), content_hash(path)),
    )
    conn.commit()


def store_claims(conn: sqlite3.Connection, claims: list[Claim]) -> None:
    conn.executemany(
        """INSERT INTO claims
           (doc_id, subject, measure, kind, value_raw, period, scope, basis, as_of,
            column_label, page, snippet, char_start, char_end)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                c.evidence.doc_id, c.subject, c.measure, c.kind, c.value_raw,
                c.qualifiers.period, c.qualifiers.scope, c.qualifiers.basis,
                c.qualifiers.as_of, c.qualifiers.column_label,
                c.evidence.page, c.evidence.snippet,
                c.evidence.char_span[0], c.evidence.char_span[1],
            )
            for c in claims
        ],
    )
    conn.commit()


def load_claims(conn: sqlite3.Connection, doc_id: str | None = None) -> list[Claim]:
    sql = ("SELECT doc_id, subject, measure, kind, value_raw, period, scope, basis, "
           "as_of, column_label, page, snippet, char_start, char_end FROM claims")
    params: tuple = ()
    if doc_id is not None:
        sql += " WHERE doc_id = ?"
        params = (doc_id,)
    sql += " ORDER BY id"
    return [_row_to_claim(row) for row in conn.execute(sql, params)]


_CLAIM_COLUMNS = ("doc_id", "subject", "measure", "kind", "value_raw", "period",
                  "scope", "basis", "as_of", "column_label", "page", "snippet",
                  "char_start", "char_end")


def load_claim_rows(conn: sqlite3.Connection, doc_id: str | None = None) -> list[dict]:
    sql = f"SELECT id, {', '.join(_CLAIM_COLUMNS)} FROM claims"
    params: tuple = ()
    if doc_id is not None:
        sql += " WHERE doc_id = ?"
        params = (doc_id,)
    sql += " ORDER BY id"
    return [dict(zip(("id",) + _CLAIM_COLUMNS, row)) for row in conn.execute(sql, params)]


def get_claim_row(conn: sqlite3.Connection, claim_id: int) -> dict | None:
    row = conn.execute(
        f"SELECT id, {', '.join(_CLAIM_COLUMNS)} FROM claims WHERE id = ?", (claim_id,)
    ).fetchone()
    return dict(zip(("id",) + _CLAIM_COLUMNS, row)) if row else None


def get_claim(conn: sqlite3.Connection, claim_id: int) -> Claim | None:
    row = conn.execute(
        f"SELECT {', '.join(_CLAIM_COLUMNS)} FROM claims WHERE id = ?", (claim_id,)
    ).fetchone()
    return _row_to_claim(row) if row else None


def list_documents(conn: sqlite3.Connection) -> list[dict]:
    return [
        {"doc_id": doc_id, "path": path}
        for doc_id, path in conn.execute("SELECT doc_id, path FROM documents ORDER BY doc_id")
    ]


def document_path(conn: sqlite3.Connection, doc_id: str) -> str | None:
    row = conn.execute("SELECT path FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
    return row[0] if row else None


def _row_to_claim(row) -> Claim:
    (doc_id, subject, measure, kind, value_raw, period, scope, basis, as_of,
     column_label, page, snippet, char_start, char_end) = row
    return Claim(
        subject=subject, measure=measure, kind=kind, value_raw=value_raw,
        qualifiers=Qualifiers(period=period, scope=scope, basis=basis, as_of=as_of,
                              column_label=column_label),
        evidence=Evidence(doc_id=doc_id, page=page, snippet=snippet,
                          char_span=(char_start, char_end)),
    )
