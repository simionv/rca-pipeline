---
name: scopus_2026
title: Scopus 2026 — two-stage Level 1 / Level 2 ticket classification
product: Scopus
status: active
owner: TBD
period: 2026-01 to 2026-09
updated: 2026-11-12
tags: [two-stage, hierarchical]
question: Why did customers contact Scopus support in 2026, at Level 1 (16 revised categories) and at Level 2 (the specific reason within each category)?
---

# Scopus 2026 — two-stage Level 1 / Level 2 ticket classification

## Business question
Scopus wanted every 2026 support ticket classified against its **revised contact-reason taxonomy**:
16 Level 1 categories, each with its own list of Level 2 reasons. The categories, decision rules and
Level 2 descriptions come from the business ("Scopus Ticket Rules and Root Cause Descriptions v3").
The original Oracle contact-reason tags use a different taxonomy and are **not** treated as evidence.

Main changes in the revised taxonomy:
- `Account Management` no longer exists. Account changes (change email, merge or delete accounts,
  registration, password questions) count as **Access**, even when the customer can sign in.
- Requests about personal data go to the new **Data / Privacy Request** category.
- **Access** and **Scopus AI Access** share one list of 11 Level 2 values, plus `Unknown rootcause`
  for tickets where no cause is stated anywhere.

## Data
- **Source:** Scopus support tickets closed January to September 2026 (Oracle export, "verbatim cleaned" workbook).
- **Period and size:** 11,940 tickets. About 1,700 have no customer text at all.
- **Location:** `data/Scopus/scopus26_stage1_input.csv` (prepared input). The raw workbook currently sits
  in the archive under `scopus_content/data/Scopus/`, not under this use case.
- **Preparation** (notebook 20, section 5): the subject is put in front of the conversation
  (`Subject: …`). Tickets with an empty conversation **and** an empty subject are assigned
  *Unclear / No Query → Empty Chat / No Content* by rule, with no LLM call (0 in this data).
  Long conversations are cut to 16,000 characters (first 4,000 + last ~11,900); 326 tickets were cut.

## Approach
- **Definition:** [`definitions/scopus_2026_pipeline_definition.xlsx`](definitions/scopus_2026_pipeline_definition.xlsx)
  (15 modules). It is **written by notebook 20** from the rules workbook — edit the notebook, not the Excel.
- **Notebook:** [`notebooks/20_scopus_2026_two_stage.ipynb`](notebooks/20_scopus_2026_two_stage.ipynb) does
  everything: reads the rules, writes the definition, builds, preprocesses, routes and merges.
- **Stage 1 — `scopus_l1`:** one Level 1 code for every ticket. The business decision rules (e.g. "can
  the customer access Scopus?" first) go into the prompt verbatim.
- **Stage 2 — 14 Level 2 modules** (`scopus_l2_access`, `_performance`, `_author_profile`,
  `_citation_metrics`, `_unclear`, `_funding`, `_content`, `_help_article`, `_search_feature`,
  `_institution_admin`, `_subscription`, `_non_scopus`, `_orcid`, `_api`). Each runs only on the tickets
  that stage 1 put in its category. Access and Scopus AI Access both go to `scopus_l2_access`.
  Data / Privacy Request has no Level 2 list, so its Level 2 is set by rule.
- **Every module returns** a code, a short justification and a verbatim evidence quote; the quote is
  checked against the ticket text (`*_evidence_grounded`).
- **Profiles:** `profiles/scopus_2026_l1.json` runs stage 1. `profiles/scopus_2026_l2_<category>.json`
  (14 files) run stage 2. Their inputs, `runs/intermediate/scopus26_subset_<category>.csv`, are written
  by notebook 20 from the stage-1 output, so they do not exist until stage 1 has run.
- **Gates in the notebook:** (1) read every prompt for free; (2) preprocess; (3) 30-ticket smoke test
  (~$0.30); (4) 300-ticket stratified sample for SME review (~$3), then a hard stop
  (`STOP_BEFORE_FULL_RUN`) before the full run. A prompt fingerprint discards stale checkpoints after edits.

## Taxonomy at a glance
Stage 1 (`scopus_l1`, 16 categories) and the Level 2 count used for each:

| Level 1 | L2 | Level 1 | L2 |
|---|---|---|---|
| Access | 12 (shared) | Help Article Feedback | 5 |
| Scopus AI Access | 12 (shared) | Search / Feature Question | 7 |
| Performance & Functionality Issues | 7 | Institution Admin / Support | 10 |
| Author Profile Correction | 10 | Data / Privacy Request | rule, no LLM |
| Citation / Metrics | 8 | Subscription / Sales | 7 |
| Unclear / No Query | 7 | Non-Scopus / Wrong Product | 5 |
| Funding / Awarded Grants Data | 5 | ORCID Issue | 4 |
| Content / Indexing | 10 | API / Integration | 4 |

Full lists and definitions: the `taxonomy` sheet of the definition.

## How to re-run
```bash
cd use_cases/scopus_2026
rca validate
rca build
rca run --profile profiles/scopus_2026_l1.json --dry-run   # stage 1, check first
rca run --profile profiles/scopus_2026_l1.json
# then run notebook 20 sections 10-12 to split by Level 1, run the 14 Level 2 profiles and merge
```
The simplest route is to run notebook 20 top to bottom: it calls the same commands and does the
splitting and merging for you. The final deliverable is `runs/output/scopus_2026_l1_l2_classification.xlsx`.

## Results
- **Sample only so far.** The archived notebook stops at the SME review gate. The 300-ticket sample
  (346 after stage-2 routing checks) ran cleanly: 1 blank Level 2 out of 346. Predicted Level 1 on the
  sample was led by Access (105), Performance & Functionality (47), Author Profile Correction (29),
  Unclear / No Query (27), Content / Indexing (24), Citation / Metrics (23) and Institution Admin (23).
- **Cost:** sample $4.29 (~$0.012 per ticket); projected full run ~$148 for 11,940 tickets.
- **Review file:** `runs/output/scopus_2026_sample_review.xlsx` (stratified by Oracle reason, blank review columns).
- No gold set exists for Scopus, so there is no accuracy figure yet.

## Lessons and reuse tips
- **Copy this pattern for any "L1 then per-category L2" request**: one small stage-1 module, one
  Level 2 module per category, routing by predicted Level 1 code. Each Level 2 prompt stays short.
- Every taxonomy is two-level because the prompt always asks for leaf codes. In stage 1 each
  Level 1 is a group with one leaf repeating its label.
- Put business decision rules into the prompt verbatim and add an explicit "override" block when the
  taxonomy has changed since the rules were written.
- Assign trivial cases (empty tickets, categories with no Level 2) by rule — cheaper and consistent.
- Avoid field names starting with `contact_reason_` / `root_cause_`: the pipeline strips them.
- Keep the stop-before-full-run gate: an SME read of 300 tickets is cheap compared with a rerun.

## Known issues
- `rca validate`: no errors; 14 warnings, all "input file `runs/intermediate/scopus26_subset_*.csv` not
  found". This is expected — notebook 20 creates them after stage 1.
- Notebook 20 still expects the rules workbook at `definitions/Scopus Ticket Rules and Root Cause
  Descriptions v3.xlsx` and the raw tickets at `data/Scopus/scopus verbatim cleaned 2026.xlsx`. In the
  new layout the rules workbook is in `use_cases/scopus_content/docs/` and the raw file is in the
  scopus_content archive. Copy or link them before re-running.
- Two Level 2 labels look alike across categories ("Awarded Grant Add Request" under Content / Indexing,
  "Missing Awarded Grant" under Funding). Both are kept from the workbook; Level 1 decides.
- The rules workbook lists only 4 Level 2 values for Scopus AI Access; by agreement it uses all Access values.

## To confirm
- Has the full run (stage 1 + stage 2 on all 11,940 tickets) been done since the archive snapshot? If so, add the headline distribution here and set the status.
- Outcome of the SME review of the 300-ticket sample, and any definition changes it led to.
- Who requested the analysis and who owns it.
