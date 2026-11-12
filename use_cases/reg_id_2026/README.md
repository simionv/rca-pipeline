---
name: reg_id_2026
title: Registration ID / BulkID requests and a cleaned account-support taxonomy
product: Elsevier account and access support
status: complete
owner: TBD
period: 2025-09 to 2026-09
updated: 2026-11-12
tags: [single-stage, gold-set]
question: Which account-support tickets are genuine requests for Registration IDs or BulkIDs, and what is every other ticket about?
---

# Registration ID / BulkID requests and a cleaned account-support taxonomy

## Business question
Two questions over an export of account and access support tickets:
1. **Which tickets are Registration ID / BulkID / remote-credential requests?** A Tableau regex already existed for this,
   written against the ticket subject line. The team wanted a more reliable count.
2. **What is everything else about?** Using a cleaned version of a taxonomy that a colleague had built by hand-tagging
   about 7,000 tickets (the "manually tagged" workbook), which had grown to 101 raw labels with many misspellings and singletons.

## Data
- **Source:** ticket export with full speaker-labelled conversation threads (`data/reg_id/reg_id_last3_months.xlsx`;
  also a .tsv copy and a metadata file), plus the manually tagged workbook used as an evaluation set.
- **Period and size:** 11,442 tickets; dates run from September 2025 to September 2026. Channels: mostly CSS Email (72%), then Web, Chat, Phone.
- **Location:** `data/`, `runs/`, `output/` and `feedback/` are links into the local data archive
  (set up with `python tools/link_archive.py <archive>`) — never committed.
- **Preparation** ([`notebooks/16_reg_id_2026_bulkid_taxonomy.ipynb`](notebooks/16_reg_id_2026_bulkid_taxonomy.ipynb), section 6):
  - The new export has **no subject line**, so the regex runs on the conversation instead.
  - Customer turns are split from agent turns. The regex and the adjudicator see the **customer's words only**
    (about 6% of tickets have no customer turn and are sent whole).
  - Conversations over 16,000 characters are cut to the first 4,000 + last 11,900 (135 tickets); 35 were already cut by
    Excel in the source export.
  - 104 near-empty tickets get "Not enough info" by rule, with no LLM call.

## Approach
- **Definition:** [`definitions/reg_id_2026_pipeline_definition.xlsx`](definitions/reg_id_2026_pipeline_definition.xlsx) — 2 modules, both enabled.
- **Steps / modules** (independent, no routing between them):
  1. **Regex filter** (in the notebook): the Tableau pattern, ported unchanged, applied to customer turns.
  2. **`regid_adjudicate`:** for the 603 regex hits, is the customer really asking for Registration/Bulk IDs, or did the
     phrase turn up some other way? Carries an analyst-written rule (marked in the workbook) based on measuring the regex
     against the tagged set.
  3. **`regid_taxonomy`:** one of 34 cleaned categories for every ticket with content (11,338).
  4. **Final label:** rule-assigned "Not enough info" first, then "BulkIDs / Registration IDs" where the adjudicator said yes,
     otherwise the taxonomy answer. Tickets the taxonomy calls BulkIDs without a regex hit keep that label (a recall backstop).
- **Profiles:**
  - `profiles/reg_id_2026_adjudicate.json` — `regid_adjudicate` on `runs/intermediate/regid_adjudicate_input.csv` (customer turns, regex hits only).
  - `profiles/reg_id_2026_taxonomy.json` — `regid_taxonomy` on `runs/intermediate/regid_taxonomy_input.csv` (full thread).
  - Both: batch size 5, 40,000 max characters per batch, 4 parallel calls, temperature 0.
- **Taxonomy consolidation:** 101 raw labels mapped onto 34 categories; the mapping and definitions are in
  [`docs/REGID_2026_taxonomy_map.md`](docs/REGID_2026_taxonomy_map.md). Each definition carries the tagger's own wording and synonyms.
- **Evaluation:** a stratified 439-ticket sample of the hand-tagged set.

## Taxonomy at a glance
- **`regid_adjudicate` (2):** Registration or Bulk ID request; Not a Registration or Bulk ID request.
- **`regid_taxonomy` (34, flat — one leaf each):** BulkIDs / Registration IDs; IP management; Account deletion / remove users;
  SSO / Shibboleth configuration; Domain management; Change or add email address; Admin access; Merge accounts; Create customer
  account or organisation; Create department; Correct organisation record; Usage reporting; Change logo; Block user; Course
  access / enrolment; Access or activation codes; Delete data; Access or reset link expired; Password reset; Other account
  settings; Complimentary access request; Add affiliation; Private email access; Not registered or signed in; Registering an
  account; Sign-in or browser issue; HTTP or platform error; WAYFless URL request; Organisation not subscribed / not entitled;
  Agreement or entitlement info request; Royalty link info request; Billing or invoicing; General information request; Not enough info.

## How to re-run
```bash
cd use_cases/reg_id_2026
rca validate
rca build
rca run --profile profiles/reg_id_2026_adjudicate.json --dry-run   # check, then run without --dry-run
rca run --profile profiles/reg_id_2026_taxonomy.json --dry-run
```
The speaker split, regex, merge and deliverable live in the notebook. Actual cost: about $3 for the adjudicator and
about $99 for the taxonomy run (70 minutes); gates (smoke + gold sample) a few dollars more.

## Results
- **Regex alone was misleading:** against the tagged set, the whole-thread regex found 97% of BulkID tickets but only 31%
  of its hits were right. 356 of its 607 false positives were complimentary-access requests that the *agent* answered by
  issuing registration IDs — the regex matched the answer, not the question.
- **Funnel (11,442 tickets):** regex on the whole thread 1,190 (10.4%, the Tableau-style figure) → on customer turns 603 →
  adjudicated as a real request 396. Plus 382 the taxonomy labelled BulkIDs without the regex firing. **Final: 881 BulkID /
  Registration ID tickets (7.7%).**
- **Other categories:** Account deletion / remove users 41%, IP management 8%, BulkIDs 8%, Sign-in or browser issue 4%,
  Complimentary access request 4%, Not enough info 4%, Add affiliation 4%; everything else under 4%.
- **Agreement with the hand tags** (439-ticket sample): 42% exact match, macro-F1 0.29. BulkIDs precision 59% / recall 81%
  (versus 31% / 97% for the regex). Strong categories: IP management, Password reset, Complimentary access, Usage reporting.
  Weak: Private email access, Not enough info, SSO, Add affiliation. Treat as indicative only — the tagged text is mostly
  the agent reply alone, unlike the production threads.
- **Deliverable:** `runs/output/reg_id_2026_classified.xlsx` (tickets, category summary, regex hits, taxonomy, raw label map) and a full-text CSV.

## Lessons and reuse tips
- **Before trusting a keyword rule, score it against labelled tickets** and look at where its false positives come from.
  Here the fix was simple: match the customer's words, not the agent's.
- Regex for recall, LLM adjudicator for precision is a cheap pattern (about $0.005 per ticket) for any "is this really X?" question.
- When inheriting a hand-built taxonomy, write an explicit raw-to-clean mapping and assert it covers every raw label.
- Classify on what the customer asked for, not how the agent fulfilled it (complimentary access vs Registration IDs).

## Known issues
- `rca validate`: no errors, no warnings.
- No accuracy figure for the production run; the 42% agreement is on differently shaped text.
- "Account deletion / remove users" takes 41% of tickets in production versus about 15% in the tagged set — worth a
  manual check before quoting it.
- Some categories were never or rarely seen in the tagged set (Create department, Course access, Delete data, Block user, Change logo), so their definitions are untested.
- Two catch-alls (Other account settings, General information request) can absorb unrelated tickets.

## To confirm
- Which products and team the export covers, and who requested the analysis.
- The data period: the file is named "last 3 months" but its dates span September 2025 to September 2026.
- Why "Account deletion / remove users" is so dominant (possibly an automated or templated request type).
