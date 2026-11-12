---
name: csd_2026
title: Scopus Content Service Desk 2026 — validation rules, rejection reasons and customer effort
product: Scopus (Content Service Desk)
status: complete
owner: TBD
period: 2026-01 to 2026-07
updated: 2026-11-12
tags: [validation-rules, policy-compliance, discovery, customer-effort, dsat, survey-linked, regression-model, deck]
question: Why are Scopus content requests rejected, does the policy matrix explain the rejections agents log, and which rejections cost customers the most effort?
---

# Scopus Content Service Desk 2026 — validation rules, rejection reasons and customer effort

## Business question
Every ticket in the 2026 Content Service Desk (CSD) file is a **rejected** content request (all carry an `Invalid-*`
resolution code). Three things describe why a request is rejected, and they had never been put on the same ticket:
1. the **Triangulation Matrix** — 24 validation rules ("a request is invalid when …"), each with a primary resolution code;
2. the **resolution code** the agent logged at close (15 values);
3. what the agent actually **wrote back** to the customer.

The study tags each ticket with a validation rule and a bottom-up rejection reason, measures how often the rule matches
the logged code ("conformance"), finds holes in the matrix and drafts candidate rules for them. Follow-ups added
customer effort (LLM-judged and survey-based), a dissatisfied-customer (DSAT) deep dive, a per-rule scorecard and an
effort regression model. Outputs were presented to Content / CSD stakeholders as decks.

## Data
- **Source:** Scopus content ticket metadata and conversation threads for 2026; the Triangulation Matrix workbook; the
  CSD CheatSheet & Templates workbook (agent reply templates, used as recognition cues); the CSAT survey answers
  (satisfaction, effort, agent questions).
- **Period and size:** tickets closed 1 January – 31 July 2026 (7 months, not a full year). 56,935 tickets; 50,714
  classifiable after removing 5,844 chats with no transcript, 369 near-empty tickets and 1 ticket that quoted its own code.
- **Sample:** 12,000 tickets drawn **stratified by resolution code** (at least 300 per code), then weighted back to the
  50,714 (weights 1.00–5.27). Never multiply sample counts by a flat factor — the deck shows why.
- **Location:** `data/`, `runs/`, `output/` and `feedback/` are links into the local data archive
  (set up with `python tools/link_archive.py <archive>`) — never committed.
- **Preparation:** [`notebooks/08_csd_2026_validation_rules.ipynb`](notebooks/08_csd_2026_validation_rules.ipynb) —
  the model input holds only ticket id and conversation (no resolution code, so the comparison is blind), capped at 16,000 characters.

## Approach
- **Definition:** [`definitions/csd_2026_pipeline_definition.xlsx`](definitions/csd_2026_pipeline_definition.xlsx) — 6 modules, all enabled.
- **Steps / modules** (in order):
  1. `csd_validation_rule` — which of the 24 matrix rules makes the request invalid, or "No applicable validation rule".
     Rule descriptions include the agent template wording so the model recognises a rule from the reply.
  2. `csd_rejection_reason` — the ground the agent gave. Taxonomy **discovered** from 400 tickets (notebook 08 section 7),
     reviewed, then written back into the definition.
  3. `csd_rule_proposal` — gap pass on the "no applicable rule" tickets only; drafts the rule that would cover them (free text, no taxonomy).
  4. `csd_customer_effort` — effort level, friction points and themes; adapted from the Scopus content definition
     ([`notebooks/09_csd_2026_customer_effort.ipynb`](notebooks/09_csd_2026_customer_effort.ipynb)).
  5. `csd_multi_rule` — multi-label re-read of the rule taxonomy (how often more than one rule applies); added by `scripts/add_multirule_module.py`.
  6. `csd_dsat_review` — structured read of dissatisfied tickets (the model never sees the score); added by `scripts/add_dsat_module.py`.
- **Profiles:**
  - `profiles/csd_2026_rules_and_reasons.json` — modules 1 and 2 together on the 12,000 sample (`runs/intermediate/csd_sample_12000.csv`).
  - `profiles/csd_2026_rule_proposals.json` — module 3 on `runs/intermediate/csd_proposal_input.csv`.
  - `profiles/csd_2026_customer_effort.json` — module 4 on its own copy of the 12,000 (later extended to the full corpus).
  - Modules 5 and 6 have no profile in `profiles/`; they were run from the notebooks/scripts.
- **Analysis scripts (`scripts/`):** observed-effort features from ticket metadata (`build_effort_features.py`, no LLM),
  per-rule scorecard, survey table, DSAT report, effort regression in R (`effort_model.R`), and the deck builders
  (`build_deck.py`, `build_rule_scorecard_deck.py`, `build_exec_deck.py` — these need the system Python with python-pptx).

## Taxonomy at a glance
- **Validation rule (25 codes):** Missing Content (14 rules), Document Correction (9), Document Correction Missing Content (1),
  No applicable validation rule (1).
- **Rejection reason (17 codes):** Indexing Status Issues (5), Content Type and Eligibility (4), Request Processing and
  Follow-up (4), Correction and Update Requests (3), Not an actionable request (1).
- **Customer effort:** Quick resolution (3), Process complexity & multi-step resolution (4), Wait time, delays &
  follow-up friction (4), Communication, transparency & handoff friction (5).

Full lists: the `taxonomy` sheet of the definition.

## How to re-run
```bash
cd use_cases/csd_2026
rca validate
rca build
rca run --profile profiles/csd_2026_rules_and_reasons.json --dry-run   # check, then run without --dry-run
rca run --profile profiles/csd_2026_rule_proposals.json --dry-run      # after the notebook writes the gap input
rca run --profile profiles/csd_2026_customer_effort.json --dry-run
```
Sampling, weighting, merges and all analysis are in notebooks 08 and 09 and in `scripts/`. Actual cost of the rule and
reason work: about $243 (main run $164); a full-corpus rule run was estimated at about $695 and not done.

## Results
- **Conformance:** where a rule and a logged code can be compared, they agree **79.9% (±0.6 points)**.
- **Matrix gaps** (counts for Jan–Jul; the main deck labels them "a year" — see Known issues):
  - three resolution codes in daily use are claimed by no rule — 9,585 tickets (advice request is the largest);
  - rule 08's designated code is almost never used; its tickets are logged as "discontinued title" (2% strict vs 85% against the real code);
  - Articles in Press (1,534 tickets) fit neither of the two narrow AiP rules;
  - 17 candidate rules drafted for the uncovered tickets (about 7,696), for Content to review.
- **Multi-rule:** 97.7% of tickets break exactly one rule, 2.3% break two. The second pass agreed with the first on 70%.
- **Customer effort:** roughly a quarter to a third of tickets are judged high effort (27.3% weighted). Effort follows the
  rejection reason, not the volume: Content Format Issues ~60% high, Content Not Yet Indexed (the largest reason) ~13%.
  Against 2,813 survey answers, the LLM's reading correlates +0.21 with the customer's own effort score — about twice the
  best handling metric (+0.11); handoffs and repeat contacts show no relationship.
- **DSAT:** on 45% of dissatisfied tickets the refusal came with no reason, and on a further 21% with no next step;
  55% of customers citing "Policy" were never told why. The handling itself was rarely the problem.
- **Docs:** [`docs/CSD_2026_deck_talking_points.md`](docs/CSD_2026_deck_talking_points.md),
  [`docs/CSD_2026_stakeholder_QA.md`](docs/CSD_2026_stakeholder_QA.md), [`docs/CSD_2026_rule_scorecard.md`](docs/CSD_2026_rule_scorecard.md),
  [`docs/CSD_2026_rule_survey_table.md`](docs/CSD_2026_rule_survey_table.md), [`docs/CSD_2026_dsat_findings.md`](docs/CSD_2026_dsat_findings.md)
  (and .docx versions). Decks are under `runs/output/` (60-slide analysis, 15-slide scorecard, 3-slide exec summary).

## Lessons and reuse tips
- **Copy the triangulation design** whenever there is a written policy plus an agent-logged code: tag the policy rule
  top-down, discover the reason bottom-up, and cross-tab both against the code. The independent reason is the tiebreaker
  that tells "matrix gap" apart from "model error".
- Stratify by the logged code and **weight back**; report sample and population side by side.
- Feed agent templates into rule descriptions — policy wording and reply wording look nothing alike.
- Fix prompts only for nameable defects (e.g. boilerplate disclaimers read as evidence), and stop once changes fall inside the probe's noise.
- Use "conformance", not "accuracy", when the reference label is itself an agent's choice.
- The stakeholder Q&A doc is a good template for defending an LLM analysis in a room.

## Known issues
- `rca validate`: no errors, no warnings.
- No human-labelled gold set; the 79.9% is agreement with agent codes, and rule test–retest agreement is only about 70%.
  Effort scores agree exactly between two runs 62% of the time (98% within one level).
- The 60-slide deck calls Jan–Jul volumes "a year" (understated by about 71%); the scorecard reports both observed and
  annualised. The talking points list three further stale figures on specific slides.
- Excluded tickets (mostly chats with no transcript) are not random — advice requests are excluded far more often.
- `csd_multi_rule` and `csd_dsat_review` have no profile, so they cannot be re-run with `rca run` as-is.

## To confirm
- Who requested the analysis (Content policy team or CSD management) and the current owner.
- Whether `docs/CKAI_PHI_screening_approach.pptx` and the ClinicalKey AI files in `data/` belong to this use case or to a separate ClinicalKey AI piece.
- Whether the matrix recommendations (rule 08 remap, enquiry rule, general AiP rule) were adopted, which would make this card superseded.
