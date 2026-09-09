"""Run the deterministic layers over arbitrary PDFs and check the invariants.

Point this at any folder of documents — the brief says the system may be tested with
additional PDFs, and this is how that was tested here. It does not use a model: it
exercises parsing, table extraction, clustering and comparison, which are the parts
whose failures would be silent.

The invariants, checked on every document:

  1. parsing does not crash
  2. every block's character span quotes its own text back from the page
  3. every table claim's evidence span quotes its snippet back from the page
  4. every table claim has a measure (a cell without context is not stored)
  5. comparison does not crash

Any document that breaks one is listed at the end, with what broke.

    python stress.py "some/folder/*.pdf"
    python stress.py a.pdf b.pdf
"""

import glob
import sys
import time
from collections import Counter

from factledger.parse import parse_pdf
from factledger.tables import build_table_claims
from factledger.resolve import cluster
from factledger.compare import compare

MAX_PAIRS = 3000  # a wide table can pair combinatorially; enough to exercise the gate


def check(path: str) -> tuple[dict, list[tuple[str, str]]]:
    problems: list[tuple[str, str]] = []
    started = time.time()
    doc = parse_pdf(path)

    bad_spans = 0
    claims = []
    rejects = 0
    for page in doc.pages:
        for block in page.blocks:
            if page.text[block.char_start:block.char_end] != block.text:
                bad_spans += 1
        kept, dropped = build_table_claims(page, doc.doc_id)
        rejects += len(dropped)
        for claim in kept:
            start, end = claim.evidence.char_span
            if page.text[start:end] != claim.evidence.snippet:
                problems.append(("table span does not quote its snippet", claim.evidence.snippet))
            if not claim.measure:
                problems.append(("table claim without a measure", claim.value_raw or ""))
        claims.extend(kept)

    if bad_spans:
        problems.append(("block spans do not round-trip", f"{bad_spans} blocks"))

    tally: Counter = Counter()
    pairs = 0
    for group in cluster(claims):
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                if pairs >= MAX_PAIRS:
                    break
                tally[compare(group[i], group[j], reconcile=lambda **kw: "unknown").verdict] += 1
                pairs += 1

    return ({
        "pages": len(doc.pages),
        "blocks": sum(len(p.blocks) for p in doc.pages),
        "tables": sum(len(p.tables) for p in doc.pages),
        "claims": len(claims),
        "rejected": rejects,
        "seconds": round(time.time() - started, 1),
        "verdicts": dict(tally),
    }, problems)


def main(patterns: list[str]) -> None:
    paths = [p for pattern in patterns for p in (glob.glob(pattern) or [pattern])]
    totals: Counter = Counter()
    failures: list[tuple[str, str, str]] = []

    for path in paths:
        name = path.replace("\\", "/").split("/")[-1]
        try:
            stats, problems = check(path)
        except Exception as exc:  # a document we cannot read is a result, not a crash
            failures.append((name, type(exc).__name__, str(exc)))
            print(f"{name[:44]:46} FAILED {type(exc).__name__}: {exc}")
            continue
        for key in ("pages", "blocks", "claims", "rejected"):
            totals[key] += stats[key]
        totals["documents"] += 1
        for reason, detail in problems:
            failures.append((name, reason, detail))
        print(f"{name[:44]:46} {stats['pages']:>4}p {stats['blocks']:>5}b "
              f"{stats['tables']:>4}T {stats['claims']:>5}c {stats['rejected']:>4}rej "
              f"{stats['seconds']:>6.1f}s {stats['verdicts'] or ''}")

    print("\ntotals:", dict(totals))
    print("failures:", len(failures))
    for name, reason, detail in failures:
        print(f"  {name}: {reason} — {detail}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["data/dev/*.pdf"])
