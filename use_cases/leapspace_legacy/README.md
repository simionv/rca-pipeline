---
name: leapspace_legacy
title: LeapSpace contact reason and root cause, gold-set version (first LeapSpace study)
product: LeapSpace
status: superseded
owner: TBD
period: 2025-10 to 2026-05
updated: 2026-11-12
tags: [hierarchical, gold-set, k-fold, feedback-examples]
question: Why do customers contact LeapSpace support, and what is the root cause behind each contact?
---

# LeapSpace contact reason and root cause, gold-set version (first LeapSpace study)

> **Superseded.** This was the first LeapSpace analysis (May to July 2026). It was replaced by
> [`leapspace_2026`](../leapspace_2026/README.md), which uses a revised taxonomy with written
> definitions and splits root cause by access type. Keep this page for the gold set, the SME review
> and the 5-fold cross-validation method, which are reusable.

## Business question
Classify every LeapSpace support ticket by **contact reason** (why the customer got in touch) and
**root cause** (what actually went wrong), so the product and support teams could see where access
and subscription problems come from. The work also set out to measure how accurate the AI labels
are against tickets labelled by people (a "gold set").

## Data
- **Source:** LeapSpace support ticket and thread extraction (the SQL used is archived as
  `data/leapspace data & threads extraction.sql`), collapsed to one conversation per ticket.
- **Period and size:** 1,326 tickets, 2025-10-24 to 2026-05-29 (mostly Web, then CSS Email, Chat, Phone).
- **Gold set:** `data/leapspace_gold_set_revised.xlsx`, 117 human-labelled tickets (116 after removing
  one duplicate, 115 usable). It replaced an older 98-ticket gold set built on a larger
  14-contact-reason / 56-root-cause taxonomy (kept as `*_OLD_*` backups).
- **Location:** `data/` (linked to the local data archive, never committed). Taxonomy JSON is read
  from `data/leapspace_taxonomies/`, not `generated/taxonomies/`.
- **Preparation:** see [`notebooks/04_leapspace_classify_with_gold_set.ipynb`](notebooks/04_leapspace_classify_with_gold_set.ipynb).

## Approach
- **Definition:** [`definitions/leapspace_pipeline_definition.xlsx`](definitions/leapspace_pipeline_definition.xlsx)
- **Steps / modules:** one **hierarchical** module, `contact_reason` (prefix `CR`). The model picks a
  single leaf code: the L1 group is the contact reason and the L2 leaf is the root cause, so only
  root causes valid for the chosen contact reason can be returned. Output fields:
  `contact_reason_primary_code` and `contact_reason_primary_description`.
- **Profiles:** [`profiles/leapspace_profile.json`](profiles/leapspace_profile.json) runs the whole
  dataset in one pass (batch size 6, concurrency 4).
- **Enhancements:**
  - **Gold set as few-shot examples.** The 115 gold tickets are written to
    `feedback/leapspace/contact_reason_corrections.jsonl` and injected into the prompt with the
    `smart` feedback strategy (up to 5 examples per batch, chosen by similarity to the batch).
  - **SME review (2026-06-12).** [`scripts/apply_gold_review.py`](scripts/apply_gold_review.py)
    matches a subject-matter expert's review of bulk predictions back to tickets by exact quote,
    updates or appends gold rows, and writes an audit report of matched / ambiguous / unmatched rows.
    It never guesses a match.
  - **LLM-checked corrections.** A reviewer re-checked 91 tickets where an earlier run disagreed with
    gold; their verdicts changed 9 contact-reason and 9 root-cause labels in the gold set.
  - **5-fold cross-validation.** Each fold uses about 92 gold tickets as examples and tests on the
    other 23, so every gold ticket is scored once without seeing itself as an example.

## Taxonomy at a glance
8 contact reasons (L1), 39 root causes (L2):

| Contact reason (L1) | Root causes (L2) |
|---|---|
| Institutional user cannot access | 10 |
| User not able to access | 6 |
| Subscription cancellation and (or) refund | 5 |
| Internal staff access | 4 |
| Billing | 4 |
| General info | 5 |
| Not enough info | 1 |
| Subscription request (incl. resub and trial) | 4 |

The root causes have **labels only, no descriptions** (the source sheet had none).

## How to re-run
```bash
cd use_cases/leapspace_legacy
rca validate
rca build
rca run --profile profiles/leapspace_profile.json --dry-run   # check, then run without --dry-run
```
The gold-set preparation and the k-fold evaluation live in the notebook, not in a profile. The
notebook still starts with a hard-coded `os.chdir` to the old project folder; change that first.

## Results
- **Bulk run (2026-07-15), 1,326 tickets:** Institutional user cannot access 506 (38%),
  Subscription cancellation and (or) refund 380 (29%), User not able to access 120, General info 118,
  Subscription request 93, Billing 69, Not enough info 26, Internal staff access 14. Top root causes:
  Cancellation and or refund service request (335) and Institution not entitled (276). All codes
  were valid contact-reason / root-cause pairs.
- **5-fold cross-validation on 115 gold tickets** (`runs/output/leapspace_kfold_eval_results.xlsx`):
  - Contact reason: **68.7%** accuracy (folds ranged 60.9% to 78.3%). Strong on Subscription
    cancellation (F1 0.92) and General info (F1 0.88); weak on User not able to access (F1 0.26) and
    Internal staff access (no correct hits, only 3 gold tickets).
  - Root cause (exact leaf): **28.7%** accuracy.
  - Biggest confusion: individual "User not able to access" tickets labelled as institutional
    (13 of the 36 contact-reason errors). Error list: `runs/output/leapspace_Root_Cause_errors.csv`.

## Lessons and reuse tips
- **Labels without definitions cap accuracy.** Root cause at under 30% was the main reason for the
  rewrite in `leapspace_2026`, which gives every category a "use when" definition and signals.
- **Individual vs institutional access needs its own rule.** This was the largest error source here
  and became an explicit split in the next version.
- **Copy the k-fold method** (notebook section 9) whenever a gold set exists: it gives an honest
  accuracy figure while still letting all gold tickets serve as examples in production.
- **Copy `apply_gold_review.py`** to fold an SME review back into a gold set safely (quote matching,
  audit file, no guessing).
- Small gold classes (3 or fewer tickets) make per-class scores meaningless; aim for 10+ per class.

## Known issues
- **These results are zero-shot, not few-shot.** The notebook passed the gold tickets with `--feedback-dir`, but before v0.1.1 `rca run` silently ignored that setting, so no examples reached the model, in the full run or in the k-fold folds (which also shared one checkpoint). Re-run with v0.1.1 or later, with a separate input and checkpoint per fold, to measure the real effect of the examples.
- `rca validate`: no errors, **53 warnings**: 39 root causes have no description, and 14 labels
  (for example *Other*, *Not enough info*, *Session data conflict/ cache and cookies issue*) appear
  under more than one contact reason. The repeats are expected in a hierarchical taxonomy; the
  missing descriptions are the real gap.
- The profile reads taxonomies from `data/leapspace_taxonomies/` in the archive. Its codes and labels
  match `generated/taxonomies/contact_reason.json`.
- `src/rca_pipeline/tools/run_kfold_eval.py` expects the old gold-set columns (`Ticket Number`,
  `Explanations`) and a 69-ticket set; the notebook inlines its own k-fold code instead.
- One gold ticket (an institutional ticket labelled *User not supposed to be entitled*) has no valid
  code and is excluded.
- The feedback file uses the `CR` codes of this taxonomy, so it **cannot** be reused by
  `leapspace_2026` without re-coding.
- `scripts/patch_*.py` are one-off notebook patches kept for history. The docstring of
  `scripts/build_leapspace_definition.py` describes an earlier 11-group version.
- `run_pipeline.log` in this folder is from a failed attempt (missing LLM credentials), not a result.

## To confirm
- Who asked for the analysis and who the SME reviewer was.
- What `data/leapspace_collapsed_may_june.*` and `leapspace_collapsed_split.xlsx` were used for
  (an earlier subset or split run?).
- Whether any deck or report was shared from these results.
