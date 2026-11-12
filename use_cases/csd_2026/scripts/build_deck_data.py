"""Compute every number and chart the CSD 2026 deck needs.

Run with the PROJECT VENV (pandas 3, matplotlib):

    .venv/Scripts/python.exe scripts/build_deck_data.py

Writes runs/output/deck/deck_data.json and runs/output/deck/figs/*.png.
scripts/build_deck.py then renders the .pptx from those, using the system
Python (which is the interpreter that has python-pptx).

Why the extrapolation is not a multiplication
---------------------------------------------
The 12,000-ticket sample was drawn stratified by resolution code with a floor of
300 per code, so rare codes are massively over-represented: `Invalid- Out of
coverage` has 59 tickets in the population and all 59 in the sample, while
`Invalid- premature` has 11,725 and only 2,224. A single scale factor would
overstate the rare strata by up to +323% and understate premature by 20%.

Every population figure here is therefore a stratified estimate using design
weights w_i = N_h / n_h, with a finite-population correction on the variance.
Two strata were sampled in full, so they contribute exactly zero sampling error.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

try:
    import numpy as np
    import pandas as pd
except ModuleNotFoundError as exc:                                  # pragma: no cover
    sys.exit(f"{exc}. Run this with the project venv:\n"
             r"    .venv\Scripts\python.exe scripts\build_deck_data.py")

if not pd.__version__.startswith("3."):
    sys.exit(f"pandas {pd.__version__}; expected 3.x from .venv. Wrong interpreter?")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                     # noqa: E402
from matplotlib.ticker import FuncFormatter                         # noqa: E402

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data" / "scopus content"
DELIVERABLE = BASE / "runs" / "output" / "csd_2026_validation_rules.xlsx"
EXCLUDED_CSV = BASE / "runs" / "intermediate" / "csd_2026_excluded.csv"
TICKETS_CSV = DATA / "scopus content_2026_threads_collapsed.csv"
META_TSV = DATA / "scopus content_2026_metadata.tsv"
MATRIX_XLSX = DATA / "Triangulation - Validation Rules vs Resolution Codes vs Templates.xlsx"
REASON_TAX = BASE / "generated" / "taxonomies" / "csd_rejection_reason.json"

OUT = BASE / "runs" / "output" / "deck"
FIGS = OUT / "figs"
FIGS.mkdir(parents=True, exist_ok=True)

RC = "resolution_code_lvl1_desc"
NAVY, ORANGE, GREY, RED, GREEN = "#0B2A4A", "#FF6C00", "#7A8794", "#C1272D", "#2E7D5B"
SOURCES: dict[str, str] = {}          # every published scalar -> where it came from


def src(key: str, where: str, value):
    """Record provenance for a published number, so any slide can be traced back."""
    SOURCES[key] = where
    return value


def recs(df: pd.DataFrame) -> list:
    return json.loads(df.to_json(orient="records"))


# ═══════════════════════════════════════════════════════════ load
print("Loading...")
tickets = pd.read_excel(DELIVERABLE, sheet_name="tickets")
sheets = {name: pd.read_excel(DELIVERABLE, sheet_name=name)
          for name in ("conformance", "coverage", "per_rule", "per_code", "association",
                       "reason_summary", "unmapped_codes", "phrase_audit", "proposed_rules",
                       "three_way", "disagreements")}

excluded = pd.read_csv(EXCLUDED_CSV, dtype=str)
all_ids = pd.read_csv(TICKETS_CSV, dtype=str, usecols=["INCIDENT_REF"])
meta = pd.read_csv(META_TSV, sep="\t", dtype=str, usecols=["incident_reference", RC])

population = (all_ids[~all_ids["INCIDENT_REF"].isin(set(excluded["INCIDENT_REF"]))]
              .merge(meta, left_on="INCIDENT_REF", right_on="incident_reference", how="left"))

# Every stratum is a resolution code, so a ticket without one cannot be weighted -
# it belongs to no stratum and sum(N_h) would fall short of the population by
# exactly that many. The 2026-08-07 metadata refresh dropped 7 references that are
# still present in the conversations file; they are removed here and reported.
_no_code = population[RC].isna()
N_NO_CODE = int(_no_code.sum())
if N_NO_CODE:
    print(f"  {N_NO_CODE} classifiable ticket(s) have no resolution code in the current "
          f"metadata and are excluded from the weighting population:")
    print(f"    {population.loc[_no_code, 'INCIDENT_REF'].tolist()}")
population = population[~_no_code].reset_index(drop=True)

N_TOTAL_FILE = len(all_ids)
N_EXCLUDED = len(excluded)
N_POP = len(population)
N_SAMPLE = len(tickets)
NAIVE_FACTOR = N_POP / N_SAMPLE

assert N_TOTAL_FILE == N_EXCLUDED + N_POP + N_NO_CODE, (
    f"the corpus does not reconcile: {N_TOTAL_FILE:,} != {N_EXCLUDED:,} + {N_POP:,} "
    f"+ {N_NO_CODE}")
print(f"  {N_TOTAL_FILE:,} in file = {N_EXCLUDED:,} excluded + {N_POP:,} classifiable")
print(f"  sample {N_SAMPLE:,}; naive factor would be {NAIVE_FACTOR:.3f}")

# ═══════════════════════════════════════════════════════════ design weights
N_h = population[RC].value_counts()
n_h = tickets["rc_label"].value_counts()
missing = set(n_h.index) - set(N_h.index)
assert not missing, f"sample strata absent from the population: {missing}"
_orphans = int(tickets["rc_label"].isna().sum())
assert _orphans == 0, (
    f"{_orphans} sampled ticket(s) have no resolution code in the current metadata. They "
    f"cannot be weighted. Re-run notebook 08 section 15 against the refreshed metadata.")

# A small number of tickets came back with a code that is not in the taxonomy at
# all - CSDVR6, CSDVR2.15, CSDVR8.1 - so derive_labels() left their label blank.
# They are given an explicit bucket rather than being dropped: a silent groupby
# drop would make every extrapolated total miss the population by that amount,
# and the rate itself is worth reporting.
INVALID_CODE_LABEL = "(invalid code returned by the model)"
_bad_code = tickets["rule_label"].isna()
INVALID_CODES = tickets.loc[_bad_code, "csdvr_code"].value_counts().to_dict()
N_INVALID_CODE = int(_bad_code.sum())
tickets["rule_label"] = tickets["rule_label"].fillna(INVALID_CODE_LABEL)
tickets["reason_label"] = tickets["reason_label"].fillna(INVALID_CODE_LABEL)
print(f"  model returned a non-taxonomy code on {N_INVALID_CODE} of {N_SAMPLE:,} tickets "
      f"({N_INVALID_CODE / N_SAMPLE:.2%}): {INVALID_CODES}")

tickets["N_h"] = tickets["rc_label"].map(N_h).astype(float)
tickets["n_h"] = tickets["rc_label"].map(n_h).astype(float)
tickets["w"] = tickets["N_h"] / tickets["n_h"]

assert abs(tickets["w"].sum() - N_POP) < 1e-6, (
    f"weights sum to {tickets['w'].sum():,.4f}, expected {N_POP:,}")
print(f"  design weights sum to {tickets['w'].sum():,.0f}  OK")

CENSUS_STRATA = sorted(N_h.index[(N_h.reindex(n_h.index).fillna(0) == n_h).reindex(N_h.index)
                                 .fillna(False)])
print(f"  strata sampled in full (zero sampling error): {CENSUS_STRATA}")


def strat_prop(mask_col: str, subset: pd.Series | None = None) -> tuple[float, float, int]:
    """Stratified estimate of a proportion, with a finite-population correction.

        p_hat = sum_h W_h * p_h
        Var   = sum_h W_h^2 * p_h(1-p_h)/n_h * (1 - n_h/N_h)

    The FPC term is what makes a fully sampled stratum contribute nothing to the
    variance: if n_h == N_h we measured it, we did not estimate it.
    Returns (estimate, half-width of the 95% interval, effective sample size).
    """
    d = tickets if subset is None else tickets[subset]
    if not len(d):
        return float("nan"), float("nan"), 0
    N_sub = d.groupby("rc_label")["N_h"].first().sum()
    est = var = 0.0
    for _, g in d.groupby("rc_label"):
        Nh, nh = float(g["N_h"].iloc[0]), float(len(g))
        W, p = Nh / N_sub, float(g[mask_col].mean())
        est += W * p
        if nh > 1:
            var += (W ** 2) * (p * (1 - p) / nh) * max(0.0, 1 - nh / Nh)
    return est, 1.96 * math.sqrt(var), len(d)


def strat_volume(subset: pd.Series) -> tuple[float, float]:
    """Estimated population count for a subgroup, and the half-width in tickets.

    The point estimate is just the sum of the weights. The interval comes from
    treating membership as a 0/1 variable over the whole sample and scaling the
    resulting proportion interval up to counts.
    """
    est = float(tickets.loc[subset, "w"].sum())
    tickets["_member"] = subset.astype(float)
    _, half_pp, _ = strat_prop("_member")
    tickets.drop(columns="_member", inplace=True)
    return est, half_pp * N_POP


def bootstrap_se(mask_col: str, subset: pd.Series | None = None, reps: int = 400) -> float:
    """Stratified bootstrap SE, WITHOUT the FPC - so it should come out slightly
    larger than the analytic SE. Used only as a sanity check on the formula."""
    d = tickets if subset is None else tickets[subset]
    groups = [(float(g["N_h"].iloc[0]), g[mask_col].to_numpy(dtype=float))
              for _, g in d.groupby("rc_label")]
    N_sub = sum(Nh for Nh, _ in groups)
    rng = np.random.default_rng(0)
    ests = np.empty(reps)
    for r in range(reps):
        ests[r] = sum((Nh / N_sub) * rng.choice(v, size=len(v), replace=True).mean()
                      for Nh, v in groups)
    return float(ests.std(ddof=1))


# ═══════════════════════════════════════════════════════════ headline metrics
print("Estimating headline metrics...")
tickets["applies"] = ~tickets["rule_is_na"]
tagged = ~tickets["rule_is_na"]
mappable_tagged = tagged & tickets["is_mappable"]

HEADLINES = []
for label, col, subset, denom in [
    ("Conformance among mappable (headline)", "conf_strict", mappable_tagged,
     "rule-tagged tickets whose code a rule claims as primary"),
    ("Conformance strict, all rule-tagged", "conf_strict", tagged, "rule-tagged tickets"),
    ("Conformance loose (primary or also-maps-to)", "conf_loose", tagged, "rule-tagged tickets"),
    ("A validation rule applies", "applies", None, "all classified tickets"),
    ("No applicable validation rule", "rule_is_na", None, "all classified tickets"),
    ("No reason stated in the ticket", "reason_is_none", None, "all classified tickets"),
    ("Mappable (code a rule claims as primary)", "is_mappable", tagged, "rule-tagged tickets"),
]:
    smp = float((tickets if subset is None else tickets[subset])[col].mean())
    est, half, n_eff = strat_prop(col, subset)
    se_boot = bootstrap_se(col, subset)
    se_an = half / 1.96
    # Some quantities carry no sampling variance at all. `is_mappable` is a property
    # of the resolution code, so it is constant within every stratum: p_h is 0 or 1,
    # the variance term vanishes and both SEs are zero up to float noise. Comparing
    # their ratio there is meaningless, so only check when there is variance to check.
    if max(se_an, se_boot) > 1e-6:
        assert se_an <= se_boot * 1.30 + 1e-6, (
            f"{label}: analytic SE {se_an:.5f} exceeds bootstrap {se_boot:.5f} - the FPC "
            f"should make it smaller, so the variance formula is wrong")
        assert se_an >= se_boot * 0.25, (
            f"{label}: analytic SE {se_an:.5f} implausibly small vs bootstrap {se_boot:.5f}")
    HEADLINES.append({"metric": label, "denominator": denom, "n_sample": n_eff,
                      "sample": smp, "population": est, "ci": half,
                      "delta": est - smp, "se_analytic": se_an, "se_bootstrap": se_boot})
    print(f"  {label:<45} {smp:6.1%} -> {est:6.1%} +/-{half:.1%}")

src("headlines", "tickets sheet, stratified estimator in this script", None)

# FPC must zero out the fully-sampled strata
for stratum in CENSUS_STRATA:
    sub = tickets[tickets["rc_label"] == stratum]
    Nh, nh = float(sub["N_h"].iloc[0]), float(len(sub))
    assert abs(1 - nh / Nh) < 1e-12, f"{stratum} is not actually a census ({nh} of {Nh})"
print(f"  FPC check: {len(CENSUS_STRATA)} census stratum/strata contribute zero variance  OK")


# ═══════════════════════════════════════════════════════════ stratification table
strat_table = pd.DataFrame({"population": N_h, "sample": n_h}).dropna()
strat_table["weight"] = strat_table["population"] / strat_table["sample"]
strat_table["pop_share"] = strat_table["population"] / strat_table["population"].sum()
strat_table["smp_share"] = strat_table["sample"] / strat_table["sample"].sum()
strat_table["naive_err"] = strat_table["smp_share"] / strat_table["pop_share"] - 1
strat_table = strat_table.sort_values("population", ascending=False)


def breakdown(col: str) -> pd.DataFrame:
    """Sample vs extrapolated volumes for a categorical column."""
    rows = []
    for value, g in tickets.groupby(col):
        member = tickets[col] == value
        est, half = strat_volume(member)
        rows.append({"label": value, "sample_n": len(g),
                     "sample_pct": len(g) / N_SAMPLE,
                     "pop_est": est, "pop_ci": half, "pop_pct": est / N_POP,
                     "naive_est": len(g) * NAIVE_FACTOR,
                     "naive_err": (len(g) * NAIVE_FACTOR) / est - 1})
    return pd.DataFrame(rows).sort_values("pop_est", ascending=False).reset_index(drop=True)


print("Building breakdowns...")
rule_bd = breakdown("rule_label")
reason_bd = breakdown("reason_label")
code_bd = breakdown("rc_label")
for name, bd in (("rule", rule_bd), ("reason", reason_bd), ("code", code_bd)):
    assert abs(bd["pop_est"].sum() - N_POP) < 1e-6, f"{name} volumes do not sum to the population"
print(f"  rule {len(rule_bd)} rows, reason {len(reason_bd)} rows, code {len(code_bd)} rows; "
      f"all sum to {N_POP:,}  OK")
print(f"  worst naive error: rule {rule_bd['naive_err'].abs().max():+.0%}, "
      f"reason {reason_bd['naive_err'].abs().max():+.0%}")


# ═══════════════════════════════════════════════════════════ weighted three-way
# The workbook's three_way sheet holds raw sample counts. Re-derive it weighted so
# the deck never mixes a design-weighted figure with a naively scaled one.
three_way_w = (tickets.groupby(["reason_label", "rule_label", "rc_label"], observed=True)
               .agg(sample_n=("w", "size"), pop_est=("w", "sum"),
                    conf_strict=("conf_strict", "mean"), mappable=("is_mappable", "first"))
               .reset_index().sort_values("pop_est", ascending=False))
three_way_w["pop_pct"] = three_way_w["pop_est"] / N_POP
assert abs(three_way_w["pop_est"].sum() - N_POP) < 1e-6, "three-way cells do not reconcile"
print(f"  three-way: {len(three_way_w)} cells, weighted, summing to {N_POP:,}")


# ═══════════════════════════════════════════════════════════ association measures
def _entropy(counts) -> float:
    p = np.asarray(counts, dtype=float)
    p = p[p > 0]
    p = p / p.sum()
    return float(-(p * np.log(p)).sum())


def assoc_from_table(ct: np.ndarray) -> dict:
    """Cramer's V (raw + Bergsma-corrected), NMI and Theil's U from a contingency table."""
    n = ct.sum()
    row, col = ct.sum(1), ct.sum(0)
    exp = np.outer(row, col) / n
    with np.errstate(divide="ignore", invalid="ignore"):
        chi2 = float(np.nansum(np.where(exp > 0, (ct - exp) ** 2 / exp, 0.0)))
    r, k = ct.shape
    phi2 = chi2 / n
    v_raw = math.sqrt(phi2 / max(1, min(r - 1, k - 1)))
    phi2c = max(0.0, phi2 - (k - 1) * (r - 1) / (n - 1))
    rc, kc = r - (r - 1) ** 2 / (n - 1), k - (k - 1) ** 2 / (n - 1)
    v_corr = math.sqrt(phi2c / max(1e-12, min(rc - 1, kc - 1)))
    hr, hc = _entropy(row), _entropy(col)
    h_joint = _entropy(ct.ravel())
    mi = hr + hc - h_joint
    return {"cramers_v": v_raw, "v_corrected": v_corr,
            "nmi": mi / max(1e-12, math.sqrt(hr * hc)),
            "u_col_given_row": mi / max(1e-12, hc),
            "u_row_given_col": mi / max(1e-12, hr)}


PAIRS = [("Rejection reason x resolution code", "reason_label", "rc_label"),
         ("Validation rule x resolution code", "rule_label", "rc_label"),
         ("Rejection reason x validation rule", "reason_label", "rule_label")]

# Weights are rescaled to sum to the SAMPLE size before computing the weighted
# association. Using the population total would inflate chi-square by ~4.2x and
# report a precision the 12,000 observations do not support.
tickets["w_scaled"] = tickets["w"] * (N_SAMPLE / tickets["w"].sum())
assoc_rows = []
for name, a, b in PAIRS:
    ct_s = pd.crosstab(tickets[a], tickets[b]).to_numpy(dtype=float)
    ct_w = pd.crosstab(tickets[a], tickets[b], values=tickets["w_scaled"],
                       aggfunc="sum").fillna(0).to_numpy(dtype=float)
    s, w = assoc_from_table(ct_s), assoc_from_table(ct_w)
    assoc_rows.append({"pair": name, "shape": f"{ct_s.shape[0]}x{ct_s.shape[1]}",
                       **{f"sample_{k}": v for k, v in s.items()},
                       **{f"pop_{k}": v for k, v in w.items()}})
assoc = pd.DataFrame(assoc_rows)
print(f"  association: rule x code V = {assoc.loc[1, 'sample_v_corrected']:.3f} sample, "
      f"{assoc.loc[1, 'pop_v_corrected']:.3f} weighted")


# ═══════════════════════════════════════════════════════════ agreement with the workbook
print("Cross-checking the sample column against the deliverable...")
wb_conf = dict(zip(sheets["conformance"]["metric"], sheets["conformance"]["value"]))
checks = [("CONFORMANCE AMONG MAPPABLE (headline)", HEADLINES[0]["sample"]),
          ("conformance strict, all rule-tagged", HEADLINES[1]["sample"]),
          ("conformance loose (primary or also-maps-to)", HEADLINES[2]["sample"]),
          ("no applicable rule", HEADLINES[4]["sample"])]
for key, mine in checks:
    stated = float(str(wb_conf[key]).rstrip("%")) / 100
    assert abs(stated - mine) < 0.0005, f"{key}: deck {mine:.4f} vs workbook {stated:.4f}"
    print(f"  {key:<45} {stated:.1%} == {mine:.1%}")

wb_cov = dict(zip(sheets["coverage"]["metric"], sheets["coverage"]["n"]))
assert int(wb_cov["tickets in the 2026 file"]) == N_TOTAL_FILE
assert int(wb_cov["excluded as unclassifiable"]) == N_EXCLUDED

# The workbook's classifiable count was computed by notebook 08 before the
# 2026-08-07 metadata refresh, which dropped a handful of incident references that
# are still present in the conversations file. Those tickets have no resolution
# code, so they cannot be weighted and are outside this deck's population. Report
# the drift rather than assert equality - but fail if it is ever more than a
# rounding error, because a large gap would mean the two are describing different
# corpora.
WB_CLASSIFIABLE = int(wb_cov["classifiable"])
POP_DRIFT = WB_CLASSIFIABLE - N_POP
if POP_DRIFT:
    print(f"  NOTE: workbook says {WB_CLASSIFIABLE:,} classifiable, this deck uses {N_POP:,} "
          f"({POP_DRIFT:+,})")
    print(f"        The workbook predates the 2026-08-07 metadata refresh. The difference is "
          f"the {N_NO_CODE} ticket(s) that lost their resolution code.")
assert abs(POP_DRIFT) <= max(50, 0.001 * WB_CLASSIFIABLE), (
    f"the workbook and this deck disagree on the population by {POP_DRIFT:,} tickets - too "
    f"large to be a metadata refresh. Re-run notebook 08 sections 15-19 against the current "
    f"metadata before publishing either.")
print("  coverage counts reconcile with the workbook  OK")

wb_rule = sheets["per_rule"].set_index("rule")["n"].to_dict()
for _, r in rule_bd.iterrows():
    key = next((k for k in wb_rule if str(r["label"]).startswith(str(k)[:40])), None)
    if key is not None:
        assert int(wb_rule[key]) == int(r["sample_n"]), f"{r['label']}: {wb_rule[key]} vs {r['sample_n']}"
print("  per-rule sample counts match the workbook  OK")


# ═══════════════════════════════════════════════════════════ exclusion reconciliation
exc_by_code = (excluded.groupby(RC).size().rename("excluded").to_frame()
               .join(pd.Series(N_h, name="classifiable"))
               .fillna(0).astype(int).sort_values("excluded", ascending=False))
exc_by_code["total"] = exc_by_code["excluded"] + exc_by_code["classifiable"]
exc_by_code["pct_excluded"] = exc_by_code["excluded"] / exc_by_code["total"]
exc_reason = excluded["exclusion_reason"].value_counts().to_dict()


# ═══════════════════════════════════════════════════════════ matrix facts
matrix = pd.read_excel(MATRIX_XLSX, sheet_name="Triangulation Matrix", header=3, dtype=str)
matrix = matrix[matrix.iloc[:, 0].notna()]
legend = pd.read_excel(MATRIX_XLSX, sheet_name="Legend & Method", header=None, dtype=str)
caveats = [" ".join(str(v).split()) for v in legend.to_numpy().ravel()
           if isinstance(v, str) and len(" ".join(str(v).split())) > 80]
LEGEND_QUOTE = next((c for c in caveats if "interpretation" in c.lower()), caveats[-1])

unmapped = sheets["unmapped_codes"].copy()
unmapped_pop = unmapped[~unmapped["is_primary"]]["resolution_code"].tolist()
unmapped_n = int(exc_by_code.loc[[c for c in unmapped_pop if c in exc_by_code.index],
                                 "classifiable"].sum())

reason_tax = json.loads(REASON_TAX.read_text(encoding="utf-8"))
n_reason_l1 = len(reason_tax)
n_reason_leaves = sum(len(v.get("children", {})) for v in reason_tax.values())


# ═══════════════════════════════════════════════════════════ charts
print("Rendering charts...")
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                     "axes.edgecolor": GREY, "axes.labelcolor": NAVY,
                     "text.color": NAVY, "xtick.color": GREY, "ytick.color": GREY,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "figure.facecolor": "none", "savefig.facecolor": "none"})
PCT = FuncFormatter(lambda v, _: f"{v:.0%}")


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIGS / f"{name}.png", dpi=200, transparent=True, bbox_inches="tight")
    plt.close(fig)
    print(f"    {name}.png")


def short_rule(s, n=44):
    s = str(s)
    return s if len(s) <= n else s[:n - 1] + "…"


# 1 · coverage funnel
fig, ax = plt.subplots(figsize=(8, 3.4))
vals = [N_TOTAL_FILE, N_POP, N_SAMPLE]
labs = [f"2026 tickets\n{N_TOTAL_FILE:,}", f"Classifiable\n{N_POP:,}",
        f"Classified sample\n{N_SAMPLE:,}"]
ax.barh(range(3), vals, color=[GREY, NAVY, ORANGE], height=0.55)
for i, (v, l) in enumerate(zip(vals, labs)):
    ax.text(v + 900, i, l, va="center", fontsize=10)
ax.set_yticks([]); ax.set_xlim(0, N_TOTAL_FILE * 1.35); ax.invert_yaxis()
ax.set_xlabel("tickets"); ax.set_title("From corpus to classified sample", loc="left",
                                       fontweight="bold")
save(fig, "01_funnel")

# 2 · sample vs population share by stratum
fig, ax = plt.subplots(figsize=(10, 4.6))
y = np.arange(len(strat_table))
ax.barh(y - 0.2, strat_table["pop_share"], 0.4, label="population share", color=NAVY)
ax.barh(y + 0.2, strat_table["smp_share"], 0.4, label="sample share", color=ORANGE)
ax.set_yticks(y); ax.set_yticklabels(strat_table.index, fontsize=8.5)
ax.invert_yaxis(); ax.xaxis.set_major_formatter(PCT); ax.legend(frameon=False)
ax.set_title("The sample is stratified, not proportional", loc="left", fontweight="bold")
save(fig, "02_strata_share")

# 3 · design weight per stratum
fig, ax = plt.subplots(figsize=(10, 4.6))
cols = [ORANGE if w <= 1.001 else NAVY for w in strat_table["weight"]]
ax.barh(range(len(strat_table)), strat_table["weight"], color=cols, height=0.6)
for i, w in enumerate(strat_table["weight"]):
    ax.text(w + 0.06, i, f"{w:.2f}", va="center", fontsize=8.5)
ax.set_yticks(range(len(strat_table))); ax.set_yticklabels(strat_table.index, fontsize=8.5)
ax.invert_yaxis(); ax.set_xlabel("design weight  (population / sample)")
ax.set_title("Each sampled ticket stands for this many tickets\n"
             "orange = sampled in full, weight 1.00, no sampling error",
             loc="left", fontweight="bold")
save(fig, "03_weights")

# 4 · naive error
fig, ax = plt.subplots(figsize=(10, 4.6))
err = strat_table["naive_err"]
ax.barh(range(len(err)), err, color=[RED if e > 0 else NAVY for e in err], height=0.6)
ax.axvline(0, color=GREY, lw=1)
for i, e in enumerate(err):
    ax.text(e + (0.06 if e >= 0 else -0.06), i, f"{e:+.0%}", va="center",
            ha="left" if e >= 0 else "right", fontsize=8.5)
ax.set_yticks(range(len(err))); ax.set_yticklabels(strat_table.index, fontsize=8.5)
ax.invert_yaxis(); ax.xaxis.set_major_formatter(PCT)
ax.set_xlim(err.min() - 0.55, err.max() + 0.55)
ax.set_title("Error if you simply multiplied the sample by 4.227", loc="left",
             fontweight="bold")
save(fig, "04_naive_error")

# 5 · conformance sample vs population
fig, ax = plt.subplots(figsize=(9.5, 4.2))
h = [r for r in HEADLINES if "Conformance" in r["metric"] or "applicable" in r["metric"]]
y = np.arange(len(h))
ax.barh(y - 0.2, [r["sample"] for r in h], 0.4, label=f"sample (n={N_SAMPLE:,})", color=GREY)
ax.barh(y + 0.2, [r["population"] for r in h], 0.4,
        xerr=[r["ci"] for r in h], error_kw={"ecolor": NAVY, "capsize": 3, "lw": 1},
        label=f"population estimate (N={N_POP:,})", color=ORANGE)
for i, r in enumerate(h):
    ax.text(r["population"] + r["ci"] + 0.015, i + 0.2, f"{r['population']:.1%}",
            va="center", fontsize=9, fontweight="bold")
ax.set_yticks(y); ax.set_yticklabels([short_rule(r["metric"], 40) for r in h], fontsize=9)
ax.invert_yaxis(); ax.set_xlim(0, 1.0); ax.xaxis.set_major_formatter(PCT)
ax.legend(frameon=False, loc="lower right")
ax.set_title("Headline rates: sample vs population estimate", loc="left", fontweight="bold")
save(fig, "05_conformance")


def paired_volume_chart(bd, title, fname, top=10):
    d = bd.head(top).iloc[::-1]
    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    y = np.arange(len(d))
    ax.barh(y - 0.2, d["sample_pct"], 0.4, label="sample share", color=GREY)
    ax.barh(y + 0.2, d["pop_pct"], 0.4, label="population share (weighted)", color=ORANGE)
    for i, (_, r) in enumerate(d.iterrows()):
        ax.text(r["pop_pct"] + 0.004, i + 0.2, f"{r['pop_est']:,.0f}", va="center",
                fontsize=8.5, fontweight="bold")
    ax.set_yticks(y); ax.set_yticklabels([short_rule(v, 46) for v in d["label"]], fontsize=8.5)
    ax.xaxis.set_major_formatter(PCT); ax.legend(frameon=False, loc="lower right")
    ax.set_xlim(0, max(d["pop_pct"].max(), d["sample_pct"].max()) * 1.28)
    ax.set_title(title, loc="left", fontweight="bold")
    save(fig, fname)


paired_volume_chart(rule_bd, "Validation rules: sample share vs estimated population share\n"
                    "labels are estimated ticket counts across 50,721", "06_rule_volumes")
paired_volume_chart(reason_bd, "Rejection reasons: sample share vs estimated population share\n"
                    "labels are estimated ticket counts across 50,721", "07_reason_volumes")


def heatmap(index_col, col_col, title, fname, top_rows=12, top_cols=12):
    ct = pd.crosstab(tickets[index_col], tickets[col_col], values=tickets["w"], aggfunc="sum")
    ct = ct.fillna(0)
    ct = ct.loc[ct.sum(1).sort_values(ascending=False).index[:top_rows],
                ct.sum(0).sort_values(ascending=False).index[:top_cols]]
    norm = ct.div(ct.sum(1), axis=0)
    fig, ax = plt.subplots(figsize=(11.5, 5.6))
    im = ax.imshow(norm.to_numpy(), cmap="YlOrBr", aspect="auto", vmin=0, vmax=1)
    ax.set_xticks(range(norm.shape[1]))
    ax.set_xticklabels([short_rule(c, 26) for c in norm.columns], rotation=40,
                       ha="right", fontsize=8)
    ax.set_yticks(range(norm.shape[0]))
    ax.set_yticklabels([short_rule(r, 40) for r in norm.index], fontsize=8)
    for i in range(norm.shape[0]):
        for j in range(norm.shape[1]):
            v = norm.iat[i, j]
            if v >= 0.04:
                ax.text(j, i, f"{v:.0%}", ha="center", va="center", fontsize=7,
                        color="white" if v > 0.55 else NAVY)
    fig.colorbar(im, ax=ax, shrink=0.7, format=PCT, label="row share")
    ax.set_title(title, loc="left", fontweight="bold")
    save(fig, fname)


heatmap("rule_label", "rc_label",
        "Validation rule x resolution code, weighted to the population (row-normalised)",
        "08_rule_x_code")
heatmap("reason_label", "rule_label",
        "Rejection reason x validation rule, weighted to the population (row-normalised)",
        "09_reason_x_rule")
# The third face of the same cube. Rule x code and reason x rule were charted; the
# reason x code pairing was computed into the workbook but never drawn, and it is
# the one that needs no classifier on the column axis at all.
heatmap("reason_label", "rc_label",
        "Rejection reason x resolution code, weighted to the population (row-normalised)",
        "19_reason_x_code")

# 10 · per-rule conformance
pr = sheets["per_rule"]
pr = pr[(pr["estimable"]) & (pr["code"] != "CSDVR4.1")].sort_values("n", ascending=True)
fig, ax = plt.subplots(figsize=(10.5, 5.4))
y = np.arange(len(pr))
ax.barh(y, pr["loose"], 0.62, color="#F5C99B", label="loose (primary or also-maps-to)")
ax.barh(y, pr["strict"], 0.62, color=ORANGE, label="strict (primary only)")
ax.set_yticks(y); ax.set_yticklabels([f"{c}  {short_rule(r, 34)}"
                                      for c, r in zip(pr["code"], pr["rule"])], fontsize=8)
for i, (_, r) in enumerate(pr.iterrows()):
    ax.text(1.01, i, f"n={int(r['n']):,}", va="center", fontsize=7.5, color=GREY)
ax.set_xlim(0, 1.0); ax.xaxis.set_major_formatter(PCT); ax.legend(frameon=False, loc="lower right")
ax.set_title("Conformance by validation rule (sample)\n"
             "rule 08 is the gap: 2% strict, 85% loose", loc="left", fontweight="bold")
save(fig, "10_per_rule")

# 11 · unmapped codes.  Counts are the CLASSIFIABLE population (50,721), not the
# full metadata, so the chart and the surrounding slide text agree.
u = unmapped.copy()
u["n"] = u["resolution_code"].map(N_h).fillna(0).astype(int)
u = u.sort_values("n", ascending=True)
fig, ax = plt.subplots(figsize=(9.5, 4.6))
cols = [RED if not p else NAVY for p in u["is_primary"]]
ax.barh(range(len(u)), u["n"], color=cols, height=0.62)
ax.set_yticks(range(len(u))); ax.set_yticklabels(u["resolution_code"], fontsize=8.5)
for i, (_, r) in enumerate(u.iterrows()):
    if not r["is_primary"]:
        ax.text(r["n"] + 120, i, "no rule claims this", va="center", fontsize=8, color=RED)
ax.set_xlabel("classifiable 2026 tickets")
ax.set_title("Three resolution codes no validation rule claims as primary", loc="left",
             fontweight="bold")
save(fig, "11_unmapped")

# 12 · association
fig, ax = plt.subplots(figsize=(9.5, 3.8))
y = np.arange(len(assoc))
ax.barh(y - 0.2, assoc["sample_v_corrected"], 0.4, label="sample", color=GREY)
ax.barh(y + 0.2, assoc["pop_v_corrected"], 0.4, label="weighted to population", color=ORANGE)
for i, r in assoc.iterrows():
    ax.text(r["pop_v_corrected"] + 0.01, i + 0.2, f"{r['pop_v_corrected']:.2f}",
            va="center", fontsize=9, fontweight="bold")
ax.set_yticks(y); ax.set_yticklabels([short_rule(p, 38) for p in assoc["pair"]], fontsize=9)
ax.invert_yaxis(); ax.set_xlim(0, 0.8); ax.legend(frameon=False, loc="lower right")
ax.set_xlabel("Cramer's V, bias-corrected")
ax.set_title("How strongly the three axes are related", loc="left", fontweight="bold")
save(fig, "12_association")


# ═══════════════════════════════════════════════════════════ customer effort
# Everything below is gated: without the effort run the deck builds unchanged.
EFFORT_XLSX = BASE / "runs" / "output" / "csd_2026_effort_triangulation.xlsx"
effort_payload = None

if EFFORT_XLSX.exists():
    print("Loading customer effort...")
    ef = {name: pd.read_excel(EFFORT_XLSX, sheet_name=name)
          for name in ("tickets", "by_rejection_reason", "by_validation_rule",
                       "by_resolution_code", "conformance_x_effort", "friction_points",
                       "effort_themes", "judged_vs_observed", "method")}
    for _opt in ("survey_validation", "survey_by_reason", "reliability"):
        try:
            ef[_opt] = pd.read_excel(EFFORT_XLSX, sheet_name=_opt)
        except ValueError:
            ef[_opt] = None
    ef["survey_validation"] = ef.pop("survey_validation", None)
    ef["survey_by_reason"] = ef.pop("survey_by_reason", None)
    ef["reliability"] = ef.pop("reliability", None)
    et = ef["tickets"]
    EFFORT_ORDER = ["very_low", "low", "medium", "high", "very_high"]

    # The effort run scored exactly the tickets the rules and reasons cover, so the
    # weights are the same ones - recomputed here rather than trusted from the file.
    et["w_check"] = et["rc_label"].map(N_h) / et["rc_label"].map(et["rc_label"].value_counts())
    assert abs(et["w_check"].sum() - N_POP) < 1e-6, (
        f"effort weights sum to {et['w_check'].sum():,.2f}, expected {N_POP:,} - the effort run "
        f"and the rule run do not cover the same tickets")
    print(f"  {len(et):,} tickets, weights reconcile to {N_POP:,}")

    # -- distribution, sample vs population --------------------------------
    dist = []
    for lev in EFFORT_ORDER:
        m = et["effort_score"] == lev
        dist.append({"level": lev, "sample_n": int(m.sum()),
                     "sample_pct": float(m.mean()),
                     "pop_est": float(et.loc[m, "w_check"].sum()),
                     "pop_pct": float(et.loc[m, "w_check"].sum() / N_POP)})
    effort_dist = pd.DataFrame(dist)
    assert abs(effort_dist["pop_est"].sum() - N_POP) < 1.0, "effort levels do not reconcile"

    et["_high"] = et["effort_score"].isin(["high", "very_high"])
    high_sample = float(et["_high"].mean())
    high_pop = float((et["_high"] * et["w_check"]).sum() / N_POP)
    rho_row = ef["method"].loc[ef["method"]["item"] == "Spearman judged vs observed", "value"]
    print(f"  effort_high: sample {high_sample:.1%}, population {high_pop:.1%}")

    # -- charts ------------------------------------------------------------
    # 13 - distribution
    fig, ax = plt.subplots(figsize=(9.5, 3.8))
    y = np.arange(len(effort_dist))
    ax.barh(y - 0.2, effort_dist["sample_pct"], 0.4, label="sample", color=GREY)
    ax.barh(y + 0.2, effort_dist["pop_pct"], 0.4, label="population (weighted)", color=ORANGE)
    for i, r in effort_dist.iterrows():
        ax.text(r["pop_pct"] + 0.006, i + 0.2, f"{r['pop_est']:,.0f}", va="center",
                fontsize=9, fontweight="bold")
    ax.set_yticks(y); ax.set_yticklabels(effort_dist["level"], fontsize=10)
    ax.invert_yaxis(); ax.xaxis.set_major_formatter(PCT); ax.legend(frameon=False)
    ax.set_xlim(0, max(effort_dist["pop_pct"].max(), effort_dist["sample_pct"].max()) * 1.3)
    ax.set_title("Judged customer effort: sample vs population estimate", loc="left",
                 fontweight="bold")
    save(fig, "13_effort_distribution")

    # 14 - effort by rejection reason
    br = ef["by_rejection_reason"]
    br = br[br["estimable"]].nlargest(10, "est_population").iloc[::-1]
    fig, ax = plt.subplots(figsize=(10.5, 5.0))
    y = np.arange(len(br))
    ax.barh(y, br["pct_high"], 0.62, color=ORANGE)
    for i, (_, r) in enumerate(br.iterrows()):
        ax.text(r["pct_high"] + 0.006, i, f"{r['pct_high']:.0%}   ({r['est_population']:,.0f}/yr)",
                va="center", fontsize=8.5)
    ax.axvline(high_pop, color=NAVY, lw=1.2, ls="--")
    ax.text(high_pop, len(br) - 0.3, f"  overall {high_pop:.0%}", color=NAVY, fontsize=9,
            va="top")
    ax.set_yticks(y); ax.set_yticklabels([short_rule(v, 44) for v in br["reason_label"]],
                                         fontsize=8.5)
    ax.set_xlim(0, br["pct_high"].max() * 1.45); ax.xaxis.set_major_formatter(PCT)
    ax.set_title("Share judged high-effort, by rejection reason", loc="left", fontweight="bold")
    save(fig, "14_effort_by_reason")

    # 15 - friction points
    fr = ef["friction_points"].sort_values("est_population").tail(9)
    fig, ax = plt.subplots(figsize=(10, 4.6))
    cols = [ORANGE if "Redirected" in str(l) else NAVY for l in fr["friction_point"]]
    ax.barh(range(len(fr)), fr["est_population"], color=cols, height=0.62)
    for i, (_, r) in enumerate(fr.iterrows()):
        ax.text(r["est_population"] * 1.01, i, f"{r['est_population']:,.0f}  "
                f"({r['pct_high_when_present']:.0%} high-effort)", va="center", fontsize=8.5)
    ax.set_yticks(range(len(fr)))
    ax.set_yticklabels([short_rule(v, 34) for v in fr["friction_point"]], fontsize=8.5)
    ax.set_xlim(0, fr["est_population"].max() * 1.5)
    ax.set_xlabel("estimated tickets per year")
    ax.set_title("Friction points, estimated annual volume\n"
                 "orange = the category added for this corpus", loc="left", fontweight="bold")
    save(fig, "15_friction_points")

    # 16 - judged vs observed
    jv = ef["judged_vs_observed"]
    fig, ax = plt.subplots(figsize=(9.5, 4.2))
    ax.plot(jv["obs_decile"], jv["pct_high_judged"], marker="o", color=ORANGE, lw=2.2,
            label="judged high-effort")
    ax.set_xticks(jv["obs_decile"])
    ax.yaxis.set_major_formatter(PCT)
    ax.set_xlabel("observed-effort decile  (1 = lightest interaction, 10 = heaviest)")
    ax.set_ylabel("share judged high-effort")
    ax.axhline(high_pop, color=GREY, lw=1, ls="--")
    ax.text(1, high_pop, f" overall {high_pop:.0%}", color=GREY, fontsize=9, va="bottom")
    ax.set_title("The model's judgement tracks the shape of the interaction", loc="left",
                 fontweight="bold")
    save(fig, "16_judged_vs_observed")

    # 17 - effort vs conformance
    ce = ef["conformance_x_effort"]
    fig, ax = plt.subplots(figsize=(9.8, 3.9))
    y = np.arange(len(ce))
    base = float(ce.loc[ce["segment"].str.startswith("Rule matches"), "pct_high"].iloc[0])
    cols = [GREY if str(sg).startswith("Rule matches") else ORANGE for sg in ce["segment"]]
    ax.barh(y, ce["pct_high"], 0.6, color=cols)
    for i, (_, r) in enumerate(ce.iterrows()):
        d = (r["pct_high"] - base) * 100          # fraction -> percentage points
        tag = "baseline" if abs(d) < 1e-9 else f"{d:+.1f}pp"
        ax.text(r["pct_high"] + 0.006, i, f"{r['pct_high']:.0%}   {tag}   "
                f"({r['est_population']:,.0f}/yr)", va="center", fontsize=8.5)
    ax.set_yticks(y); ax.set_yticklabels([short_rule(v, 32) for v in ce["segment"]], fontsize=9)
    ax.invert_yaxis(); ax.set_xlim(0, ce["pct_high"].max() * 1.6)
    ax.xaxis.set_major_formatter(PCT)
    ax.set_title("Does the matrix failing the ticket cost the customer effort?", loc="left",
                 fontweight="bold")
    save(fig, "17_effort_vs_conformance")

    # -- survey validation: the only measure here from a customer ----------
    surv = ef.get("survey_validation")
    surv_by_reason = ef.get("survey_by_reason")
    if surv is not None and len(surv):
        sv = surv.sort_values("spearman")
        fig, ax = plt.subplots(figsize=(9.8, 4.4))
        y = np.arange(len(sv))
        cols = [ORANGE if str(l).startswith("LLM") else NAVY for l in sv["signal"]]
        ax.barh(y, sv["spearman"], 0.6, color=cols,
                xerr=[sv["spearman"] - sv["ci_lo"], sv["ci_hi"] - sv["spearman"]],
                error_kw={"ecolor": GREY, "capsize": 3, "lw": 1})
        ax.axvline(0, color=GREY, lw=1)
        for i, (_, r) in enumerate(sv.iterrows()):
            ax.text(r["ci_hi"] + 0.006, i, f"{r['spearman']:+.3f}", va="center", fontsize=9,
                    fontweight="bold" if str(r["signal"]).startswith("LLM") else "normal")
        ax.set_yticks(y); ax.set_yticklabels([short_rule(v, 30) for v in sv["signal"]],
                                             fontsize=9)
        ax.set_xlim(min(-0.10, sv["ci_lo"].min() - 0.02), sv["ci_hi"].max() + 0.06)
        ax.set_xlabel("Spearman correlation with the customer's own effort answer")
        ax.set_title("What actually predicts how hard the customer found it\n"
                     "orange = the model reading the transcript; navy = the handling record",
                     loc="left", fontweight="bold")
        save(fig, "18_survey_agreement")

    lvl = ef["tickets"]
    if "survey_levels" in ef:
        pass
    effort_payload_survey = {
        "validation": recs(surv) if surv is not None else None,
        "by_reason": recs(surv_by_reason) if surv_by_reason is not None else None,
        "reliability": recs(ef["reliability"]) if ef.get("reliability") is not None else None,
    }

    effort_payload = {
        "survey": effort_payload_survey,
        "distribution": recs(effort_dist),
        "high_sample": high_sample, "high_pop": high_pop,
        "spearman": str(rho_row.iloc[0]) if len(rho_row) else "",
        "by_reason": recs(ef["by_rejection_reason"]),
        "by_rule": recs(ef["by_validation_rule"]),
        "by_code": recs(ef["by_resolution_code"]),
        "conformance": recs(ef["conformance_x_effort"]),
        "friction": recs(ef["friction_points"]),
        "themes": recs(ef["effort_themes"]),
        "deciles": recs(ef["judged_vs_observed"]),
        "method": recs(ef["method"]),
        "obs_medians": {
            "turns": float(et["obs_turns"].median()),
            "span_h": float(et["obs_span_h"].median()),
            "handoffs": float(et["obs_agent_handoffs"].mean()),
            "repeat_pct": float(et["obs_repeat_contact"].mean()),
        },
    }
else:
    print(f"No effort data at {EFFORT_XLSX.name} - the deck will build without Part F.")


# ═══════════════════════════════════════════════════════════ emit
# ═══════════════════════════════════ deep dive · Invalid- discontinued title
# Finding 1 names three unmapped codes; this is the largest of them that is not
# simply an enquiry, and the one a matrix change could fix outright.
DT = "Invalid- discontinued title"
_dt = tickets[tickets["rc_label"] == DT]
_dtw = float(_dt["w"].sum())


def _share(col):
    s = _dt.groupby(col)["w"].sum().sort_values(ascending=False) / _dtw
    return [{"label": k, "share": float(v)} for k, v in s.head(5).items()]


dt_detail = {
    "code": DT,
    "sample_n": int(len(_dt)),
    "est_pop": round(_dtw),
    "est_pop_annualised": round(_dtw * 12 / 7),
    "pct_of_population": _dtw / N_POP,
    "conf_strict": float(_dt["conf_strict"].mean()),
    "conf_loose": float(_dt["conf_loose"].mean()),
    "pct_mappable": float(_dt["is_mappable"].mean()),
    "top_rules": _share("rule_label"),
    "top_reasons": _share("reason_label"),
    "vol_2025": 7455,          # resolution codes osvc-Copy.xlsx, Sheet1
    "total_2026_jan_jul": 4051,
}
dt_detail["yoy_pct"] = (dt_detail["total_2026_jan_jul"] * 12 / 7) / 7455 - 1

payload = {
    "discontinued_title": dt_detail,
    "meta": {
        "n_total_file": N_TOTAL_FILE, "n_excluded": N_EXCLUDED, "n_population": N_POP,
        "n_sample": N_SAMPLE, "naive_factor": NAIVE_FACTOR,
        "census_strata": CENSUS_STRATA,
        "n_reason_l1": n_reason_l1, "n_reason_leaves": n_reason_leaves,
        "n_rules": int(len(matrix)),
        "legend_quote": LEGEND_QUOTE,
        "matrix_code_coverage": float(str(dict(zip(sheets["conformance"]["metric"],
                                                   sheets["conformance"]["value"]))
                                          ["matrix code coverage"]).rstrip("%")) / 100,
        "unmapped_codes": unmapped_pop,
        "unmapped_n_classifiable": unmapped_n,
        "exclusion_reasons": exc_reason,
        "n_invalid_code": N_INVALID_CODE, "invalid_codes": INVALID_CODES,
        "n_no_code": N_NO_CODE, "pop_drift_vs_workbook": POP_DRIFT,
        "invalid_code_label": INVALID_CODE_LABEL,
        "pop_by_code": {k: int(v) for k, v in N_h.items()},
        "cost_usd_total": 242.52, "cost_main_run_usd": 164.33,
    },
    "headlines": HEADLINES,
    "strata": recs(strat_table.reset_index().rename(columns={"index": "resolution_code"})),
    "rule_breakdown": recs(rule_bd),
    "reason_breakdown": recs(reason_bd),
    "code_breakdown": recs(code_bd),
    "association": recs(assoc),
    "per_rule": recs(sheets["per_rule"]),
    "per_code": recs(sheets["per_code"]),
    "reason_summary": recs(sheets["reason_summary"]),
    "proposed_rules": recs(sheets["proposed_rules"]),
    "phrase_audit": recs(sheets["phrase_audit"]),
    "unmapped": recs(unmapped),
    "exclusion_by_code": recs(exc_by_code.reset_index()),
    "three_way_top": recs(three_way_w.head(12)),
    "n_three_way_cells": int(len(three_way_w)),
    "reason_taxonomy": [{"l1": v["label"],
                         "leaves": [c["label"] for c in v.get("children", {}).values()]}
                        for v in reason_tax.values()],
    "sources": SOURCES,
    "effort": effort_payload,
}

(OUT / "deck_data.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                                    encoding="utf-8")
print(f"\nWrote {(OUT / 'deck_data.json').relative_to(BASE)} "
      f"({(OUT / 'deck_data.json').stat().st_size / 1024:.0f} KB)")
print(f"Wrote {len(list(FIGS.glob('*.png')))} charts to {FIGS.relative_to(BASE)}")
print("\nAll assertions passed. Next:")
print(r'    & "C:\Program Files\Python311\python.exe" scripts\build_deck.py')
