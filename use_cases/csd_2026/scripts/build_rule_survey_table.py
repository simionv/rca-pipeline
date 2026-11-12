"""Per-validation-rule table: volume, resolution code, rejection reasons, and the
three survey scores (CSAT, CES, ASAT).

All three scores are reported as POSITIVE rates so they read in the same direction
- higher is better on every one:

    CSAT%  CSAT_ANSWER_CODE 1-3   extremely satisfied / very satisfied / satisfied
    CES%   CSAT_EFFORT_CODE 1-2   strongly agree / agree that it was easy
    ASAT%  AGENT_CSAT_CODE  1-2   strongly agree / agree (agent-directed question)

Each is blank where fewer than MIN_N customers answered, with the count shown.
"""
from __future__ import annotations

from pathlib import Path

import math
import re

import numpy as np
import pandas as pd

# Copied from scripts/build_rule_scorecard.py (notebook 08 code cell 4), not
# imported - the matrix and the metadata spell codes inconsistently
# ("Invalid - X" / "Invalid-X" / trailing ";"), and this normaliser is the one
# the scorecard's own 2025 volumes already key on.
_NA_TOKENS = {"", "na", "n/a"}


def norm_res_code(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    s = str(value).strip().rstrip(";").strip()
    s = re.sub(r"^invalid\s*-\s*", "invalid-", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).casefold()
    return "" if s in _NA_TOKENS else s

BASE = Path(__file__).resolve().parents[1]
META = BASE / "data" / "scopus content" / "scopus content_2026_metadata.tsv"
TRI = BASE / "runs" / "output" / "csd_2026_effort_triangulation.xlsx"
RULES = BASE / "runs" / "output" / "csd_2026_validation_rules.xlsx"
OSVC_XLSX = BASE / "data" / "scopus content" / "resolution codes osvc-Copy.xlsx"
OUT_XLSX = BASE / "runs" / "output" / "csd_2026_rule_survey_table.xlsx"
OUT_MD = BASE / "docs" / "CSD_2026_rule_survey_table.md"

MIN_N = 30
N_SAMPLE = 12000

print("=" * 78)
print("PER-RULE SURVEY TABLE")
print("=" * 78)

t = pd.read_excel(TRI, sheet_name="tickets")
t["ref"] = t["INCIDENT_REF"].astype(str).str.strip()
t["rule_label"] = t["rule_label"].fillna("(invalid code returned by the model)")
t["reason_label"] = t["reason_label"].fillna("(invalid code returned by the model)")

meta = pd.read_csv(META, sep="\t", dtype=str,
                   usecols=["incident_reference", "CSAT_ANSWER_CODE",
                            "CSAT_EFFORT_CODE", "AGENT_CSAT_CODE"])
meta["ref"] = meta["incident_reference"].astype(str).str.strip()
# Codes 0/6/8 are non-responses on all three scales, not extreme answers.
meta["csat"] = pd.to_numeric(meta["CSAT_ANSWER_CODE"], errors="coerce").where(
    lambda s: s.between(1, 7))
meta["ces"] = pd.to_numeric(meta["CSAT_EFFORT_CODE"], errors="coerce").where(
    lambda s: s.between(1, 5))
meta["asat"] = pd.to_numeric(meta["AGENT_CSAT_CODE"], errors="coerce").where(
    lambda s: s.between(1, 5))
t = t.merge(meta[["ref", "csat", "ces", "asat"]], on="ref", how="left")

t["csat_pos"] = (t["csat"] <= 3).where(t["csat"].notna())
t["ces_pos"] = (t["ces"] <= 2).where(t["ces"].notna())
t["asat_pos"] = (t["asat"] <= 2).where(t["asat"].notna())
print(f"  sample {len(t):,}   answered CSAT {int(t.csat.notna().sum())}  "
      f"CES {int(t.ces.notna().sum())}  ASAT {int(t.asat.notna().sum())}")

conf = pd.read_excel(RULES, sheet_name="per_rule")
CODE = {}
for _, r in conf.iterrows():
    CODE[str(r["rule"]).strip()[:40]] = (r["code"], r["expected"], r["modal_actual"])

# 2025 volumes, same source and same normaliser as scripts/build_rule_scorecard.py.
# CODE-LEVEL, not rule-level: several rules share one primary resolution code, so
# this is the code's full-year 2025 count, not a rule-specific one.
osvc = pd.read_excel(OSVC_XLSX, sheet_name="Sheet1", header=1)
osvc = osvc.dropna(subset=[osvc.columns[1]])
osvc["code_n"] = osvc[osvc.columns[1]].map(norm_res_code)
osvc = osvc[osvc["code_n"].str.startswith("invalid")]
VOL25 = dict(zip(osvc["code_n"], osvc[2025].astype(float)))


def suppressed(g, col):
    v = g[col].dropna()
    n = len(v)
    return n, (float(v.mean()) if n >= MIN_N else np.nan)


rows = []
for rule, g in t.groupby("rule_label"):
    code, expected, modal = CODE.get(str(rule).strip()[:40], ("", "", ""))
    # Reason and rule are many-to-many - a rule averages 8.4 distinct reasons - so a
    # single modal reason would misrepresent most rules. List everything at >=10%.
    rs = (g.groupby("reason_label")["w"].sum() / g["w"].sum()).sort_values(ascending=False)
    reasons = "; ".join(f"{k} {v:.0%}" for k, v in rs.head(3).items() if v >= 0.10)
    n_csat, p_csat = suppressed(g, "csat_pos")
    n_ces, p_ces = suppressed(g, "ces_pos")
    n_asat, p_asat = suppressed(g, "asat_pos")
    rows.append({
        "csdvr_code": code, "validation_rule": rule,
        "sample_n": len(g), "sample_pct": len(g) / N_SAMPLE,
        "est_population": round(float(g["w"].sum())),
        "resolution_code_designated": expected,
        "resolution_code_most_logged": modal,
        "code_vol_2025": VOL25.get(expected, np.nan),
        "rejection_reasons_10pct_plus": reasons,
        "n_distinct_reasons": int(g["reason_label"].nunique()),
        "CSAT_n": n_csat, "CSAT_pct": p_csat,
        "CES_n": n_ces, "CES_pct": p_ces,
        "ASAT_n": n_asat, "ASAT_pct": p_asat,
    })

tab = pd.DataFrame(rows).sort_values("sample_n", ascending=False).reset_index(drop=True)

assert tab["sample_n"].sum() == N_SAMPLE, f"rows sum to {tab.sample_n.sum()}"
for m in ["CSAT", "CES", "ASAT"]:
    got, want = tab[f"{m}_n"].sum(), int(t[f"{m.lower()}_pos"].notna().sum())
    assert got == want, f"{m} counts {got} != {want}"
    thin = tab[(tab[f"{m}_n"] < MIN_N) & tab[f"{m}_pct"].notna()]
    assert thin.empty, f"{m} suppression leaked on {len(thin)} rows"
print(f"  rules: {len(tab)}   clearing n>={MIN_N}:  "
      f"CSAT {int((tab.CSAT_n >= MIN_N).sum())}  CES {int((tab.CES_n >= MIN_N).sum())}  "
      f"ASAT {int((tab.ASAT_n >= MIN_N).sum())}")

DEFS = [
    ("CSAT%", "CSAT_ANSWER_CODE 1-3 - extremely satisfied / very satisfied / satisfied. "
     "Neutral (4) counts as NOT satisfied. The underlying scale is inverted: 1 is best."),
    ("CES%", "CSAT_EFFORT_CODE 1-2 - strongly agree / agree that the request was easy to "
     "handle. Higher is better, so this is the inverse of the '% not easy' figure used "
     "elsewhere in this analysis."),
    ("ASAT%", "AGENT_CSAT_CODE 1-2 - strongly agree / agree on a separate agent-directed "
     "question. Answered on only 2,306 tickets corpus-wide, the thinnest of the three."),
    ("Suppression", f"A percentage is blank where fewer than {MIN_N} customers answered "
     f"that question for that rule. The count is always shown."),
    ("rejection_reasons_10pct_plus", "Every rejection reason accounting for at least 10% "
     "of the rule's design-weighted volume, up to three. Reason and rule are a "
     "MANY-TO-MANY mapping - a rule averages 8.4 distinct reasons - so "
     "n_distinct_reasons is given alongside."),
    ("resolution_code_designated", "The primary code the triangulation matrix assigns to "
     "the rule. Where it differs from most_logged the rule cannot conform, however well "
     "it is applied."),
    ("code_vol_2025", "CODE-LEVEL, not rule-level, same as in csd_2026_rule_scorecard.xlsx: "
     "the full-year 2025 volume of this rule's designated resolution code, from "
     "'resolution codes osvc-Copy.xlsx'. Several rules share one primary code, so this "
     "number repeats across those rows and cannot be summed to a rule-level total."),
    ("Basis", "12,000 stratified sample; est_population is design-weighted to the 50,714 "
     "classifiable tickets closed Jan-Jul 2026 (seven months, not a year)."),
]

with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as xl:
    tab.to_excel(xl, sheet_name="per_rule_survey", index=False)
    pd.DataFrame(DEFS, columns=["item", "definition"]).to_excel(
        xl, sheet_name="definitions", index=False)
print(f"  wrote {OUT_XLSX}")


def pc(v):
    return "—" if pd.isna(v) else f"{v * 100:.0f}%"


L = ["# Per-validation-rule survey table — Scopus CSD 2026", "",
     "All three scores are **positive rates**: higher is better on each. Blank where "
     f"fewer than {MIN_N} customers answered that question for that rule; the response "
     "count is always shown.", "",
     "| Rule | Validation rule | Sample n | Sample % | Est. pop. | 2025 code vol. | "
     "Code designated | Code most logged | Rejection reasons (≥10%) | CSAT n | CSAT % | "
     "CES n | CES % | ASAT n | ASAT % |",
     "|---|---|---:|---:|---:|---:|---|---|---|---:|---:|---:|---:|---:|---:|"]
for _, r in tab.iterrows():
    v25 = "—" if pd.isna(r.code_vol_2025) else f"{r.code_vol_2025:,.0f}"
    L.append(f"| {r.csdvr_code} | {str(r.validation_rule)[:46]} | {r.sample_n:,} | "
             f"{r.sample_pct:.1%} | {r.est_population:,} | {v25} | "
             f"{r.resolution_code_designated} | {r.resolution_code_most_logged} | "
             f"{r.rejection_reasons_10pct_plus} | {r.CSAT_n} | {pc(r.CSAT_pct)} | "
             f"{r.CES_n} | {pc(r.CES_pct)} | {r.ASAT_n} | {pc(r.ASAT_pct)} |")
L += ["", "## Definitions", ""]
for k, v in DEFS:
    L.append(f"- **{k}** — {v}")
L.append("")
OUT_MD.write_text("\n".join(L), encoding="utf-8")
print(f"  wrote {OUT_MD}")
