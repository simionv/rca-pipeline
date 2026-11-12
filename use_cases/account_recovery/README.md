---
name: account_recovery
title: Mendeley Account Recovery — accidental vs deliberate deletion deep dive
product: Mendeley
status: complete
owner: TBD
period: 2024-08 to 2026-02
updated: 2026-11-12
tags: [single-stage]
question: Among Mendeley account-recovery tickets, how many are really accidental deletion, deliberate deletion, or an email already in use?
---

# Mendeley Account Recovery — accidental vs deliberate deletion deep dive

## Business question
In the full [Mendeley run](../mendeley/README.md), "Account recovery" tickets often had the root cause
"Accidental Account Deletion". This slice re-checks those tickets with a narrow root-cause list, to split
accidental deletion from deliberate deletion and from email-already-in-use cases.

It is one of three ID and access slices taken from the same Mendeley run. The other two are
[Account Already Exists](../account_already_exists/README.md) and [Login Blocked](../login_blocked/README.md).

## Data
- **Source:** a subset of the Mendeley run. These are tickets with contact reason "Account Recovery" and root cause
  "Accidental Account Deletion" (190) or "Account Already Exists / Email Already in Use" (36).
- **Period and size:** **226 tickets**, the same window as the Mendeley data (2024-08 to 2026-02).
- **Location:** `data/Account Recovery (Accidental Account Deletion & Account Already Exists_Email Already in Use).xlsx`.
  Columns: `uid`, `conversation`, `Reference #`, and `root_cause`, which holds the label from the Mendeley run.
- **Preparation:** filtered from `Mendeley_enriched.xlsx`. The filter step is not saved as a notebook.

## Approach
- **Definition:** [`definitions/account_recovery_pipeline_definition.xlsx`](definitions/account_recovery_pipeline_definition.xlsx)
- **Steps / modules:** `contact_reason` with a single leaf (Account details & personal data → Account recovery),
  so every ticket keeps that label. The real work is in `root_cause`: four hand-written leaves, each with a justification,
  an evidence quote, an evidence type and an access domain.
- **Profiles:** none. The output columns show it was run with hierarchical contact reason, language detection and
  confidence scoring switched on.

## Taxonomy at a glance
- `contact_reason`: Account details & personal data (1: Account recovery).
- `root_cause`: Account Configuration & Data Issues (4): Accidental Account Deletion, Deliberate Account Deletion /
  Deletion Request, Account Already Exists / Email Already in Use, Email Update Request.

## How to re-run
```bash
cd use_cases/account_recovery
rca validate
rca build
rca run --input "data/Account Recovery (Accidental Account Deletion & Account Already Exists_Email Already in Use).xlsx" \
  --text-col conversation --id-col "Reference #" --enable-confidence --dry-run
```

## Results
From `runs/output/..._enriched.xlsx`, which has a summary pivot, the per-ticket sheet and the definitions sheet:
- **Root cause mix (226 tickets):** Deliberate deletion / deletion request **102**, Accidental deletion **75**,
  Account already exists **47**, Email update 1, blank 1.
- **Against the Mendeley run label:** of the 190 tickets first tagged accidental deletion, only 71 stayed accidental.
  101 were re-read as deliberate deletion and 16 as account already exists. Of the 36 tickets tagged already-exists,
  31 kept that label.
- **Main point:** most "accidental deletion" in the broad run was customers who asked for their account to be deleted
  and later wanted it back. The count of truly accidental deletions is closer to 75 than 190. No deck was found.

## Lessons and reuse tips
- Re-running a narrow slice with 3–5 sharply described root causes is a cheap way to test a surprising number
  from a broad run.
- Write the "accidental" and "deliberate" descriptions as a contrasting pair. That pairing is what separated them here.
- Keep the earlier label in the input (the `root_cause` column) so you can cross-tab old against new.

## Known issues
- `rca validate`: no errors and no warnings.
- The definition's README sheet and module descriptions are copied from Mendeley ("Mendeley support RCA pipeline").
  They describe the 4-group Mendeley taxonomy, not this one.
- 216 of 226 rows are flagged `_needs_review`, and a confidence score was filled for only 14, so the review flag tells you little.
- With only one contact-reason leaf, the contact-reason output carries no information.

## To confirm
- Who asked for this and when it ran (thought to be around 2026-05). Whether results were shared in a deck.
- Whether this, Account Already Exists and Login Blocked were one request with three slices.
- Whether the 192 Account Recovery tickets with root cause "No longer has access to registered email" were left out on purpose.
