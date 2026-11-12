---
name: account_already_exists
title: Mendeley Account Already Exists — email in use vs email change
product: Mendeley
status: complete
owner: TBD
period: 2024-08 to 2026-02
updated: 2026-11-12
tags: [single-stage, discovery]
question: Are Mendeley "account already exists / email already in use" tickets really blocked sign-ups, or customers trying to change their email?
---

# Mendeley Account Already Exists — email in use vs email change

## Business question
In the full [Mendeley run](../mendeley/README.md), 525 tickets had the root cause "Account Already Exists / Email
Already in Use". This slice re-checks them to separate blocked registrations or sign-ins (the email is already
on another account) from customers who want to change the email on their existing account.

It is one of three ID and access slices taken from the same Mendeley run. The other two are
[Account Recovery](../account_recovery/README.md) and [Login Blocked](../login_blocked/README.md).

## Data
- **Source:** every ticket in the Mendeley run with root cause "Account Already Exists / Email Already in Use".
  In that run their contact reasons were mostly Registration failed (141), Update email (95) and General enquiry (76).
- **Period and size:** **525 tickets**, the same window as the Mendeley data (2024-08 to 2026-02). All were in English.
- **Location:** `data/Account Already Exists_Email Already in Use.xlsx`, with columns `uid`, `conversation` and `Reference #`.
- **Preparation:** filtered from `Mendeley_enriched.xlsx`. The filter step is not saved as a notebook.

## Approach
- **Definition:** [`definitions/Account_Already_Exists_pipeline_definition.xlsx`](definitions/Account_Already_Exists_pipeline_definition.xlsx)
- **Steps / modules:** `root_cause` only, with a justification, an evidence quote, an evidence type and an access domain.
- **Taxonomy route:** discovery was run first. The draft in `generated/taxonomies/drafts/root_cause_draft.json`
  had 7 groups and 29 leaves (registration, identity and email, authentication, institutional, billing, data, support).
  It was replaced by a hand-written 2-leaf list.
- **Profiles:** none. A 100-ticket sample was run and reviewed first, then all 525.

## Taxonomy at a glance
`root_cause`: Account Configuration & Data Issues (2): Account Already Exists / Email Already in Use, Email Update Request.

## How to re-run
```bash
cd use_cases/account_already_exists
rca validate
rca build
rca run --input "data/Account Already Exists_Email Already in Use.xlsx" \
  --text-col conversation --id-col "Reference #" --enable-confidence --dry-run
```

## Results
From `runs/output/..._enriched.xlsx`, which has a summary pivot and the raw data:
- **Full run (525 tickets):** Account already exists / email in use **480 (91%)**, Email update request **45 (9%)**.
- **Evidence type:** 349 from the customer's description of the symptom, 167 from what the agent did, 9 from a system message.
- **Sample run (100 tickets):** 69 already exists, 25 email update, and 6 returned only the L1 group.
  The sample has an evidence pivot for review.
- No deck was found.

## Lessons and reuse tips
- On a slice this narrow, the discovered draft was far too broad. Start from the 2–4 outcomes the business
  actually needs to tell apart.
- Run a 100-ticket sample first to check that every row gets a leaf code before you run the whole slice.
- `root_cause_access_domain` is free text, so expect mixed values (for example "account", "platform",
  "Mendeley", "billing"). Make it an enum if you want to report on it.

## Known issues
- `rca validate`: no errors and no warnings.
- The definition's README sheet and module description are copied from Mendeley and describe the wrong taxonomy.
- 444 of 525 rows are flagged `_needs_review`, and a confidence score was filled for only 81.
- With only two leaves, tickets about other things are still forced into one of them. In the Mendeley run, some of
  these tickets were billing or data questions.

## To confirm
- Who asked for this and when it ran (thought to be around 2026-05). Whether results were shared in a deck.
- Whether this, Account Recovery and Login Blocked were one request with three slices.
