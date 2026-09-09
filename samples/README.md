# Sample output

Pipeline output as it actually came out, so the shape of a claim and a comparison can
be read without running anything.

These are not outputs for the six documents in full. They cover the pages that were
actually ingested, which is what the measured numbers in `notes/` are based on:

- `development-claims.json` — the development pages listed in `audit.py`
  (annual report 4 and 22, earnings deck 13, 16 and 17, prospectus 44, 45 and 47).
  144 claims, 539 pairs compared.
- `holdout-claims.json` — the held-out macroeconomy pages listed in `coldrun.py`.
  Produced only after development was finished; see `notes/coldrun.md`.

Each file holds every stored claim with its qualifiers and its evidence — the verbatim
snippet, the page, and the character span that quotes it back — followed by the verdict
tally over all compared pairs and a sample of the pairs themselves.

To regenerate: run `python audit.py` (or `python coldrun.py`) to build the database,
then export it:

```
python -c "import json;from collections import Counter;from factledger import store;from factledger.resolve import cluster;from factledger.compare import compare;conn=store.connect('factledger.db');rows=store.load_claim_rows(conn);claims=[store.get_claim(conn,r['id']) for r in rows];t=Counter();[t.update([compare(g[i],g[j],reconcile=lambda **k:'unknown').verdict]) for g in cluster(claims) for i in range(len(g)) for j in range(i+1,len(g))];print(dict(t))"
```

Nothing under `factledger/` reads this directory. It is output, not input.
