# FactLedger — working agreement

Read this file at the start of every session. It overrides convenience, speed, and
your own instincts about what would be nice to add.

## What we are building

A fact knowledge layer. It ingests PDFs, extracts claims, binds every claim to
validated evidence in its source document, resolves which claims are about the same
thing, and determines the relationship between them — with a written, auditable
reason. It must work on documents it has never seen, from domains it was not
developed on.

The comparison-and-explanation layer is the point. The UI is not.

---

## 1. Hard invariants

These are not preferences. Violating one is a defect regardless of test results.

1. **No document-specific logic.** No string literal in `factledger/` may reference
   Delhivery, revenue, crore, lakh, FY2024, PIN codes, GDP, RBI, IMF, or any starter
   filename. Domain vocabulary (unit names, fiscal-year patterns, scope words) lives
   in declarative data files under `factledger/lexicon/`, loaded at runtime, never in
   control flow. If a rule only makes sense for financial filings, it is wrong.

2. **A claim without validated evidence does not exist.** Not stored, not returned,
   not counted. There is no "unverified" tier.

3. **The model never assigns a verdict.** See §5. It supplies signals and prose.

4. **Demo cases never influence production logic.** If a required demonstration case
   does not fall out of the general mechanism, either fix the mechanism for general
   reasons or report that the case was not found. Never special-case, never tune a
   threshold to make a specific pair pass.

5. **`samples/` and `eval/` are read-only fixtures.** No module under `factledger/`
   may import from them, read them at runtime, or branch on their contents. Expected
   labels live only in `eval/` and are consumed only by the test harness.

6. **This is a prototype and says so.** The words "production-ready", "enterprise",
   "robust", "comprehensive", "seamless" appear nowhere in the repository.

7. **No comparative or speculative claims anywhere in the repo.** Not "the best
   approach", not "unlike other systems", not "no other submission would". Only
   statements backed by a measurement in `eval/` output.

8. **Never invent a number.** Every count, rate, timing or accuracy figure that
   appears in the README, `notes/audit.md`, or a docstring must be the output of a
   command that can be re-run. If you cannot produce it, say so and stop. See §2.

---

## 2. Ask, don't invent

**Stop and ask the user** — do not proceed and flag later, do not pick a plausible
default — when any of these occur:

- A number, count, rate or metric would be stated that was not measured by code.
- A required demonstration case cannot be produced from real extracted data.
- An evidence span cannot be validated against source text.
- A design choice would require assuming something about the document's domain.
- The spec is ambiguous in a way that changes system behaviour.
- You are about to write "approximately", "typically", "around" or "roughly" about
  our own results.
- You are about to fabricate example output in documentation rather than paste real
  output.
- A test would need to be weakened or skipped to make the build pass.

Format the question exactly like this and then wait:

```
DECISION NEEDED
Context:   <one sentence>
Options:   A) ...  B) ...
Recommend: A, because <one sentence>
```

Guessing and disclosing afterwards is worse than stopping. There is no time pressure
that justifies an invented number.

---

## 3. Pipeline

Each stage has one responsibility. A stage may not reach into another's concerns.

```
parse      PDF -> layout blocks + table cells, with page, char offsets, bbox,
           and for every cell its row label, column label and parent header chain
extract    block -> candidate claims (LLM), each carrying a verbatim snippet
evidence   validate every snippet against source; reject what fails
normalize  values, units, periods, scope and basis into canonical form
entities   raw mention -> canonical entity + confidence
resolve    retrieve candidate claim pairs that may be about the same thing
compare    decide the relationship between a pair, with reasons
store      persist claims, evidence, entities, relationships
api        upload, inspect, explain
```

`resolve` **retrieves**; it does not decide. Embedding or lexical similarity may
propose that two claims are comparable. It may never establish that they are, and its
score may not appear in the final verdict.

---

## 4. The relationship model

Five verdicts, and they are exhaustive:

| Verdict | Meaning |
|---|---|
| `CORROBORATED` | Same claim, compatible context, compatible values. |
| `CONTRADICTED` | Same claim, compatible context, incompatible values. |
| `RECONCILED_BY_CONTEXT` | Values differ, and a specific contextual difference accounts for the difference. |
| `UNCERTAIN` | Something needed to judge is missing or unresolved. Name exactly what. |
| `NOT_COMPARABLE` | The claims look related but measure different concepts or scopes; comparing them would be a category error. |

**Source authority is a separate output, not part of the verdict.** A conflict
between an audited report and a press release is still `CONTRADICTED`. The system
may additionally emit `preferred_source` with a reason (recency, audit status,
specificity). A lower-authority source is never marked false, and authority never
converts a `CONTRADICTED` into anything else.

`UNCERTAIN` must always name the missing dimension:
`"UNCERTAIN: neither claim specifies a reporting period."`

---

## 5. Comparison authority — asymmetric

Compute these signals independently, each with its own score and its own reason
string. Do not collapse them into one similarity number.

```
entity_compatibility     temporal_compatibility    unit_compatibility
measure_compatibility    scope_compatibility       basis_compatibility
value_compatibility      evidence_quality
```

The deterministic layer combines signals into a candidate verdict. Then:

**The model may:**
- answer one narrow, bounded question per pair, phrased about this pair only
  (e.g. "does a standalone-to-consolidated scope difference plausibly account for a
  9.2% higher value?"), returning a yes/no/unknown plus one sentence;
- write the human-readable explanation from signals already computed;
- judge whether two measure descriptions refer to the same underlying quantity.

**The model may not:**
- produce `CORROBORATED` or `CONTRADICTED` where the deterministic layer did not;
- alter any numeric value, unit, date, page or span;
- decide entity identity on its own;
- override a failed evidence validation.

**Asymmetric rule:** the model may only move a verdict *toward* uncertainty
(`CORROBORATED`/`CONTRADICTED` → `UNCERTAIN` or `NOT_COMPARABLE`). It can never move
a verdict toward confidence. This keeps the system reproducible where it asserts and
conservative where it doubts.

**`RECONCILED_BY_CONTEXT` is not automatic.** A qualifier difference is *evidence to
reason about*, not a reconciliation. Reconciliation requires that the contextual
difference plausibly explains the observed difference in value, in the direction and
roughly the magnitude observed. Multiple qualifiers may differ and still reconcile;
a single differing qualifier may fail to explain anything. Record which difference
was held to be explanatory and why. If nothing explains it, the answer is
`CONTRADICTED` or `UNCERTAIN`, not reconciliation.

---

## 6. Entity resolution

A first-class stage, not a field on a claim.

```
raw mention -> canonical entity id + confidence + the evidence for the link
```

- Never merge on name similarity alone.
- A parent, a subsidiary, an acquired company and a joint venture are distinct
  entities even when the source text says "the Company".
- A pronoun or bare "the Company" resolves only from the enclosing block's own
  context; if that is absent, the entity is unresolved.
- Two people with similar names are distinct until evidence links them.
- **Unresolved or low-confidence entity on either side ⇒ `NOT_COMPARABLE`.** Never
  `CONTRADICTED`.

---

## 7. Temporal state, not contradiction

Claims about state (role, status, ownership, appointment) carry an effective date or
an as-of date. Two state claims with different values at different times are a
**state transition**, not a contradiction:

```
2023 filing: A. Person — Director — active
2024 filing: A. Person — Director — resigned, effective 2024-07-01
=> STATE_TRANSITION, not CONTRADICTED
```

A contradiction requires incompatible states asserted for the *same* point in time.

---

## 8. Evidence validation

Every claim must pass all of these or be rejected:

- the document id exists;
- the page number is within that document;
- the snippet occurs in the source text of that page after normalization;
- the recorded character span maps back to the snippet;
- the span lies within a single layout block (this is what catches multi-column
  contamination).

Normalization permitted when matching: collapse whitespace, join soft hyphens,
normalize unicode punctuation and digits. Store the **raw** source text alongside the
normalized form; provenance is proven against raw, matched against normalized.

The model never supplies a page number, a span, or a document id. Those come from
`parse` and are attached by code.

---

## 9. Tables

A number extracted from a table is not a claim until it carries its context:

```
row label, column label, full parent header chain, unit, period, scope, footnote refs
```

If any of those cannot be determined, the cell does not become a claim, and the
reason is recorded so it appears in the failure audit. A number without its table
context is the single most dangerous artefact this system can produce, because it
looks correct.

Prefer deterministic cell extraction. Where layout defeats it and the model must read
a value, mark the claim `transcribed_by_model: true`, cap its confidence, and exclude
it from ever producing `CONTRADICTED`. The principle is not "numbers never touch the
model" — it is that the model is not trusted to transcribe a number when
deterministic extraction was available.

---

## 10. Generality

- Development corpus: `data/dev/` only.
- `data/holdout/` must not be opened, read, sampled, or referenced by any code or
  session until the cold-run stage. Do not tune anything against it.
- After the cold run, failures are recorded. Rules may only be changed for reasons
  that are general; "the holdout needed it" is not a reason.
- Before any stage is considered done, ask: does this work on a document with no
  currency, no fiscal year, and no tables? If not, it is domain logic in disguise.

---

## 11. Evaluation

`eval/` holds an adversarial fixture set. Each case is a claim pair plus the expected
verdict plus a one-line rationale. Cover at least:

same number different periods · different numbers different periods · same number
different scope · same number different units · percentage vs absolute · annual vs
quarterly · consolidated vs standalone · current vs historical · same person vs
different person · parent vs subsidiary · acquired-entity bleed · competing
projections from different institutions · approximate or rounded values · missing
period · missing scope · missing entity · unit present on one side only

Report only measured numbers: claims extracted, claims rejected and why, evidence
validation pass rate, fixture cases passed and failed, processing time per document.
State plainly how ground truth was labelled, by whom, what counts as correct, and
what was not evaluated.

---

## 12. Commits

- One commit per completed unit of work. Not per file, not per hour.
- Run the test harness before committing. Do not commit a red build.
- Messages: lowercase, imperative, plain. `add span validation for table cells`.
  No conventional-commit prefixes, no emoji, no generated-looking cadence.
- Push after each commit.
- If an approach is abandoned, commit the removal with a message saying why.
- Never amend or rewrite history to make it look different from what happened.

---

## 13. Forbidden

- A `utils/`, `helpers/`, `common/` or `core/` module.
- An abstract base class with one implementation.
- A configuration system with one caller.
- A retry/backoff/caching layer not demanded by an observed failure.
- Defensive `try/except` that swallows an error and continues with a default.
- Tests that assert a function returns without asserting what it returned.
- Docstrings on trivial functions.
- Any file that exists to be tidy rather than because something calls it.

Aim for clear responsibility boundaries and no speculative structure. The test for a
new module is: does something else already call it? If not, it does not exist yet.
