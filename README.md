# FactLedger

The thing that made this problem interesting to me is that a fact is not a value.

When I started reading the annual report I kept finding the same measure written more
than once with different numbers, and every version was correct. Revenue depends on
whether you mean the parent company or the group. The same amount appears in million
in one document and in crore in another. Total income is revenue plus other income,
which is a different measure wearing a similar name. If you compare on the number
alone you report contradictions that aren't there.

So the thing I actually built is not a contradiction detector. It's a system that
tries very hard to work out whether two claims are even talking about the same thing,
and refuses to compare them when they aren't. A claim is a value held under
qualifiers — period, scope, basis, unit, and which column of a table it came from.
Two claims can only agree or disagree if they share all of those. Most of the code is
about establishing that, and most of the verdicts it returns are "these are not
comparable", which I've come to think is the correct answer far more often than it
looks.

## Setup and Run Instructions

No API key. The model runs locally through Ollama.

```
ollama pull qwen2.5:7b-instruct-q4_K_M
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Set `FACTLEDGER_LLM_MODEL=qwen2.5:7b-instruct-q4_K_M` (see `.env.example`).

The fastest way to see what the system does is the test suite, which includes the
evaluation fixtures:

```
.venv\Scripts\python -m pytest -q
```

To browse claims and their source spans:

```
.venv\Scripts\python run.py serve
```

then open http://127.0.0.1:8000 and upload a PDF.

One honest warning about `python run.py` with no arguments: it ingests everything in
`data/dev` and then serves. On CPU that is hours, because the local model is called
once per narrative block. A seven page document took 1,099.8 seconds end to end.
Table-heavy documents are much faster than prose-heavy ones, because table cells never
go near the model. If you want to reproduce my numbers on a bounded set of pages,
`python audit.py` does that and writes `notes/audit_stats.json`.

## Video Demo

*(link to be added)*

## Approach

The pipeline is: parse the PDF into layout blocks and tables with character offsets,
pull claims out of them, normalise units and periods, resolve the subject to an
entity, cluster claims that might be about the same measure, and then compare them.

Two decisions carry most of the weight.

**The model never decides anything.** It proposes claims and copies a verbatim
snippet for each one. It never supplies a page number, a character span, or a
document id — those are attached by code from the parser. For table cells it isn't
involved at all; values are read from the cell. The one place it is allowed an opinion
is a single bounded question per pair: does this qualifier difference plausibly account
for this gap, yes/no/unknown. And that answer can only move a verdict toward
uncertainty, never toward confidence. This is deliberate. A comparator that asks a
model to classify pairs gives different answers on different runs, and I wanted the
same input to produce the same verdict every time.

**A claim without validated evidence doesn't exist.** Every snippet must be an exact
substring of its source block, and for a numeric claim the value has to appear inside
that snippet. Anything that fails is thrown away and counted. On the pages I audited
this rejected 46 snippets that weren't in the source and 5 numbers that weren't in
their own snippet. That's the hallucination check, and it's mechanical rather than
based on trusting the model.

Source authority is a separate output, not part of the verdict. If two claims genuinely
conflict, the system can say which source outranks the other and why, but a conflict
stays a conflict and a lower-tier source is never marked false.

Things I got wrong along the way, since I think these are more informative than the
parts that worked:

I built narrative extraction first and only later realised that almost everything I
cared about lives in tables, where a number is meaningless without its row label and
its column header. Adding deterministic table extraction moved the evidence validation
pass rate from 0.356 to 0.738.

I pulled in sentence-transformers to cluster claims by meaning, then never used it —
lexical overlap on the measure name was enough for retrieval, and retrieval isn't
allowed to decide anything anyway. I removed the dependency.

The worst bug was found by running the system over documents from outside the
assignment. Table extraction required a column header to exist and then discarded it,
because the header was only ever consulted for a scope or a period. A column meaning a
region or a segment left no trace on the claim, so two cells from different columns
became identical claims with different values — which the comparison then reported as
a contradiction. Revenue of 100 under "North Region" against 150 under "South Region"
came back as CONTRADICTED. That is exactly the failure the whole design exists to
prevent, produced by my own code.

Two more from the same sweep. A figure in brackets was read as positive, so a loss of
(1,679.68) corroborated a profit of 1,679.68 — a wrong answer stated with confidence,
which is worse than a false contradiction. And my value tolerance allowed half a
rounding step on each side, which meant any two adjacent values at the same precision
compared as equal: 6.5 per cent and 6.6 per cent, the exact shape of two competing
forecasts, were "the same number".

## Limitations and Next Steps

The most important limitation is that the demonstration cases I set out to show do not
come out of the system. I'm stating that plainly rather than staging them.

On the audited pages the pipeline kept 144 claims and rejected 105, an evidence
validation pass rate of 0.738. It then clustered those into 18 groups and compared 539
pairs, and every single pair came back NOT_COMPARABLE. Nothing corroborated, nothing
contradicted. There are three real reasons.

Within one table every cell is a different period, so they correctly don't share a
coordinate.

126 of those 144 claims have no subject at all, and are therefore unresolved before
the comparison looks at measure or period. They are the earnings deck's table cells,
and the reason is in the document: the word Delhivery does not appear anywhere on the
pages those tables sit on. Nothing beside the data names the company. I could have
filled the subject in from elsewhere in the file, and I decided not to — on that deck
it wouldn't even have picked the right company, because the first entity named on its
cover page is BSE Limited, the exchange it was filed with. Every revenue and EBITDA
figure would have been attributed to the stock exchange. Two bugs on the way there are
worth naming: the caption search required a block to end above the table, which never
matched once line grouping had merged a dense table's heading into its body, so those
tables had no caption at all; and before that the caption itself was stored as the
subject, so a table title would have been treated as an entity.

And on the one page that holds the revenue table I wanted, the PDF parser recovered the
two-level Standalone/Consolidated header but none of the data rows underneath it.

The failure counts by class, on the audited pages: 46 snippets not found in the source,
45 claims missing a subject or measure, 7 table cells with no row label, 5 values not
found inside their own snippet, 2 table cells with no column header. The last three are
the guard refusing to store a number that has lost its context.

Speed is a real limitation, not a footnote. One call per narrative block on CPU means
eighteen minutes for seven pages. The backend is behind a small seam in `llm.py`, so a
stronger or faster model can be swapped in and measured against the same gate, and I'd
expect the extraction quality problems above to shrink if I did.

Deliberately not built, each for a reason: no OCR, because the supplied PDFs have a
text layer and I verified that; no graph database, because the brief says it isn't the
point and SQLite runs from a clone with no setup; no multi-page table reconstruction;
no authentication or containers; and no extraction of qualitative claims, because they
can't be compared deterministically, which is the entire basis of the engine.

## Additional Notes

I developed against the three Delhivery documents only and did not open the three
macroeconomy documents until everything was fixed. That cold run is written up in
`notes/coldrun.md`. The pipeline ran on a different domain — no company entities, no
fiscal scope, percentages throughout — without domain-specific breakage and without
asserting anything it couldn't ground: 18 claims, 10 pairs, all not comparable. It also
did not find the competing GDP projections I was hoping for, because the local model
extracted a sub-sector figure and a single-quarter actual instead of the headline
forecasts. I didn't tune anything against that corpus.

Because the brief says the solution may be tested with additional PDFs, I also ran the
deterministic layers over 68 documents from outside both corpora — a paper, lecture
slides, job descriptions, project reports, mostly with no currency, no fiscal year and
no tables. 1,670 pages and 3,850 blocks, no character span that failed to quote its own
text back, and nothing asserted that couldn't be grounded. Two files failed to open at
all; they are cloud placeholders the operating system can't read either, and the sweep
reports them rather than stopping. That sweep is what found the three bugs above.
`python stress.py "some/folder/*.pdf"` runs it on anything.

`eval/cases.json` holds 24 adversarial claim pairs with the verdict each should get and
why, covering periods, scope, units, percentage against absolute, annual against
quarterly, state transitions, similar names, parent and subsidiary, acquired-entity
bleed, competing projections, rounding, and each missing qualifier. All 24 pass. The
full suite is 100 tests. Every number in this README comes from `notes/audit.md`,
`notes/coldrun.md` or `notes/stresstest.md`, and each of those says which command
produces it.

On AI tools: I used Claude Code throughout. I wrote the working agreement in
`CLAUDE.md` that the work had to follow, made the design decisions, and reviewed the
diffs; the model wrote most of the code and the notes under that direction. The commit
history is the real record of how it went, including the commits that back things out.
