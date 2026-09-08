"""Re-runnable case hunt over whatever is in the store.

Clusters the stored claims by measure, compares every pair inside a cluster, and
prints the verdict and explanation. This is how a contradiction (Case 2) is looked
for: from real clusters, not by construction. Pass --model to let the bounded
reconciliation question reach the local model; by default it answers "unknown", so
reconciliations show as uncertain and corroborations/contradictions still stand.

    python casehunt.py           # deterministic, no model
    python casehunt.py --model   # ask the model the reconciliation question
"""

import sys
from collections import Counter

from factledger import store
from factledger.resolve import cluster
from factledger.compare import compare

DB = "factledger.db"


def run(use_model: bool) -> None:
    conn = store.connect(DB)
    rows = {r["id"]: r for r in store.load_claim_rows(conn)}
    claims = [store.get_claim(conn, cid) for cid in rows]
    by_id = dict(zip(rows.keys(), claims))
    id_of = {id(c): cid for cid, c in by_id.items()}

    reconcile = None if use_model else (lambda **kw: "unknown")
    clusters = cluster(claims)
    tally = Counter()
    print(f"{len(claims)} claims -> {len(clusters)} candidate clusters\n")
    for group in clusters:
        measures = sorted({c.measure for c in group})
        print(f"cluster ({len(group)}): {measures}")
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                r = compare(a, b, reconcile=reconcile)
                tally[r.verdict] += 1
                if r.verdict in ("CONTRADICTED", "CORROBORATED", "RECONCILED_BY_CONTEXT"):
                    ia, ib = id_of[id(a)], id_of[id(b)]
                    print(f"  [{ia} vs {ib}] {r.verdict}: {r.explanation}")
        print()
    print("verdict tally:", dict(tally))


if __name__ == "__main__":
    run("--model" in sys.argv)
