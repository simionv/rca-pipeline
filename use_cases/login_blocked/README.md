---
name: login_blocked
title: Mendeley Login Blocked — other credential issues deep dive
product: Mendeley
status: complete
owner: TBD
period: 2024-08 to 2026-02
updated: 2026-11-12
tags: [single-stage, discovery]
question: What is really behind Mendeley "login blocked" tickets that the broad run could only label "other credential issues"?
---

# Mendeley Login Blocked — other credential issues deep dive

## Business question
In the full [Mendeley run](../mendeley/README.md), 319 tickets had contact reason "Login Blocked" and the catch-all
root cause "Other Credential Issues". This slice re-classifies them with taxonomies discovered from the tickets
themselves, to find out what the "other" actually is.

It is one of three ID and access slices taken from the same Mendeley run. The other two are
[Account Recovery](../account_recovery/README.md) and [Account Already Exists](../account_already_exists/README.md).

## Data
- **Source:** every ticket in the Mendeley run with contact reason Login Blocked and root cause Other Credential Issues.
- **Period and size:** **319 tickets**, the same window as the Mendeley data (2024-08 to 2026-02). 317 were in English.
- **Location:** `data/Login blocked_Other credential issues.xlsx`, with columns `uid`, `conversation` and `Reference #`.
- **Preparation:** filtered from `Mendeley_enriched.xlsx`. The filter step is not saved as a notebook.

## Approach
- **Definition:** none. This folder has no definition workbook. Only the taxonomy files in `generated/taxonomies/`
  survive.
- **Steps / modules:** `contact_reason` and `root_cause`, each with a justification and evidence. The output shows
  hierarchical contact reason, language detection and confidence scoring were switched on.
- **Taxonomy route:** `rca discover` on the tickets. The contact-reason and root-cause drafts in `drafts/` were promoted
  unchanged. The `resolution_codes`, `troubleshooting_steps` and `customer_effort` files are the standard starter
  lists and were not run.
- **Profiles:** none. A 100-ticket sample was run first, then all 319.

## Taxonomy at a glance
- `contact_reason` (discovered): Account Issues (5), Technical Problems (5), General Inquiries (3).
- `root_cause` (discovered): Authentication Issues (5), Account Management (5), Technical Issues (5),
  User Experience Issues (4), Email and Communication Issues (4), Integration Issues (4), System Configuration Issues (3).

## How to re-run
There is no definition, so `rca validate` and `rca build` cannot run here. First add a workbook to `definitions/`
whose taxonomy matches `generated/taxonomies/` (for example, copy the
[Account Recovery](../account_recovery/README.md) workbook and swap in these categories). Then:
```bash
cd use_cases/login_blocked
rca build
rca run --input "data/Login blocked_Other credential issues.xlsx" --text-col conversation --id-col "Reference #" \
  --modules contact_reason root_cause --enable-confidence --dry-run
```

## Results
From `runs/output/Login blocked_Other credential issues_enriched.xlsx`, which has a summary pivot and the per-ticket sheet:
- **Root cause (319 tickets):** Authentication Issues 243 and Account Management 67. By leaf: Credential Failure **197**,
  Account Access Issue 48, Access Restriction 36, Account Status Issue 11, System Failure 7, Account Not Found 7,
  Two-step authentication 3, and the rest at 3 or fewer.
- **Contact reason:** Technical Problems 188 (Installation / Integration 152, Plugin / Integration 20, Citation
  management 11), Account Issues 127 (Login / Authentication 103, Account Access 20) and General Inquiries 4.
- **Access domain:** over a quarter of tickets name a Mendeley product, such as the desktop app, Mendeley Cite or the
  Word plug-in. Together with the contact-reason mix, this suggests many "login blocked" cases happen while signing in from an installed app or plug-in, not on the web.
- No deck was found.

## Lessons and reuse tips
- Discovery on a narrow slice gave generic categories. Most tickets still landed in a broad "Credential Failure" leaf.
  Look at the discovered drafts critically and break up the biggest leaf before running.
- The surprising part (sign-ins from the app or plug-in) shows up in the contact reason and access domain more than
  in the root cause. Keep both modules.
- Save the definition workbook with the use case. Without it, this analysis can't be rebuilt directly.

## Known issues
- No definition workbook, so `rca validate` was not run.
- 316 of 319 rows are flagged `_needs_review`, and a confidence score was filled for only 16.
- The discovered contact-reason list includes categories that are not about login (citation management, import / export).

## To confirm
- Who asked for this and when it ran (thought to be around 2026-05). Whether results were shared in a deck.
- Whether this, Account Recovery and Account Already Exists were one request with three slices.
- Whether the original definition workbook still exists somewhere and can be restored.
