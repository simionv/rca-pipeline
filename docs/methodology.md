# RCA Pipeline — Methodology

This document explains **why** the pipeline classifies tickets the way it does: how taxonomies are
designed, when to use one stage or several, how prompts are written, how hallucination is contained,
how accuracy is measured, and what the limits are. For the commands and settings, see
[manual.md](manual.md). For the code structure, see [ARCHITECTURE.md](ARCHITECTURE.md).

Each pattern links to a use case that demonstrates it (`../use_cases/<name>/README.md`). Figures quoted
from past work come from the October 2026 portfolio review and are list-price estimates (costs) or
scores on the stated sample; they illustrate the method and are not guarantees.

---

## Contents

1. [Purpose and principles](#1-purpose-and-principles)
2. [Classification approach](#2-classification-approach)
3. [Taxonomy design](#3-taxonomy-design)
4. [Taxonomy discovery](#4-taxonomy-discovery)
5. [Single-stage vs multi-stage designs](#5-single-stage-vs-multi-stage-designs)
6. [Prompt engineering](#6-prompt-engineering)
7. [Containing hallucination](#7-containing-hallucination)
8. [Confidence](#8-confidence)
9. [Few-shot feedback selection](#9-few-shot-feedback-selection)
10. [Quality checks](#10-quality-checks)
11. [Measuring accuracy](#11-measuring-accuracy)
12. [LLM resilience](#12-llm-resilience)
13. [Checkpointing and resume](#13-checkpointing-and-resume)
14. [Cost and the spend ladder](#14-cost-and-the-spend-ladder)
15. [Limitations](#15-limitations)
16. [Data privacy](#16-data-privacy)

---

## 1. Purpose and principles

The pipeline turns free-text support conversations into structured, auditable labels: why the
customer got in touch, what caused the problem, how it was handled, how much effort it cost the
customer, and similar questions. It was built for support-operations analysis (root-cause analysis,
"RCA"), where the output feeds counts, trends and decisions, so consistency and traceability matter
more than eloquence.

Principles:

- **One definition per analysis.** Modules, output fields, instructions and categories live in one
  Excel workbook per use case. Everything the model sees is generated from it, so a reviewer can read
  the whole "program" without reading code.
- **Closed-set classification.** The model chooses from a curated two-level category list; it does not
  invent categories. Results are comparable across runs, analysts and months.
- **Evidence for every judgement.** Interpretive fields come with a short justification and a verbatim
  quote, and every quote is checked against the transcript.
- **Every record gets an output.** Transient failures, malformed responses and refusals degrade to
  smaller calls and, at worst, to an error stub — never to a crash that loses a run.
- **Measure before spending.** Prompts are reviewed for free, then tested on a handful of tickets,
  then scored on a gold set or probe, and only then run at scale.
- **Workflow logic stays visible.** Routing between stages, merging and scoring are written in the
  use case's notebook as ordinary pandas code, not hidden in the engine.

## 2. Classification approach

### 2.1 One module, one question

A **module** answers one question about a ticket ("what is the contact reason?", "was it escalated?").
It has a task description, a set of output fields (each with an instruction), and optionally a
category list. The build turns each module into a small classifier that sends batches of tickets to
the LLM with a system prompt and parses a JSON array back — one object per ticket.

Modules are **independent**: one module never sees another's answer within a run. This prevents an
early mistake from cascading inside a single call, at the price of no shared context. When a later
question genuinely depends on an earlier answer (root cause *given* the contact reason), the
dependency is made explicit with a second stage ([section 5](#5-single-stage-vs-multi-stage-designs)).

### 2.2 What the model sees

The system prompt has a fixed shape: a role line; `Your task:` with the module description; the
category list with each code, label and definition; numbered field instructions; a JSON example of the
expected output; and closing rules (valid JSON only, return every uid, use leaf codes only). The user
message is the batch as a JSON list of `{uid, text}`. Fixing the shape means differences between
modules are differences of content, which a reviewer can read and compare.

### 2.3 Batching

Several tickets go into one call to spread the system-prompt tokens over many records. A batch closes
at `batch_size` records or when the next ticket would exceed `max_chars` characters; a single long
ticket goes alone. Batching is a cost lever with a quality cost:

- Long transcripts with prompts that ask for many quotes have produced **cross-talk** — a quote or
  label from a neighbouring ticket in the same batch. In the Scopus 2LS smoke test at batch size 3,
  2 of 40 tickets received another ticket's quote; the module was moved to batch size 1
  ([scopus_2ls_2026](../use_cases/scopus_2ls_2026/README.md)).
- A refused batch (content filter) is stubbed whole, so batch size is also the "blast radius" of one
  bad ticket.

Rule of thumb: batch size 5 for single-label modules with one quote; batch size 1 for wide modules
that quote evidence for several fields.

### 2.4 Temperature and determinism

Classification runs at temperature 0.0. That minimises but does not remove run-to-run variation:
identical smoke tests have returned slightly different results, and re-classifying the same tickets
has agreed 66–95% at L1 and 57–90% at leaf level across use cases (lower for uncurated taxonomies).
Report retest agreement where decisions rest on small differences.

## 3. Taxonomy design

### 3.1 Exactly two levels

Every category list has L1 groups and L2 leaves; codes are `<PREFIX>n` and `<PREFIX>n.m`. Deeper
hierarchies multiply the decision space and blur boundaries; two levels are enough for reporting. When
more depth is needed, split an L1 group into several L1 groups, or add a second stage with its own
module per group (as [sd_2026](../use_cases/sd_2026/README.md) and
[scopus_2026](../use_cases/scopus_2026/README.md) do).

The model is always asked for a **leaf** code. Flat lists are therefore modelled as one L1 per
category with a single identical L2 leaf (ScienceDirect stage 1: 13 contact reasons, each one L1 with
one leaf).

### 3.2 Descriptions are the classification anchors

A label alone is ambiguous ("Login issues" can mean a password, single sign-on, a locked account or a
browser problem). The description says what belongs in the category and what does not. The 2026 use
cases write every leaf description as:

> Definition: Use when … . Do not use for … (use *X* instead).

Writing the boundary against the nearest neighbour is the single most effective accuracy improvement.
When a subject-matter expert supplies definitions, copy them verbatim and keep any rules you add
yourself (precedence between categories, evidence requirements) as separate text, so both can be
checked in the rendered prompt ([sd_2026](../use_cases/sd_2026/README.md) asserts all 134 taxonomy
strings appear verbatim).

### 3.3 Catch-all and "not enough information"

Each group gets an "Other" leaf, and stages where tickets may be too thin to decide get a "Not enough
info" leaf. Without them the model forces edge cases into the nearest category and inflates it. A
catch-all that collects more than about 10–15% of a group signals a missing category. Keep the
catch-all **last**, so appending new categories does not renumber it.

### 3.4 Stable codes

Codes come from row order. Inserting a row renumbers every later code and silently breaks comparison
with earlier runs, gold-set mappings and stored corrections. Append rows; when a taxonomy must be
reorganised, treat it as a new version (new gold mapping, old corrections retired — as
[leapspace_2026](../use_cases/leapspace_2026/README.md) did when it replaced the LeapSpace taxonomy).
Where prompts refer to fixed reference numbers, the optional `code` column pins them
([scopus_content](../use_cases/scopus_content/README.md) uses `PA1`… for policy rules).

### 3.5 Where taxonomies come from

| Source | When | Example |
|---|---|---|
| SME codebook / gold workbook | The business already has definitions | [sd_2026](../use_cases/sd_2026/README.md), [scopus_2026](../use_cases/scopus_2026/README.md) |
| Written specification | A stakeholder document defines the categories | [sd_2026_accessing_content](../use_cases/sd_2026_accessing_content/README.md) |
| Consolidated manual tags | A hand-tagged sample exists but is messy | [reg_id_2026](../use_cases/reg_id_2026/README.md) |
| Rules matrix | Categories are rules to check compliance against | [csd_2026](../use_cases/csd_2026/README.md), [scopus_content](../use_cases/scopus_content/README.md) |
| Reuse | An existing, signed-off list fits | [leapspace_2026_email_reg](../use_cases/leapspace_2026_email_reg/README.md) reuses the LeapSpace contact reasons verbatim |
| Discovery + curation | Nothing exists | [csd_2026](../use_cases/csd_2026/README.md) rejection reasons, [embase_2026_email_reg](../use_cases/embase_2026_email_reg/README.md) |
| Generic | A broad starting point | [generic](../use_cases/generic/README.md) (19 modules) |

## 4. Taxonomy discovery

When no category list exists, `rca discover` drafts one from a sample of tickets in two passes:

1. **Extraction (Pass 1).** Batches of sampled tickets are sent with the module's `extract_prompt`;
   the model returns short abstract category phrases per ticket. Phrases are counted, and
   near-duplicates (token overlap ≥ 0.75) are merged.
2. **Normalisation (Pass 2).** One call receives the `top_n` most frequent phrases with their counts
   and organises them into a two-level taxonomy with the module's prefix; the result is forced to two
   levels.

The draft is **never used directly**. A person reads it beside the phrase counts and a sample of
tickets, merges duplicates, renames vague labels, writes definitions with boundaries, adds the
catch-all, and copies the result into the workbook. That curation step is where most of the quality
comes from; discovery mainly saves the first reading of a few hundred tickets.

Sampling matters: discovery sees only `sample_n` tickets (seeded), so rare reasons may be missed. A
pre-stratified sample file of exactly `sample_n` rows keeps your stratification. Used in:
[csd_2026](../use_cases/csd_2026/README.md) (rejection reasons),
[leapspace_2026_email_reg](../use_cases/leapspace_2026_email_reg/README.md) and
[embase_2026_email_reg](../use_cases/embase_2026_email_reg/README.md) (email-account sub-categories;
Embase contact reasons), [scopus_content](../use_cases/scopus_content/README.md) (`discovery_mode` on
its modules).

## 5. Single-stage vs multi-stage designs

### 5.1 The common skeleton

Every use case follows the same outline, whatever its number of stages:

```
PREPARE   rebuild one clean conversation per ticket, apply rule gates, truncate (head + tail)
CLASSIFY  stage 1 on every ticket
ROUTE     send each ticket, by predicted CODE, to a stage-2 module or a deterministic label
MERGE     join every stage back 1:1 onto the ticket list, with a provenance column
VERIFY    gold set or proxy; audits; grounding; retest
DELIVER   Excel-safe workbook with a Method sheet; analysis on top
```

Routing and merging are notebook code: a stage-1 output is split by predicted code into subset input
files, each subset runs its own profile, and results are merged back with a 1:1 check and a
`classification_source` column (`llm`, `deterministic:…`, `rule:…`, `error:…`) on every row.

### 5.2 Single stage, one or many modules

All modules run on all tickets, independently. Simple, one pass per module, no routing errors; but
each module carries its whole category list and cannot use another module's answer.

- [generic](../use_cases/generic/README.md) — the 19-module generic engine (contact reason, root
  cause, effort, sentiment, agent performance, …): a broad first look at a new product.
- [mendeley](../use_cases/mendeley/README.md) — a product run with seven modules (contact reason, root
  cause, resolution, escalation, troubleshooting, metadata, customer effort).
- [evolve](../use_cases/evolve/README.md) — contact reason with 54 leaves plus resolution, escalation,
  troubleshooting and metadata.

### 5.3 Contact reason and root cause in one taxonomy

A single module whose L1 groups are contact reasons and whose L2 leaves are root causes: one call
yields both, and they are consistent by construction. Works when the root-cause lists per contact
reason are short; the leaf list grows quickly otherwise.
[leapspace_legacy](../use_cases/leapspace_legacy/README.md) (L1 = contact reason, L2 = root cause,
scored against a gold set).

### 5.4 The hierarchical enhancement (two calls inside one module)

The library can split one module into an L1 call and, per group, an L2 call with only that group's
leaves (`hierarchical_modules`, [manual 7.4](manual.md#74-hierarchical-classification)). It narrows
each decision at twice the calls. It runs only through the library path, and no current use case
relies on it; the explicit two-stage design below gives the same narrowing with per-stage prompts,
profiles, checkpoints and scoring.

### 5.5 Routed two-stage: contact reason → root cause

Stage 1 assigns one of N contact reasons to every ticket. Each contact reason that has root causes
gets its own stage-2 module with only its root causes and a description stating that every ticket has
already been classified into that reason. Contact reasons with a single root cause, or none, are
labelled **deterministically** without an LLM call.

Why: each stage-2 prompt is short and specific (better boundaries, lower cost), each can be reviewed
and tuned alone, and scoring separates routing errors from root-cause errors. The cost is that a
stage-1 error cannot be corrected later — measure stage 1 carefully.

- [sd_2026](../use_cases/sd_2026/README.md) — 13 contact reasons, 11 root-cause modules, 2
  deterministic routes, held-out gold scoring.
- [leapspace_2026](../use_cases/leapspace_2026/README.md) — 8 contact reasons, root-cause modules for
  institutional and individual access.
- [scopus_2026](../use_cases/scopus_2026/README.md) — 16 Level-1 categories, 14 Level-2 modules
  (two Level-1 categories share one), one Level-2 set by rule.

### 5.6 Gate → sub-reason → fallback

For "is this ticket about X, which kind of X, and otherwise what is it about?": stage A is a binary
gate (two one-leaf groups: *about X* / *not about X*), stage B gives the sub-category for gate
positives (often a discovered taxonomy), and stage C gives the general contact reason for gate
negatives (often an existing taxonomy reused verbatim). A keyword search over customer turns is run
beside the gate as a free audit — never as the label — and the cross-tab shows what the LLM adds (in
the LeapSpace case the regex alone would have missed 19 of 45 positives and flagged 65 other tickets).

- [leapspace_2026_email_reg](../use_cases/leapspace_2026_email_reg/README.md)
- [embase_2026_email_reg](../use_cases/embase_2026_email_reg/README.md)

### 5.7 Primary + sub-reason from a written specification

A binary primary classification (*Accessing content* vs *anything else*) followed by a sub-reason for
the positives, transcribed from a stakeholder specification, with checks that the prompt reproduces
the specification and audits for the markers it names.
[sd_2026_accessing_content](../use_cases/sd_2026_accessing_content/README.md).

### 5.8 Rule gate + LLM adjudicator + taxonomy

A regular expression finds candidate tickets cheaply; an LLM adjudicator decides whether the customer
is really asking for the thing (the adjudicator sees **customer turns only**, because agent replies
contained the trigger phrase in most false positives); a taxonomy module classifies the payload; the
results are merged by precedence (adjudicated yes > rule > LLM).
[reg_id_2026](../use_cases/reg_id_2026/README.md).

### 5.9 Wide extraction modules

One module returning many fields per ticket — escalation, hand-off count, internal notes, effort,
friction points, outcome, sentiment — each with its own verbatim quote and short justification, and
lists of objects (`turn`, `direction`, `event`, `evidence`) exploded into columns. Run at batch size 1.
Paired with a stratified sample and design weights instead of a full run when the question is about a
distribution. [scopus_2ls_2026](../use_cases/scopus_2ls_2026/README.md).

### 5.10 Multi-label, rule conformance and gap passes

- **Rule conformance:** the category list is a set of validation rules; the module says which rule a
  ticket's handling followed ([csd_2026](../use_cases/csd_2026/README.md)).
- **Multi-label:** a `list` field of all applicable codes plus a `code` field for the best one, with
  evidence for the second rule so the extra labels are checkable ([csd_2026](../use_cases/csd_2026/README.md)).
- **List of verdicts:** each applicable rule returned as `{code, verdict, evidence}`, exploded per key
  and grounded per quote ([scopus_content](../use_cases/scopus_content/README.md), policy rules).
- **Gap pass:** a module without a taxonomy runs only on tickets that matched no rule and drafts the
  rule that would cover them, as free text for experts ([csd_2026](../use_cases/csd_2026/README.md)).

### 5.11 Drill-downs

A narrow module run on the subset of tickets with one contact reason from an earlier broad run, to
split that reason into root causes: [account_recovery](../use_cases/account_recovery/README.md),
[account_already_exists](../use_cases/account_already_exists/README.md),
[login_blocked](../use_cases/login_blocked/README.md) (follow-ups to
[mendeley](../use_cases/mendeley/README.md)). This is the manual precursor of the routed two-stage
design.

### 5.12 Choosing a design

| Question shape | Design | Start from |
|---|---|---|
| Broad first look at a new product | Single stage, generic modules | [generic](../use_cases/generic/README.md) |
| Contact reason, then root cause from an expert codebook | Routed two-stage | [sd_2026](../use_cases/sd_2026/README.md) |
| Short root-cause lists per reason | One module, CR as L1 and RC as L2 | [leapspace_legacy](../use_cases/leapspace_legacy/README.md) |
| Is it about X, which X, else what | Gate → sub-reason → fallback | [embase_2026_email_reg](../use_cases/embase_2026_email_reg/README.md) |
| Categories from a written spec | Primary + sub-reason | [sd_2026_accessing_content](../use_cases/sd_2026_accessing_content/README.md) |
| Find a request type that keywords over-match | Rule gate + adjudicator | [reg_id_2026](../use_cases/reg_id_2026/README.md) |
| Escalation / effort with evidence for each claim | Wide extraction, batch 1, sample | [scopus_2ls_2026](../use_cases/scopus_2ls_2026/README.md) |
| Was a rule followed, which rules apply | Rule conformance, multi-label | [csd_2026](../use_cases/csd_2026/README.md) |

## 6. Prompt engineering

### 6.1 Where the levers are

| Lever | Workbook location | Effect |
|---|---|---|
| Task and decision rules | `modules.description` | Frames the whole module; put precedence rules here ("if both A and B apply, choose A"). |
| Category boundaries | `taxonomy.description` | Most of the accuracy for code fields. |
| Field instructions | `fields.prompt_instruction` | What each field must contain; the main lever for non-code fields. |
| Output shape | `field_type`, `explode_keys` | The JSON example the model mirrors; enum options listed. |

### 6.2 The code / justification / evidence trio

The 2026 use cases give every classification module three fields:

- `<stub>_code` — *"Assign the single leaf-level code (e.g. SDLI1.1) … Match on each Definition, not on
  surface keywords."*
- `<stub>_justification` — *"In one or two sentences, explain why this applies and why the closest
  alternative does not."* Asking for the rejected alternative forces a comparison against the nearest
  neighbour, and gives reviewers the model's reasoning. Instructions ask for no quotes or apostrophes
  to keep the JSON valid.
- `<stub>_evidence` — *"Copy verbatim the single sentence or phrase from the transcript that most
  strongly supports this choice. Do not paraphrase, infer, or add words."* Where it matters, prefer the
  customer's words over the agent's.

### 6.3 Input preparation is part of the prompt

- **One clean conversation per ticket**: deduplicate thread rows, order by time, label speakers,
  strip quoted history.
- **Head + tail truncation** with a visible marker (e.g. 4,000 characters from the start and 11,900
  from the end, capped at 16,000) keeps the opening request and the resolution within budget.
- **Customer turns only** when agent text would mislead (the trigger phrase in agent replies drove
  most regex false positives in [reg_id_2026](../use_cases/reg_id_2026/README.md)).
- **Rule gates** for trivially decidable tickets (empty or very short conversations) are labelled
  `rule:<name>` without an LLM call.

### 6.4 Review before spending

Render every system prompt exactly as the model will receive it and read it in full (free). Assert
that every definition, label and authored rule appears verbatim, and record a fingerprint of each
prompt so stale checkpoints can be discarded when the prompt changes
([sd_2026](../use_cases/sd_2026/README.md), [leapspace_2026_email_reg](../use_cases/leapspace_2026_email_reg/README.md)).
Freeze prompts before the gold evaluation and the full run: later edits invalidate both.

## 7. Containing hallucination

### 7.1 Closed sets and validation

- **Codes** come from the category list; the closing prompt line demands leaf codes. Codes not in the
  list get an empty label in post-processing — count them as off-taxonomy.
- **Enums** are validated twice (in the generated module at parse time and in post-processing): an
  answer outside the allowed values is blanked, not guessed.
- **L1 repair:** when the model returns a group code instead of a leaf in a `…primary…` field, the
  only child is used, or the lowest-numbered child with a warning. That keeps a valid code in the
  column but can be wrong; a high L1-repair rate means the leaf definitions are unclear.

### 7.2 Verbatim evidence and the grounding check

Every column whose name contains `_evidence` or `_snippet` is checked against the ticket text after
classification:

1. **Normalise** both texts: lowercase, fold typographic quotes and dashes to ASCII, collapse
   whitespace.
2. **Exact match:** the normalised quote is a substring of the normalised transcript → grounded.
3. **Overlap match:** otherwise, if at least **65%** of the quote's units appear in the transcript →
   grounded. Units are words when the quote has 4 or more words; for shorter quotes (and scripts such
   as Chinese and Japanese that barely use spaces) they are distinct characters.

The result is a boolean `<column>_grounded`. Ungrounded quotes are logged and **flagged, not
blanked**, so a reviewer can see what the model wrote. The character fallback fixed a script bias:
on a 1,000-record sample, CJK evidence had been flagged at 9.9% against 0.32% for other text.

### 7.3 What the check does not catch

- **Empty evidence counts as grounded.** Report the grounded share on non-empty evidence, and the
  empty share separately.
- **Short quotes are lenient.** Under 4 words, character-set overlap passes almost any Latin-script
  phrase; trust the flag for longer quotes.
- **Cross-talk passes.** A quote copied from another ticket in the same batch is "grounded" in that
  other ticket but may still overlap this one. Check flagged quotes against neighbouring rows, and use
  batch size 1 for wide-evidence modules.
- **Prompt echo.** Models sometimes quote signal phrases from the prompt; search quotes for prompt text.
- **Quote rewriting.** The JSON repair step rewrites curly quotes in every answer, so "verbatim"
  quotes may not be byte-identical to the source. Strict re-checks have found lower grounding (94%)
  than the flag reported (99.8%).

## 8. Confidence

With confidence enabled (library path), the model adds a self-reported `confidence` between 0 and 1
using calibration bands, and records below a threshold (default 0.70) are flagged for review and can be
exported to a review queue sorted lowest first. Self-reported confidence is a **triage signal**, not a
probability: it is useful to order a review queue, but should be calibrated against a gold set before
being used to accept or reject labels. Token log-probabilities would give a more objective signal; the
API is asked for them, but the pipeline does not yet turn them into scores. `rca run` produces no
confidence columns ([manual 7.2](manual.md#72-confidence-scoring)).

The hierarchical enhancement multiplies the L1 and L2 confidences, because both decisions must be
right for the leaf to be right.

## 9. Few-shot feedback selection

Human corrections can be shown to the model as "known hard cases": the transcript (cut to 800
characters), the wrong and correct classification, and the reviewer's reason. They anchor ambiguous
boundaries the definitions did not settle. The block is capped at 4,000 characters, which bounds its
cost.

Strategies:

- **recent** — the newest corrections (latest reviewer judgement wins).
- **diverse** — one per distinct corrected code (coverage of the taxonomy).
- **frequent** — the most common wrong → right pairs (systematic errors).
- **smart** — two stages, recommended once there are corrections for many codes:
  - *Stage 1, pool (once per run):* group corrections by corrected code and keep the best
    representative of each group, scored
    `0.4 × has_reason + 0.3 × content_score + 0.3 × recency`, where
    `content_score = (unique_words / total_words) × min(unique_words, 80) / 80` rewards varied,
    substantive text, and recency is the timestamp scaled to 0–1 over the module's history.
  - *Stage 2, per batch:* rerank the pool by similarity to the batch:
    `max over tickets in batch of |words(correction) ∩ words(ticket)| / max(|words(correction)|, |words(ticket)|)`,
    ties broken by the stage-1 score, and take the top `feedback_max_examples`. Different batches get
    different examples, chosen for their content.

Cautions:

- Few-shot injection runs only through the library path. `rca run` accepts the feedback settings but
  does not inject examples; evaluations run that way were zero-shot
  ([leapspace_legacy](../use_cases/leapspace_legacy/README.md), [evolve](../use_cases/evolve/README.md)).
  No accuracy lift from feedback has yet been measured in this repository.
- Corrections are tied to one taxonomy version. Retire them when codes change
  ([leapspace_2026](../use_cases/leapspace_2026/README.md) deliberately omits the old corrections).
- Never use held-out gold tickets as examples, or the held-out score stops being blind
  ([sd_2026](../use_cases/sd_2026/README.md) draws its corrections from in-run tickets only and reports
  the held-out stratum).
- Test a feedback change as a before/after comparison on held-out tickets.

## 10. Quality checks

Most failures are silent: the run exits normally and writes a plausible file. Check:

| Check | Target | How |
|---|---|---|
| Blank / error rate | ≤ 0.5% | Count empty codes and `_error` rows; review the bad-UID list. |
| Off-taxonomy codes | 0 | Codes with no label after post-processing. |
| Grounding | ≥ 95% on non-empty evidence | `*_grounded`, with empty evidence reported separately. |
| Catch-all share | small; investigate above 10–15% | Share of "Other" / "Not enough info". |
| Mode collapse | no code above ~60% unless expected | Code distribution. |
| Keyword cross-tab | disagreements read in both directions | Regex over customer turns beside the LLM label. |
| Batch neighbours | none | Ungrounded quotes found in rows within a few positions. |
| Retest | ≥ 80–85% agreement on ~100 tickets | Re-run with identical settings; report L1 and leaf separately. |
| Row count | output rows = input tickets | 1:1 merge assertions in the notebook. |

The **quality dashboard** (library path) automates part of this — coverage per module, rare and
dominant codes, unused codes, evidence types, error rate, confidence and language distributions,
anomalies and run-over-run comparison — as JSON (for automated gating) and Excel
([manual 7.8](manual.md#78-quality-dashboard)).

## 11. Measuring accuracy

### 11.1 Words matter

Use **accuracy** only against a labelled gold set. Against agent-assigned codes, surveys or keyword
rules, say **agreement**: agent codes follow workflows rather than causes and use different label
spaces, and survey answers are self-selected (LLM-judged effort correlated with customer-reported
effort at only r ≈ 0.11–0.21, which was itself the finding).

### 11.2 Building a gold set

- Version it, and score against the version frozen **before** the run. Reviewer overlays are a new
  version.
- Keep reviewers blind to predictions (when reviewers saw the model's answer, overturned labels tended
  to adopt it).
- Normalise labels before joining (zero-width characters, non-breaking spaces, dash variants), map them
  onto codes, and record exclusions.
- Check the gold text is the production text: gold extracts are often anonymised or from another
  export, and scores differ between the two.
- Mark categories with no gold example as unvalidated.

### 11.3 Held-out strata and leakage

Split gold tickets into those also in the production run and those held out. Once feedback examples
are drawn from production tickets, only the held-out stratum is blind; report it as the headline
([sd_2026](../use_cases/sd_2026/README.md): 102 held-out tickets). Never tune authored rules on the set
you report.

### 11.4 Metrics

Report, per stage: accuracy and macro-F1 with n and a 95% interval (at n = 102 about ±8 points), the
majority-class baseline and the lift over it, per-class precision/recall/F1, and the top confusion
pairs. For routed designs report three figures — stage 1, stage 2 given correct routing, and end to
end — plus the number of misrouted tickets. Score root causes at leaf level or within their parent,
never by label text alone, because generic leaves ("Other") repeat under several parents.

Illustration from [sd_2026](../use_cases/sd_2026/README.md) (held-out, n = 102): contact reason 77.5%
(baseline 60.8%, macro-F1 0.435); root cause given correct routing 65.8%; end to end 51.0%.

### 11.5 Cross-validation

When the gold set is small and is also the source of few-shot examples, k-fold cross-validation
estimates accuracy as if every gold ticket were an example: each fold's training tickets become the
examples, and the held-out fold is classified. The k-fold runs in
[leapspace_legacy](../use_cases/leapspace_legacy/README.md) and [evolve](../use_cases/evolve/README.md)
went through `rca run`, which does not inject examples, so they measured **zero-shot** agreement; their
folds also shared one checkpoint. Re-run through the library path, with a unique input per fold, before
quoting them as few-shot results.

### 11.6 Evaluation tiers

Each deliverable states how it was validated:

| Tier | Evidence | Allowed wording |
|---|---|---|
| A | Held-out labelled gold set | Accuracy, macro-F1, lift over baseline |
| B | Expert spot review of production samples | Expert agreement |
| C | Proxy: agent codes, survey, keyword cross-tab, retest | Agreement, not accuracy |
| D | Exploratory, no validation | Labelled exploratory |

Default acceptance thresholds, written down **before** the gold evaluation: blank/error rate ≤ 0.5%;
grounding ≥ 95% on non-empty evidence; tier A lift ≥ 10 points over the majority baseline and
macro-F1 ≥ 0.40; no class with n ≥ 5 at F1 = 0 without a named fix; retest agreement ≥ 80–85%
(otherwise "aggregate use only"); an n and a 95% interval beside every rate.

## 12. LLM resilience

Every call goes through four tiers, so that each record ends with either a result or an error stub:

| Tier | Trigger | Action |
|---|---|---|
| 1 Retry | Rate limit, service unavailable, connection error, timeout | Up to `retries` total attempts; wait `Retry-After` + 1 s if the server sends it, else exponential backoff with jitter from 2 s up to 90 s. |
| 2 Split | Response is not valid JSON / not a list, on a batch of more than 2 | Split the batch in half and retry each half, at most 4 levels deep. |
| 3 Single | Still failing, or a batch of 1–2 | One record per call, no further degradation; a failure becomes `{uid, _error}`. |
| 4 UID repair | The response lacks some uids | Re-request each missing uid alone; still missing → stub. |
| (other) | Any other error (exhausted retries, content-policy refusal) | Every record of the batch is stubbed with `_error`; no split. |

Supporting mechanisms:

- **Rate-limit gate.** When any call hits a retryable error, all in-flight calls pause for the
  `Retry-After` time (or 30 s), instead of retrying together and hitting the limit again.
- **Tolerant JSON parsing.** Code fences, curly quotes, trailing commas and surrounding prose are
  removed; complete objects are salvaged from truncated responses.
- **Log-probability fallback.** A deployment that rejects log-probabilities is remembered and not asked
  again.

Known gaps: Tier 4 does not discard unexpected or duplicate uids, so swapped answers pass unnoticed;
an empty response makes every uid go through Tier 4 one by one; a refused batch takes its innocent
neighbours with it.

## 13. Checkpointing and resume

Long runs are interrupted. `rca run` appends results after every batch and, on restart, skips records
whose **sentinel field** (the module's first code field, else bool, else text) is already filled. This
makes resume cheap and robust to crashes. It deliberately does not try to detect *why* a result exists,
so it cannot tell that a prompt, taxonomy or model has changed; the use-case notebooks therefore store
a fingerprint of each module's prompt (and output-affecting settings) beside the checkpoint and discard
it when the fingerprint changes. Resume works per batch, so changing the input between resumes can
re-send finished records. Details: [manual section 10](manual.md#10-checkpoints-and-crash-recovery).

## 14. Cost and the spend ladder

Spend is controlled by gates, each costing more than the last:

| Gate | What runs | Typical cost (est.) |
|---|---|---|
| G1 prompt review | Render and read every prompt; verbatim check | free |
| G2 smoke | 20–40 stratified tickets, fresh checkpoint | ≈ $0.2–1.3 |
| G3 gold evaluation or probe | The gold set, or 1,000 random production tickets, plus a retest | ≈ $1.4–14 |
| G4 full run or sample | All tickets, or a stratified sample with design weights | scales with volume |

Write the go / no-go decision down after G3 and before any run of 1,000 tickets or more. When the
question is about a distribution, a stratified sample with weights `w_h = N_h / n_h` and per-stratum
floors answers it for a fraction of the cost
([scopus_2ls_2026](../use_cases/scopus_2ls_2026/README.md) read 5,760 of about 64,000 tickets;
[csd_2026](../use_cases/csd_2026/README.md) 12,000 of about 50,700).

Unit costs have been about $0.005–0.014 per ticket per module pass. The system prompt dominates input
tokens at small batch sizes, so trimming it lowers cost directly.

## 15. Limitations

- **Bounded by the model and the taxonomy.** Vague labels, missing definitions or overlapping
  categories produce poor results whatever the model; the pipeline cannot repair an ambiguous taxonomy.
- **Non-determinism.** Temperature 0 still varies between runs; retest agreement is well below 100% for
  fine-grained taxonomies.
- **No cross-module reasoning within a stage.** Dependencies must be made explicit as stages, and a
  stage-1 error propagates to stage 2.
- **Self-reported confidence** is not a calibrated probability.
- **Grounding is lenient** for short and empty quotes and blind to cross-talk.
- **Resume ignores definition changes**; a stale checkpoint replays old answers silently.
- **Inference fields** (customer profile, insights, deflection potential) are less verifiable than
  coded, evidenced fields.
- **Gold sets are small** (tens to a few hundred tickets), so intervals are wide and rare categories
  stay unvalidated.
- **Enhancements in `rca run`:** only cost tracking runs there; feedback, confidence, hierarchical,
  incremental, language and quality-dashboard features need the library path.
- **Costs are estimates** from a static price table.

## 16. Data privacy

Transcripts are sent to the configured LLM provider under its data-processing agreement; with Azure
private endpoints they do not cross the public internet. Transcript text is stored in the input files,
checkpoints, outputs, review queues and feedback files (feedback keeps the first 1,500 characters);
incremental state keeps only a hash of the text. All of these live in the local data archive, never in
git. Names and email addresses reach the model and the deliverables unless the preparation step removes
them — decide on anonymisation per use case and record the decision. Inferred personal
characteristics (customer type, sophistication) should be treated as personal data.
