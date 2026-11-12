"""Render the effort-model results: charts + runs/output/csd_2026_effort_model.xlsx.

Reads runs/output/model/model_results.json written by scripts/effort_model.R.
Run under the project venv.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                    # noqa: E402
import numpy as np                                                 # noqa: E402
import pandas as pd                                                # noqa: E402
from matplotlib.ticker import FuncFormatter                        # noqa: E402

BASE = Path(__file__).resolve().parents[1]
MDIR = BASE / "runs" / "output" / "model"
FIGS = MDIR / "figs"
FIGS.mkdir(parents=True, exist_ok=True)
OUT = BASE / "runs" / "output" / "csd_2026_effort_model.xlsx"

NAVY, ORANGE, GREY, RED, GREEN = "#0B2A4A", "#FF6C00", "#7A8794", "#C1272D", "#2E7D5B"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                     "axes.edgecolor": GREY, "axes.labelcolor": NAVY,
                     "text.color": NAVY, "xtick.color": GREY, "ytick.color": GREY,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "figure.facecolor": "none", "savefig.facecolor": "none"})
PCT = FuncFormatter(lambda v, _: f"{v:.0%}")

D = json.loads((MDIR / "model_results.json").read_text(encoding="utf-8"))
M = D["meta"]
summary = pd.DataFrame(D["summary"])
coefs = pd.DataFrame(D["coefficients"])
blocks = pd.DataFrame(D["blocks"])
type2 = pd.DataFrame(D["type2"])
perm = pd.DataFrame(D["perm"])
calib = pd.DataFrame(D["calibration"])
vif = pd.DataFrame(D["vif"])
po = pd.DataFrame(D["po_check"])
roc = pd.read_csv(MDIR / "roc_curves.csv")
drivers_all = pd.read_csv(MDIR / "survey_vs_llm_drivers.csv")

print("=" * 78)
print("EFFORT MODEL REPORT")
print("=" * 78)
print(f"  n={M['n_analysis']:,}  not-easy events={M['events_not_easy']}  "
      f"base rate={M['base_rate_not_easy']:.1%}")


def save(fig, name):
    # A chart whose data frame came back empty still renders perfectly good axes
    # and reference lines, so it ships looking deliberate. Count only the artists
    # that carry data - scatters, bars, error bars - and refuse to write a figure
    # that has none.
    for ax in fig.axes:
        data_artists = len(ax.collections) + len(ax.patches)
        plotted_lines = [ln for ln in ax.lines if ln.get_linestyle() not in ("--", ":")]
        assert data_artists or plotted_lines, (
            f"{name}: axes contain no data, only decoration - the source frame is "
            f"probably empty")
    fig.tight_layout()
    fig.savefig(FIGS / f"{name}.png", dpi=200, transparent=True, bbox_inches="tight")
    plt.close(fig)
    print(f"    {name}.png")


def pretty(term: str) -> str:
    t = (term.replace("resolution_code", "code: ")
             .replace("contact_reason_l1", "request: ")
             .replace("reason_grp", "reason: ")
             .replace("conformance_status", "matrix: ")
             .replace("repeat_contact_obs", "repeat contact: ")
             .replace("resolution_transparency", "transparency: ")
             .replace("obs_agent_handoffs", "agent handoffs")
             .replace("obs_customer_turns", "customer messages")
             .replace("obs_responses", "agent responses")
             .replace("log_tat_days", "log turnaround (days)")
             .replace("log_span_h", "log thread span (h)")
             .replace("log_frt_days", "log first response (days)")
             .replace("llm_effort_num", "LLM effort score")
             .replace("friction_count", "friction points counted")
             .replace("customer_type", "customer: ")
             .replace("close_half", "closed ")
             .replace("channel", "channel: "))
    return t[:52]


# ══════════════════════════════════════════════ 1 · forest plot, structural model
s1 = coefs[(coefs.model == "S1") & (coefs.term != "(Intercept)")].copy()
s1 = s1.sort_values("odds_ratio")
sig = s1[s1.p_value < 0.05]
fig, ax = plt.subplots(figsize=(10, max(4.2, 0.32 * len(sig))))
y = np.arange(len(sig))
cols = [RED if o > 1 else GREEN for o in sig.odds_ratio]
ax.hlines(y, sig.or_lo, sig.or_hi, color=GREY, lw=1.4, zorder=2)
ax.scatter(sig.odds_ratio, y, color=cols, s=46, zorder=3)
ax.axvline(1, color=NAVY, ls="--", lw=1.2)
ax.set_yticks(y); ax.set_yticklabels([pretty(t) for t in sig.term], fontsize=8.5)
ax.set_xscale("log")
ax.set_xlabel("odds ratio on the customer saying it was not easy (log scale)")
save(fig, "m01_forest_structural")

# ════════════════════════════════════════════════ 2 · block contributions
fig, ax = plt.subplots(figsize=(10, 4.2))
b = blocks.copy()
lab = [c.replace(" -> ", "\n→ ") for c in b.comparison]
cols = [NAVY if p < 0.05 else GREY for p in b.p_value]
ax.barh(np.arange(len(b)), b.delta_mcfadden, 0.6, color=cols)
ax.set_yticks(np.arange(len(b))); ax.set_yticklabels(lab, fontsize=8.5)
ax.set_xlabel("increase in McFadden pseudo-R² when the block is added")
for i, (v, p) in enumerate(zip(b.delta_mcfadden, b.p_value)):
    ax.text(v + 0.0012, i, "p<0.001" if p < 0.001 else f"p={p:.3f}",
            va="center", fontsize=8, color=GREY)
ax.invert_yaxis()
save(fig, "m02_block_contributions")

# ═════════════════════════════════════════════════════════ 3 · ROC + null
fig, ax = plt.subplots(figsize=(6.4, 5.6))
for m, c in [("S1", NAVY), ("S2", ORANGE)]:
    r = roc[roc.model == m]
    a = float(summary.loc[summary.model == m, "auc_in_sample"].iloc[0])
    ax.plot(r.fpr, r.tpr, color=c, lw=1.8, label=f"{m}  AUC {a:.3f}")
ax.plot([0, 1], [0, 1], color=GREY, ls="--", lw=1)
_p95 = float(perm.loc[perm.model == "S1", "null_p95"].iloc[0])
_cv = float(perm.loc[perm.model == "S1", "observed_cv5"].iloc[0])
ax.set_xlabel("false positive rate"); ax.set_ylabel("true positive rate")
ax.legend(frameon=False, fontsize=9, loc="lower right")
ax.set_title(f"cross-validated AUC {_cv:.3f}   ·   shuffled-outcome null 95th pct {_p95:.3f}",
             fontsize=9.5, color=GREY)
save(fig, "m03_roc")

# ════════════════════════════════════════════════════════ 4 · calibration
fig, ax = plt.subplots(figsize=(6.4, 5.2))
ax.plot([0, calib.observed.max() * 1.1], [0, calib.observed.max() * 1.1],
        color=GREY, ls="--", lw=1)
ax.scatter(calib.predicted, calib.observed, color=NAVY, s=52, zorder=3)
for _, r in calib.iterrows():
    ax.annotate(int(r.decile), (r.predicted, r.observed), textcoords="offset points",
                xytext=(6, -3), fontsize=8, color=GREY)
ax.set_xlabel("predicted probability (decile mean)")
ax.set_ylabel("observed share saying it was not easy")
ax.xaxis.set_major_formatter(PCT); ax.yaxis.set_major_formatter(PCT)
save(fig, "m04_calibration")

# ══════════════════════════════════ 5 · what drives the customer vs the model
dr = drivers_all[drivers_all.term.str.startswith(("reason_grp", "conformance_status"))].copy()
dr = dr[np.isfinite(dr.odds_ratio_survey) & np.isfinite(dr.odds_ratio_llm)]
# An earlier build paired the wrong two models here and shipped a blank chart,
# because the merge simply produced no rule/reason rows. Fail rather than plot air.
assert len(dr) >= 8, (
    f"only {len(dr)} rule/reason terms shared between the survey and LLM models - the "
    f"drivers merge is pairing the wrong models")
fig, ax = plt.subplots(figsize=(9.0, 6.2))
lim = [min(dr.odds_ratio_llm.min(), dr.odds_ratio_survey.min()) * 0.7,
       max(dr.odds_ratio_llm.max(), dr.odds_ratio_survey.max()) * 1.4]
ax.plot(lim, lim, color=GREY, ls=":", lw=1.1, zorder=1)
ax.axhline(1, color=GREY, ls="--", lw=1); ax.axvline(1, color=GREY, ls="--", lw=1)
dr = dr.sort_values("odds_ratio_llm").reset_index(drop=True)
for i, r in dr.iterrows():
    is_conf = r.term.startswith("conformance")
    c = ORANGE if is_conf else (NAVY if r.p_value_survey < 0.05 else GREY)
    ax.vlines(r.odds_ratio_llm, r.or_lo_survey, r.or_hi_survey, color=c, lw=1, alpha=.45)
    ax.scatter(r.odds_ratio_llm, r.odds_ratio_survey, s=70, color=c, zorder=3)
    # The prefixes are already given by the axis labels and the colour key, and
    # leaving them on makes neighbouring labels collide.
    lab = (r.term.replace("reason_grp", "").replace("conformance_status", ""))[:22]
    ax.annotate(lab, (r.odds_ratio_llm, r.odds_ratio_survey),
                textcoords="offset points",
                xytext=(8, 5) if i % 2 == 0 else (8, -11),
                fontsize=7.5, color=NAVY if not is_conf else ORANGE)
ax.set_xscale("log"); ax.set_yscale("log")
ax.set_xlim(lim); ax.set_ylim(lim)
ax.set_xlabel("odds ratio on the LLM calling it high effort  (n=12,000)")
ax.set_ylabel("odds ratio on the customer saying it was not easy  (n=625)")
ax.set_title("dotted line = the two agree;  orange = matrix conformance;  "
             "grey = not significant for the customer", fontsize=8.5, color=GREY)
save(fig, "m05_drivers_survey_vs_llm")
print(f"    ({len(dr)} rule/reason terms plotted)")

# ══════════════════════════════════════════════ 6 · rules arm: the null result
r2 = coefs[(coefs.model == "R2") & (coefs.term != "(Intercept)")].copy()
r2 = r2[r2.term.str.startswith(("conformance_status", "reason_grp"))].sort_values("odds_ratio")
fig, ax = plt.subplots(figsize=(9.6, max(4.0, 0.34 * len(r2))))
y = np.arange(len(r2))
cols = [ORANGE if t.startswith("conformance") else
        (NAVY if p < 0.05 else GREY) for t, p in zip(r2.term, r2.p_value)]
ax.hlines(y, r2.or_lo.clip(upper=60), r2.or_hi.clip(upper=60), color=GREY, lw=1.3, zorder=2)
ax.scatter(r2.odds_ratio, y, color=cols, s=48, zorder=3)
ax.axvline(1, color=NAVY, ls="--", lw=1.2)
ax.set_yticks(y); ax.set_yticklabels([pretty(t) for t in r2.term], fontsize=8.5)
ax.set_xscale("log")
ax.set_xlabel("odds ratio on the customer saying it was not easy  (n=625)")
save(fig, "m06_rules_arm")

# ══════════════════════════════════════════════════════════════════ workbook
def sheet(df):
    return df.copy()


DD = [
    ("What the outcome is", "survey_not_easy",
     "The customer's own answer, codes 3-5 on CSAT_EFFORT_CODE - they did not agree the "
     f"request was easy to handle. {M['events_not_easy']} of {M['n_analysis']:,} "
     f"({M['base_rate_not_easy']:.1%}). The stricter 4-5 threshold is {M['base_rate_hard']:.1%}."),
    ("Why two thresholds", "survey_not_easy vs survey_hard",
     "52.4% of respondents pick the top box, so the scale is lumpy. Codes 4-5 give 7.9% and "
     "codes 3-5 give 13.3%, against the LLM's 27.3% high-effort rate. No survey threshold "
     "matches the LLM's base rate, so the two measures are comparable on RANKING only."),
    ("odds_ratio", "coefficients sheet",
     "Multiplicative change in the odds of 'not easy' for a one-unit increase, or versus the "
     "reference level. Above 1 = harder. Reference levels: resolution code = the "
     "alphabetically first retained level; rejection reason = Content Already Indexed; "
     "matrix status = rule matches code; repeat contact = no."),
    ("auc_cv5 vs auc_in_sample", "model_summary",
     "Five-fold cross-validated AUC is the honest figure. In-sample AUC on 360 events with up "
     "to 41 terms is optimistic by construction."),
    ("permutation null", "permutation_null sheet",
     "The outcome was shuffled 200 times and the model refitted. If the real cross-validated "
     "AUC sat inside that null distribution the model would not predict at all."),
    ("epv / stability", "model_summary",
     "Events per variable. Below 10 is borderline and below 5 is unstable; coefficients from "
     "those fits should be read as directional only."),
    ("EXCLUDED - obs_distinct_agents", "diagnostics",
     "Equals obs_agent_handoffs + 1 on 98% of rows (r = 0.998). Entering both left the design "
     "rank-deficient, so it was dropped."),
    ("EXCLUDED - obs_effort_index", "diagnostics",
     "The mean of percentile ranks of four columns already in the model."),
    ("EXCLUDED - all CSAT_* except the outcome", "diagnostics",
     "Same survey instrument. CSAT_ANSWER_CODE correlates with the outcome at Spearman 0.731 "
     "and is populated only on survey rows, so it also encodes responding at all."),
    ("Non-response bias", "meta",
     f"Repeat contact runs {M['repeat_corpus']:.1%} corpus-wide but {M['repeat_respondents']:.1%} "
     f"among survey respondents. People who keep coming back are under-represented in exactly "
     f"the population being modelled, which biases the repeat-contact coefficient towards zero."),
    ("Design weighting", "L1 only",
     "The 12,000 is a stratified sample so L1 uses svyglm with strata = resolution code. The "
     "2,813 survey respondents span the whole corpus and are not design-weighted; they are, "
     "however, self-selected."),
]

with pd.ExcelWriter(OUT, engine="openpyxl") as xl:
    sheet(summary).to_excel(xl, sheet_name="model_summary", index=False)
    sheet(blocks).to_excel(xl, sheet_name="block_contributions", index=False)
    sheet(type2).to_excel(xl, sheet_name="type2_tests", index=False)
    sheet(coefs).to_excel(xl, sheet_name="coefficients", index=False)
    sheet(drivers_all).to_excel(xl, sheet_name="survey_vs_llm_drivers", index=False)
    sheet(perm).to_excel(xl, sheet_name="permutation_null", index=False)
    sheet(calib).to_excel(xl, sheet_name="calibration", index=False)
    sheet(vif).to_excel(xl, sheet_name="vif", index=False)
    sheet(po).to_excel(xl, sheet_name="proportional_odds_check", index=False)
    pd.DataFrame(DD, columns=["item", "where", "meaning"]).to_excel(
        xl, sheet_name="data_dictionary", index=False)

assert len(coefs) > 0 and len(summary) == 8
print(f"\nwrote {OUT}")
print(f"  {len(summary)} models, {len(coefs)} coefficients, {len(blocks)} block tests")
