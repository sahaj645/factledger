"""Cold run on the held-out macroeconomy corpus.

This is the first and only time these documents are opened. The pipeline is run
unchanged; nothing is tuned to what is found here. It ingests a set of pages that
discuss GDP growth across the three institutions, stores the claims, and compares
every pair, reporting what emerges. Results are recorded in notes/coldrun.md.

    python coldrun.py
"""

import time
from collections import Counter

from factledger.parse import parse_pdf
from factledger import store
from factledger.resolve import cluster
from factledger.compare import compare
from run import extract_page

INGEST = {
    "india-economic-survey-2024-25": [4, 14],
    "rbi-annual-report-2024-25": [22],
    "imf-india-2025-article-iv": [3, 13],
}
DB = "holdout.db"


def run() -> None:
    import os
    if os.path.exists(DB):
        os.remove(DB)
    conn = store.connect(DB)
    reasons = Counter()
    for stem, pages in INGEST.items():
        doc = parse_pdf(f"data/holdout/{stem}.pdf")
        store.store_document(conn, doc.doc_id, f"data/holdout/{stem}.pdf")
        kept = []
        started = time.time()
        for page in doc.pages:
            if page.number not in pages:
                continue
            print(f"[{doc.doc_id} p{page.number}] {len(page.blocks)} blocks, "
                  f"{len(page.tables)} tables...", flush=True)
            c, r = extract_page(page, doc.doc_id)
            kept.extend(c)
            for rej in r:
                reasons[rej.reason] += 1
        store.store_claims(conn, kept)
        print(f"  {doc.doc_id}: {len(kept)} claims in {round(time.time()-started,1)}s", flush=True)

    claims = [store.get_claim(conn, r["id"]) for r in store.load_claim_rows(conn)]
    print(f"\ntotal stored claims: {len(claims)}")
    print("rejections:", dict(reasons))

    tally = Counter()
    interesting = []
    for group in cluster(claims):
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                res = compare(group[i], group[j], reconcile=lambda **kw: "unknown")
                tally[res.verdict] += 1
                if res.verdict in ("CONTRADICTED", "CORROBORATED", "RECONCILED_BY_CONTEXT"):
                    interesting.append((group[i], group[j], res))
    print("verdict tally:", dict(tally))
    for a, b, res in interesting[:20]:
        print(f"  {res.verdict}: {a.subject[:18]}|{a.measure[:22]}={a.value_raw} vs "
              f"{b.subject[:18]}|{b.measure[:22]}={b.value_raw} :: {res.explanation}")

    # show the GDP-growth claims that were extracted, for the record
    print("\nGDP-related claims:")
    for c in claims:
        text = f"{c.measure} {c.value_raw}".lower()
        if "gdp" in text or "growth" in text or "%" in (c.value_raw or ""):
            print(f"  {c.doc_id if hasattr(c,'doc_id') else c.evidence.doc_id} | "
                  f"{c.subject[:22]:22} | {c.measure[:30]:30} | {c.value_raw} | per={c.qualifiers.period}")


if __name__ == "__main__":
    run()
