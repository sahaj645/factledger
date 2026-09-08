# Stress test on unseen documents

The brief warns the system may be tested with additional PDFs, so it was run against
documents from outside both starter corpora: an arXiv paper, university lecture
slides, job descriptions, hackathon problem statements, and project reports. None of
these are financial filings; most have no currency, no fiscal year, and no tables,
which is the test CLAUDE.md section 10 asks for.

The deterministic layers were exercised directly (parse, table extraction, clustering
and comparison), because they are where a wrong answer would be silent.

## Scale

68 PDFs, 1,670 pages, 296 table claims.

## Invariants checked on every document

1. `parse_pdf` does not crash.
2. Every block's character span quotes its own text back from the page.
3. Every table claim's evidence span quotes its snippet back from the page.
4. No table claim exists without a row label and a column header.
5. `compare` does not crash and asserts nothing it cannot ground.

Results: **0 span mismatches** across 1,670 pages, 0 table-extraction crashes, 0
comparison crashes, and no `CORROBORATED` or `CONTRADICTED` asserted anywhere in the
sweep.

## Defect found: a dropped column qualifier produced a false contradiction

This is the one that mattered, and it was found on an unseen document.

A report of model results contained a table whose rows were metrics (CAGR,
Volatility, Sharpe) and whose columns were three different strategies. The extractor
required a column header to be present — and then discarded it, because the column
label was only ever used to look up a scope or a period. A label that is neither
(a region, a segment, a strategy, a scenario, a series) left no trace on the claim.

The result was three claims with the same subject, the same measure, and identical
qualifiers, holding three different values. Here it was survivable: no period was
stated, so the null-qualifier rule downgraded every comparison to uncertain. But with
a period present in the header the same shape produces a false contradiction. Reduced
to a minimal case:

| Metric | North Region | South Region |
|---|---|---|
| | FY2024 | FY2024 |
| Revenue | 100 | 150 |

Before the fix, comparing those two cells returned:

```
CONTRADICTED: same Revenue under matching context (FY2024); 100 and 150 disagree
```

Two regions' revenues are not a contradiction. This is exactly the failure the
architecture is built to prevent — a number that has lost a qualifier looking like a
disagreement — reproduced by the system itself.

**Fix.** The column header now travels with the claim as `column_label`, carrying
whatever the column said beyond its period and scope, and a difference in it counts
as a qualifier difference during comparison. Parts of the header that were already
read as scope or period are stripped, so a Standalone/Consolidated column adds no
duplicate signal. After the fix the same pair returns:

```
UNCERTAIN: 100 vs 150 differ across column, and the difference does not account for the gap
```

A regression test covers both halves: that region-style columns no longer contradict,
and that scope/period columns leave `column_label` empty.

## Defect found: a bracketed figure was read as positive

Accounting writes a negative in brackets. The value parser searched for the first
number in the string and ignored the brackets around it, so `(1,679.68)` became
positive 1,679.68. The development corpus contains exactly this: a claim extracted as
`Loss for the year = (1,679.68)`.

Two consequences, both demonstrated before the fix:

| Pair | Verdict before | Should be |
|---|---|---|
| the same loss written `(1,679.68)` and `-1,679.68` | `CONTRADICTED` | corroborated |
| a loss `(1,679.68)` against a profit `1,679.68` | `CORROBORATED` | contradicted |

The second is the more serious of the two: the system asserted that a loss and a
profit of the same size agree. A false contradiction is noise; a false corroboration
of opposite facts is a wrong answer stated confidently.

**Fix.** A number is negated when brackets open before it and close after it.
Brackets that open and close before the number — a unit or a note, as in
`Revenue (net) 1,234` or `EBITDA (in million) 250` — do not negate, and are covered
by tests. After the fix the two pairs return corroborated and contradicted
respectively.

## Defect found: a scale stated on only one side was read as disagreement

`100 crore` compared against a bare `100`, under the same entity, measure, period and
scope, returned `CONTRADICTED`. The two figures may well be the same fact, with the
second one's scale sitting in a header the extractor did not capture — a gap the
audit shows really happens. The comparison treated an unrecorded unit as a stated
one.

This is the case the brief lists as "unit present on one side only", and it belongs
with the null-qualifier rule: what is unknown has to block a contradiction rather
than permit one. Comparison now returns `UNCERTAIN` and names the missing dimension.
Figures that both state a scale are unaffected — `100 crore` against
`1,000 million` still corroborates — and two bare figures still compare normally.

## Defect found: two cells could share one character span

A table cell was located by searching its layout block for the first place its digits
appeared. A dense table collapses into a single layout block, so when the same figure
occurs in two rows, both claims recorded the same span. On the earnings income
statement, 10 spans were each claimed by two different rows — "Revenue for services"
and "Revenue from customers" both pointed at the same 1,860.

Evidence validation did not catch this, and could not: the span does quote the
snippet back, and it does lie in one block. It is the wrong occurrence, which means
the source view would highlight a number from another row. For a system whose central
promise is that a claim can be traced to its exact place in the document, pointing at
a different instance of the same value is a real failure even though every stated
invariant held.

**Fix.** Parsing now records where each word landed in the page text, so a cell is
located by the words that sit inside its own bounding box, falling back to the string
search only when that fails. Shared spans on that page went from 10 to 0, with every
span still quoting its snippet back.

## Second finding: unreadable files raise rather than report

Two files in the sweep raised `OSError: [Errno 22]` during parsing. They are
cloud-placeholder files whose contents are not present on disk — the operating system
cannot read them either. This is not a parsing defect, and it is deliberately not
wrapped in a handler that would swallow it; a file that cannot be read should fail
loudly. It is recorded here because an upload of such a file would surface as a
server error rather than a message about the file.

## What this did not test

The model-dependent narrative extraction path was not swept across all 68 documents;
only the deterministic layers were, because they are the ones whose failures are
silent. Nothing here measures extraction quality on unseen documents, only
correctness and grounding of what is extracted.
