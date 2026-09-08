# Extraction and comparison audit

All numbers here are produced by `audit.py` and `casehunt.py` and can be re-run.
The model was Ollama `qwen2.5:7b-instruct-q4_K_M`, running on CPU. Figures below are
from one run over a fixed set of development pages; they are not averages.

## Method

`audit.py` runs the real extractor on a fixed page set and stores what survives the
snippet gate. The hand-audit range is annual-report page 22 — the revenue and
segment table whose two-level Standalone/Consolidated header is where a dropped
scope qualifier would manufacture a false contradiction. The other pages carry the
figures the four required cases were expected to use (adjusted EBITDA, the revenue
table, PIN codes served, the acquired-entity revenue split). `casehunt.py` then
clusters the stored claims by measure and compares every pair.

## Measured extraction

| Document | Pages | Blocks | Claims kept | Rejected | Seconds |
|---|---|---|---|---|---|
| annual report | 4, 22 | 54 | 9 | 22 | 687.3 |
| Q4 FY24 earnings | 13, 16, 17 | 28 | 12 | 17 | 448.8 |
| prospectus | 44, 45, 47 | 22 | 11 | 68 | 1555.4 |
| **total** | | **104** | **32** | **107** | |

Rejections by reason, across all pages:

| Reason | Count |
|---|---|
| snippet not a verbatim substring of block | 51 |
| missing subject or measure | 49 |
| value not found inside snippet | 7 |

Evidence-validation failures are the snippet and value checks: 58 of 107 rejections.
Evidence-validation pass rate = 32 / (32 + 58) = **0.356**.

Hand-audit range (annual-report page 22): 24 blocks, 8 claims kept, 16 rejected
(15 snippet-not-a-substring, 1 missing subject/measure).

## What the rejections mean

The snippet gate is doing the job it exists for: 51 claims were dropped because the
model's snippet was not a verbatim substring of the block, and 7 numeric claims were
dropped because the stated value did not appear inside the snippet. These are
hallucinations and ungrounded numbers caught mechanically rather than by trust. None
of them reached the store.

## Comparison result

`casehunt.py` clustered the 32 stored claims into 6 candidate clusters and compared
35 pairs. Every pair returned `NOT_COMPARABLE`. The cause is in the stored claims:
on the dense financial tables the local model assigned table **row labels** as the
subject ("Total income", "Revenue from services") instead of the entity, so no two
claims resolve to the same entity and the engine declines to compare them. This is
the conservative outcome the design intends — no false contradiction was produced —
but it also means the corroboration, contradiction and reconciliation cases did not
arise from this run.

## The four cases, honestly

- **Case 1 (corroboration across units).** Not reproduced. No grounded adjusted-EBITDA
  claim survived extraction from the annual-report or earnings pages, so the
  million-versus-crore corroboration had no pair to form.
- **Case 2 (genuine contradiction).** Not found in the development corpus from this
  run. No pair reached `CONTRADICTED`. It was not constructed. The strongest lead
  remains the held-out macroeconomy corpus (competing GDP projections), which opens
  only at the cold-run stage.
- **Case 3 (apparent contradiction explained by context).** Not reproduced. On the
  revenue table the scope qualifier (standalone/consolidated) was dropped during
  extraction, and no PIN-code claim survived, so neither the scope reconciliation nor
  the as-of-date reconciliation had the claims it needed.
- **Case 4 (extraction and reasoning failures found and handled).** Found, in real
  output:
  - **Dropped scope qualifier.** The revenue-table claims carry `scope = null`; the
    Standalone/Consolidated header was not captured. This is the failure the
    architecture was built to prevent, observed here in the extractor's own output.
  - **Subject misattribution.** Row labels were stored as subjects instead of the
    entity, which is why every comparison came back not-comparable.
  - **Hallucinated snippets and ungrounded values.** 51 and 7 respectively, all
    rejected before storage.

## Reading of this run

The grounding and comparison guarantees held: nothing ungrounded was stored, and no
false contradiction was asserted. The limiting factor was the local 7B model's
extraction quality on dense financial tables — dropped qualifiers and row-label
subjects. The model backend is selectable through the `llm.py` seam, so a stronger
extractor can be measured against the same gate without changing any of the
comparison logic.
