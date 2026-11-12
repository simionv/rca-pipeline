---
name: leapspace_2026_email_reg
title: LeapSpace 2026 email-registration tickets, with contact reason for the rest
product: LeapSpace
status: complete
owner: TBD
period: 2026-03 to 2026-09
updated: 2026-11-12
tags: [gate-then-subreason, email-registration, discovery]
question: How many LeapSpace support tickets are about email registration or an email-account problem, what kinds are they, and why did everyone else contact support?
---

# LeapSpace 2026 email-registration tickets, with contact reason for the rest

> **Sibling study:** [`embase_2026_email_reg`](../embase_2026_email_reg/README.md) asks the same
> question for Embase with the same design (gate, then sub-reason, then contact reason) and the same
> cleaning code. Read the two pages together.

## Business question
Size and describe the email-registration problem in LeapSpace support: tickets where the customer's
issue is the email address on the account or the registration itself (verification emails, which
address to register with, purchases on the wrong email, and so on). Every other ticket gets the
standard LeapSpace contact reason, so the email-registration share can be read against the full mix.

## Data
- **Source:** the LeapSpace thread export of 2026-07-27 to date
  (`leapspace data & threads extraction_2026-07-27_todate.tsv`), **one row per message**, not per ticket.
- **Period and size:** 1,857 message rows over **424 tickets**, messages dated 2026-03-02 to 2026-09-28.
  Channels: Web 296, Email 87, Chat 21, Phone 20.
- **Location:** `data/` (linked to the local data archive, never committed); see Known issues.
- **Preparation** ([`notebooks/18_leapspace_2026_email_registration.ipynb`](notebooks/18_leapspace_2026_email_registration.ipynb), sections 1 to 3):
  - 134 exact duplicate rows dropped.
  - Messages ordered by creation time (the `sequence` column is not a real order).
  - Each message cleaned: HTML removed, quoted reply history cut (many languages handled),
    banners and repeated pasted messages removed. Text shrank to 22% of the raw size.
  - One conversation per ticket rebuilt with speaker labels: CUSTOMER, AGENT, and
    CUSTOMER (logged by agent) for notes an agent typed for the customer.
  - Conversations over 16,000 characters sent as start plus end (2 tickets).

## Approach
- **Definition:** [`definitions/leapspace_2026_email_registration_definition.xlsx`](definitions/leapspace_2026_email_registration_definition.xlsx)
- **Steps / modules:**
  - **Stage A, gate** `ls_emailreg` (LER), every ticket: email registration / email-account issue, or not.
    The prompt stresses judging what the *customer* raises, not agents asking for an email address.
  - **Stage B, sub-reason** `ls_emailreg_sub` (LES), gate positives only: 7 sub-categories. Drafted
    with `rca discover` over the positives, then curated by hand on 2026-09-29.
  - **Stage C, contact reason** `leapspace_contact_reason` (LCR), gate negatives only: the 8-category
    taxonomy from [`leapspace_2026`](../leapspace_2026/README.md), copied word for word and in the
    same order so codes mean the same thing.
- **Profiles:** [`profiles/leapspace_2026_emailreg_gate.json`](profiles/leapspace_2026_emailreg_gate.json) (A),
  [`profiles/leapspace_2026_emailreg_sub.json`](profiles/leapspace_2026_emailreg_sub.json) (B),
  [`profiles/leapspace_2026_emailreg_cr.json`](profiles/leapspace_2026_emailreg_cr.json) (C).
  All use one ticket per call, temperature 0, concurrency 4. Their inputs in `runs/intermediate/`
  are written by the notebook.
- **Enhancements:** a free **keyword audit** (regex over the customer side) is cross-tabulated
  against the gate to find disagreements to read by hand; a 20-ticket smoke test stratified by
  channel before the full gate run; a prompt-fingerprint check so stale checkpoints are not reused.

## Taxonomy at a glance
- **Gate (2):** Email registration / email-account issue; Not email registration.
- **Email-account sub-categories (7):** Verification or activation email problem; New account
  registration or which email to register with; Purchase or access sits on a different email or
  account; Complimentary or editor access not applied to the registered email; Change, link or
  consolidate the email on an account; Sign-in or password problem tied to the registered email;
  Other email-account issue.
- **Contact reason (8):** as in `leapspace_2026`.

## How to re-run
```bash
cd use_cases/leapspace_2026_email_reg
rca validate
rca build
rca run --profile profiles/leapspace_2026_emailreg_gate.json --dry-run   # check, then run without --dry-run
rca run --profile profiles/leapspace_2026_emailreg_sub.json
rca run --profile profiles/leapspace_2026_emailreg_cr.json
```
For new data, run the notebook: it cleans the export, writes the three input files, splits
positives and negatives between stages, and merges the final workbook.

## Results
Run on 2026-09-29, about 1 cent per ticket per stage. Deliverable:
`runs/output/leapspace_2026_email_registration.xlsx` (one row per ticket, with a `final_tag` column)
plus a full-text CSV.

- **45 of 424 tickets (10.6%) are email-registration tickets.** By sub-category: Verification or
  activation email problem 13; Complimentary or editor access not applied 8; Purchase or access on a
  different email or account 8; New account registration or which email 8; Change, link or
  consolidate email 4; Sign-in or password problem 4; Other 0.
- **The other 379, by contact reason** (share of all 424): User not able to access 98 (23.1%),
  Internal staff access 56 (13.2%), Subscription cancellation and/or refund 55 (13.0%),
  Other / not covered 50 (11.8%), Institutional user cannot access 46 (10.8%), Subscription request
  29 (6.8%), Not enough info 25 (5.9%), Billing 20 (4.7%).
- **Keyword cross-check:** 91 tickets mention registration-type words; the gate accepted 26 of them
  and found 19 more with no keyword. Reading the disagreements showed most keyword hits (often
  "activate") were about something else, such as payment or search errors.
- No gold set: quality was checked by reading the smoke-test and positive-ticket justifications.

## Lessons and reuse tips
- **Copy this whole notebook for any "how many tickets are about X, and what kind" request** on a
  message-level export: cleaning, conversation rebuild, gate, discover-then-curate, contact reason.
  The Embase sibling shows it transfers to another product with almost no change.
- **Reuse an existing contact-reason taxonomy verbatim** (same row order) so results line up with
  earlier runs.
- **Keyword audit is a cheap guard** against a gate definition that is too wide or too narrow.
- **Curated codes follow list order:** add new sub-categories at the end, never in the middle.
- One ticket per call at temperature 0 keeps the gate stable and the cost predictable.

## Known issues
- `rca validate`: no errors, no warnings.
- This use case's `data/` folder is empty in the archive. The raw export the notebook expects is
  stored under `leapspace_2026/data/`; copy or link it before re-running from scratch.
- *Other email-account issue* received no tickets; the catch-all is untested.
- 9 tickets have no customer turn at all (agent-only notes); they are classified on the agent text.
- Discovery drafts are kept in `generated/taxonomies/drafts/` for reference only.

## To confirm
- Who requested the email-registration analysis and what decision it fed.
- How much this 424-ticket export overlaps with the 1,505 tickets in `leapspace_2026`.
- Whether results were shared in a deck or report, and where it is stored.
