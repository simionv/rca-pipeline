# Validation-rule scorecard — Scopus CSD 2026

Generated from `runs/output/csd_2026_rule_scorecard.xlsx`. Companion deck: `runs/output/CSD_2026_rule_scorecard.pptx` (15 slides).

## Read these three things first

**1. The corpus is 7 months, not a year.** Every ticket closed between 2026-01-01 and 2026-07-31. Volumes appear twice: on that observed basis, and annualised (×1.714). *The earlier 60-slide deck labels these same volumes "a year" — those figures are understated by 71%.* Rates and percentages are unaffected.

**2. CSAT and effort run in opposite directions.** CSAT is an inverted 1–7 scale where 1 = extremely satisfied, so a **lower** mean is better. Both effort scales run 1–5 where 5 = hardest. The three have been checked against each other for sign and they cohere (effort~hard +0.38, effort~satisfied −0.67, hard~satisfied −0.83).

**3. Survey columns are thin.** 625 survey-effort and 641 CSAT answers across 12,000 classified tickets. Only **8 of 23** rules reach 30 responses; the rest show a dash. The count is always printed. This covers the entire top ten by volume.

---

## The scorecard

All volumes are design-weighted estimates. The effort figures reproduce the existing triangulation workbook exactly.

| Validation rule | Est. vol Jan–Jul | Annualised | 2025 vol of primary code | Conf. strict | Survey n | **% not easy** (survey 3–5) | **% hard** (survey 4–5) | **% high** (LLM) | Survey mean | LLM mean | TAT med (d) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 05 Published less than 4 weeks ago - too recent Vol… | 11,529 | 19,765 | 15,713 | 80% | 133 | 6% | 3% | 10% | 1.55 | 2.74 | 2.8 |
| 06 Paper already available in Scopus (on search) | 8,788 | 15,065 | 20,469 | 95% | 93 | 6% | 2% | 8% | 1.40 | 2.36 | 3.4 |
| No applicable validation rule | 7,696 | 13,193 | — | 0% | 97 | 17% | 12% | 23% | 1.85 | 2.85 | 2.9 |
| 02 Journal under re-evaluation (refers to the sourc… | 5,102 | 8,746 | 3,131 | 66% | 56 | 21% | 14% | 49% | 2.03 | 3.41 | 2.0 |
| 07 Already in the pipeline - appears within ~4 days | 3,837 | 6,577 | 2,916 | 75% | 46 | 10% | 10% | 9% | 1.78 | 2.70 | 2.4 |
| 01 Journal not covered ( refers to the source has n… | 3,683 | 6,314 | 4,126 | 54% | 43 | 21% | 9% | 49% | 1.98 | 3.41 | 4.1 |
| 08 Coverage mismatch - pre-dates coverage start, or… | 3,536 | 6,062 | 263 | 2% | 66 | 19% | 9% | 69% | 1.87 | 3.66 | 3.6 |
| 15 Scopus already matches the publisher version of … | 2,328 | 3,991 | 4,703 | 47% | 35 | 13% | 8% | 36% | 1.78 | 2.95 | 5.9 |
| 03 Journal published on an unauthentic publisher si… | 1,923 | 3,297 | 1,824 | 69% | 27 | — | — | 69% | — | 3.67 | 4.6 |
| 14 AiP requested for a MEDLINE-sourced title, or fr… | 917 | 1,572 | 1,669 | 96% | 10 | — | — | 39% | — | 3.34 | 3.6 |
| 24 OA change not verifiable / no publisher evidence… | 277 | 475 | 20,687 | 7% | 4 | — | — | 70% | — | 3.69 | 6.0 |
| 09 Document type out of scope (meeting abstract, bo… | 214 | 366 | 424 | 85% | 7 | — | — | 37% | — | 3.23 | 4.9 |
| 17 Needs a publisher erratum / retraction first | 185 | 317 | 20,687 | 16% | 2 | — | — | 67% | — | 3.59 | 10.2 |
| 11 Preprint from a not-selected source, or a second… | 158 | 270 | 634 | 2% | 2 | — | — | 46% | — | 3.38 | 5.1 |
| (invalid code returned by the model) | 145 | 249 | — | — | 2 | — | — | 3% | — | 1.98 | 3.8 |
| 23 Change already reflected, or duplicate open requ… | 98 | 167 | 4,703 | 38% | 0 | — | — | 23% | — | 2.61 | 8.6 |
| 18 Add abstract / reference / funding not in source… | 88 | 150 | 263 | 0% | 1 | — | — | 53% | — | 3.28 | 4.9 |
| 20 Concerns citation counts / metrics - computed, n… | 68 | 117 | 20,687 | 27% | 1 | — | — | 27% | — | 2.89 | 8.1 |
| 22 Missing vol / issue / page on an AiP - not an er… | 67 | 116 | 1,669 | 86% | 0 | — | — | 30% | — | 3.12 | 4.4 |
| 16 Change would make the record differ from publish… | 33 | 57 | 4,703 | 40% | 0 | — | — | 84% | — | 3.84 | 4.4 |
| 21 Target is a secondary (cited-only) document | 21 | 35 | 20,687 | 14% | 0 | — | — | 29% | — | 3.29 | 4.9 |
| 04 Significant journal change -> re-evaluated as ne… | 19 | 32 | 3,131 | 0% | 0 | — | — | 52% | — | 3.52 | 14.9 |
| 19 Document type already matches Scopus definitions | 1 | 2 | 4,703 | 0% | 0 | — | — | 0% | — | 2.00 | 4.8 |

> **The 2025 column is a resolution-code volume, not a rule volume.** It is the 2025 volume of that rule's *primary* resolution code, so rules sharing a code repeat the figure and **the column cannot be summed**. Rule 24's 20,687 is the 2025 volume of `Invalid- Others`, not of rule 24.

---

## What customers actually said

The 8 rules with at least 30 survey responses.

| Validation rule | CSAT n | CSAT mean (1–7, low = good) | % satisfied | Survey n | Effort mean (1–5, high = hard) | % hard | LLM effort | LLM − survey |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 05 Published less than 4 weeks ago - too recent… | 134 | 1.77 | 93% | 133 | 1.55 | 3% | 2.74 | +1.19 |
| 06 Paper already available in Scopus (on search) | 94 | 1.59 | 94% | 93 | 1.40 | 2% | 2.36 | +0.96 |
| No applicable validation rule | 99 | 2.25 | 84% | 97 | 1.85 | 12% | 2.85 | +1.00 |
| 02 Journal under re-evaluation (refers to the s… | 59 | 2.64 | 80% | 56 | 2.03 | 14% | 3.41 | +1.38 |
| 07 Already in the pipeline - appears within ~4 … | 46 | 1.95 | 91% | 46 | 1.78 | 10% | 2.70 | +0.92 |
| 01 Journal not covered ( refers to the source h… | 44 | 2.50 | 86% | 43 | 1.98 | 9% | 3.41 | +1.42 |
| 08 Coverage mismatch - pre-dates coverage start… | 69 | 2.32 | 85% | 66 | 1.87 | 9% | 3.66 | +1.79 |
| 15 Scopus already matches the publisher version… | 37 | 2.35 | 86% | 35 | 1.78 | 8% | 2.95 | +1.16 |

**The model reads every rule as harder than the customer reported.** The gap runs +0.92 to +1.79 (mean +1.23) and is positive on all 8 rules. The score ranks rules correctly but sits about one level above the customer's own answer — treat it as an ordering, never as a level.

**Satisfaction holds up even where effort does not.** It never falls below 80% on any measurable rule, including those where the majority are judged high effort. Customers are broadly satisfied with how they were treated while disagreeing with the outcome.

---

## Both effort measures, by each axis

The survey base differs sharply by axis, and that is the point. The resolution code is known for every ticket in the corpus, so that view rests on all 2,813 respondents — **11 of 15 codes** clear 30 responses. Rules and reasons exist only on the 12,000 sample, so they rest on 625 — **8 of 23 rules** and **7 of 17 reasons** clear it.

> The survey and LLM percentages are **not on the same scale**. Codes 3–5 give 13.3% of respondents and codes 4–5 give 7.9%, against the LLM's 27.3% high-effort rate. Compare the ordering across rows, never the level between columns.

### By resolution code (all respondents)

| Category | Volume | Survey n | % not easy (3–5) | % hard (4–5) | % high (LLM) | Survey mean | LLM mean | TAT med (d) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Invalid- premature | 12,375 | 680 | 8% | 4% | 7% | 1.57 | 2.68 | 2.2 |
| Invalid-Not Missing | 12,208 | 789 | 8% | 4% | 13% | 1.51 | 2.47 | 3.3 |
| Invalid- advice request | 8,428 | 444 | 10% | 7% | 17% | 1.66 | 2.76 | 0.4 |
| Invalid- Others | 4,125 | 237 | 22% | 17% | 41% | 2.06 | 3.22 | 2.2 |
| Invalid- discontinued title | 4,051 | 253 | 30% | 18% | 69% | 2.22 | 3.65 | 2.8 |
| Invalid- reevaluation | 3,850 | 196 | 15% | 9% | 60% | 1.85 | 3.60 | 1.9 |
| Invalid- recently delivered in OBII | 3,256 | 219 | 7% | 5% | 8% | 1.51 | 2.67 | 2.1 |
| Invalid- Title not covered | 2,696 | 112 | 22% | 11% | 51% | 2.01 | 3.44 | 3.8 |
| Invalid-Captured correct | 2,516 | 113 | 26% | 21% | 54% | 2.19 | 3.33 | 6.1 |
| Invalid- AIP | 1,616 | 66 | 11% | 5% | 33% | 1.71 | 3.24 | 3.3 |
| Invalid- not authentic | 1,566 | 87 | 21% | 7% | 68% | 1.91 | 3.65 | 3.7 |

### By rejection reason (12,000 sample)

| Category | Volume | Survey n | % not easy (3–5) | % hard (4–5) | % high (LLM) | Survey mean | LLM mean | TAT med (d) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Content Not Yet Indexed | 16,575 | 187 | 8% | 5% | 13% | 1.62 | 2.79 | 2.9 |
| Source Coverage Issues | 7,713 | 104 | 20% | 9% | 47% | 1.91 | 3.31 | 2.8 |
| Content Already Indexed | 5,742 | 64 | 5% | 2% | 8% | 1.40 | 2.37 | 3.3 |
| Journal Re-evaluation | 5,465 | 64 | 22% | 16% | 43% | 2.04 | 3.29 | 1.8 |
| Request Under Review | 4,132 | 51 | 8% | 4% | 23% | 1.49 | 2.79 | 3.9 |
| Ineligible Content Types | 3,075 | 44 | 28% | 13% | 53% | 2.07 | 3.46 | 4.9 |
| No reason stated in the ticket | 1,823 | 32 | 17% | 10% | 29% | 1.73 | 2.86 | 4.2 |

### By validation rule (12,000 sample)

| Category | Volume | Survey n | % not easy (3–5) | % hard (4–5) | % high (LLM) | Survey mean | LLM mean | TAT med (d) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 05 Published less than 4 weeks ago - too rece… | 11,529 | 133 | 6% | 3% | 10% | 1.55 | 2.74 | 2.8 |
| 06 Paper already available in Scopus (on sear… | 8,788 | 93 | 6% | 2% | 8% | 1.40 | 2.36 | 3.4 |
| No applicable validation rule | 7,696 | 97 | 17% | 12% | 23% | 1.85 | 2.85 | 2.9 |
| 02 Journal under re-evaluation (refers to the… | 5,102 | 56 | 21% | 14% | 49% | 2.03 | 3.41 | 2.0 |
| 07 Already in the pipeline - appears within ~… | 3,837 | 46 | 10% | 10% | 9% | 1.78 | 2.70 | 2.4 |
| 01 Journal not covered ( refers to the source… | 3,683 | 43 | 21% | 9% | 49% | 1.98 | 3.41 | 4.1 |
| 08 Coverage mismatch - pre-dates coverage sta… | 3,536 | 66 | 19% | 9% | 69% | 1.87 | 3.66 | 3.6 |
| 15 Scopus already matches the publisher versi… | 2,328 | 35 | 13% | 8% | 36% | 1.78 | 2.95 | 5.9 |

---

## Validation rules per resolution code

The matrix assigns **24 rules to just 12 distinct primary codes** — a structural mean of **2.00** rules per claimed code. Observed on the tagged tickets, the design-weighted mean is **1.91**. The near-match is a validation: the tickets behave almost exactly as the matrix is built.

*Effective rules* is the inverse-Simpson count, `1 / Σ(share²)`: 1.0 means one rule owns the code, 4.0 means it is as ambiguous as four equally common rules. It is far less inflated by long tails than a raw distinct count.

| Resolution code | Est. vol Jan–Jul | 2025 vol | Rules naming it primary | …also maps to it | Distinct observed | **Effective rules** | Rules covering 90% |
|---|---:|---:|---:|---:|---:|---:|---:|
| Invalid- premature | 11,725 | 15,713 | 1 | 0 | 10 | **1.34** | 2 |
| Invalid-Not Missing | 11,681 | 20,469 | 1 | 0 | 16 | **1.83** | 3 |
| Invalid- advice request | 5,332 | 10,881 | 0 | 0 | 17 | **2.31** | 4 |
| Invalid- discontinued title | 3,684 | 7,455 | 0 | 1 | 9 | **1.46** | 2 |
| Invalid- reevaluation | 3,450 | 3,131 | 2 | 0 | 8 | **1.05** | 1 |
| Invalid- recently delivered in OBII | 3,062 | 2,916 | 1 | 0 | 8 | **1.22** | 1 |
| Invalid- Others | 2,729 | 20,687 | 4 | 5 | 20 | **3.96** | 8 |
| Invalid- Title not covered | 2,532 | 4,126 | 1 | 1 | 11 | **1.25** | 2 |
| Invalid-Captured correct | 2,409 | 4,703 | 4 | 1 | 17 | **4.27** | 6 |
| Invalid- AIP | 1,534 | 1,669 | 2 | 0 | 13 | **2.38** | 3 |
| Invalid- not authentic | 1,441 | 1,824 | 2 | 0 | 7 | **1.27** | 2 |
| Invalid- book | 569 | 794 | 0 | 0 | 10 | **3.73** | 4 |
| Invalid- Non-GenCAR | 307 | 424 | 1 | 0 | 13 | **3.12** | 4 |
| Invalid-Not within scope | 200 | 634 | 3 | 2 | 19 | **9.29** | 10 |
| Invalid- Out of coverage | 59 | 263 | 2 | 0 | 4 | **2.09** | 2 |

Two things to take from this table. `Invalid- Others` is claimed as primary by 4 rules and touched by 9 in total — no wonder it functions as a wastebasket. And three codes — `Invalid- advice request`, `Invalid- discontinued title`, `Invalid- book` — are claimed by **no rule at all**, which is finding 1 of the main deck arriving by a second route.

---

## Validation rules per rejection reason

Observed only — the matrix contains no reason↔rule mapping. The design-weighted mean is **2.50**, against 1.91 for resolution codes. Higher is expected and reassuring: the reasons were discovered bottom-up from the tickets with no reference to the matrix, so they cut across it.

| Rejection reason | Est. vol Jan–Jul | Distinct observed | **Effective rules** | Rules covering 90% | Modal rule | Modal share |
|---|---:|---:|---:|---:|---|---:|
| Content Not Yet Indexed | 16,575 | 16 | **2.09** | 4 | 05 Published less than 4 weeks ago - to… | 67% |
| Source Coverage Issues | 7,713 | 19 | **3.66** | 4 | 08 Coverage mismatch - pre-dates covera… | 42% |
| Content Already Indexed | 5,742 | 15 | **1.53** | 3 | 06 Paper already available in Scopus (o… | 80% |
| Journal Re-evaluation | 5,465 | 12 | **1.65** | 2 | 02 Journal under re-evaluation (refers … | 75% |
| Request Under Review | 4,132 | 12 | **3.34** | 4 | 06 Paper already available in Scopus (o… | 46% |
| Ineligible Content Types | 3,075 | 18 | **4.00** | 7 | 01 Journal not covered ( refers to the … | 44% |
| No reason stated in the ticket | 1,823 | 13 | **1.79** | 3 | No applicable validation rule | 73% |
| Content Format Issues | 1,412 | 12 | **3.00** | 4 | 03 Journal published on an unauthentic … | 47% |
| Status Inquiries | 1,146 | 7 | **1.90** | 3 | 06 Paper already available in Scopus (o… | 70% |
| Update Requests | 1,047 | 14 | **3.64** | 7 | 15 Scopus already matches the publisher… | 46% |
| Correction Requests | 1,038 | 14 | **2.74** | 7 | 15 Scopus already matches the publisher… | 58% |
| Duplicate Requests | 740 | 7 | **1.82** | 3 | 06 Paper already available in Scopus (o… | 72% |
| Publication Timing Issues | 281 | 8 | **3.79** | 4 | 01 Journal not covered ( refers to the … | 40% |
| Other Request Processing Issues | 226 | 5 | **1.80** | 3 | 06 Paper already available in Scopus (o… | 73% |
| Other Indexing Status Issues | 151 | 12 | **2.70** | 8 | No applicable validation rule | 59% |
| Other Content Type Issues | 92 | 3 | **1.16** | 1 | No applicable validation rule | 93% |
| Other Correction and Update Issues | 57 | 6 | **2.93** | 4 | No applicable validation rule | 47% |

---

## Year on year — volumes are flat, not halved

| | Invalid- tickets |
|---|---:|
| 2025, full calendar year | 95,927 |
| 2026, Jan–Jul actual | 57,876 |
| 2026, annualised ×1.714 | **99,216** |
| Year on year | **+3.4%** |

Reading the Triangulation Matrix's 2025 column against its 2026 column suggests volumes halved. They did not — that 2026 figure is a 6-month snapshot (48,634). Annualising it independently gives 97,268, within 2% of the figure derived from our own corpus. Two routes, one answer.

| Resolution code | 2025 full year | 2026 osvc partial | 2026 Jan–Jul actual | 2026 annualised | YoY |
|---|---:|---:|---:|---:|---:|
| invalid-others | 20,687 | 3,347 | 4,125 | 7,071 | -66% |
| invalid-not missing | 20,469 | 10,063 | 12,208 | 20,928 | +2% |
| invalid-premature | 15,713 | 10,308 | 12,375 | 21,214 | +35% |
| invalid-advice request | 10,881 | 7,221 | 8,428 | 14,448 | +33% |
| invalid-discontinued title | 7,455 | 3,370 | 4,051 | 6,945 | -7% |
| invalid-captured correct | 4,703 | 2,142 | 2,516 | 4,313 | -8% |
| invalid-title not covered | 4,126 | 2,353 | 2,696 | 4,622 | +12% |
| invalid-reevaluation | 3,131 | 3,062 | 3,850 | 6,600 | +111% |
| invalid-recently delivered in obii | 2,916 | 2,764 | 3,256 | 5,582 | +91% |
| invalid-not authentic | 1,824 | 1,323 | 1,566 | 2,685 | +47% |
| invalid-aip | 1,669 | 1,315 | 1,616 | 2,770 | +66% |
| invalid-book | 794 | 491 | 592 | 1,015 | +28% |
| invalid-not within scope | 634 | 212 | 216 | 370 | -42% |
| invalid-non-gencar | 424 | 272 | 318 | 545 | +29% |
| invalid-out of coverage | 263 | 50 | 63 | 108 | -59% |
| invalid-correction online | 224 | 334 | 0 | 0 | -100% |
| invalid-'0' document profile | 14 | 7 | 0 | 0 | -100% |

---

## What explains customer effort — the model

Fitted in **R 4.3.1** (`glm`, `MASS::polr`, `survey::svyglm`). Full output in `runs/output/csd_2026_effort_model.xlsx`.

**Outcome:** the customer's own answer, codes 3–5 ("did not agree it was easy") — 360 of 2,813 respondents, 12.8%. Every other CSAT field is excluded as a predictor: they are the same survey instrument (`CSAT_ANSWER_CODE` correlates with the outcome at Spearman 0.731) and are populated only on survey rows, so they would also encode responding at all.

### How much each block explains

| Block added | df | ΔPseudo-R² | p |
|---|---:|---:|---:|
| null → handling | 9 | 0.0637 | <0.001 |
| handling → + resolution code and context | 18 | 0.0496 | <0.001 |
| context → + the LLM's reading | 13 | 0.0214 | <0.001 |
| minimal → + conformance status (n=625) | 3 | 0.0049 | 0.460 |
| conformance → + rejection reason (n=625) | 9 | 0.0431 | 0.007 |

**The result worth pausing on.** Whether the matrix mapped the ticket correctly adds nothing to the prediction of customer effort (p=0.46), while what the agent actually refused on adds a great deal (p=0.007). Governance correctness and customer pain are separate problems. This tempers the earlier deck's conformance-versus-effort slide, which was measured against the *LLM's* effort score — that association holds; it does not carry through to the customer's own answer.

### Model performance

| Model | What it adds | n | Events | Terms | EPV | Pseudo-R² | AUC in-sample | AUC 5-fold CV | Stability |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| S0 | Handling only (TAT, turns, handoffs, repeat) | 2,813 | 360 | 9 | 40.0 | 0.064 | 0.686 | 0.664 | ok |
| S1 | + resolution code and request context | 2,813 | 360 | 27 | 13.3 | 0.113 | 0.734 | 0.702 | ok |
| S2 | + the LLM's reading of the transcript | 2,813 | 360 | 41 | 8.8 | 0.135 | 0.751 | 0.717 | borderline |
| S1-hard | S1 spec, stricter outcome (codes 4-5) | 2,813 | 216 | 27 | 8.0 | 0.137 | 0.769 | 0.726 | borderline |
| R0 | Minimal controls only | 625 | 92 | 4 | 23.0 | 0.054 | 0.675 | 0.647 | ok |
| R1 | + conformance status (grouped rules) | 625 | 92 | 7 | 13.1 | 0.059 | 0.683 | 0.647 | ok |
| R2 | + rejection reason | 625 | 92 | 16 | 5.8 | 0.102 | 0.729 | 0.662 | borderline |
| L1 | LLM high-effort call, design-weighted | 12,000 | 3684 | 28 | 131.6 | — | 0.859 | — | ok |

**Cross-validated AUC is the figure to quote.** Shuffling the outcome 200 times and refitting gives a null AUC whose 95th percentile is 0.598; the structural model reaches 0.702 out of fold. The signal is real and modest. Pseudo-R² of 0.113 means **most of what makes a ticket feel effortful is not in the handling record at all** — that is a finding, not a failure.

### The structural drivers

| Term | Odds ratio | 95% CI | p |
|---|---:|---:|---:|
| resolution_codeother | 7.62 | 3.07 – 18.94 | <0.001 |
| resolution_codeInvalid- discontinued title | 5.56 | 3.04 – 10.19 | <0.001 |
| resolution_codeInvalid- Title not covered | 4.17 | 2.01 – 8.67 | <0.001 |
| resolution_codeInvalid- not authentic | 4.03 | 1.82 – 8.93 | <0.001 |
| resolution_codeInvalid- reevaluation | 2.65 | 1.36 – 5.18 | 0.004 |
| resolution_codeInvalid-Captured correct | 2.63 | 1.03 – 6.69 | 0.043 |
| resolution_codeInvalid- Others | 2.35 | 1.27 – 4.35 | 0.007 |
| contact_reason_l1Source Title Information | 2.02 | 1.25 – 3.25 | 0.004 |
| log_tat_days | 1.81 | 1.18 – 2.77 | 0.007 |
| obs_responses | 1.56 | 1.27 – 1.91 | <0.001 |
| obs_agent_handoffs | 0.62 | 0.46 – 0.82 | <0.001 |

**Agent handoffs are protective**, not harmful: odds ratio 0.62 (0.46–0.82). A second agent touching the ticket is associated with roughly 38% lower odds that the customer calls it not easy. The likely mechanism is escalation to someone who could actually resolve it — this is an association, not an intervention estimate.

**The resolution code matters more than the handling.** It is the strongest block in the model, and the LLM's own high-effort call is far more predictable from rule and reason (AUC 0.859) than the customer's answer is (AUC 0.702). The model is more rule-governed than the person.

---

## Limitations

- **Survey respondents are not the corpus.** Repeat contact runs 53% corpus-wide but 33% among respondents. People who keep coming back are under-represented in exactly the population being modelled, which biases the repeat-contact coefficient towards zero. Nothing here corrects for it.
- **Per-rule effects on customer effort are not estimable.** 625 respondents carry a rule tag, 92 of them in the outcome — enough for grouped effects, not 23 coefficients. Extending rule tagging to the full corpus (about $530) would lift this to 2,813.
- **Association, not causation.** No coefficient here is an intervention estimate.
- **The 2025 column is code-level, not rule-level.** It cannot be summed. See the note under the scorecard.
- **Annualisation assumes the remaining five months resemble the first seven.** Monthly volumes over Jan–Jul range 7,462 to 9,659, so the assumption is reasonable but untested; seasonality in academic publishing could break it.
- **Survey respondents are self-selected**, and there are only 625 of them (~5% of tickets). Design weighting corrects the stratified sample design; it does not correct who chose to answer. Comparisons between signals are fair because they rest on the same people; absolute levels may not generalise.
- **The LLM effort score agrees with itself only 62.3% of the time** (test-retest Spearman +0.675). That caps how well it can correlate with anything, and means aggregate rates move a few points between runs. Quote them to the nearest few points.
- **Conformance is agreement with the matrix, not accuracy.** The resolution code is one agent's choice at close. Where rule and code disagree, either can be wrong.
- **15 rules have too few survey responses to quote**, and several have fewer than 30 tickets in the sample at all. Their rates are shown for completeness and are illustrative only.
