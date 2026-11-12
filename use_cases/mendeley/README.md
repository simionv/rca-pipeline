---
name: mendeley
title: Mendeley support — ID and access contact reasons and root causes
product: Mendeley
status: complete
owner: TBD
period: 2024-08 to 2026-02
updated: 2026-11-12
tags: [single-stage, escalation]
question: Why do Mendeley customers contact support about sign-in, accounts and institutional access, and what causes those problems?
---

# Mendeley support — ID and access contact reasons and root causes

## Business question
Profile all solved Mendeley support tickets by contact reason, root cause, resolution and escalation, with a focus
on identity and access (signing in, account setup, account data, institutional access). The full run was then used
to pull three deep-dive slices: [Account Recovery](../account_recovery/README.md),
[Account Already Exists](../account_already_exists/README.md) and [Login Blocked](../login_blocked/README.md).
An accidental-deletion and data-loss scan was also built on top of it.

## Data
- **Source:** Mendeley support tickets, file `Mendeley_processed_conversations.csv`. Columns used: `Reference #` (ID)
  and `conversation` (text). The file also has agent `Contact reason Level 1/2`, `Channel ID`, `Resolution Code Lvl1 Desc`,
  `Mailbox Name`, `is_follow_up` and `interaction_count`.
- **Period and size:** **25,872 tickets**, 2024-08-19 to 2026-02-10, all with status Solved. About 13.6k came by web and 11.8k by chat.
  87% came through the Mendeley Support mailbox.
- **Location:** `data/` (linked to the local archive). Outputs are in `runs/output/`.
- **Preparation:** conversations were already processed into one text per ticket. The notebook that did this
  is not in this folder.

## Approach
- **Definition:** [`definitions/mendeley_pipeline_definition.xlsx`](definitions/mendeley_pipeline_definition.xlsx)
- **Steps / modules:** `contact_reason` (primary plus secondary codes, personal vs institutional, contact type),
  `root_cause` (with justification and evidence), `resolution` (status and code), `escalation` (yes/no and target),
  `troubleshooting` (steps), `metadata` (products, errors, urgency, summary). `customer_effort` is defined but
  does not appear in the archived output.
- **Profiles:** [`profiles/mendeley_profile.json`](profiles/mendeley_profile.json) uses batch 12, 80k characters,
  concurrency 3, confidence threshold 0.70 with a review queue, cost tracking and a quality check. It only lists
  `contact_reason` and `root_cause`.
- **Enhancements:** confidence scoring and a review queue. Discovery drafts exist in `generated/taxonomies/drafts/`
  but were not used. The final taxonomy was built from the group, sub-category and root-cause list that was provided (March 2026).

## Taxonomy at a glance
Current definition:
- `contact_reason`: Signing in & authentication (4), Account creation & setup (3), Account details & personal data (5),
  Organisation & network access (9, which also holds General enquiry, Feedback and Unrelated).
- `root_cause`: Credential & password (4), Institutional & entitlement (4), Security & network (3), System & platform (4), Other (1).
- `resolution`: 5 groups and 13 codes. `troubleshooting`: 3 groups and 13 steps. `customer_effort`: 4 groups and 8 codes.

## How to re-run
```bash
cd use_cases/mendeley
rca validate
rca build
rca run --profile profiles/mendeley_profile.json --dry-run   # check, then run without --dry-run
```
Add `--modules contact_reason root_cause resolution escalation troubleshooting metadata` to match the archived output.
The profile writes `Mendeley_processed_conversations_enriched.xlsx`, not the archived `Mendeley_enriched.xlsx`.

## Results
From `runs/output/Mendeley_enriched.xlsx`, which has a summary sheet and the raw data:
- **68% of tickets are not ID or access related.** "Other / Uncategorised" covers 17.5k tickets
  (General enquiry 13.0k, Unrelated 4.2k).
- **ID and access contact reasons:** Signing in & authentication 4.6k, Account details & personal data 2.1k,
  Organisation & network access 1.1k, Account creation & setup 0.4k. The top leaves are Other sign-in issue 2.7k,
  Login blocked 1.0k, Account recovery 0.7k, Password 0.6k, Merge / transfer accounts 0.5k and Update email 0.4k.
- **Specific root causes:** Multiple profiles / accounts 1.2k, No longer has access to registered email 0.8k,
  Accidental account deletion 0.7k, Account already exists / email in use 0.5k, Institution not entitled 0.5k,
  Incorrect password 0.5k, Firewall / proxy block 0.4k.
- **Escalation and resolution:** 31% of tickets were escalated. Resolution status was 38% pending, 21% resolved,
  16% no action, 16% escalated and 9% workaround.
- **Deletion and data-loss follow-up** (`Mendeley_acct_deletion_data_loss.xlsx` and extra sheets in the enriched file):
  a keyword (regex) scan found 326 unique tickets with deletion or data loss, mostly general data or content loss (249).
  Only 47 tickets matched explicit accidental account deletion, and 30 of those agreed with the model's root cause.
- Review samples of 100 and 150 tickets are in `runs/output/`. No deck was found.

## Lessons and reuse tips
- On an all-ticket export, an ID-focused taxonomy leaves most tickets in "Other". Filter to ID and access tickets
  first, or add proper non-access groups.
- Running all tickets once and then re-classifying narrow slices with a small, focused taxonomy worked well
  (see the three linked slices).
- Keep catch-all labels (General enquiry, Unrelated) in their own L1 group, not under a real group.

## Known issues
- `rca validate` passes with 1 warning: `troubleshooting` has a category list but no code field.
- **The current definition does not match the archived run.** The output uses different labels and extra root
  causes (for example Cloudflare block, Shibboleth not activated, Multiple profiles, Accidental account deletion), so
  re-running will not reproduce those numbers.
- The README sheet says "15 L2 leaf codes", but the taxonomy sheet has 21.
- `runs/mendeley_run.log` is from a different, partial session that loaded other taxonomies. The profile points
  `feedback_dir` at an empty folder.
- `access_classification_contact` came back with values outside the allowed list (corporate, open access and others, about 70 rows).

## To confirm
- Who asked for this, the run date, and whether a deck or report exists.
- Where the version of the taxonomy that produced `Mendeley_enriched.xlsx` lives, and whether to restore it to the definition.
- Whether `customer_effort` was ever run.
