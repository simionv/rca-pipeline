---
name: evolve
title: Evolve 2026 — contact reason and root cause with an SME gold set
product: Evolve
status: complete
owner: TBD
period: 2026-01 to 2026-02
updated: 2026-11-12
tags: [hierarchical, gold-set, k-fold, feedback-examples]
question: Why do Evolve customers contact support in 2026, and what is the root cause within each contact reason?
---

# Evolve 2026 — contact reason and root cause with an SME gold set

## Business question
Classify every 2026 Evolve support ticket by contact reason (L1) and the root cause behind it (L2), using a
codebook written by subject-matter experts (SMEs), and measure how well the model agrees with SME labels.
It follows the LeapSpace gold-set pattern (see `leapspace_legacy`).

## Data
- **Source:** Evolve support tickets (phone, web, chat, email), export `Evolve_Collapsed.xlsx`. Columns used:
  `Reference #` (ID), `Conversation` (text). The export also carries the agent-tagged `Contact_Reason_Level_1/2`,
  `Channel` and `Chat_Start_Date`.
- **Period and size:** the export has 126,504 tickets from 2023-10 to 2026-02-10. Only the 2026 slice was
  classified: **20,070 tickets** (2026-01-01 to 2026-02-10). By channel: phone 7.8k, web 5.9k, chat 5.3k, email ~1k.
- **Gold set:** `Evolve gold set.xlsx`, 284 SME-labelled tickets (282 after removing duplicates, 280 that map to
  the taxonomy). Its `Definition` sheet is the SME codebook.
- **Corrections:** `evolve_Root_Cause_errors.xlsx`, a review of the 170 gold tickets where an earlier run disagreed.
  51 got a reviewer verdict and reason, which changed 24 contact-reason and 32 root-cause gold labels.
- **Location:** `data/`, `runs/`, `feedback/` (linked to the local archive). Also there: `data/evolve_taxonomies/`
  and `data/evolve_code_map.json` (label-to-code lookup).
- **Preparation:** [`notebooks/05_evolve_classify_with_gold_set.ipynb`](notebooks/05_evolve_classify_with_gold_set.ipynb)
  filters to 2026 and writes the slice to `runs/_evolve_sample_tmp.xlsx`. Feedback text is cut to 1,500 characters.

## Approach
- **Definition:** [`definitions/evolve_pipeline_definition.xlsx`](definitions/evolve_pipeline_definition.xlsx)
- **Steps / modules:** one hierarchical `contact_reason` module, where L1 is the contact reason and L2 is the root cause
  within that contact reason. The model picks one leaf code (for example CR4.2) and gives a description, justification,
  evidence quote, evidence type, contact type (incident / service request / user guidance) and personal vs institutional.
  The old separate `root_cause` module was switched off on 2026-07-02 and its evidence fields moved into `contact_reason`.
- **Notebook flow:** parse the SME `Definition` sheet into the taxonomy sheet, then `rca build`, then turn the gold set
  (with corrections) into few-shot examples, classify the 2026 slice, and finally run 5-fold cross-validation on the gold set.
- **Profiles:** none. The notebook calls `rca run` with flags (see below).
- **Enhancements:** 280 gold tickets as feedback examples (`smart` strategy, 5 per batch). The reviewer reasons
  are used as the example `reason`. Evidence grounding is checked.

## Taxonomy at a glance
`contact_reason`: 11 L1 groups, 54 L2 root causes. Access / QR code (8), Login / password (5), Account (7),
Course Access (6), eBook & other stores (6), Resources (5), Product request (6), Other access related (2),
Other not access related (3), Non Evolve (1), Trial (5). The labels "Other", "Not enough info" and "Lack of user
guidance" repeat under several L1 groups, each with its own description.

## How to re-run
```bash
cd use_cases/evolve
rca validate
rca build
rca run --input runs/_evolve_sample_tmp.xlsx --id-col "Reference #" --text-col Conversation \
  --modules contact_reason --feedback-dir feedback/evolve --feedback-strategy smart \
  --feedback-max-examples 5 --batch-size 10 --concurrency 4 --track-costs --dry-run
```
Always pass `--modules contact_reason`. The other enabled modules were never run, and two of them have no taxonomy.
To rebuild the slice, the gold-set examples or the k-fold evaluation, run the notebook. Its first cell still points
to an old Windows path, so change that before running.

## Results
- **Full run (2026-07-15):** all 20,070 tickets classified at about $0.0065 per ticket (roughly $130–140 in total).
  16 rows came back blank, and 475 evidence quotes could not be found in the transcript.
- **Contact reason mix:** Product request 3.2k, Course Access 3.1k, Access / QR code 3.0k, Account 2.7k,
  Other not access related 2.3k, Login / password 2.1k, eBook & other stores 1.3k, Other access related 1.0k,
  Resources 0.8k, Non Evolve 0.3k, Trial 0.3k.
- **Root cause:** "Not enough info" (5.6k) and "Other" (5.1k) together take 54% of tickets. The most common
  specific causes are Lack of user guidance (1.6k), Invalid code (1.0k), No institution associated (0.7k) and
  Update email / Account update (0.6k).
- **Gold-set accuracy (5-fold, n=280):** contact reason **59.6%**, root cause **41.1%**, both correct 32.9%.
  Strong classes: Access / QR code (F1 0.82), Login / password (0.74), Product request (0.69), Damaged code (0.88),
  Duplicate accounts (0.80). Weak classes: Resources (recall 0.22), Other access related, Non Evolve.
  Results are in `runs/output/evolve_kfold_eval_results.xlsx`. No deck was found.

## Lessons and reuse tips
- If the SMEs already have a codebook, parse it into the taxonomy sheet as this notebook does. Don't hand-write it.
- Root-cause labels that repeat under different parents need parent-scoped matching. Use `resolve_cr_rc_to_code`
  in the notebook, which normalises labels, resolves the contact reason first, then the root cause within it.
- The biggest root-cause errors are true causes predicted as "Not enough info". Tighten that description,
  or report it separately, before trusting the root-cause mix.
- A round of reviewed disagreements with written reasons is cheap and goes straight back in as few-shot examples.

## Known issues
- **These results are zero-shot, not few-shot.** The notebook passed the gold tickets with `--feedback-dir`, but before v0.1.1 `rca run` silently ignored that setting, so no examples reached the model, in the full run or in the k-fold folds (which also shared one checkpoint). Re-run with v0.1.1 or later, with a separate input and checkpoint per fold, to measure the real effect of the examples.
- `rca validate` passes with 24 warnings: 21 repeated L2 labels (expected by design), `resolution` and
  `troubleshooting` have no taxonomy, and `troubleshooting` has no code field.
- `root_cause` is kept in the workbook but disabled. `resolution`, `escalation`, `troubleshooting` and `metadata`
  are enabled but were never run or checked.
- The definition's README sheet still describes "discovery mode / empty taxonomy", which is out of date.
- The "Trial" group has no gold examples, so its accuracy is unknown.

## To confirm
- Who asked for this and who owns it. What decision it fed, and whether a deck or report exists.
- Whether `period` should show the data window (Jan–Feb 2026) or when the work was done (July 2026).
- Whether the 2023–2025 tickets (106k) were ever meant to be classified.
