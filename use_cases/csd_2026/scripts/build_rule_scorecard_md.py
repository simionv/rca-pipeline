"""Render docs/CSD_2026_rule_scorecard.md from scorecard_data.json.

Standard library only. Run with either interpreter:

    .venv\\Scripts\\python.exe scripts\\build_rule_scorecard_md.py
"""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
D = json.loads((BASE / "runs" / "output" / "scorecard" / "scorecard_data.json")
               .read_text(encoding="utf-8"))
M = D["meta"]
MD = json.loads((BASE / "runs" / "output" / "model" / "model_results.json")
                .read_text(encoding="utf-8"))
MM = MD["meta"]
MSUM = {r["model"]: r for r in MD["summary"]}
MPERM = {r["model"]: r for r in MD["perm"]}
MBLK = MD["blocks"]
MCOEF = MD["coefficients"]
OUT = BASE / "docs" / "CSD_2026_rule_scorecard.md"


def pct(x, dp=0):
    return "—" if x is None else f"{x * 100:.{dp}f}%"


def num(x):
    return "—" if x is None else f"{x:,.0f}"


def dec(x, dp=2):
    return "—" if x is None else f"{x:.{dp}f}"


def cut(s, n):
    s = str(s)
    return s if len(s) <= n else s[:n - 1] + "…"


L: list[str] = []
w = L.append

w("# Validation-rule scorecard — Scopus CSD 2026\n")
w("Generated from `runs/output/csd_2026_rule_scorecard.xlsx`. "
  "Companion deck: `runs/output/CSD_2026_rule_scorecard.pptx` (15 slides).\n")

w("## Read these three things first\n")
w(f"**1. The corpus is {M['months_observed']} months, not a year.** Every ticket closed "
  f"between {M['closed_from']} and {M['closed_to']}. Volumes appear twice: on that observed "
  f"basis, and annualised (×{M['annualise']:.3f}). *The earlier 60-slide deck labels these "
  f"same volumes \"a year\" — those figures are understated by 71%.* Rates and percentages "
  f"are unaffected.\n")
w("**2. CSAT and effort run in opposite directions.** CSAT is an inverted 1–7 scale where "
  "1 = extremely satisfied, so a **lower** mean is better. Both effort scales run 1–5 where "
  "5 = hardest. The three have been checked against each other for sign and they cohere "
  "(effort~hard +0.38, effort~satisfied −0.67, hard~satisfied −0.83).\n")
w(f"**3. Survey columns are thin.** {M['n_survey']} survey-effort and {M['n_csat']} CSAT "
  f"answers across {M['n_sample']:,} classified tickets. Only **{M['n_rules_clearing']} of "
  f"{M['n_rules_total']}** rules reach {M['min_survey_n']} responses; the rest show a dash. "
  f"The count is always printed. This covers the entire top ten by volume.\n")
w("---\n")

# ─────────────────────────────────────────────────────────── the scorecard
w("## The scorecard\n")
w("All volumes are design-weighted estimates. The effort figures reproduce the existing "
  "triangulation workbook exactly.\n")
w("| Validation rule | Est. vol Jan–Jul | Annualised | 2025 vol of primary code | Conf. "
  "strict | Survey n | **% not easy** (survey 3–5) | **% hard** (survey 4–5) | "
  "**% high** (LLM) | Survey mean | LLM mean | TAT med (d) |")
w("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for r in D["per_rule"]:
    w(f"| {cut(r['rule_label'], 52)} | {num(r['est_vol_jan_jul'])} | "
      f"{num(r['est_vol_annualised'])} | {num(r['code_vol_2025'])} | "
      f"{pct(r['conf_strict'])} | {r['survey_n']} | {pct(r['pct_not_easy'])} | "
      f"{pct(r['pct_hard'])} | {pct(r['pct_high_effort'])} | "
      f"{dec(r['survey_effort_mean_1_5'])} | {dec(r['llm_effort_mean_1_5'])} | "
      f"{dec(r['tat_median_days'], 1)} |")
w("")
w("> **The 2025 column is a resolution-code volume, not a rule volume.** It is the 2025 "
  "volume of that rule's *primary* resolution code, so rules sharing a code repeat the "
  "figure and **the column cannot be summed**. Rule 24's 20,687 is the 2025 volume of "
  "`Invalid- Others`, not of rule 24.\n")
w("---\n")

# ────────────────────────────────────────────────────── the customer's view
srv = [r for r in D["per_rule"] if r["survey_n"] >= M["min_survey_n"]]
w("## What customers actually said\n")
w(f"The {M['n_rules_clearing']} rules with at least {M['min_survey_n']} survey responses.\n")
w("| Validation rule | CSAT n | CSAT mean (1–7, low = good) | % satisfied | Survey n | "
  "Effort mean (1–5, high = hard) | % hard | LLM effort | LLM − survey |")
w("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
for r in srv:
    w(f"| {cut(r['rule_label'], 48)} | {r['csat_n']} | {dec(r['csat_mean_1_7'])} | "
      f"{pct(r['pct_satisfied'])} | {r['survey_n']} | "
      f"{dec(r['survey_effort_mean_1_5'])} | {pct(r['pct_hard'])} | "
      f"{dec(r['llm_effort_mean_1_5'])} | +{r['llm_vs_survey_delta']:.2f} |")
w("")
w(f"**The model reads every rule as harder than the customer reported.** The gap runs "
  f"+{M['delta_min']:.2f} to +{M['delta_max']:.2f} (mean +{M['delta_mean']:.2f}) and is "
  f"positive on all {M['n_rules_clearing']} rules. The score ranks rules correctly but sits "
  f"about one level above the customer's own answer — treat it as an ordering, never as a "
  f"level.\n")
w(f"**Satisfaction holds up even where effort does not.** It never falls below "
  f"{min(r['pct_satisfied'] for r in srv) * 100:.0f}% on any measurable rule, including "
  f"those where the majority are judged high effort. Customers are broadly satisfied with "
  f"how they were treated while disagreeing with the outcome.\n")
w("---\n")

# ────────────────────────────────────────────────────── effort by each axis
w("## Both effort measures, by each axis\n")
w(f"The survey base differs sharply by axis, and that is the point. The resolution code is "
  f"known for every ticket in the corpus, so that view rests on all {MM['n_analysis']:,} "
  f"respondents — **{M['codes_adequate']} of {M['n_codes']} codes** clear "
  f"{M['min_survey_n']} responses. Rules and reasons exist only on the 12,000 sample, so "
  f"they rest on 625 — **{M['rules_adequate']} of {M['n_rules_total']} rules** and "
  f"**{M['reasons_adequate']} of {M['n_reasons']} reasons** clear it.\n")
w("> The survey and LLM percentages are **not on the same scale**. Codes 3–5 give 13.3% of "
  "respondents and codes 4–5 give 7.9%, against the LLM's 27.3% high-effort rate. Compare "
  "the ordering across rows, never the level between columns.\n")

for key, title, lab, volcol in [
        ("effort_by_code", "By resolution code (all respondents)", "rc_label", "n_tickets"),
        ("effort_by_reason", "By rejection reason (12,000 sample)", "reason_label",
         "est_vol_jan_jul"),
        ("effort_by_rule", "By validation rule (12,000 sample)", "rule_label",
         "est_vol_jan_jul")]:
    rows = [r for r in D[key] if r["survey_base_adequate"]]
    w(f"### {title}\n")
    w("| Category | Volume | Survey n | % not easy (3–5) | % hard (4–5) | % high (LLM) | "
      "Survey mean | LLM mean | TAT med (d) |")
    w("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        w(f"| {cut(r[lab], 46)} | {num(r[volcol])} | {r['survey_n']} | "
          f"{pct(r['pct_not_easy_survey'])} | {pct(r['pct_hard_survey'])} | "
          f"{pct(r['pct_high_llm'])} | {dec(r['survey_effort_mean_1_5'])} | "
          f"{dec(r['llm_effort_mean_1_5'])} | {dec(r['tat_median_days'], 1)} |")
    w("")
w("---\n")

# ─────────────────────────────────────────────────── rules per resolution code
w("## Validation rules per resolution code\n")
w(f"The matrix assigns **24 rules to just {M['n_primary_codes']} distinct primary codes** — "
  f"a structural mean of **{M['structural_mean']:.2f}** rules per claimed code. Observed on "
  f"the tagged tickets, the design-weighted mean is **{M['obs_mean_code']:.2f}**. The "
  f"near-match is a validation: the tickets behave almost exactly as the matrix is built.\n")
w("*Effective rules* is the inverse-Simpson count, `1 / Σ(share²)`: 1.0 means one rule owns "
  "the code, 4.0 means it is as ambiguous as four equally common rules. It is far less "
  "inflated by long tails than a raw distinct count.\n")
w("| Resolution code | Est. vol Jan–Jul | 2025 vol | Rules naming it primary | …also maps "
  "to it | Distinct observed | **Effective rules** | Rules covering 90% |")
w("|---|---:|---:|---:|---:|---:|---:|---:|")
for r in D["rules_per_code"]:
    w(f"| {r['rc_label']} | {num(r['est_vol_jan_jul'])} | {num(r['code_vol_2025'])} | "
      f"{r['n_rules_primary']} | {r['n_rules_also']} | {r['distinct_rules']} | "
      f"**{dec(r['effective_rules_inv_simpson'])}** | {r['rules_covering_90pct']} |")
w("")
w("Two things to take from this table. `Invalid- Others` is claimed as primary by 4 rules "
  "and touched by 9 in total — no wonder it functions as a wastebasket. And three codes — "
  + ", ".join("`" + c + "`" for c in M["unclaimed_codes"]) +
  " — are claimed by **no rule at all**, which is finding 1 of the main deck arriving by a "
  "second route.\n")
w("---\n")

# ──────────────────────────────────────────────── rules per rejection reason
w("## Validation rules per rejection reason\n")
w(f"Observed only — the matrix contains no reason↔rule mapping. The design-weighted mean is "
  f"**{M['obs_mean_reason']:.2f}**, against {M['obs_mean_code']:.2f} for resolution codes. "
  f"Higher is expected and reassuring: the reasons were discovered bottom-up from the "
  f"tickets with no reference to the matrix, so they cut across it.\n")
w("| Rejection reason | Est. vol Jan–Jul | Distinct observed | **Effective rules** | Rules "
  "covering 90% | Modal rule | Modal share |")
w("|---|---:|---:|---:|---:|---|---:|")
for r in D["rules_per_reason"]:
    w(f"| {r['reason_label']} | {num(r['est_vol_jan_jul'])} | {r['distinct_rules']} | "
      f"**{dec(r['effective_rules_inv_simpson'])}** | {r['rules_covering_90pct']} | "
      f"{cut(r['modal_rule'], 40)} | {pct(r['modal_share'])} |")
w("")
w("---\n")

# ───────────────────────────────────────────────────────────── year on year
w("## Year on year — volumes are flat, not halved\n")
w("| | Invalid- tickets |")
w("|---|---:|")
w(f"| 2025, full calendar year | {M['vol_2025']:,} |")
w(f"| 2026, Jan–Jul actual | {M['n_invalid_file']:,} |")
w(f"| 2026, annualised ×{M['annualise']:.3f} | **{M['n_pop_annualised']:,}** |")
w(f"| Year on year | **{M['yoy_pct'] * 100:+.1f}%** |")
w("")
_gap = abs(M["n_pop_annualised"] - M["ann_from_osvc"]) / M["n_pop_annualised"] * 100
w(f"Reading the Triangulation Matrix's 2025 column against its 2026 column suggests volumes "
  f"halved. They did not — that 2026 figure is a {M['osvc_months']}-month snapshot "
  f"({M['vol_2026_osvc_partial']:,}). Annualising it independently gives "
  f"{M['ann_from_osvc']:,}, within {_gap:.0f}% of the figure derived from our own corpus. "
  f"Two routes, one answer.\n")
w("| Resolution code | 2025 full year | 2026 osvc partial | 2026 Jan–Jul actual | "
  "2026 annualised | YoY |")
w("|---|---:|---:|---:|---:|---:|")
for r in D["code_yoy"]:
    y = r["yoy_pct"]
    w(f"| {r['resolution_code']} | {r['vol_2025_full_year']:,} | "
      f"{r['vol_2026_osvc_partial']:,} | {r['actual_2026_jan_jul']:,} | "
      f"{r['actual_2026_annualised']:,} | "
      f"{'—' if y is None else format(y * 100, '+.0f') + '%'} |")
w("")
w("---\n")

# ─────────────────────────────────────────────────────── the regression model
w("## What explains customer effort — the model\n")
w(f"Fitted in **R {MM['r_version']}** (`glm`, `MASS::polr`, `survey::svyglm`). Full output in "
  f"`runs/output/csd_2026_effort_model.xlsx`.\n")
w(f"**Outcome:** the customer's own answer, codes 3–5 (\"did not agree it was easy\") — "
  f"{MM['events_not_easy']} of {MM['n_analysis']:,} respondents, "
  f"{MM['base_rate_not_easy']:.1%}. Every other CSAT field is excluded as a predictor: they "
  f"are the same survey instrument (`CSAT_ANSWER_CODE` correlates with the outcome at "
  f"Spearman 0.731) and are populated only on survey rows, so they would also encode "
  f"responding at all.\n")

w("### How much each block explains\n")
w("| Block added | df | ΔPseudo-R² | p |")
w("|---|---:|---:|---:|")
for b in MBLK:
    pv = b["p_value"]
    w(f"| {b['comparison'].replace(' -> ', ' → ')} | {b['df']} | "
      f"{b['delta_mcfadden']:.4f} | {'<0.001' if pv < 0.001 else f'{pv:.3f}'} |")
w("")
_cs = next(b for b in MBLK if "conformance" in b["comparison"] and "minimal" in b["comparison"])
_rs = next(b for b in MBLK if "rejection reason" in b["comparison"])
w(f"**The result worth pausing on.** Whether the matrix mapped the ticket correctly adds "
  f"nothing to the prediction of customer effort (p={_cs['p_value']:.2f}), while what the "
  f"agent actually refused on adds a great deal (p={_rs['p_value']:.3f}). Governance "
  f"correctness and customer pain are separate problems. This tempers the earlier deck's "
  f"conformance-versus-effort slide, which was measured against the *LLM's* effort score — "
  f"that association holds; it does not carry through to the customer's own answer.\n")

w("### Model performance\n")
w("| Model | What it adds | n | Events | Terms | EPV | Pseudo-R² | AUC in-sample | "
  "AUC 5-fold CV | Stability |")
w("|---|---|---:|---:|---:|---:|---:|---:|---:|---|")
for k in ["S0", "S1", "S2", "S1-hard", "R0", "R1", "R2", "L1"]:
    r = MSUM[k]
    r2s = dec(r["mcfadden_r2"], 3)
    cvs = dec(r["auc_cv5"], 3)
    w(f"| {k} | {r['label']} | {num(r['n'])} | {r['events']} | {r['terms']} | "
      f"{r['epv']:.1f} | {r2s} | {r['auc_in_sample']:.3f} | {cvs} | {r['stability']} |")
w("")
w(f"**Cross-validated AUC is the figure to quote.** Shuffling the outcome 200 times and "
  f"refitting gives a null AUC whose 95th percentile is {MPERM['S1']['null_p95']:.3f}; the "
  f"structural model reaches {MSUM['S1']['auc_cv5']:.3f} out of fold. The signal is real and "
  f"modest. Pseudo-R² of {MSUM['S1']['mcfadden_r2']:.3f} means **most of what makes a ticket "
  f"feel effortful is not in the handling record at all** — that is a finding, not a failure.\n")

w("### The structural drivers\n")
_s1 = [c for c in MCOEF if c["model"] == "S1" and c["term"] != "(Intercept)"
       and c["p_value"] < 0.05]
_s1 = sorted(_s1, key=lambda c: -c["odds_ratio"])
w("| Term | Odds ratio | 95% CI | p |")
w("|---|---:|---:|---:|")
for c in _s1:
    pv = c["p_value"]
    w(f"| {c['term']} | {c['odds_ratio']:.2f} | {c['or_lo']:.2f} – {c['or_hi']:.2f} | "
      f"{'<0.001' if pv < 0.001 else f'{pv:.3f}'} |")
w("")
_h = next((c for c in _s1 if c["term"] == "obs_agent_handoffs"), None)
if _h:
    w(f"**Agent handoffs are protective**, not harmful: odds ratio {_h['odds_ratio']:.2f} "
      f"({_h['or_lo']:.2f}–{_h['or_hi']:.2f}). A second agent touching the ticket is "
      f"associated with roughly {(1 - _h['odds_ratio']) * 100:.0f}% lower odds that the "
      f"customer calls it not easy. The likely mechanism is escalation to someone who could "
      f"actually resolve it — this is an association, not an intervention estimate.\n")
w(f"**The resolution code matters more than the handling.** It is the strongest block in the "
  f"model, and the LLM's own high-effort call is far more predictable from rule and reason "
  f"(AUC {MSUM['L1']['auc_in_sample']:.3f}) than the customer's answer is "
  f"(AUC {MSUM['S1']['auc_cv5']:.3f}). The model is more rule-governed than the person.\n")
w("---\n")

# ───────────────────────────────────────────────────────────── limitations
w("## Limitations\n")
w(f"- **Survey respondents are not the corpus.** Repeat contact runs "
  f"{MM['repeat_corpus']:.0%} corpus-wide but {MM['repeat_respondents']:.0%} among "
  f"respondents. People who keep coming back are under-represented in exactly the population "
  f"being modelled, which biases the repeat-contact coefficient towards zero. Nothing here "
  f"corrects for it.")
w(f"- **Per-rule effects on customer effort are not estimable.** {MSUM['R2']['n']} "
  f"respondents carry a rule tag, {MSUM['R2']['events']} of them in the outcome — enough for "
  f"grouped effects, not 23 coefficients. Extending rule tagging to the full corpus (about "
  f"$530) would lift this to {MM['n_analysis']:,}.")
w("- **Association, not causation.** No coefficient here is an intervention estimate.")
w("- **The 2025 column is code-level, not rule-level.** It cannot be summed. See the note "
  "under the scorecard.")
w("- **Annualisation assumes the remaining five months resemble the first seven.** Monthly "
  "volumes over Jan–Jul range 7,462 to 9,659, so the assumption is reasonable but untested; "
  "seasonality in academic publishing could break it.")
w(f"- **Survey respondents are self-selected**, and there are only {M['n_survey']} of them "
  f"(~5% of tickets). Design weighting corrects the stratified sample design; it does not "
  f"correct who chose to answer. Comparisons between signals are fair because they rest on "
  f"the same people; absolute levels may not generalise.")
w("- **The LLM effort score agrees with itself only 62.3% of the time** (test-retest "
  "Spearman +0.675). That caps how well it can correlate with anything, and means aggregate "
  "rates move a few points between runs. Quote them to the nearest few points.")
w("- **Conformance is agreement with the matrix, not accuracy.** The resolution code is one "
  "agent's choice at close. Where rule and code disagree, either can be wrong.")
w(f"- **{M['n_rules_total'] - M['n_rules_clearing']} rules have too few survey responses to "
  f"quote**, and several have fewer than 30 tickets in the sample at all. Their rates are "
  f"shown for completeness and are illustrative only.")
w("")

OUT.write_text("\n".join(L), encoding="utf-8")
print(f"wrote {OUT}  ({len(L)} lines)")
