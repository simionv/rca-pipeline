---
name: generic
title: Generic module library — the starter definition for new analyses
product: Any (product-neutral)
status: active
owner: TBD
period: n/a
updated: 2026-11-12
tags: [single-stage]
question: Which ready-made, product-neutral modules can I copy to start a new ticket-classification request quickly?
---

# Generic module library — the starter definition for new analyses

> This is not an analysis. It is the library of 19 product-neutral modules to copy from when a new
> request comes in. There is no data, profile or result here.

## Business question
Most requests ask a familiar set of questions: why did the customer contact us, what was the
underlying cause, how hard was it for them, how did they feel, how well did the agent do, was it
escalated, was it resolved? This workbook answers all of them with generic wording and generic
categories, so a new use case can start from a working definition and then make it product-specific.

## Data
- **Source:** none. The modules work on any support transcript (chat, email, call notes) with one text
  column and one id column.
- **Period and size:** n/a.
- **Location:** `data/` is linked to the archive but is empty for this use case.
- **Preparation:** n/a — prepare data in the new use case that copies these modules.

## Approach
- **Definition:** [`definitions/generic_pipeline_definition.xlsx`](definitions/generic_pipeline_definition.xlsx)
  — 19 modules, 148 fields, 10 taxonomies. The `how_to_use` sheet lists every module with its purpose
  and a cost note ("core — always enable", "enable for QA programs", …).
- **Modules with a category list (taxonomy):**
  - `contact_reason` (CR) — why the customer contacted; primary + secondary reason, urgency, evidence. Core.
  - `root_cause` (RC) — the underlying cause behind the symptom; systemic issue flag.
  - `customer_effort` (CE) — effort level and themes, friction points, repeat contact, channel switches, transparency.
  - `agent_performance` (AP) — empathy, ownership, accuracy, coaching points.
  - `voice_of_customer` (VOC) — feature requests, product feedback, churn and competitor signals.
  - `resolution_actions` (RA) — what the agent actually did.
  - `follow_up` (FU) — commitments, owner, deadline.
  - `compliance_and_risk` (RISK) — regulatory, fraud, vulnerability, reputational signals.
  - `knowledge_management` (KM) — documentation or training gaps, suggested article.
  - `customer_intent` (INT) — the action the customer wants taken (distinct from contact reason).
- **Modules with fields only (no category list):** `customer_sentiment`, `communication_effectiveness`,
  `escalation`, `resolution_quality` (FCR, completeness), `insights_and_opportunities`,
  `customer_profile` (inferred), `interaction_classification` (lightweight, always useful),
  `containment_and_deflection` (could self-service have handled it), `customer_journey`.
- **Profiles:** none. Each new use case writes its own profile listing the modules it needs.
- **Enhancements available in every run:** confidence scoring and review queue, feedback examples,
  cost tracking, language detection, quality report, gold-set evaluation (see `rca run --help`).

## Taxonomy at a glance
| Module | L1 groups (L2 count) |
|---|---|
| contact_reason (9 / 49) | Technical & platform (7), Billing & payment (6), Account & access (7), Product inquiry (5), Complaint (5), Delivery & logistics (6), Data & privacy (5), Returns & exchanges (5), General enquiry (3) |
| root_cause (8 / 38) | Product or software defect, Process or policy failure, Agent or human error, Customer error, Infrastructure failure, Third-party failure (5 each), Configuration or setup (4), Communication or notification failure (4) |
| customer_effort (7 / 32) | Resolution difficulty, Process burden, Communication friction, Channel and access friction (5 each), Information gaps, Repeat contact burden, Emotional labour (4 each) |
| agent_performance (5 / 22) | Communication quality (5), Problem-solving (5), Empathy and rapport (4), Technical knowledge (4), Process adherence (4) |
| voice_of_customer (8 / 25) | Product quality, Service experience, Price and value, Competitor comparison, Feature request (4), Unmet need, Positive endorsement, Loyalty and churn signal |
| resolution_actions (6 / 23) | Information provided (4), Account or system action (6), Escalation (4), Workaround (3), Complaint or goodwill (3), No action (3) |
| follow_up (5 / 18) | Agent-owned (5), Customer-required (4), Internal team (4), Automated (3), None required (2) |
| compliance_and_risk (6 / 21) | Regulatory and legal (5), Customer vulnerability (4), Fraud and security (4), Reputational (4), Product safety (3), No risk (1) |
| knowledge_management (4 / 10) | Customer-facing documentation gap (4), FAQ opportunity (2), Internal training gap (3), No gap (1) |
| customer_intent (10 / 42) | Cancel, Refund, Restore access, Update account, Get information / status, Report a problem, Dispute, Technical fix, Data export, Change plan |

## How to re-run
```bash
# start a new use case from the template, then copy the generic definition in
cp -r use_cases/_template use_cases/<new_name>
cp use_cases/generic/definitions/generic_pipeline_definition.xlsx use_cases/<new_name>/definitions/<new_name>_definition.xlsx
cd use_cases/<new_name>
# edit the workbook: keep only the modules you need (enabled = FALSE), rename categories for the product
rca validate
rca build
rca run --input data/<file>.csv --text-col <text column> --id-col <id column> --modules contact_reason customer_effort --dry-run
```
To check the library itself: `cd use_cases/generic && rca validate && rca build`.

## Results
None — this is a starting point, not an analysis. Its module and field patterns (contact reason,
root cause, customer effort with evidence) recur in the product use cases.

## Lessons and reuse tips
- **Start small.** Enable `contact_reason`, `customer_effort` and `interaction_classification` first;
  add others only if the question needs them. Every module adds prompt length and cost.
- **Replace the generic categories** with the product's own wording before a real run; the generic lists
  (e.g. Delivery & logistics, Returns & exchanges) suit retail more than research products. Use
  `rca discover` on a sample to draft product categories.
- Codes are assigned by row order: **append new categories at the end**, never insert, or earlier outputs shift.
- Keep the `*_evidence` fields: they are checked against the transcript and make results defensible.

## Known issues
- `rca validate`: no errors, 1 warning — `follow_up_owner` is defined in both `resolution_quality` and
  `follow_up`, so one overwrites the other in the output. Rename one before enabling both.
- `generated/modules/` holds three extra modules that are not in the workbook (`metadata.py`,
  `resolution.py`, `troubleshooting.py`); `metadata.py` refers to Scopus.
- `history/pre_rebuild_snapshot/` holds older module copies from the shared generated folder of the old
  project. Some are Scopus-era: its `contact_reason` and `customer_effort` taxonomies use Scopus Content
  categories, not the generic ones. Do not copy from the snapshot by mistake.

## To confirm
- Whether `metadata.py`, `resolution.py` and `troubleshooting.py` should become proper modules in the workbook or be removed.
- Which of the two `follow_up_owner` fields to keep.
- Who maintains the library.
