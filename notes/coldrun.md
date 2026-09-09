# Cold run on the held-out corpus

These three macroeconomy documents were opened for the first time here, after the
pipeline was fixed. Nothing was changed in response to what was found; `coldrun.py`
reproduces this run. The model was Ollama `qwen2.5:7b-instruct-q4_K_M` on CPU.

## What was run

Pages that discuss GDP growth across the three institutions, chosen because the
competing GDP projections were the strongest lead for a genuine contradiction:
Economic Survey pages 4 and 14, RBI Annual Report page 22, IMF Article IV pages 3
and 13.

| Document | Pages | Claims kept | Seconds |
|---|---|---|---|
| India Economic Survey 2024-25 | 4, 14 | 2 | 207.0 |
| RBI Annual Report 2024-25 | 22 | 1 | 139.4 |
| IMF India 2025 Article IV | 3, 13 | 15 | 221.3 |
| **total** | | **18** | |

Rejections: 20 snippet-not-a-substring, 3 kind-not-in-schema, 2 table cell without
row label, 1 missing subject/measure, 1 table value not grounded. The snippet and
schema gates behaved exactly as on the development corpus.

## What compared

18 claims, 10 pairs compared, all `NOT_COMPARABLE`. No false contradiction and no
false corroboration.

## The Case 2 lead

The competing projections were the reason to look here: the Economic Survey's
6.3–6.8 per cent range, the IMF's figure, and the RBI's, for Indian real GDP over
the same period. They did not survive extraction as comparable claims. What the local
model actually produced from these pages was, for example:

- Economic Survey: `industrial sector | growth | 6.2 per cent | FY25` — a sub-sector
  figure, not headline GDP.
- IMF: `India | real GDP growth | 7.8 percent | first quarter of FY2025/26` — a
  single-quarter actual, not the annual projection.

The headline projection figures were not extracted with a matching entity, measure
and period across the three documents, so no pair shared a coordinate system and the
contradiction did not form. It was not constructed to make it appear.

## Run again after the later fixes

Several defects were found after the first cold run and fixed: a discarded column
label, a bracketed figure read as positive, a scale stated on one side only, two cells
sharing a character span, a value tolerance that made adjacent figures equal, a caption
search that missed a heading grouped into its table, and a table subject taken from a
caption rather than from a named entity. Every one of those came from the development
corpus or from documents outside both corpora. None came from here.

`coldrun.py` was then run again on this corpus. It produced the same 18 claims, the
same rejection counts, and the same 10 not-comparable verdicts; only wall-clock time
differed. The figures above are from that second run. Nothing was changed in response
to anything in these documents.

## Reading of the cold run

The system generalized in the way that matters for safety: it ran on a different
domain — no company entities, no fiscal-company scope, "per cent" and "percent"
spellings, percentage measures throughout — without domain-specific breakage, and it
asserted nothing it could not ground. What it did not do is surface the genuine
disagreement that is present in these documents, because the local model did not
extract the headline projections cleanly and consistently. This is a limit of the
extractor, not of the comparison logic, and the `llm.py` seam is where a stronger
extractor would be substituted and measured against the same gate.
