---
name: scopus_content
title: Scopus Content — customer effort, policy compliance and policy rules
product: Scopus
status: complete
owner: TBD
period: 2024-11 to 2026-03
updated: 2026-11-12
tags: [single-stage, customer-effort, policy-compliance, survey-linked, discovery, regression-model, deck]
question: What drives customer effort on Scopus Content tickets, and how much of it comes from content policies being misapplied or misunderstood?
---

# Scopus Content — customer effort, policy compliance and policy rules

## Business question
Scopus Content support handles requests about missing articles, corrections, journal coverage and
author profiles. Customers often report high effort in the post-contact survey (CES). The work asked:
- What do customers go through (themes, friction points, turnaround), and what drives effort?
- Which **content policy** applied to each ticket, did the agent apply it correctly, and did the
  customer understand it? Is the policy itself too strict?
- Which specific, checkable **policy rules** (e.g. the six missing-content eligibility checks) fail most?
- How do the transcript view (LLM-read effort) and the survey view (CES) compare?

## Data
- **Source:** Scopus Content tickets from Oracle with the CES survey answer and survey comments joined on.
- **Period and size:** tickets from November 2024 to March 2026. **8,307 tickets** (8,305 with a survey
  year: 6,464 in 2025, 1,841 in 2026). A separate file of **~600 survey effort comments** was also classified.
- **Location:** `data/Scopus_Content_Collapsed.xlsx` (one row per ticket, conversation collapsed into one
  text) and `data/scopus_content_effort_survey_comments.xlsx`. Supporting reference files (resolution
  codes, validation-rule triangulation, Tableau workbook) sit in `data/scopus content/`.
- **Preparation:** one conversation per ticket; language detection was on for the effort run.

## Approach
- **Definition (live):** [`definitions/scopus_content_pipeline_definition_v2.xlsx`](definitions/scopus_content_pipeline_definition_v2.xlsx).
  The first version (contact reason + effort only) is in `history/scopus_content_pipeline_definition.xlsx`.
- **Modules in v2:**
  - `contact_reason` (CR) — why the customer contacted support.
  - `customer_effort` (CE) — effort score, effort themes, friction points, repeat contact, channel
    switches, resolution transparency, with evidence.
  - `policy_compliance` (PC) — which policy areas PA1–PA18 apply (Content Coverage Guide and CAR
    Creation Manual), whether the agent was compliant, the violation type, and whether the customer
    struggled to understand the policy and why. The policy reference text is in the module description.
  - `policy_rules` (PA) — 49 atomic rules grouped under the same PA1–PA18 areas; one compliance
    verdict per matched rule.
  - `policy_understanding` (PU) — **retired**: merged into `policy_compliance` (enabled = FALSE).
- **Profiles:**
  - `scopus_content_profile.json` — contact reason + effort, with confidence scoring, review queue and
    feedback examples (`diverse`, 5 per prompt).
  - `scopus_policy_compliance_interactions_profile.json` — policy compliance on the 8,307 tickets.
  - `scopus_policy_rules_profile.json` — policy rules on the 8,307 tickets.
  - Historical (use the retired `policy_understanding`, cannot run as-is):
    `scopus_policy_understanding_interactions_profile.json`, `scopus_policy_understanding_survey_profile.json`,
    `scopus_policy_compliance_survey_profile.json`.
- **Analysis:** the outputs were joined 1:1 on ticket id and analysed in R (`scopus_effort_master.R` in
  the archive folder `runs/output/Scopus effort/`): descriptive tables, logistic / ordinal models,
  bootstrap "what if we fixed X" estimates, and quote verification (a quote is shown only if it appears
  literally in the conversation).
- **Scripts here:** `scripts/add_policy_rules_module.py` (adds PA12–PA18 and the `policy_rules` module to
  v2), `update_excel_taxonomy.py` (harmonised policy framework), `build_policy_rules_notebook.py`
  (full-run runbook), `create_master_v1.py` (R script variant), `update_notebooks_01_02.py`.

## Taxonomy at a glance
From the v2 workbook (what `rca build` produces today):
- **contact_reason** (8 L1 / 42 L2): Content coverage & indexing (8), Citations & references (5), Author
  profiles & identification (6), Metrics, rankings & evaluations (5), Data accuracy & corrections (5),
  Search & platform functionality (5), Access & subscription (4), General enquiry & other (4)
- **customer_effort** (4 L1 / 16 L2): Quick resolution (3), Process complexity (4), Wait time & follow-up (4), Communication & handoff friction (5)
- **policy_compliance** (3 groups): Violation type (5), Policy area (19, PA1–PA18 + none), Customer root cause (5)
- **policy_rules** (18 policy areas / 49 rules), e.g. Missing content processing eligibility (6), Document type coverage (5)

## How to re-run
```bash
cd use_cases/scopus_content
rca validate
rca build
rca run --profile profiles/scopus_policy_compliance_interactions_profile.json --dry-run
rca run --profile profiles/scopus_policy_rules_profile.json --dry-run
rca run --profile profiles/scopus_content_profile.json --dry-run   # fix its input path first (see Known issues)
```

## Results
From the June 2026 effort narrative (8,305 tickets):
- **Two yardsticks:** the measured drivers explain 79% of LLM-read effort but only 6% of survey effort;
  the two correlate weakly (r = 0.11). Survey "hard effort" baseline 43.9% (2025); LLM "high" 38.4%.
- **Friction:** slow response 51% of tickets, lack of transparency 46%, process complexity 38%,
  escalation 31%, repeated explanation 20%. Each extra friction point adds ~26 points to LLM high effort.
- **Policy:** compliant 60%, partial 13%, non-compliant 6%, no policy applies 21%. Only 1.2% of
  policy tickets show a genuinely "too strict" grievance. **44% show policy confusion, and 91% of that
  traces to confusing policy wording**, worst in Re-evaluation & discontinuation (83% confused).
- **Biggest survey lever:** removing policy confusion (about −2.7 points on the 43.9% hard-effort rate).
  Priority areas: Title selection & CSAB evaluation, then Re-evaluation & discontinuation, then Processing timelines.
- **Policy rules:** missing-content eligibility checks fail most often on "authentic online sourcing URL"
  (31% of tickets where it applied) and "journal must be selected / actively indexed" (~18%).
- **Survey comments (~600):** effort themes led by resolution outcome problems, communication quality and delays.
- **Decks and write-ups** (archive, `runs/output/Scopus effort/`): `Scopus_Effort_Narrative.pptx`,
  `Scopus_Friction_Themes.pptx`, `Scopus_Policy_Deep_Dive_v1.pptx`, `Scopus_Effort_Analysis_v2.pptx`,
  `EFFORT_NARRATIVE.md`, `DEFINITIONS.md`, `STAKEHOLDER_QA.md` and talk tracks.

## Lessons and reuse tips
- **Put the policy text in the prompt** and give every policy area a stable code (PA1–PA18); then one
  module can judge both the agent (compliance) and the customer (understanding) against the same anchor.
- Split broad policy areas into **atomic, checkable rules** when you need to know *which* rule fails.
- Keep the survey and the LLM effort score side by side: they measure different things and both matter.
- Only show quotes that verify as literal text from the ticket (94% of effort quotes did).
- `docs/Scopus Ticket Rules and Root Cause Descriptions v3.xlsx` (classification rules + root-cause
  descriptions) is reference material; it is the source for the Scopus 2026 taxonomy (`scopus_2026`).

## Known issues
- `rca validate`: no errors, 9 warnings:
  - three profiles use the retired `policy_understanding` module and cannot run as-is (historical);
  - `scopus_content_profile.json` points to `data/scopus_conversations.csv`, which does not exist (the
    actual effort run used `Scopus_Content_Collapsed`);
  - `policy_rules` has a category list but no `code` field, so no single category is assigned (it
    returns matched rule codes as a list instead);
  - one field uses `enum`/`yes|no` in an unrecognised way (treated as free text); one duplicate
    "Not applicable" label in `policy_understanding`; one L2 without a description in `policy_compliance`.
- **The taxonomies used in the archived runs differ from what v2 builds.** The curated copies in
  `history/pre_rebuild_snapshot/` (and the archived outputs) use a 6-group discovered contact reason
  (e.g. "Publication Indexing and Database Inclusion", "Author Profile and Identifier Management") and a
  7-group effort taxonomy for survey comments. v2 builds an 8-group contact reason and a 4-group effort
  taxonomy. Re-running v2 will **not** reproduce the archived labels.
- The ticket-level effort output also carries effort labels ("Indexing and Visibility Status", …) that match neither version.

## To confirm
- Which contact-reason and effort taxonomies should be treated as the official ones: the curated snapshot (used in the delivered results) or the v2 workbook?
- Whether the snapshot taxonomies should be written back into the v2 workbook so a re-run reproduces the results.
- Where the ticket-level effort L1 labels ("Indexing and Visibility Status" etc.) came from.
- Correct input file and id column for `scopus_content_profile.json`.
- Who requested the work and which deck is the final one presented.
