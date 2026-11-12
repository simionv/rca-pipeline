---
name: sd_2026
title: ScienceDirect 2026 — contact reason and root cause (two-stage)
product: ScienceDirect
status: complete
owner: TBD
period: 2026-01 to 2026-07
updated: 2026-11-12
tags: [two-stage, hierarchical, gold-set, feedback-examples]
question: Why do ScienceDirect customers contact support in 2026, and what is the root cause behind each contact reason?
---

# ScienceDirect 2026 — contact reason and root cause (two-stage)

## Business question
ScienceDirect operations wanted every 2026 support ticket labelled with **why the customer got in touch**
(contact reason, 13 categories) and **what was behind it** (root cause, 56 categories in total, each tied to
one contact reason). The category list and its definitions came from the operations team's SME gold workbook,
which also holds 163 human-labelled tickets used to measure accuracy. The output supports volume reporting and
prioritising fixes (for example, firewall blocks versus entitlement problems).

## Data
- **Source:** ScienceDirect ticket export with full conversation threads (`data/sd_collapsed_2026.csv`, one row per ticket),
  plus the SME gold workbook (category definitions, allowed contact reason / root cause pairs, 163 labelled tickets).
- **Period and size:** 23,344 rows; 23,055 dated January–July 2026 were kept (289 earlier rows set aside, not dropped silently).
- **Location:** `data/`, `runs/`, `output/` and `feedback/` are links into the local data archive
  (set up with `python tools/link_archive.py <archive>`) — never committed.
- **Preparation** (done in [`notebooks/07_sd_2026_two_stage.ipynb`](notebooks/07_sd_2026_two_stage.ipynb), sections 5–6):
  - 2,250 near-empty tickets (payload under 150 characters, e.g. ghost calls) get "Not enough info" by rule, with no LLM call.
  - Very long conversations are cut to 16,000 characters (first 4,000 + last 11,900, with a visible truncation marker);
    only 234 tickets were affected.
  - Result: 20,805 tickets sent to the model, written to `data/sd_stage1_input_2026.csv`.

## Approach
- **Definition:** [`definitions/sd_2026_pipeline_definition.xlsx`](definitions/sd_2026_pipeline_definition.xlsx) — 12 modules, all enabled.
- **Steps / modules:**
  1. **Stage 1 — `sd_contact_reason`:** one of 13 contact reasons for every ticket.
  2. The notebook **splits tickets by predicted contact reason code** and writes one subset file per reason.
  3. **Stage 2 — one root-cause module per contact reason** (`sd_rc_security_block`, `sd_rc_access_reports`,
     `sd_rc_institutional_signin`, `sd_rc_close_delete`, `sd_rc_login`, `sd_rc_bulk_account`, `sd_rc_teams_departments`,
     `sd_rc_update_email`, `sd_rc_download_config`, `sd_rc_accessing_content`, `sd_rc_other_not_access`). Each module only
     sees the root causes allowed for its reason, so an impossible pair cannot be produced. The two reasons with a single
     allowed root cause ("Other - access related", "Not enough info") are filled in automatically, without a model call.
  4. The notebook merges everything back onto the 23,055 tickets; a `classification_source` column says whether a row was
     labelled by the model, forced (single root cause) or by rule (empty ticket).
- **Profiles:**
  - `profiles/sd_2026_step1_contact_reason.json` — stage 1 on all 20,805 tickets.
  - `profiles/sd_2026_step2_<reason>.json` (11 files) — stage 2, one per contact reason, each reading its subset from
    `runs/intermediate/sd_2026_subset_<reason>.csv`.
  - All use batch size 5, 40,000 max characters per batch, 4 parallel calls, cost tracking on.
- **Enhancements:** each module returns a code, a short justification and a verbatim evidence quote (checked against the
  transcript). Accuracy measured against the SME gold set before the full run. 34 corrections were seeded into
  `feedback/` (contact reason, security block, other-not-access, accessing content) for a possible next iteration.

## Taxonomy at a glance
Stage 1 has 13 contact reasons (each one L1 group with a single L2 leaf). Root causes per contact reason (stage 2):

| Contact reason | Root causes |
|---|---|
| Access blocked by security/network controls | 5 |
| Access reports | 4 |
| Institutional sign in not working | 4 |
| Close delete account | 3 |
| Login issues | 9 |
| Bulk account issue | 5 |
| Set up teams or departments | 3 |
| Update email address | 3 |
| Account configuration for download articles | 3 |
| Accessing content | 5 |
| Other - not access related | 10 |
| Other - access related / Not enough info | 1 each (assigned automatically) |

Full list: the `taxonomy` sheet of the definition.

## How to re-run
```bash
cd use_cases/sd_2026
rca validate
rca build
rca run --profile profiles/sd_2026_step1_contact_reason.json --dry-run   # check, then run without --dry-run
# after the notebook has split stage 1 output into subsets:
rca run --profile profiles/sd_2026_step2_accessing_content.json --dry-run  # repeat for each step2 profile
```
Preprocessing, the split between stages, the merge and the scoring all live in the notebook, so use it alongside the CLI.
Full run cost was estimated at about $275 and 8 hours (stage 1 about $150, stage 2 about $120).

## Results
- **Volume (23,055 tickets):** Other - not access related 29%, Accessing content 27%, Access blocked by security/network
  controls 18%, Not enough info 13% (2,250 by rule, 676 by model), Institutional sign in not working 5%; every other reason is 3% or less.
- **Top root causes overall:** Issue with content entitlement (14% of all tickets), Content Protection - Cloudflare firewall
  rules (12%), Content issue (7%), Billing / invoice (4%).
- **Accuracy against the SME gold set** (headline = 102 labelled tickets not in the 2026 run, so free of leakage):
  contact reason 77.5% (majority-class baseline 60.8%, macro-F1 0.44); root cause 65.8% where stage 1 routed correctly;
  **both right end-to-end 51.0%**. On the 61 labelled tickets that are in the run: 62–66% contact reason, 43–48% end-to-end.
  With about 100 tickets the margin of error is roughly ±8 points.
- Most stage 1 errors are between "Access blocked by security/network controls" and "Accessing content".
- **Deliverable:** `runs/output/sd_2026_two_stage.xlsx` (13 sheets: all tickets, summaries, contact reason x root cause
  matrix, by month and channel, eval and methodology, taxonomy, run manifest, cost reports) and a full-text CSV.

## Lessons and reuse tips
- **Copy the two-stage routing** whenever each top-level category has its own short list of sub-categories: route by
  stage 1 *code* (not label text) and run one small module per branch.
- **Gate before spending:** review prompts (free), 30-ticket smoke (~$0.25), gold-set eval (~$2), 1,000-ticket probe (~$8),
  then the full run. Notebook sections 4 and 7–9 are a reusable template for this.
- **Report two numbers for stage 2:** root cause given correct routing (module quality) and end-to-end (what ops experiences).
- Keep a held-out slice of the gold set out of the feedback store so you can still answer "did feedback help?".
- Clean label text before joining: the gold workbook carries invisible characters and stray spaces, and one root cause
  ("Request for information") sat under different contact reasons in two sheets — the allowed-pairs sheet was used.
- A checkpoint resumes even after a prompt change; the notebook fingerprints each module's prompt so only edited modules re-run.

## Known issues
- `rca validate`: no errors, no warnings.
- Two root-cause modules (`sd_rc_access_reports`, `sd_rc_update_email`) have no labelled examples and are unvalidated.
- One gold ticket has the contact reason pasted into the root-cause cell; it was excluded from root-cause scoring.
- The gold workbook's conversation text differs from the ticket export for almost all overlapping tickets, so in-run and
  held-out accuracy measure slightly different text.
- 10 tickets have a blank contact reason in the delivered workbook.
- Evidence quotes are occasionally not found verbatim in the transcript; these are flagged (`*_evidence_grounded`), not removed.

## To confirm
- Whether the seeded feedback corrections were ever applied in a second run (the profiles do not reference `feedback/`).
- Who requested the analysis and who owns it now.
- Whether the "Request for information" parentage question was resolved with the taxonomy owner.
