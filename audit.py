"""Re-runnable extraction audit over a fixed set of development pages.

Runs the real extractor on the pages named below, stores what survives, and reports
measured counts: blocks seen, claims kept, claims rejected and why, evidence-
validation pass rate, and wall-clock time per document. The hand-audit range is the
annual report's revenue and segment tables, where a dropped scope qualifier would
manufacture a false contradiction; the other pages carry the pinned demonstration
cases. Nothing here changes extraction behaviour — it only measures it.

    python audit.py            # writes notes/audit_stats.json and factledger.db
"""

import json
import time
from collections import Counter
from pathlib import Path

from factledger.parse import parse_pdf
from factledger.extract import extract_from_block
from factledger import store

INGEST = {
    "delhivery-annual-report-fy24": [4, 22],
    "delhivery-q4-fy24-earnings": [13, 16, 17],
    "delhivery-prospectus-2022": [44, 45, 47],
}
AUDIT_RANGE = ("delhivery-annual-report-fy24", [22])
EVIDENCE_FAILURES = {"snippet not a verbatim substring of block", "value not found inside snippet"}

DB = "factledger.db"
DEV = Path("data/dev")


def run() -> dict:
    Path(DB).unlink(missing_ok=True)
    conn = store.connect(DB)
    per_doc = {}
    reasons = Counter()
    audit_reasons = Counter()
    audit_blocks = audit_claims = 0

    for stem, pages in INGEST.items():
        path = str(DEV / f"{stem}.pdf")
        doc = parse_pdf(path)
        store.store_document(conn, doc.doc_id, path)
        wanted = {p.number: p for p in doc.pages if p.number in pages}

        blocks = claims = rejected = 0
        started = time.time()
        kept_claims = []
        for number, page in wanted.items():
            print(f"[{doc.doc_id} p{number}] {len(page.blocks)} blocks...", flush=True)
            for block in page.blocks:
                blocks += 1
                keep, drop = extract_from_block(block, number, doc.doc_id)
                kept_claims.extend(keep)
                claims += len(keep)
                rejected += len(drop)
                for r in drop:
                    reasons[r.reason] += 1
                if stem == AUDIT_RANGE[0] and number in AUDIT_RANGE[1]:
                    audit_blocks += 1
                    audit_claims += len(keep)
                    for r in drop:
                        audit_reasons[r.reason] += 1
        store.store_claims(conn, kept_claims)
        per_doc[doc.doc_id] = {
            "pages": pages, "blocks": blocks, "claims": claims,
            "rejected": rejected, "seconds": round(time.time() - started, 1),
        }

    total_kept = sum(d["claims"] for d in per_doc.values())
    evidence_failures = sum(reasons[r] for r in EVIDENCE_FAILURES)
    stats = {
        "per_doc": per_doc,
        "rejections_by_reason": dict(reasons),
        "totals": {
            "claims_kept": total_kept,
            "claims_rejected": sum(d["rejected"] for d in per_doc.values()),
            "evidence_validation_failures": evidence_failures,
            "evidence_pass_rate": round(total_kept / (total_kept + evidence_failures), 3)
            if (total_kept + evidence_failures) else None,
        },
        "hand_audit_range": {
            "document": AUDIT_RANGE[0], "pages": AUDIT_RANGE[1],
            "blocks": audit_blocks, "claims": audit_claims,
            "rejections_by_reason": dict(audit_reasons),
        },
    }
    Path("notes").mkdir(exist_ok=True)
    Path("notes/audit_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))
    return stats


if __name__ == "__main__":
    run()
