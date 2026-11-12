"""Per-validation-rule scorecard for the 2026 Scopus CSD corpus.

Joins five existing artefacts onto one row per validation rule:

    rule volume (design-weighted)  x  conformance  x  CSAT  x  survey effort
    x  LLM-judged effort  x  turnaround time

and computes how many validation rules attach to each resolution code and to
each rejection reason - structurally (what the matrix designs) and observed
(what the tagged tickets actually show).

No LLM calls. Everything here is aggregation over files already on disk.

Three properties of the source data drive most of the awkwardness below and are
recorded in the data_dictionary sheet so the workbook stands on its own:

  1. The corpus is SEVEN MONTHS (close date 2026-01-01 .. 2026-07-31), not a
     year. Volumes are reported on the observed basis and annualised x12/7.
  2. CSAT_ANSWER_CODE is an INVERTED 1-7 scale (1 = extremely satisfied) while
     CSAT_EFFORT_CODE is a 1-5 scale where higher = harder. They run in
     opposite directions.
  3. The 2025 volume is a RESOLUTION-CODE figure, not a rule figure. Rules
     sharing a primary code carry the same number and the column cannot be
     summed.

Writes runs/output/csd_2026_rule_scorecard.xlsx (5 sheets).
"""
from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
TRIANG = BASE / "runs" / "output" / "csd_2026_effort_triangulation.xlsx"
RULES_XLSX = BASE / "runs" / "output" / "csd_2026_validation_rules.xlsx"
META_TSV = BASE / "data" / "scopus content" / "scopus content_2026_metadata.tsv"
MATRIX_XLSX = (BASE / "data" / "scopus content" /
               "Triangulation - Validation Rules vs Resolution Codes vs Templates.xlsx")
OSVC_XLSX = BASE / "data" / "scopus content" / "resolution codes osvc-Copy.xlsx"
OUT = BASE / "runs" / "output" / "csd_2026_rule_scorecard.xlsx"

MONTHS_OBSERVED = 7
ANNUALISE = 12 / MONTHS_OBSERVED
MIN_SURVEY_N = 30          # below this, survey-derived cells are suppressed
NA_LEAF = "No applicable validation rule"
INVALID_CODE_LABEL = "(invalid code returned by the model)"

_NA_TOKENS = {"", "na", "n/a", "[na]", "-", "none", "nan", "[n/a]"}


# ───────────────────────────────────────────────────── resolution-code normalisers
# Copied from notebook 08 code cell 4. The matrix and the metadata spell the
# codes inconsistently ("Invalid - X" / "Invalid-X" / trailing ";"), and the
# Also Maps To cells contain a literal "NA\n" that a naive split turns into a
# phantom code.
def norm_res_code(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    s = str(value).strip().rstrip(";").strip()
    s = re.sub(r"^invalid\s*-\s*", "invalid-", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).casefold()
    return "" if s in _NA_TOKENS else s


def split_res_codes(value) -> list[str]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return []
    out = []
    for part in re.split(r"[;\n]+", str(value)):
        c = norm_res_code(part)
        if c:
            out.append(c)
    return out


def rule_no(label: str):
    """Leading matrix rule number from a taxonomy leaf label, else None."""
    m = re.match(r"^(\d+)\s", str(label))
    return int(m.group(1)) if m else None


print("=" * 78)
print("PER-RULE SCORECARD")
print("=" * 78)

# ═══════════════════════════════════════════════════════════════ 1 · base frame
tickets = pd.read_excel(TRIANG, sheet_name="tickets")
N_SAMPLE = len(tickets)
tickets["ref"] = tickets["INCIDENT_REF"].astype(str).str.strip()
tickets["rule_label"] = tickets["rule_label"].fillna(INVALID_CODE_LABEL)
tickets["reason_label"] = tickets["reason_label"].fillna(INVALID_CODE_LABEL)

# strat_prop needs the stratum sizes; the triangulation sheet carries only w.
n_h = tickets["rc_label"].value_counts()
tickets["n_h"] = tickets["rc_label"].map(n_h).astype(float)
tickets["N_h"] = (tickets["w"] * tickets["n_h"]).round()
N_POP = int(round(tickets["w"].sum()))
print(f"  sample {N_SAMPLE:,}   design weights sum to {N_POP:,}")
assert abs(tickets["w"].sum() - N_POP) < 1.0, "weights do not sum to an integer population"


def strat_prop(mask_col: str, subset: pd.Series | None = None) -> tuple[float, float, int]:
    """p_hat = sum_h W_h p_h ; Var = sum_h W_h^2 p_h(1-p_h)/n_h (1 - n_h/N_h).

    Copied from scripts/build_deck_data.py:149 rather than imported - that
    module closes over globals and importing it re-runs the whole deck build.
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
    est = float(tickets.loc[subset, "w"].sum())
    tickets["_member"] = subset.astype(float)
    _, half_pp, _ = strat_prop("_member")
    tickets.drop(columns="_member", inplace=True)
    return est, half_pp * N_POP


# ═══════════════════════════════════════════════════ 2 · CSAT / survey / TAT join
meta = pd.read_csv(
    META_TSV, sep="\t", dtype=str,
    usecols=["incident_reference", "incident_closed_datetime", "CSAT_ANSWER_CODE",
             "CSAT_EFFORT_CODE", "created_to_closed_days",
             "created_to_initial_response_days", "resolution_code_lvl1_desc"])
meta = meta.rename(columns={"resolution_code_lvl1_desc": "_rc"})
meta["ref"] = meta["incident_reference"].astype(str).str.strip()

# The seven-month basis is asserted, not assumed - every annualised figure in
# this workbook depends on it.
_closed = pd.to_datetime(meta["incident_closed_datetime"], errors="coerce")
span_months = _closed.dt.to_period("M").nunique()
assert span_months == MONTHS_OBSERVED, (
    f"corpus spans {span_months} months, not {MONTHS_OBSERVED}; the annualisation "
    f"factor in this script is wrong")
print(f"  corpus close dates {_closed.min():%Y-%m-%d} .. {_closed.max():%Y-%m-%d} "
      f"({span_months} months, annualise x{ANNUALISE:.3f})")

# CSAT_ANSWER_CODE: 1..7 usable, 1 = extremely satisfied (INVERTED).
# CSAT_EFFORT_CODE: 1..5 usable, 5 = strongly disagree it was easy (HARDEST).
# 0 = "No Value", 6 = "Do Not Know / N/A", 8 = "Do not know" - all non-responses.
meta["sat"] = pd.to_numeric(meta["CSAT_ANSWER_CODE"], errors="coerce")
meta.loc[~meta["sat"].between(1, 7), "sat"] = np.nan
meta["eff_survey"] = pd.to_numeric(meta["CSAT_EFFORT_CODE"], errors="coerce")
meta.loc[~meta["eff_survey"].between(1, 5), "eff_survey"] = np.nan
meta["tat_days"] = pd.to_numeric(meta["created_to_closed_days"], errors="coerce")
meta["frt_days"] = pd.to_numeric(meta["created_to_initial_response_days"], errors="coerce")

# The year-on-year comparison must be like for like. The 2025 figure counts every
# Invalid- incident; the classifiable population (N_POP) excludes the 6,214 with
# no usable transcript, so comparing against it understates 2026 by ~11%. The
# metadata file is itself pre-filtered to the 15 Invalid- codes, so its row count
# is the right 2026 counterpart.
N_INVALID_FILE = len(meta)

t = tickets.merge(meta[["ref", "sat", "eff_survey", "tat_days", "frt_days"]],
                  on="ref", how="left")
assert len(t) == N_SAMPLE, "the metadata join duplicated rows"
tickets = t

N_CSAT = int(tickets["sat"].notna().sum())
N_SURVEY = int(tickets["eff_survey"].notna().sum())
print(f"  CSAT answers {N_CSAT}   survey-effort answers {N_SURVEY}")
assert N_CSAT == 641, f"expected 641 CSAT answers on the sample, got {N_CSAT}"
assert N_SURVEY == 625, f"expected 625 survey-effort answers on the sample, got {N_SURVEY}"

tickets["sat_good"] = tickets["sat"].where(tickets["sat"].isna(), tickets["sat"] <= 3)
tickets["survey_hard"] = tickets["eff_survey"].where(
    tickets["eff_survey"].isna(), tickets["eff_survey"] >= 4)
# Codes 3-5: the customer did not agree it was easy. Reported alongside 4-5
# because 4-5 is only 7.9% of answers against the LLM's 27.3% high-effort rate,
# and no survey threshold matches that base rate - 3-5 gives 13.3%, 2-5 gives
# 47.6%. The two measures can be compared on ranking, never on level.
tickets["survey_not_easy"] = tickets["eff_survey"].where(
    tickets["eff_survey"].isna(), tickets["eff_survey"] >= 3)

# ═══════════════════════════════════════════════════════════ 3 · matrix metadata
mx = pd.read_excel(MATRIX_XLSX, sheet_name="Triangulation Matrix", header=3, dtype=str)
mx = mx.dropna(subset=[mx.columns[0]])
mx = mx[mx[mx.columns[0]].astype(str).str.strip().str.match(r"^\d+$")]
C = list(mx.columns)
RULES = {}
for _, r in mx.iterrows():
    n = int(str(r[C[0]]).strip())
    RULES[n] = {
        "request_type": str(r[C[1]]).strip(),
        "guideline": str(r[C[3]]).strip(),
        "primary": norm_res_code(r[C[4]]),
        "primary_raw": str(r[C[4]]).strip().rstrip(";").strip(),
        "also": split_res_codes(r[C[5]]),
    }
assert sorted(RULES) == list(range(1, 25)), f"expected rules 1..24, got {sorted(RULES)}"
print(f"  matrix parsed: {len(RULES)} rules")

PRIM_COUNT = Counter(v["primary"] for v in RULES.values())
ALSO_COUNT = Counter(c for v in RULES.values() for c in v["also"])
STRUCTURAL_MEAN = len(RULES) / len(PRIM_COUNT)
print(f"  {len(RULES)} rules over {len(PRIM_COUNT)} distinct primary codes "
      f"-> structural mean {STRUCTURAL_MEAN:.2f} rules per claimed code")

# ═══════════════════════════════════════════════════════════ 4 · year volumes
osvc = pd.read_excel(OSVC_XLSX, sheet_name="Sheet1", header=1)
osvc = osvc.dropna(subset=[osvc.columns[1]])
osvc["code_n"] = osvc[osvc.columns[1]].map(norm_res_code)
osvc = osvc[osvc["code_n"].str.startswith("invalid")]
VOL25 = dict(zip(osvc["code_n"], osvc[2025].astype(float)))
VOL26_PARTIAL = dict(zip(osvc["code_n"], osvc[2026].astype(float)))
TOT25 = int(sum(VOL25.values()))
TOT26_PARTIAL = int(sum(VOL26_PARTIAL.values()))
print(f"  osvc volumes: 2025 full year {TOT25:,}   2026 partial {TOT26_PARTIAL:,}")

# ═══════════════════════════════════════════════════════════ 5 · conformance
per_rule_src = pd.read_excel(RULES_XLSX, sheet_name="per_rule")
CONF = {}
for _, r in per_rule_src.iterrows():
    key = rule_no(r["rule"]) or str(r["rule"]).strip()
    CONF[key] = {
        "csdvr_code": r["code"],
        "expected": r["expected"],
        "modal_actual": r["modal_actual"],
        "modal_share": float(r["modal_share"]),
        "strict": float(r["strict"]),
        "loose": float(r["loose"]),
    }


# ═══════════════════════════════════════════════════════════ 6 · per-rule sheet
def wmode(g: pd.DataFrame, col: str) -> str:
    s = g.groupby(col)["w"].sum()
    return "" if s.empty else str(s.idxmax())


def top_friction(g: pd.DataFrame) -> str:
    cols = [c for c in g.columns if c.startswith("friction_points_")]
    tally: dict[str, float] = {}
    for c in cols:
        sub = g[[c, "w"]].dropna(subset=[c])
        for k, v in sub.groupby(c)["w"].sum().items():
            k = str(k).strip()
            if k:
                tally[k] = tally.get(k, 0.0) + float(v)
    return max(tally, key=tally.get) if tally else ""


def wmean(g: pd.DataFrame, col: str) -> float:
    """Design-weighted mean over the rows where col is present.

    Everything else in this analysis is design-weighted; an unweighted rule mean
    would silently over-represent the deliberately over-sampled rare codes.
    """
    v = pd.to_numeric(g[col], errors="coerce")
    m = v.notna()
    if not m.any():
        return float("nan")
    w = g.loc[m, "w"]
    return float((v[m] * w).sum() / w.sum())


def suppressed(g: pd.DataFrame, col: str, n: int) -> float:
    """Design-weighted survey statistic, or NaN when the base is too thin to quote.

    Weighting corrects the stratified sample design. It does NOT correct the
    self-selection of who chooses to answer a survey - that is unfixable here and
    is recorded in the data dictionary instead."""
    return wmean(g, col) if n >= MIN_SURVEY_N else float("nan")


rows = []
for label, g in tickets.groupby("rule_label"):
    no = rule_no(label)
    meta_r = RULES.get(no, {})
    conf = CONF.get(no if no else label, {})
    subset = tickets["rule_label"] == label
    vol, ci = strat_volume(subset)

    n_sat = int(g["sat"].notna().sum())
    n_srv = int(g["eff_survey"].notna().sum())
    prim = meta_r.get("primary", "")

    rows.append({
        "rule_no": no,
        "csdvr_code": conf.get("csdvr_code", ""),
        "rule_label": label,
        "request_type": meta_r.get("request_type", ""),
        "guideline_ref": meta_r.get("guideline", ""),

        "sample_n": len(g),
        "est_vol_jan_jul": round(vol),
        "ci95": round(ci),
        "est_vol_annualised": round(vol * ANNUALISE),
        "pct_of_population": vol / N_POP,

        "primary_code": meta_r.get("primary_raw", ""),
        "code_vol_2025": VOL25.get(prim, np.nan),
        "code_vol_2026_partial": VOL26_PARTIAL.get(prim, np.nan),

        "expected_primary": conf.get("expected", ""),
        "modal_actual": conf.get("modal_actual", ""),
        "modal_share": conf.get("modal_share", np.nan),
        "conf_strict": conf.get("strict", np.nan),
        "conf_loose": conf.get("loose", np.nan),
        "pct_mappable": wmean(g, "is_mappable"),

        "csat_n": n_sat,
        "csat_mean_1_7": suppressed(g, "sat", n_sat),
        "pct_satisfied": suppressed(g, "sat_good", n_sat),

        "survey_n": n_srv,
        "survey_effort_mean_1_5": suppressed(g, "eff_survey", n_srv),
        "pct_not_easy": suppressed(g, "survey_not_easy", n_srv),
        "pct_hard": suppressed(g, "survey_hard", n_srv),

        "llm_effort_mean_1_5": wmean(g, "effort_score_num"),
        "pct_high_effort": wmean(g, "effort_high"),
        "llm_vs_survey_delta": (wmean(g, "effort_score_num")
                                - suppressed(g, "eff_survey", n_srv)),

        "tat_median_days": float(g["tat_days"].median()),
        "tat_p90_days": float(g["tat_days"].quantile(0.90)),
        "first_response_median_h": float(g["obs_first_response_h"].median()),
        "span_median_h": float(g["obs_span_h"].median()),

        "pct_repeat_contact": wmean(g, "obs_repeat_contact"),
        "median_customer_turns": float(g["obs_customer_turns"].median()),
        "top_rejection_reason": wmode(g, "reason_label"),
        "top_friction_point": top_friction(g),
        "estimable": len(g) >= 30,
    })

per_rule = pd.DataFrame(rows).sort_values("est_vol_jan_jul", ascending=False)


# ═════════════════════════════════════════════════ 7 · rule concentration
def concentration(by: str) -> pd.DataFrame:
    out = []
    for key, g in tickets.groupby(by):
        p = g.groupby("rule_label")["w"].sum()
        p = (p / p.sum()).sort_values(ascending=False)
        inv_simpson = 1.0 / float((p ** 2).sum())
        exp_entropy = float(np.exp(-(p * np.log(p)).sum()))
        n90 = int((p.cumsum() < 0.90).sum()) + 1
        out.append({
            by: key,
            "est_vol_jan_jul": round(float(g["w"].sum())),
            "distinct_rules": int(len(p)),
            "effective_rules_inv_simpson": round(inv_simpson, 2),
            "effective_rules_exp_entropy": round(exp_entropy, 2),
            "rules_covering_90pct": n90,
            "modal_rule": str(p.index[0]),
            "modal_share": round(float(p.iloc[0]), 4),
        })
    return pd.DataFrame(out).sort_values("est_vol_jan_jul", ascending=False)


rules_per_code = concentration("rc_label")
rules_per_code["code_norm"] = rules_per_code["rc_label"].map(norm_res_code)
rules_per_code["n_rules_primary"] = rules_per_code["code_norm"].map(
    lambda c: PRIM_COUNT.get(c, 0))
rules_per_code["n_rules_also"] = rules_per_code["code_norm"].map(
    lambda c: ALSO_COUNT.get(c, 0))
rules_per_code["n_rules_touching"] = (rules_per_code["n_rules_primary"]
                                      + rules_per_code["n_rules_also"])
rules_per_code["code_vol_2025"] = rules_per_code["code_norm"].map(VOL25)
rules_per_code["est_vol_annualised"] = (rules_per_code["est_vol_jan_jul"]
                                        * ANNUALISE).round()
rules_per_code = rules_per_code[[
    "rc_label", "est_vol_jan_jul", "est_vol_annualised", "code_vol_2025",
    "n_rules_primary", "n_rules_also", "n_rules_touching",
    "distinct_rules", "effective_rules_inv_simpson", "effective_rules_exp_entropy",
    "rules_covering_90pct", "modal_rule", "modal_share"]]

rules_per_reason = concentration("reason_label")
rules_per_reason["est_vol_annualised"] = (rules_per_reason["est_vol_jan_jul"]
                                          * ANNUALISE).round()

OBS_MEAN_CODE = float(np.average(rules_per_code["effective_rules_inv_simpson"],
                                 weights=rules_per_code["est_vol_jan_jul"]))
OBS_MEAN_REASON = float(np.average(rules_per_reason["effective_rules_inv_simpson"],
                                   weights=rules_per_reason["est_vol_jan_jul"]))
print(f"  effective rules per resolution code : {OBS_MEAN_CODE:.2f} "
      f"(structural {STRUCTURAL_MEAN:.2f})")
print(f"  effective rules per rejection reason: {OBS_MEAN_REASON:.2f}")

# ═══════════════════════════════════════════════════════ 8 · year on year
# Exact counts, not estimates: every Invalid- incident carries its code in the
# metadata, so the 2026 side of this table is counted rather than weighted.
meta["code_n"] = meta["_rc"].map(norm_res_code)
actual_by_code = meta["code_n"].value_counts()
yoy_rows = []
for code_raw, v25 in VOL25.items():
    ours = float(actual_by_code.get(code_raw, 0))
    ann = ours * ANNUALISE
    yoy_rows.append({
        "resolution_code": code_raw,
        "vol_2025_full_year": int(v25),
        "vol_2026_osvc_partial": int(VOL26_PARTIAL.get(code_raw, 0)),
        "actual_2026_jan_jul": int(ours),
        "actual_2026_annualised": round(ann),
        "yoy_pct": (ann / v25 - 1) if v25 else np.nan,
    })
code_yoy = pd.DataFrame(yoy_rows).sort_values("vol_2025_full_year", ascending=False)

ANN_FROM_CORPUS = N_INVALID_FILE * ANNUALISE
OSVC_MONTHS = round(TOT26_PARTIAL / (N_INVALID_FILE / MONTHS_OBSERVED))
ANN_FROM_OSVC = TOT26_PARTIAL * 12 / OSVC_MONTHS
print(f"  2026 Jan-Jul, all Invalid- incidents: {N_INVALID_FILE:,}")
print(f"  2025 full year {TOT25:,}")
print(f"  2026 annualised from our corpus  {ANN_FROM_CORPUS:,.0f}")
print(f"  2026 annualised from osvc ({OSVC_MONTHS} mo) {ANN_FROM_OSVC:,.0f}")
_gap = abs(ANN_FROM_CORPUS - ANN_FROM_OSVC) / ANN_FROM_CORPUS
assert _gap < 0.05, (
    f"the two annualisation routes disagree by {_gap:.1%}; the 'volumes are flat' "
    f"claim rests on them agreeing")
print(f"  routes agree within {_gap:.1%}; year on year {ANN_FROM_CORPUS / TOT25 - 1:+.1%}")

# ═══════════════════════════════════════════════════════ 9 · data dictionary
DD = [
    ("BASIS", "Corpus period",
     f"All {len(meta):,} incidents closed {_closed.min():%Y-%m-%d} to {_closed.max():%Y-%m-%d} "
     f"- {MONTHS_OBSERVED} months, NOT a year. Columns named *_jan_jul are on the observed "
     f"basis; *_annualised are x{ANNUALISE:.3f}."),
    ("BASIS", "Population",
     f"{N_POP:,} classifiable tickets. 6,214 tickets with no usable transcript are excluded "
     f"and never extrapolated over."),
    ("BASIS", "Weighting",
     "Design weight w = N_h/n_h by resolution code, from the triangulation workbook. "
     "Intervals use a finite-population correction; census strata contribute zero variance."),
    ("est_vol_jan_jul / ci95", "csd_2026_effort_triangulation.xlsx :: tickets :: w",
     "Design-weighted volume over the 7 observed months, with the 95% half-width."),
    ("est_vol_annualised", "derived",
     f"est_vol_jan_jul x {ANNUALISE:.3f}. Assumes the remaining 5 months resemble the first 7."),
    ("code_vol_2025", "resolution codes osvc-Copy.xlsx :: Sheet1 :: 2025",
     "CODE-LEVEL, not rule-level: the 2025 volume of this rule's PRIMARY resolution code. "
     "Rules sharing a primary code repeat the figure. DO NOT SUM THIS COLUMN."),
    ("code_vol_2026_partial", "resolution codes osvc-Copy.xlsx :: Sheet1 :: 2026",
     f"A ~{OSVC_MONTHS}-month 2026 snapshot, not a full year. Reading it against "
     f"code_vol_2025 suggests volumes halved; annualised they are flat."),
    ("csat_n / csat_mean_1_7 / pct_satisfied",
     "scopus content_2026_metadata.tsv :: CSAT_ANSWER_CODE",
     "INVERTED 1-7 scale: 1 = extremely satisfied, 7 = extremely dissatisfied, so a LOWER "
     "mean is better. pct_satisfied = codes 1-3. Codes 0/8 are non-responses and dropped."),
    ("survey_n / survey_effort_mean_1_5 / pct_hard",
     "scopus content_2026_metadata.tsv :: CSAT_EFFORT_CODE",
     "1-5 agreement with 'it was easy', reverse-scored so HIGHER = HARDER. pct_hard = codes "
     "4-5. Codes 0/6 are non-responses and dropped. Runs opposite to CSAT."),
    ("SUPPRESSION", "applied to all CSAT and survey columns",
     f"Any survey-derived statistic with fewer than {MIN_SURVEY_N} responses is blank; the "
     f"count is still shown. {int((per_rule['survey_n'] >= MIN_SURVEY_N).sum())} of "
     f"{len(per_rule)} rules clear it for survey effort."),
    ("llm_effort_mean_1_5 / pct_high_effort", "csd_2026_effort_triangulation.xlsx",
     "Model reading the transcript, 1-5, higher = harder. Test-retest agreement is 62.3% "
     "exact and Spearman +0.675, so quote aggregate rates to the nearest few points and "
     "never treat a single ticket's score as fact."),
    ("llm_vs_survey_delta", "derived",
     "llm_effort_mean_1_5 minus survey_effort_mean_1_5. Positive = the model reads the "
     "interaction as harder than the customer reported. Blank where survey_n < 30."),
    ("tat_median_days / tat_p90_days",
     "scopus content_2026_metadata.tsv :: created_to_closed_days",
     "Turnaround from incident creation to close, in decimal days."),
    ("first_response_median_h / span_median_h", "runs/intermediate/csd_effort_features.csv",
     "Computed from thread timestamps: hours to the first staff reply, and first-to-last "
     "entry span. Complete on all incidents except where no staff reply exists."),
    ("conf_strict / conf_loose", "csd_2026_validation_rules.xlsx :: per_rule",
     "Agreement between the rule and the agent-logged code. Strict = the rule's designated "
     "primary code; loose also counts the matrix's 'also maps to'. Agreement, NOT accuracy - "
     "the resolution code is one agent's choice at close, not ground truth."),
    ("n_rules_primary / n_rules_also / n_rules_touching",
     "Triangulation Matrix :: Primary Resolution Code, Also Maps To",
     "STRUCTURAL: how many of the 24 rules name this code. Counted from the matrix, not from "
     "the tickets - several rules share a primary and the 'also' links appear in no output."),
    ("effective_rules_inv_simpson", "derived, design-weighted",
     "1 / sum(share^2) over the rules observed on this code or reason. 1.0 = one rule owns "
     "it; 4.0 = as ambiguous as four equally common rules. Less inflated by long tails than "
     "a raw distinct count."),
    ("effective_rules_exp_entropy", "derived, design-weighted",
     "exp(Shannon entropy). Same idea, more sensitive to rare rules, so always >= "
     "inv_simpson."),
    ("estimable", "derived",
     "sample_n >= 30. Rules below this are shown for completeness; their rates are "
     "illustrative only."),
]
data_dictionary = pd.DataFrame(DD, columns=["column", "source", "meaning"])

SUMMARY = pd.DataFrame([
    ("Corpus period", f"{_closed.min():%Y-%m-%d} .. {_closed.max():%Y-%m-%d} "
                      f"({MONTHS_OBSERVED} months)"),
    ("Classifiable population (7 mo)", f"{N_POP:,}"),
    ("All Invalid- incidents (7 mo)", f"{N_INVALID_FILE:,}"),
    ("All Invalid- annualised", f"{ANN_FROM_CORPUS:,.0f}"),
    ("Invalid- tickets, 2025 full year", f"{TOT25:,}"),
    ("Year on year", f"{ANN_FROM_CORPUS / TOT25 - 1:+.1%} (flat)"),
    ("Structural rules per claimed code", f"{STRUCTURAL_MEAN:.2f} "
                                          f"({len(RULES)} rules / {len(PRIM_COUNT)} codes)"),
    ("Observed effective rules per code", f"{OBS_MEAN_CODE:.2f}"),
    ("Observed effective rules per reason", f"{OBS_MEAN_REASON:.2f}"),
    ("CSAT answers on the sample", f"{N_CSAT}"),
    ("Survey-effort answers on the sample", f"{N_SURVEY}"),
    ("Rules clearing the survey threshold",
     f"{int((per_rule['survey_n'] >= MIN_SURVEY_N).sum())} of {len(per_rule)}"),
], columns=["item", "value"])

# ═══════════════════════════════════════════════════════════════ 10 · checks
assert int(per_rule["sample_n"].sum()) == N_SAMPLE
assert abs(per_rule["est_vol_jan_jul"].sum() - N_POP) <= len(per_rule)
assert int(per_rule["csat_n"].sum()) == N_CSAT
assert int(per_rule["survey_n"].sum()) == N_SURVEY
_thin = per_rule[(per_rule["survey_n"] < MIN_SURVEY_N)
                 & per_rule["survey_effort_mean_1_5"].notna()]
assert _thin.empty, f"suppression leaked on {len(_thin)} rule(s)"
_bad = rules_per_code[rules_per_code["effective_rules_exp_entropy"]
                      < rules_per_code["effective_rules_inv_simpson"] - 1e-9]
assert _bad.empty, "exp(entropy) below inverse-Simpson - a diversity index is wrong"

# CSAT runs 1 = best while both effort scales run 5 = worst. Silently inverting
# one would flip a conclusion without breaking anything, so the three pairings
# are checked for sign rather than trusted.
_q = per_rule.dropna(subset=["pct_hard", "pct_satisfied"])
if len(_q) >= 5:
    def _rho(a, b):
        ra, rb = _q[a].rank(), _q[b].rank()
        return float(np.corrcoef(ra, rb)[0, 1])
    r_hard = _rho("pct_high_effort", "pct_hard")
    r_sat = _rho("pct_high_effort", "pct_satisfied")
    r_cross = _rho("pct_hard", "pct_satisfied")
    assert r_hard > 0, f"LLM effort and survey hardness disagree in sign ({r_hard:+.2f})"
    assert r_sat < 0, f"LLM effort and satisfaction should oppose ({r_sat:+.2f})"
    assert r_cross < 0, f"survey hardness and satisfaction should oppose ({r_cross:+.2f})"
    print(f"  scale directions cohere: effort~hard {r_hard:+.2f}, "
          f"effort~satisfied {r_sat:+.2f}, hard~satisfied {r_cross:+.2f}")

# The model reads effort about one level harder than customers report it. This
# is a calibration offset, not a ranking failure - worth surfacing, not fixing.
_delta = per_rule["llm_vs_survey_delta"].dropna()
print(f"  LLM minus survey effort: {_delta.min():+.2f} to {_delta.max():+.2f} "
      f"(mean {_delta.mean():+.2f}) across {len(_delta)} rules")
assert abs(STRUCTURAL_MEAN - 2.0) < 0.01, f"structural mean moved to {STRUCTURAL_MEAN}"
print("  all integrity checks passed")

# ═══════════════════════════════════════════════ 9b · effort by each axis
# Both effort measures side by side. The survey base differs sharply by axis and
# that is the point: the resolution code is known for every ticket in the corpus,
# so the code view rests on all 2,813 respondents, while rules and reasons exist
# only on the 12,000 sample and rest on 625.
EFFORT_FULL = BASE / "runs" / "output" / "csd_2026_customer_effort_full.xlsx"
_EMAP = {"very_low": 1, "low": 2, "medium": 3, "high": 4, "very_high": 5}
_full = pd.read_excel(EFFORT_FULL, usecols=["INCIDENT_REF", "effort_score"])
_full["ref"] = _full["INCIDENT_REF"].astype(str).str.strip()
_full["llm_num"] = _full["effort_score"].map(_EMAP)
_corpus = meta[["ref", "_rc", "eff_survey", "tat_days"]].merge(
    _full[["ref", "llm_num"]], on="ref", how="left")
_corpus["llm_high"] = (_corpus["llm_num"] >= 4).astype(float).where(
    _corpus["llm_num"].notna())
_corpus["not_easy"] = (_corpus["eff_survey"] >= 3).astype(float).where(
    _corpus["eff_survey"].notna())
_corpus["hard"] = (_corpus["eff_survey"] >= 4).astype(float).where(
    _corpus["eff_survey"].notna())


def effort_view(frame, by, weighted, label_col):
    """One row per category with both effort measures and their bases."""
    out = []
    for key, g in frame.groupby(by):
        n_srv = int(g["eff_survey"].notna().sum()) if "eff_survey" in g else 0
        if weighted:
            vol = float(g["w"].sum())
            llm_m = wmean(g, "effort_score_num")
            llm_h = wmean(g, "effort_high")
            srv_m = suppressed(g, "eff_survey", n_srv)
            ne = suppressed(g, "survey_not_easy", n_srv)
            hd = suppressed(g, "survey_hard", n_srv)
            tat = float(g["tat_days"].median())
        else:
            vol = float(len(g))
            llm_m = float(g["llm_num"].mean())
            llm_h = float(g["llm_high"].mean())
            ok = n_srv >= MIN_SURVEY_N
            srv_m = float(g["eff_survey"].mean()) if ok else float("nan")
            ne = float(g["not_easy"].mean()) if ok else float("nan")
            hd = float(g["hard"].mean()) if ok else float("nan")
            tat = float(g["tat_days"].median())
        out.append({
            label_col: key,
            "n_tickets": int(len(g)),
            "est_vol_jan_jul": round(vol),
            "survey_n": n_srv,
            "pct_not_easy_survey": ne,
            "pct_hard_survey": hd,
            "survey_effort_mean_1_5": srv_m,
            "llm_effort_mean_1_5": llm_m,
            "pct_high_llm": llm_h,
            "llm_minus_survey": (llm_m - srv_m) if pd.notna(srv_m) else float("nan"),
            "tat_median_days": tat,
            "survey_base_adequate": n_srv >= MIN_SURVEY_N,
        })
    return pd.DataFrame(out).sort_values("est_vol_jan_jul", ascending=False)


effort_by_rule = effort_view(tickets, "rule_label", True, "rule_label")
effort_by_reason = effort_view(tickets, "reason_label", True, "reason_label")
effort_by_code = effort_view(_corpus[_corpus["_rc"].notna()], "_rc", False, "rc_label")

_ok_code = int(effort_by_code["survey_base_adequate"].sum())
_ok_rule = int(effort_by_rule["survey_base_adequate"].sum())
_ok_reason = int(effort_by_reason["survey_base_adequate"].sum())
print(f"  effort views - survey base adequate: {_ok_code}/{len(effort_by_code)} codes, "
      f"{_ok_rule}/{len(effort_by_rule)} rules, {_ok_reason}/{len(effort_by_reason)} reasons")
assert int(effort_by_code["survey_n"].sum()) == int(meta["eff_survey"].notna().sum())

OUT.parent.mkdir(parents=True, exist_ok=True)
with pd.ExcelWriter(OUT, engine="openpyxl") as xl:
    per_rule.to_excel(xl, sheet_name="per_rule", index=False)
    effort_by_rule.to_excel(xl, sheet_name="effort_by_rule", index=False)
    effort_by_code.to_excel(xl, sheet_name="effort_by_code", index=False)
    effort_by_reason.to_excel(xl, sheet_name="effort_by_reason", index=False)
    rules_per_code.to_excel(xl, sheet_name="rules_per_code", index=False)
    rules_per_reason.to_excel(xl, sheet_name="rules_per_reason", index=False)
    code_yoy.to_excel(xl, sheet_name="code_year_on_year", index=False)
    SUMMARY.to_excel(xl, sheet_name="summary", index=False)
    data_dictionary.to_excel(xl, sheet_name="data_dictionary", index=False)

print(f"\nwrote {OUT}")
print(f"  per_rule {per_rule.shape}  rules_per_code {rules_per_code.shape}  "
      f"rules_per_reason {rules_per_reason.shape}  code_year_on_year {code_yoy.shape}")

# ═══════════════════════════════════════════════════════ 11 · charts + JSON
import json                                                    # noqa: E402
import matplotlib                                              # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                # noqa: E402
from matplotlib.ticker import FuncFormatter                    # noqa: E402

NAVY, ORANGE, GREY, RED, GREEN = "#0B2A4A", "#FF6C00", "#7A8794", "#C1272D", "#2E7D5B"
SC_DIR = BASE / "runs" / "output" / "scorecard"
FIGS = SC_DIR / "figs"
FIGS.mkdir(parents=True, exist_ok=True)

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


def short_rule(s, n=42):
    s = str(s)
    return s if len(s) <= n else s[:n - 1] + "…"


print("Rendering charts...")
est = per_rule[per_rule["estimable"]].copy()

# 1 · volume against customer effort
fig, ax = plt.subplots(figsize=(10, 5.2))
ax.scatter(est["est_vol_annualised"], est["pct_high_effort"],
           s=60 + est["sample_n"] / 6, color=NAVY, alpha=.75, zorder=3)
OVERALL_HIGH = float((tickets["effort_high"] * tickets["w"]).sum() / tickets["w"].sum())
ax.axhline(OVERALL_HIGH, color=ORANGE, ls="--", lw=1.2, zorder=2)
for _, r in est.iterrows():
    ax.annotate(str(r["csdvr_code"]), (r["est_vol_annualised"], r["pct_high_effort"]),
                textcoords="offset points", xytext=(7, 3), fontsize=8, color=GREY)
ax.set_xscale("log")
ax.set_xlabel("estimated annualised volume (log scale)")
ax.set_ylabel("share judged high effort")
ax.yaxis.set_major_formatter(PCT)
save(fig, "01_volume_vs_effort")

# 2 · conformance against effort
fig, ax = plt.subplots(figsize=(10, 5.2))
ax.scatter(est["conf_strict"], est["pct_high_effort"], s=60 + est["sample_n"] / 6,
           color=NAVY, alpha=.75, zorder=3)
for _, r in est.iterrows():
    ax.annotate(str(r["csdvr_code"]), (r["conf_strict"], r["pct_high_effort"]),
                textcoords="offset points", xytext=(7, 3), fontsize=8, color=GREY)
ax.set_xlabel("strict conformance")
ax.set_ylabel("share judged high effort")
ax.xaxis.set_major_formatter(PCT); ax.yaxis.set_major_formatter(PCT)
save(fig, "02_conformance_vs_effort")

# 3 · the model against the customer, on the rules where the survey supports it
srv = per_rule.dropna(subset=["survey_effort_mean_1_5"]).sort_values(
    "llm_effort_mean_1_5", ascending=True)
fig, ax = plt.subplots(figsize=(10, 4.6))
y = np.arange(len(srv))
ax.barh(y - .2, srv["survey_effort_mean_1_5"], .4, color=ORANGE,
        label="customer's own answer (1-5)")
ax.barh(y + .2, srv["llm_effort_mean_1_5"], .4, color=NAVY, label="model reading the transcript")
ax.set_yticks(y); ax.set_yticklabels([short_rule(s) for s in srv["rule_label"]], fontsize=8)
ax.set_xlabel("mean effort, 1-5 (higher = harder)")
ax.legend(frameon=False, fontsize=9, loc="lower right")
for i, (a, b, n) in enumerate(zip(srv["survey_effort_mean_1_5"],
                                  srv["llm_effort_mean_1_5"], srv["survey_n"])):
    ax.text(max(a, b) + .05, i, f"n={n}", va="center", fontsize=7.5, color=GREY)
save(fig, "03_llm_vs_customer")

# 4 · turnaround by rule
tat = est.sort_values("tat_median_days", ascending=True)
fig, ax = plt.subplots(figsize=(10, 5.0))
y = np.arange(len(tat))
ax.barh(y, tat["tat_median_days"], .58, color=NAVY, label="median")
ax.scatter(tat["tat_p90_days"], y, color=ORANGE, s=26, zorder=3, label="90th percentile")
ax.set_yticks(y); ax.set_yticklabels([short_rule(s) for s in tat["rule_label"]], fontsize=8)
ax.set_xlabel("days from creation to close")
ax.set_xscale("log")
ax.legend(frameon=False, fontsize=9, loc="lower right")
save(fig, "04_tat_by_rule")

# 5 · rules per resolution code, designed against observed
rpc = rules_per_code.sort_values("est_vol_jan_jul", ascending=True)
fig, ax = plt.subplots(figsize=(10, 5.4))
y = np.arange(len(rpc))
ax.barh(y - .2, rpc["n_rules_primary"], .4, color=GREY, label="rules naming it as primary (matrix)")
ax.barh(y + .2, rpc["effective_rules_inv_simpson"], .4, color=NAVY,
        label="effective rules observed")
ax.axvline(1.0, color=ORANGE, ls="--", lw=1.2)
ax.set_yticks(y); ax.set_yticklabels(rpc["rc_label"], fontsize=8.5)
ax.set_xlabel("number of validation rules")
ax.legend(frameon=False, fontsize=9, loc="lower right")
save(fig, "05_rules_per_code")

# 6 · rules per rejection reason
rpr = rules_per_reason.sort_values("est_vol_jan_jul", ascending=True).tail(14)
fig, ax = plt.subplots(figsize=(10, 5.4))
y = np.arange(len(rpr))
cols = [RED if v >= 3 else NAVY for v in rpr["effective_rules_inv_simpson"]]
ax.barh(y, rpr["effective_rules_inv_simpson"], .6, color=cols)
ax.axvline(OBS_MEAN_REASON, color=ORANGE, ls="--", lw=1.2)
ax.set_yticks(y); ax.set_yticklabels([short_rule(s, 38) for s in rpr["reason_label"]], fontsize=8.5)
ax.set_xlabel("effective number of validation rules (inverse Simpson)")
save(fig, "06_rules_per_reason")

# 7 · year on year, annualised
yy = code_yoy[code_yoy["vol_2025_full_year"] >= 400].sort_values("vol_2025_full_year")
fig, ax = plt.subplots(figsize=(10, 5.2))
y = np.arange(len(yy))
ax.barh(y - .2, yy["vol_2025_full_year"], .4, color=GREY, label="2025, full year")
ax.barh(y + .2, yy["actual_2026_annualised"], .4, color=NAVY, label="2026, annualised from Jan-Jul")
ax.set_yticks(y); ax.set_yticklabels(yy["resolution_code"], fontsize=8.5)
ax.set_xlabel("Invalid- tickets")
ax.legend(frameon=False, fontsize=9, loc="lower right")
save(fig, "07_year_on_year")


def jrecs(df):
    return json.loads(df.to_json(orient="records"))


payload = {
    "meta": {
        "months_observed": MONTHS_OBSERVED,
        "annualise": ANNUALISE,
        "closed_from": f"{_closed.min():%Y-%m-%d}",
        "closed_to": f"{_closed.max():%Y-%m-%d}",
        "n_sample": N_SAMPLE,
        "n_population": N_POP,
        "n_invalid_file": N_INVALID_FILE,
        "n_pop_annualised": round(ANN_FROM_CORPUS),
        "vol_2025": TOT25,
        "vol_2026_osvc_partial": TOT26_PARTIAL,
        "osvc_months": OSVC_MONTHS,
        "ann_from_osvc": round(ANN_FROM_OSVC),
        "yoy_pct": ANN_FROM_CORPUS / TOT25 - 1,
        "n_csat": N_CSAT,
        "n_survey": N_SURVEY,
        "min_survey_n": MIN_SURVEY_N,
        "n_rules_clearing": int((per_rule["survey_n"] >= MIN_SURVEY_N).sum()),
        "codes_adequate": _ok_code, "n_codes": len(effort_by_code),
        "rules_adequate": _ok_rule, "reasons_adequate": _ok_reason,
        "n_reasons": len(effort_by_reason),
        "survey_not_easy_rate": float(_corpus["not_easy"].mean()),
        "survey_hard_rate": float(_corpus["hard"].mean()),
        "n_rules_total": len(per_rule),
        "structural_mean": STRUCTURAL_MEAN,
        "n_primary_codes": len(PRIM_COUNT),
        "obs_mean_code": OBS_MEAN_CODE,
        "obs_mean_reason": OBS_MEAN_REASON,
        "delta_min": float(_delta.min()),
        "delta_max": float(_delta.max()),
        "delta_mean": float(_delta.mean()),
        "overall_high_effort": OVERALL_HIGH,
        "unclaimed_codes": [c for c in rules_per_code["rc_label"]
                            if PRIM_COUNT.get(norm_res_code(c), 0) == 0],
    },
    "per_rule": jrecs(per_rule),
    "effort_by_rule": jrecs(effort_by_rule),
    "effort_by_code": jrecs(effort_by_code),
    "effort_by_reason": jrecs(effort_by_reason),
    "rules_per_code": jrecs(rules_per_code),
    "rules_per_reason": jrecs(rules_per_reason),
    "code_yoy": jrecs(code_yoy),
}
(SC_DIR / "scorecard_data.json").write_text(
    json.dumps(payload, indent=1, allow_nan=False, default=str), encoding="utf-8")
print(f"wrote {SC_DIR / 'scorecard_data.json'}")
