---
name: my_usecase
title: My use case — one-line name
product: Product name
status: active            # active | complete | superseded
owner: Your Name
period: 2026-01 to 2026-03
updated: 2026-01-31
tags: [single-stage]      # e.g. two-stage, gate-then-subreason, email-registration, customer-effort, gold-set, survey, discovery
question: The business question this analysis answers, in one sentence.
---

# My use case — one-line name

> Copy this folder to `use_cases/<new_name>/`, then fill in every section. Keep it short: this page is how
> people find and reuse your work later. `rca catalog` builds the master list from the block at the top.

## Business question
What did we want to learn, and who asked? What decision will it support?

## Data
- **Source:** where the tickets/transcripts come from (system, export, query)
- **Period and size:** date range, number of records
- **Location:** `data/` (linked to the local data archive — never committed)
- **Preparation:** filtering, de-duplication, text limits (link the notebook that does it)

## Approach
- **Definition:** [`definitions/my_usecase_definition.xlsx`](definitions/my_usecase_definition.xlsx)
- **Steps / modules:** what each module answers, and in which order they run
- **Profiles:** which file in `profiles/` runs which step
- **Enhancements:** feedback examples, confidence scoring, gold-set evaluation, …

## Taxonomy at a glance
List the L1 groups (and the number of L2 categories in each). Full list: the taxonomy sheet of the definition.

## How to re-run
```bash
cd use_cases/my_usecase
rca validate
rca build
rca run --profile profiles/example.json --dry-run   # check, then run without --dry-run
```

## Results
Key findings, accuracy against any gold set, and links to decks/reports in `docs/`.

## Lessons and reuse tips
What worked, what did not, and what to copy for a similar request.

## Known issues
Validation warnings worth knowing about, retired modules, missing inputs.
