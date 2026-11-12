---
name: scopus_2ls_2026
title: Scopus Content 2LS — escalation check, back-and-forth and customer effort
product: Scopus
status: complete
owner: TBD
period: 2024-11 to 2026-09
updated: 2026-11-12
tags: [single-stage, escalation, customer-effort, regression-model, deck]
question: Were Scopus Content tickets really escalated from first-line (1LS) to second-line (2LS) support, how often did they bounce back and forth, and how much extra effort did that cost the customer?
---

# Scopus Content 2LS — escalation check, back-and-forth and customer effort

## Business question
Every ticket in the Scopus Content "2LS" extract is supposed to be a hand-off from first-line agents
(1LS) to the team behind them (2LS: technical / content team, and beyond that the content suppliers).
The questions were:
1. Was the ticket **actually** escalated, and to whom?
2. How many times did it **cross the 1LS/2LS boundary** (hand-offs, returns, re-escalations)?
3. Are there **internal notes** about the escalation?
4. What did it cost the customer: effort score, friction points, chasing, repeated information,
   outcome, how clearly the outcome was explained, end sentiment, deadline pressure?

## Data
- **Source:** Scopus Content support tickets (Oracle), two files: a ticket workbook (metadata, filter
  columns) and the raw thread export (TSV, one row per message).
- **Period and size:** tickets from November 2024 to September 2026 (the 16 November 2024 tickets are counted as 2025).
  In scope (`IS_VALUE_ADD == TRUE` and present in both files): **63,824 tickets**. About 83% came in
  through the web form, and almost all were handled by one 1LS agent group.
- **Location:** `data/scopus content/` (both files currently sit in the scopus_content archive; see Known issues).
- **Preparation** (notebook 17, sections 1–2): transcripts are **rebuilt from the TSV**, not taken from
  the workbook, because the workbook repeats messages (about 10% duplicates from an upstream join) and
  cuts long conversations at Excel's cell limit. Each turn gets a header with turn number, date, days
  since the previous turn and speaker. Agents become anonymous aliases (A1, A2, …); automated
  messages and customer auto-replies are labelled so they never count as effort.

## Approach
- **Definition:** [`definitions/scopus_2ls_2026_pipeline_definition.xlsx`](definitions/scopus_2ls_2026_pipeline_definition.xlsx)
  — one module, `s2ls_escalation_effort` (prefix `SLJ`), 37 output fields. Written by notebook 17; do not edit by hand.
- **Notebook:** [`notebooks/17_scopus_2ls_escalation_effort.ipynb`](notebooks/17_scopus_2ls_escalation_effort.ipynb).
- **Free rule-based features for all 63,824 tickets** (section 3): turn counts, agent changes, days open,
  waits, follow-ups, repeat contacts (`obs_*`), plus a keyword pass for escalation wording (`rx_*`) used
  as a cross-check and a sampling stratum.
- **Stratified sample for the LLM** (section 3b): 50 tickets per *year × contact reason × resolution code*
  cell (whole cell if smaller; rare values grouped as "Other"). 5,760 tickets. Every ticket carries a
  weight so population figures add back to 63,824. 77 of 239 cells are reportable, covering 97% of tickets.
- **One LLM call per ticket** reads the whole transcript and returns every judgement at once. Each
  judgement has a verbatim evidence quote and a short justification naming the turns. Hand-offs and
  friction points are lists of events, each with its own quote.
- **Profile:** `profiles/scopus_2ls_2026_escalation_effort.json` (batch size 1, temperature 0) runs the
  sample input `runs/intermediate/s2ls_sample_input.csv`.
- **Gates:** 40-ticket smoke test (~$1.30) with a review workbook, then the sample run (~$180, ~2 hours).
- **Analysis and deck:** `scripts/build_s2ls_deck_data.R` fits the regression models and writes
  `runs/output/s2ls_deck/deck_data.json`; `scripts/build_s2ls_deck.py` lays the numbers out as an
  editable PowerPoint (`runs/output/S2LS_2026_back_and_forth_customer_effort.pptx`).

## Taxonomy at a glance
Escalation journey (`SLJ`), one code per ticket:
- **Not escalated** (4): resolved at 1LS; rejected or out of scope at 1LS; closed for no customer response; redirected outside Scopus support
- **Escalated once, no back-and-forth** (3): resolved by 2LS; rejected by 2LS; outcome not visible
- **Escalated with back-and-forth** (3): 2LS needed more information; re-escalated after pushback or reopening; multiple hand-offs between teams
- **Unclear** (1): cannot tell from the transcript

Plus fixed-value fields: effort score (very low … very high), outcome, transparency, end sentiment,
internal-note type, escalation target, 11 friction categories and 7 hand-off event types.

## How to re-run
```bash
cd use_cases/scopus_2ls_2026
rca validate
rca build
rca run --profile profiles/scopus_2ls_2026_escalation_effort.json --dry-run   # check, then run without --dry-run
Rscript scripts/build_s2ls_deck_data.R      # models -> runs/output/s2ls_deck/deck_data.json
python scripts/build_s2ls_deck.py           # needs python-pptx
```
The profile input is produced by notebook 17 (sections 1–3b), so run the notebook first for new data.

## Results
Weighted to the 63,824-ticket population:
- **82.5% were really escalated**; 17.5% were not (mostly resolved at 1LS). Escalation was slightly
  higher in 2026 (83.8%) than 2025 (80.8%).
- **Crossing patterns:** not escalated 17.5%, one-way (handed off, nothing visible came back) 9.2%,
  round trip 65.0%, 3 crossings 7.3%, 4+ crossings 0.9%. About **8% of all tickets (~5,200) show real
  back-and-forth**; 10% of escalated tickets.
- Among escalated tickets, 78% were resolved by 2LS, 8% rejected by 2LS, 8% needed more information.
- **Outcome:** 80% resolved, 9% rejected, 5% partially resolved, 5% unclear, 2% unresolved.
- **Effort and back-and-forth (regression, controlling for year, contact reason, resolution code,
  channel, customer type):** each crossing beyond a round trip multiplies the odds of a higher effort
  score by about 7, adds about 23% to days open, and raises customer messages by ~50% and follow-ups by ~90%.
  Predicted chance of medium-or-higher effort: 4% (not escalated), 29% (round trip), 73% (3 crossings), 95% (4+).
  One-way tickets carry more effort than round trips, because nothing comes back to the customer.
- **Quality checks:** evidence quotes grounded in the transcript ≥ 99.9%; LLM and keyword pass agree on
  escalated yes/no for 85.6% of tickets; effort score tracks observed customer turns (Spearman 0.50).
- **Cost:** $180.56 for the sample (~$0.032 per ticket).
- **Deliverables:** `runs/output/scopus_2ls_2026_escalation_effort_sample.xlsx` (one row per sampled
  ticket with weights, plus summary sheets) and the deck above.

## Lessons and reuse tips
- **Reuse for any escalation or hand-off question**: the turn-header transcript format, the
  "one module, every judgement, evidence + justification for each" pattern, and the event list.
- **Rebuild transcripts from the raw thread export** when you need timings or speaker changes; the
  cleaned workbook loses them and duplicates messages.
- **Sample by strata and weight back** instead of classifying everything: ~$180 instead of ~$2,000, and
  every reportable cell has at least 50 tickets (±14 points at worst).
- Run a free keyword pass alongside the LLM: it is a useful cross-check and a sampling stratum.
- Recount hand-offs from the event list rather than trusting the model's own counts (they disagreed on 5.6%).
- The R script is a ready template for "does X drive effort" questions (ordinal logit, Poisson, robust errors).

## Known issues
- `rca validate`: no errors, no warnings.
- `data/` is empty for this use case. The raw TSV is archived under `scopus_content/data/scopus content/`;
  the ticket workbook (`scopus content 2ls verbatim cleaned 2025_2026.xlsx`) is not in the archive index at all.
- The R and deck scripts contain Windows paths for R and the system Python; adjust before running elsewhere.
- 2 sampled tickets have no journey code; 37 were "cannot tell".

## To confirm
- Location of the ticket workbook (`scopus content 2ls verbatim cleaned 2025_2026.xlsx`) needed to re-run notebook 17.
- Who requested the analysis, and whether the deck was presented and to whom.
