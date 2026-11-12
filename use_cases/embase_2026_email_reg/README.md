---
name: embase_2026_email_reg
title: Embase 2026 email-registration tickets, with a discovered contact reason for the rest
product: Embase
status: complete
owner: TBD
period: 2025-12 to 2026-09
updated: 2026-11-12
tags: [gate-then-subreason, email-registration, discovery]
question: How many Embase support tickets are about email registration or an email-account problem, what kinds are they, and why did everyone else contact support?
---

# Embase 2026 email-registration tickets, with a discovered contact reason for the rest

> **Sibling study:** [`leapspace_2026_email_reg`](../leapspace_2026_email_reg/README.md) asks the
> same question for LeapSpace with the same design (gate, then sub-reason, then contact reason) and
> the same cleaning code. The difference: LeapSpace reused an existing contact-reason taxonomy,
> while Embase had none, so both the sub-reasons and the contact reasons here were **discovered**
> from the tickets.

## Business question
Size and describe the email-registration problem in Embase support: tickets where the customer's
issue is the email address on an account or the registration itself (new user IDs, removing users,
changing the email on a licence, missing verification emails, and so on). Every other ticket gets a
contact reason, so the email-registration share can be read against the full mix.

## Data
- **Source:** the Embase thread export of 2026-07-27 to date
  (`data/embase/embase verbstim extraction_2026-07-27_todate.tsv`), **one row per message**, plus a
  metadata file with the contact reason the **agent** chose for each ticket
  (`embase metadata extraction_2026-07-27_todate.csv`). The agent's reason is only joined on for
  comparison (`agent_cr_l1` / `agent_cr_l2`); it is not used to classify.
- **Period and size:** 3,037 message rows over **774 tickets**, 2025-12-04 to 2026-09-29.
  Channels: Web 414, Email 282, Chat 56, Phone 21, Fax 1.
- **Location:** `data/embase/` (linked to the local data archive, never committed).
- **Preparation** ([`notebooks/19_embase_2026_email_registration.ipynb`](notebooks/19_embase_2026_email_registration.ipynb), sections 1 to 3),
  same code as the LeapSpace notebook:
  - 266 exact duplicate rows dropped.
  - Messages ordered by creation time (the `sequence` column is not a real order).
  - HTML, quoted reply history, banners and repeated pasted messages removed. Text shrank to 24% of
    the raw size; Embase record markup such as `<inf>` is kept as content.
  - One speaker-labelled conversation per ticket (CUSTOMER, AGENT, CUSTOMER (logged by agent)).
  - Conversations over 16,000 characters sent as start plus end (6 tickets).

## Approach
- **Definition:** [`definitions/embase_2026_email_registration_definition.xlsx`](definitions/embase_2026_email_registration_definition.xlsx)
- **Steps / modules:**
  - **Stage A, gate** `embase_emailreg` (EER), every ticket: email registration / email-account
    issue, or not. Judges what the customer (or a librarian or administrator writing for users)
    raises, not agents asking for an email address.
  - **Stage B, sub-reason** `embase_emailreg_sub` (EES), gate positives only: 7 sub-categories.
  - **Stage C, contact reason** `embase_contact_reason` (ECR), gate negatives only: 12 contact reasons.
  - B and C were each drafted with `rca discover` over their whole population, then curated by hand
    on 2026-09-30 using the draft, the item counts, a read of the tickets and (for C) the agent's own
    contact reasons. Nothing was classified until both lists were reviewed.
- **Profiles:** [`profiles/embase_2026_emailreg_gate.json`](profiles/embase_2026_emailreg_gate.json) (A),
  [`profiles/embase_2026_emailreg_sub.json`](profiles/embase_2026_emailreg_sub.json) (B),
  [`profiles/embase_2026_emailreg_cr.json`](profiles/embase_2026_emailreg_cr.json) (C).
  One ticket per call, temperature 0, concurrency 4. Inputs in `runs/intermediate/` are written by the notebook.
- **Enhancements:** keyword audit cross-tabulated against the gate; 20-ticket smoke test stratified
  by channel; prompt-fingerprint check on checkpoints.

## Taxonomy at a glance
- **Gate (2):** Email registration / email-account issue; Not email registration.
- **Email-account sub-categories (7):** New user registration or registration ID request; Remove,
  revoke or delete a user account; Change or transfer the email on an account or licence;
  Verification or login-details email not received; Personal account not linked to the institution
  or organisation; Sign-in problem with registered credentials; Other email-account issue.
- **Contact reason (12):** Correction to a published record; Indexing error or data quality problem;
  Missing article or record not yet indexed; Journal coverage, evaluation or indexing status;
  Organisation access set-up or entitlement; User cannot access Embase; Error message or technical
  fault; Search, export or product feature question; Feedback or feature request; Usage report or
  usage data request; Order, purchase, renewal or invoice; Other / not enough information.

## How to re-run
```bash
cd use_cases/embase_2026_email_reg
rca validate
rca build
rca run --profile profiles/embase_2026_emailreg_gate.json --dry-run   # check, then run without --dry-run
rca run --profile profiles/embase_2026_emailreg_sub.json
rca run --profile profiles/embase_2026_emailreg_cr.json
```
For new data, run the notebook: it cleans the export, writes the input files, splits positives and
negatives between stages, and merges the final workbook.

## Results
Run on 2026-09-30, about 1 cent per ticket per stage. Deliverables in `runs/output/`:
`embase_2026_email_registration.xlsx` (one row per ticket with `final_tag` and the agent's contact
reason alongside), `embase_2026_email_registration_summary.xlsx` (pivot) and a full-text CSV.

- **52 of 774 tickets (6.7%) are email-registration tickets.** By sub-category: New user
  registration or registration ID request 21; Personal account not linked to the institution 8;
  Remove, revoke or delete a user account 7; Change or transfer the email 6; Verification or
  login-details email not received 5; Sign-in problem 5; Other 0.
- **The other 722, by contact reason** (share of all 774): Correction to a published record 238
  (30.7%), Journal coverage, evaluation or indexing status 82 (10.6%), Organisation access set-up or
  entitlement 72 (9.3%), User cannot access Embase 52 (6.7%), Search, export or product feature
  question 49 (6.3%), Error message or technical fault 46, Other / not enough information 46, Usage
  report request 43, Indexing error 27, Order / renewal / invoice 25, Feedback or feature request 23,
  Missing article 19.
- **Keyword cross-check:** 108 tickets mention registration-type words; the gate accepted 31 and found
  21 more with no keyword. Most rejected hits were content or indexing requests.
- No gold set: quality was checked by reading justifications, and the derived contact reason can be
  compared with the agent's reason in the deliverable.

## Lessons and reuse tips
- **Same recipe as LeapSpace, different product:** the cleaning and staging code moved across almost
  unchanged. Start from either notebook for a similar request.
- **When no taxonomy exists, discover then curate.** The raw discovery draft grouped tickets by admin
  topic; hand curation turned it into categories a customer would recognise. Budget time for that read.
- Embase is mostly **content** work (record corrections, coverage, indexing), not access; the
  email-registration share is smaller than in LeapSpace (6.7% vs 10.6%) and is dominated by
  organisations requesting accounts for users.
- Keep the agent's own contact reason next to the AI one: it is a free sanity check.
- Curated codes follow list order: add new categories at the end, never in the middle.

## Known issues
- `rca validate`: no errors, no warnings.
- The sub-categories were curated from 40 first-pass positives, but the final gate produced 52.
  The final run looks fine (*Other email-account issue* got 0), but the list was not re-curated.
- 46 tickets have no customer turn at all (agent-only notes); they are classified on the agent text.
- 8 metadata rows have no matching thread in the export and are ignored.
- Discovery drafts are kept in `generated/taxonomies/drafts/` for reference only.

## To confirm
- Who requested the analysis and what decision it fed.
- Why the gate count moved from 40 to 52 positives between curation and the final run (gate prompt
  change?).
- Whether results were shared in a deck or report, and where it is stored.
