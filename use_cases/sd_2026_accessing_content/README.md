---
name: sd_2026_accessing_content
title: ScienceDirect 2026 — "Accessing content" and its sub-contact reasons
product: ScienceDirect
status: complete
owner: TBD
period: 2026-01 to 2026-07
updated: 2026-11-12
tags: [two-stage, gate-then-subreason]
question: How many 2026 ScienceDirect tickets are about accessing specific content, and what kind of content-access need is behind each one?
---

# ScienceDirect 2026 — "Accessing content" and its sub-contact reasons

## Business question
A follow-up to [`sd_2026`](../sd_2026/README.md). The ScienceDirect team wrote a short specification
([`docs/ScienceDirect – "Accessing Content" and further LLM analysis.docx`](docs/)) asking for a simpler, stricter split:
is each ticket about **getting hold of specific content** (an article, issue, archive item, package or supporting file),
or **anything else** (login, browser, network blocks, billing, account admin, ScienceDirect AI)? For the content tickets
only, which of six sub-contact reasons applies — Patient Access, institution subscription question, institutional
entitlement failure, personal purchase, missing content, or other. The spec insists on classifying the customer's
actual need, not the word "access", and on not inferring anything the ticket does not state.

This is an independent classification of the same ticket extract as `sd_2026`; the two taxonomies answer different
questions and are not comparable ticket by ticket.

## Data
- **Source:** the same ScienceDirect ticket export as `sd_2026` (`sd_collapsed_2026.csv`, full conversation threads).
  Note: an earlier candidate file named as ScienceDirect turned out to be a copy of Evolve (nursing education) data and
  was rejected — check the product mix of any input before running.
- **Period and size:** 23,055 tickets dated 1 January – 31 July 2026 (289 earlier rows set aside).
- **Location:** `data/`, `runs/`, `output/` and `feedback/` are links into the local data archive
  (set up with `python tools/link_archive.py <archive>`) — never committed.
- **Preparation** ([`notebooks/10_sd_2026_accessing_content.ipynb`](notebooks/10_sd_2026_accessing_content.ipynb), section 5):
  1,014 content-free tickets (payload under 40 characters) get "Anything else" by rule; conversations over 16,000
  characters are cut to the first 4,000 + last 11,900 (234 tickets). 22,041 tickets go to the model, written to
  `data/sd_ac_stage1_input_2026.csv`.

## Approach
- **Definition:** [`definitions/sd_2026_accessing_content_definition.xlsx`](definitions/sd_2026_accessing_content_definition.xlsx) — 2 modules, both enabled.
- **Steps / modules:**
  1. **Stage 1 — `sd_ac_primary` (gate):** Accessing content vs Anything else, for every ticket.
  2. The notebook routes only the "Accessing content" tickets (by code) into a subset file.
  3. **Stage 2 — `sd_ac_subreason`:** one of six sub-contact reasons for that subset. "Anything else" tickets can never
     get a sub-reason, which is what the spec requires.
- **Profiles:**
  - `profiles/sd_2026_ac_primary.json` — stage 1, reads `data/sd_ac_stage1_input_2026.csv`.
  - `profiles/sd_2026_ac_subreason.json` — stage 2, reads `runs/intermediate/sd_ac_stage2_input.csv`.
  - Both: batch size 5, 40,000 max characters per batch, 4 parallel calls, temperature 0.
- **Definitions are copied word for word from the spec** (the notebook checks this against the .docx). Two rules were
  added by the analyst and are marked as such in the workbook `notes` column: a decision order for the primary split
  (the obstacle the ticket actually states decides; Patient Access counts as content), and an evidence threshold for
  stage 2 (use OTHER when the required markers are missing — OTHER is a valid answer, not a failure).
- **Checks instead of accuracy:** every answer carries a verbatim evidence quote (checked against the transcript), and a
  "marker audit" tests whether the spec's required keywords for the chosen sub-reason appear in the text.

## Taxonomy at a glance
- **Stage 1 (`sd_ac_primary`):** Accessing content; Anything else (2 categories, one leaf each).
- **Stage 2 (`sd_ac_subreason`):** PA – Patient Access request; INST_INFO – does an institution subscribe to a title/year/package;
  INST_ISSUE – institution entitled but user cannot access; PURCHASED – content bought directly from ScienceDirect;
  AVAILABILITY – missing article, archive item or supplementary material; OTHER (6 categories, one leaf each).

Full definitions: the `taxonomy` sheet of the definition.

## How to re-run
```bash
cd use_cases/sd_2026_accessing_content
rca validate
rca build
rca run --profile profiles/sd_2026_ac_primary.json --dry-run     # check, then run without --dry-run
# after the notebook has written the Accessing content subset:
rca run --profile profiles/sd_2026_ac_subreason.json --dry-run
```
Preprocessing, routing, the marker audit, the merge and the deliverable live in the notebook. Measured cost: about
$0.0056 per ticket; full run about $165 (stage 1 ~$125 / 4.7 h, stage 2 ~$40 / 1.4 h).

## Results
- **Stage 1 (23,055 tickets):** Anything else 71.9%, **Accessing content 28.1% (6,476)**, 10 refused by the model.
  Content tickets are far more common in CSS Email (about 54% in a 1,000-ticket probe) than in Web, Chat or Phone (10–14%).
- **Stage 2 (6,466 content tickets scored):** PA 74.7%, OTHER 14.5%, PURCHASED 4.1%, INST_ISSUE 3.4%, AVAILABILITY 2.4%,
  INST_INFO 1.0%. Patient Access requests dominate the content workload.
- **Evidence quotes:** 99.6% found verbatim in the transcript (1,000-ticket probe).
- **Marker audit** (share of a code chosen with none of its required markers present): PA 2.0%, INST_INFO 6.0%,
  PURCHASED 4.9%, AVAILABILITY 9.9%, INST_ISSUE 16.4%. 517 of 936 OTHER tickets contain markers for a specific code —
  possible misses, often agent boilerplate.
- **There is no accuracy figure** for either stage: no human-labelled set exists for this taxonomy. All numbers are counts
  and distributions; the deliverable's `Eval methodology` sheet says so.
- **Deliverable:** `runs/output/sd_2026_accessing_content.xlsx` (10 sheets) plus a full-text CSV and a summary workbook.

## Lessons and reuse tips
- **Copy the gate-then-subreason pattern** for any "is it X? if so, which kind of X?" request: a cheap two-way gate on
  everything, then a focused module only on the positives.
- When the brief is a Word spec, transcribe definitions verbatim and assert the transcription against the document, so a
  spec edit cannot silently go stale. Keep any rules you add clearly labelled as yours.
- Sample smoke tests across months and channels, not the first rows: templated requests (e.g. Patient Access forms)
  arrive in bursts and skew a sliced sample.
- When a keyword audit disagrees with the model, suspect the audit first — early marker lists were too narrow and made
  INST_* look like they over-fired.
- Temperature 0 is not fully repeatable (batch neighbours vary); expect about ±1 ticket of noise in a 30-ticket smoke.
- Highest-value next step: hand-label about 150 Accessing content tickets (stratified by predicted code) to get real precision/recall.

## Known issues
- `rca validate`: no errors, no warnings.
- No gold set, so neither stage is validated for accuracy.
- The spec's OTHER definition is cut off mid-sentence; the finished wording from its "Classification principles" was used
  and the defect recorded for the taxonomy owner.
- 10 tickets were refused at stage 1 and 10 at stage 2 (marked `error:refused_*` in `classification_source`).
- 116 of 4,828 PA tickets do not contain the word "patient" anywhere, although the spec says Patient Access must be explicit.
- INST_ISSUE has the highest unsupported rate (16.4%) — worth reviewing first if definitions are tuned.

## To confirm
- Who wrote the specification and requested the study.
- Whether a labelled set for the six sub-contact reasons was ever produced.
- The notebook mentions extending to 2025 (about 106,000 tickets), which does not match the 289 pre-2026 rows in this extract — confirm which file that refers to.
