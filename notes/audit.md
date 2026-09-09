# Extraction and comparison audit

All numbers here are produced by `audit.py` and `casehunt.py` and can be re-run.
The model was Ollama `qwen2.5:7b-instruct-q4_K_M`, running on CPU. Figures are from
one run over a fixed set of development pages after table-cell extraction was added;
they are not averages.

## Method

`audit.py` runs the pipeline on a fixed page set: table cells are extracted
deterministically with their row label, column header chain, magnitude and scope;
narrative blocks that fall outside any table go to the model. The hand-audit range
is annual-report page 22 — the revenue and segment table whose two-level
Standalone/Consolidated header is where a dropped scope qualifier would manufacture a
false contradiction. `casehunt.py` clusters the stored claims by measure and compares
every pair.

## Measured extraction

| Document | Pages | Blocks | Claims kept | Rejected | Seconds |
|---|---|---|---|---|---|
| annual report | 4, 22 | 54 | 9 | 22 | 683.8 |
| Q4 FY24 earnings | 13, 16, 17 | 28 | 126 | 15 | 188.2 |
| prospectus | 44, 45, 47 | 22 | 9 | 68 | 2360.4 |
| **total** | | **104** | **144** | **105** | |

Rejections by reason, across all pages:

| Reason | Count |
|---|---|
| snippet not a verbatim substring of block | 46 |
| missing subject or measure | 45 |
| table cell without row label | 7 |
| value not found inside snippet | 5 |
| table cell without column header | 2 |

Evidence-validation failures (snippet, value, and table-grounding checks) are 51 of
105 rejections. Evidence-validation pass rate = 144 / (144 + 51) = **0.738**.

Hand-audit range (annual-report page 22): 24 blocks, 8 claims kept, 16 rejected
(15 snippet-not-a-substring, 1 missing subject/measure). The table on this page was
detected as a header only — pdfplumber recovered the two-level Standalone/Consolidated
header but none of its data rows — so the 8 claims here came from narrative blocks,
not table cells.

## What table extraction changed

Adding deterministic table extraction raised the evidence pass rate from 0.356 to
0.738: the earnings-deck income statement (page 17) yielded 126 grounded claims
whose values are read from cells rather than transcribed by the model, so they do
not hallucinate. The two new rejection reasons — 7 cells without a row label and 2
without a column header — are the §9 guard refusing to store a number that has lost
its context.

## Comparison result

`casehunt.py` clustered the 144 claims into 18 candidate clusters and compared 539
pairs. Every pair returned `NOT_COMPARABLE`. No pair reached `CORROBORATED`,
`CONTRADICTED`, or `RECONCILED_BY_CONTEXT`. Two reasons, both real:

- **Within a table, each cell is a different period.** The earnings table states each
  measure across Q4 FY23, Q3 FY24, Q4 FY24, FY23 and FY24. Same entity and measure,
  different temporal coordinate — not comparable, correctly.
- **Most claims have no subject at all.** 126 of the 144 stored claims carry an
  empty subject and are therefore unresolved at the first gate of comparison, before
  measure, period or value are examined. All 126 are the earnings deck's table cells.
  The reason is in the source: the word "Delhivery" does not appear anywhere on the
  pages those tables sit on. Nothing in their enclosing context names the entity, so
  the system leaves the subject empty rather than supplying one.

  Two defects were fixed here and both are worth recording. The caption search
  required a block to end above the table; line grouping merges a dense table's
  heading into its body, so that block starts above the table and ends below it and
  was never considered, and the table came back with no caption at all. And the
  subject was previously whatever the caption said, so a table title would have been
  stored as though it were an entity. A table now takes only an entity its own caption
  names.

  What it deliberately does not do is inherit the entity the document is mostly about.
  On the earnings deck that would not even have produced the right company: the first
  entity named on its cover page is BSE Limited, the exchange it was filed with. Every
  revenue and EBITDA figure would have been attributed to the stock exchange.

No false contradiction and no false corroboration was produced.

## The four cases, honestly

- **Case 1 (corroboration across units).** Did not emerge. The earnings deck yielded
  12 grounded EBITDA claims, but no grounded EBITDA claim survived from the annual
  report, and the deck's claims have no subject because its pages never name the
  company. The pair cannot form without asserting a subject the document does not
  state beside the data.
- **Case 2 (genuine contradiction).** Not found in the development corpus, and not
  constructed. The lead remains the held-out macroeconomy corpus, which opens at the
  cold-run stage.
- **Case 3 (apparent contradiction explained by context).** Did not emerge. The
  revenue table's data rows were not recovered from page 22 (header only), so the
  standalone-versus-consolidated pair had no values to reconcile.
- **Case 4 (extraction and reasoning failures found and handled).** Found, in real
  output:
  - **Table data rows not recovered.** On page 22, only the two-level header was
    detected; the numbers underneath it were not, so the scope reconciliation could
    not be attempted at all.
  - **Hallucinated snippets and ungrounded values.** 46 and 5 respectively, rejected
    before storage.
  - **Context-less table cells.** 9 cells were dropped because a row or column label
    could not be determined — the guard against storing a number without its context.

## Reading of this run

The grounding and comparison guarantees held: nothing ungrounded was stored, and no
false verdict was asserted. The limits are the local 7B model's narrative extraction
on dense pages, pdfplumber's recovery of data rows under a multi-level header, and
cross-document entity resolution for table claims. The comparison cases did not fall
out of this run, and none were manufactured. The model backend is selectable through
the `llm.py` seam, so a stronger extractor can be measured against the same gate.
