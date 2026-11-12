"""Assemble the customer-effort modelling frame for R.

Outcome is the customer's own survey answer (CSAT_EFFORT_CODE, 1-5, higher =
harder). Predictors come in blocks so that R can test each block's contribution
by likelihood-ratio test against the block below it.

Writes:
    runs/output/model/effort_model_input.csv       one row per candidate incident
    runs/output/model/effort_model_dictionary.csv  every column, source, caveat
    runs/output/model/effort_model_levels.json     the collapsing maps

Nothing is fitted here. Modelling happens in scripts/effort_model.R.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
META_TSV = BASE / "data" / "scopus content" / "scopus content_2026_metadata.tsv"
OBS_CSV = BASE / "runs" / "intermediate" / "csd_effort_features.csv"
EFFORT_FULL = BASE / "runs" / "output" / "csd_2026_customer_effort_full.xlsx"
TRIANG = BASE / "runs" / "output" / "csd_2026_effort_triangulation.xlsx"
OUTDIR = BASE / "runs" / "output" / "model"
OUTDIR.mkdir(parents=True, exist_ok=True)

EFFORT_MAP = {"very_low": 1, "low": 2, "medium": 3, "high": 4, "very_high": 5}

# Every one of these is populated only on survey rows, so including any of them
# would encode "this person responded" as well as leaking the outcome itself.
# CSAT_ANSWER_CODE correlates with the outcome at Spearman 0.731.
LEAKY = ["CSAT_ANSWER_CODE", "CSAT_ANSWER_DESC", "CSAT_EFFORT_DESC", "CSAT_THUMBS",
         "CSAT_DSAT_REASON", "CSAT_REDFLAG_STATUS", "CSAT_COMPLETE", "CSAT_SURVEY_DATE",
         "AGENT_CSAT_CODE", "AGENT_CSAT_DESC"]

print("=" * 78)
print("EFFORT MODEL - BUILD FRAME")
print("=" * 78)

# ═══════════════════════════════════════════════════════════════ metadata
meta = pd.read_csv(META_TSV, sep="\t", dtype=str)
meta["ref"] = meta["incident_reference"].astype(str).str.strip()
print(f"  metadata {len(meta):,} rows")

survey = pd.to_numeric(meta["CSAT_EFFORT_CODE"], errors="coerce")
meta["survey_effort"] = survey.where(survey.between(1, 5))
N_USABLE = int(meta["survey_effort"].notna().sum())
print(f"  usable survey answers (1-5): {N_USABLE:,}")
assert N_USABLE == 3233, f"expected 3,233 usable survey answers, got {N_USABLE}"

meta["survey_not_easy"] = (meta["survey_effort"] >= 3).astype("Int64").where(
    meta["survey_effort"].notna())
meta["survey_hard"] = (meta["survey_effort"] >= 4).astype("Int64").where(
    meta["survey_effort"].notna())

for c in ["created_to_closed_days", "created_to_initial_response_days"]:
    meta[c] = pd.to_numeric(meta[c], errors="coerce")
meta["number_of_responses"] = pd.to_numeric(meta["number_of_responses"], errors="coerce")

_closed = pd.to_datetime(meta["incident_closed_datetime"], errors="coerce")
meta["close_month"] = _closed.dt.month
# Seven months of data would cost six dummies against ~360 events. A half-year
# split costs one and still catches any drift.
meta["close_half"] = np.where(meta["close_month"] <= 3, "Jan-Mar", "Apr-Jul")

LEVELS: dict[str, list] = {}


def collapse(series: pd.Series, keep: list[str], other: str = "other") -> pd.Series:
    return series.where(series.isin(keep), other)


# resolution code: keep every level with at least 50 usable respondents, pool the rest
_s = meta.loc[meta["survey_effort"].notna(), "resolution_code_lvl1_desc"].value_counts()
KEEP_CODES = sorted(_s[_s >= 50].index)
LEVELS["resolution_code"] = KEEP_CODES
meta["resolution_code"] = collapse(meta["resolution_code_lvl1_desc"], KEEP_CODES)
print(f"  resolution_code: {len(KEEP_CODES)} levels kept (n>=50), "
      f"{_s.size - len(KEEP_CODES)} pooled")

# contact reason L1: only three levels clear n>=100 among respondents
_r = meta.loc[meta["survey_effort"].notna(), "contact_reason_lvl1_desc"].value_counts()
KEEP_REASON = sorted(_r[_r >= 100].index)
LEVELS["contact_reason_l1"] = KEEP_REASON
meta["contact_reason_l1"] = collapse(meta["contact_reason_lvl1_desc"], KEEP_REASON)

meta["channel"] = np.where(meta["channel_desc"].isin(["Web", "Chat"]),
                           meta["channel_desc"], "other")
LEVELS["channel"] = ["Web", "Chat", "other"]

meta["customer_type"] = np.where(meta["customer_classification_type"] == "Author",
                                 "Author", "other")
LEVELS["customer_type"] = ["Author", "other"]

# ═══════════════════════════════════════════════════════════ observed features
obs = pd.read_csv(OBS_CSV)
obs["ref"] = obs["INCIDENT_REF"].astype(str).str.strip()
OBS_NUM = ["obs_turns", "obs_customer_turns", "obs_agent_turns", "obs_agent_handoffs",
           "obs_distinct_agents", "obs_span_h", "obs_first_response_h",
           "obs_prior_tickets_90d", "obs_responses"]
for c in OBS_NUM:
    obs[c] = pd.to_numeric(obs[c], errors="coerce")

# obs_repeat_contact is <NA> by design where CONTACT_ID cannot be resolved. Filling
# it to False would assert "this customer never came back" about ~13% of tickets on
# no evidence, so it becomes an explicit third level instead.
_rc = pd.to_numeric(obs["obs_repeat_contact"], errors="coerce")
obs["repeat_contact_obs"] = np.where(_rc.isna(), "unknown",
                                     np.where(_rc > 0, "yes", "no"))

# obs_effort_index is deliberately NOT carried through: it is the equal-weight mean
# of the percentile ranks of four columns that are themselves predictors here, so
# it is perfectly collinear with its own parts.
obs = obs[["ref", "repeat_contact_obs"] + OBS_NUM]

# ═══════════════════════════════════════════════════════════ LLM effort reading
llm = pd.read_excel(EFFORT_FULL)
llm["ref"] = llm["INCIDENT_REF"].astype(str).str.strip()
llm["llm_effort_num"] = llm["effort_score"].map(EFFORT_MAP)
llm["llm_high"] = (llm["llm_effort_num"] >= 4).astype("Int64").where(
    llm["llm_effort_num"].notna())

# "na" is a literal string in this column - a hidden missing category, not a level.
llm["resolution_transparency"] = llm["resolution_transparency"].replace("na", np.nan)
llm["repeat_contact_llm"] = llm["repeat_contact"].astype(str).str.lower().map(
    {"true": "yes", "false": "no"})

FRICTION_COLS = [c for c in llm.columns if re.fullmatch(r"friction_points_\d+", c)]
THEME_COLS = [c for c in llm.columns if re.fullmatch(r"effort_themes_\d+", c)]
llm["friction_count"] = llm[FRICTION_COLS].notna().sum(axis=1)

# Friction points are multi-label spread across columns; OR them into indicators.
all_friction = pd.unique(pd.concat([llm[c] for c in FRICTION_COLS]).dropna())
FRICTION_LEVELS = sorted(str(f).strip() for f in all_friction if str(f).strip())
LEVELS["friction_points"] = FRICTION_LEVELS


def slug(s: str) -> str:
    return "fr_" + re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_")[:28]


for f in FRICTION_LEVELS:
    hit = pd.Series(False, index=llm.index)
    for c in FRICTION_COLS:
        hit |= llm[c].astype(str).str.strip().eq(f)
    llm[slug(f)] = hit.astype(int)
FRICTION_VARS = [slug(f) for f in FRICTION_LEVELS]
print(f"  friction indicators: {len(FRICTION_VARS)} from {len(FRICTION_COLS)} columns")

llm = llm[["ref", "llm_effort_num", "llm_high", "resolution_transparency",
           "repeat_contact_llm", "friction_count", "effort_class_l1"] + FRICTION_VARS]

# ═══════════════════════════════════════════════════ rules / reasons (12,000 only)
tri = pd.read_excel(TRIANG, sheet_name="tickets")
tri["ref"] = tri["INCIDENT_REF"].astype(str).str.strip()
tri["rule_label"] = tri["rule_label"].fillna("(invalid code returned by the model)")
tri["reason_label"] = tri["reason_label"].fillna("(invalid code returned by the model)")

# The governance-relevant grouping, and the one the deck already uses. Individual
# rule coefficients are not estimable at n=625; these four levels are.
tri["conformance_status"] = np.select(
    [tri["rule_is_na"].astype(bool),
     ~tri["is_mappable"].astype(bool),
     tri["conf_strict"].astype(bool)],
    ["no rule applies", "code no rule can claim", "rule matches code"],
    default="rule and code disagree")

_rl = tri["reason_label"].value_counts()
KEEP_REASONS = sorted(_rl[_rl >= 300].index)
LEVELS["reason_top"] = KEEP_REASONS
tri["reason_grp"] = collapse(tri["reason_label"], KEEP_REASONS)

_ru = tri["rule_label"].value_counts()
KEEP_RULES = sorted(_ru[_ru >= 500].index)
LEVELS["rule_top"] = KEEP_RULES
tri["rule_grp"] = collapse(tri["rule_label"], KEEP_RULES)

tri = tri[["ref", "conformance_status", "reason_grp", "rule_grp", "rule_label",
           "reason_label", "w"]]

# ═══════════════════════════════════════════════════════════════════ assemble
keep_meta = ["ref", "survey_effort", "survey_not_easy", "survey_hard",
             "resolution_code", "contact_reason_l1", "channel", "customer_type",
             "close_half", "created_to_closed_days", "created_to_initial_response_days",
             "number_of_responses"]
df = (meta[keep_meta]
      .merge(obs, on="ref", how="left")
      .merge(llm, on="ref", how="left")
      .merge(tri, on="ref", how="left"))
assert len(df) == len(meta), "a join duplicated rows"

# Log-transform the durations: all three are extremely right-skewed and contain
# true zeros, so log1p rather than log.
for src, dst in [("created_to_closed_days", "log_tat_days"),
                 ("created_to_initial_response_days", "log_frt_days"),
                 ("obs_span_h", "log_span_h"),
                 ("obs_first_response_h", "log_first_resp_h")]:
    df[dst] = np.log1p(df[src].clip(lower=0))

df["has_survey"] = df["survey_effort"].notna().astype(int)
df["has_llm"] = df["llm_effort_num"].notna().astype(int)
df["has_rule"] = df["conformance_status"].notna().astype(int)
df["in_analysis"] = ((df["has_survey"] == 1) & (df["has_llm"] == 1)
                     & df["obs_turns"].notna()).astype(int)

N_ANALYSIS = int(df["in_analysis"].sum())
N_RULE = int(((df["in_analysis"] == 1) & (df["has_rule"] == 1)).sum())
print(f"  analysis sample (survey + LLM + obs): {N_ANALYSIS:,}")
print(f"  ... also carrying a rule and reason : {N_RULE:,}")
assert N_ANALYSIS == 2813, f"expected 2,813 in the analysis sample, got {N_ANALYSIS}"
assert N_RULE == 625, f"expected 625 with a rule, got {N_RULE}"

_a = df[df["in_analysis"] == 1]
print(f"  events: not-easy {int(_a['survey_not_easy'].sum())}, "
      f"hard {int(_a['survey_hard'].sum())}")
assert int(_a["survey_not_easy"].sum()) == 360
assert int(_a["survey_hard"].sum()) == 216

# ═══════════════════════════════════════════════════════════════════ guards
leaked = [c for c in LEAKY if c in df.columns]
assert not leaked, f"survey-derived columns leaked into the frame: {leaked}"
assert "obs_effort_index" not in df.columns, "the composite index must not be a predictor"
print("  no leakage, no collinear composite  OK")

# The two repeat-contact measures disagree by construction and must never be
# entered together; the frame carries both but R uses them in different blocks.
_both = df[df["in_analysis"] == 1]
print(f"  repeat contact: observational "
      f"{(_both['repeat_contact_obs'] == 'yes').mean():.1%} vs LLM "
      f"{(_both['repeat_contact_llm'] == 'yes').mean():.1%} - different constructs")

# Non-response bias on the very dimension being modelled.
_corpus = (df["repeat_contact_obs"] == "yes").mean()
_resp = (_a["repeat_contact_obs"] == "yes").mean()
print(f"  NON-RESPONSE BIAS: repeat contact {_corpus:.1%} corpus vs {_resp:.1%} "
      f"among respondents")

OUT_CSV = OUTDIR / "effort_model_input.csv"
df.to_csv(OUT_CSV, index=False)
(OUTDIR / "effort_model_levels.json").write_text(
    json.dumps(LEVELS, indent=1), encoding="utf-8")

DD = [
    ("survey_effort", "metadata :: CSAT_EFFORT_CODE",
     "OUTCOME. 1-5, higher = harder. Codes 0/6 dropped as non-responses. Two survey "
     "instruments are mixed under these codes (an agree/disagree wording on 3,196 rows and a "
     "very-low..very-high effort wording on 37); both run in the same direction."),
    ("survey_not_easy", "derived", "PRIMARY OUTCOME. survey_effort >= 3. 360 events of 2,813."),
    ("survey_hard", "derived", "Robustness outcome. survey_effort >= 4. 216 events."),
    ("llm_effort_num", "csd_2026_customer_effort_full.xlsx :: effort_score",
     "The model's reading, mapped very_low=1..very_high=5. A JUDGEMENT of effort, not a "
     "structural fact - models containing it answer 'does the LLM agree with the customer'."),
    ("log_tat_days", "metadata :: created_to_closed_days",
     "log1p. Turnaround creation to close, days. Extremely right-skewed with true zeros."),
    ("log_frt_days", "metadata :: created_to_initial_response_days", "log1p. First response."),
    ("log_span_h / log_first_resp_h", "csd_effort_features.csv", "log1p of the thread-derived "
     "equivalents. Correlated with the metadata durations but computed independently."),
    ("repeat_contact_obs", "csd_effort_features.csv :: obs_repeat_contact",
     "yes / no / UNKNOWN. Unknown is a real level - CONTACT_ID is unresolvable on ~13% of "
     "tickets and coding those as 'no' would assert something unevidenced."),
    ("repeat_contact_llm", "csd_2026_customer_effort_full.xlsx :: repeat_contact",
     "The LLM's judgement, 8.2% yes against the observational 62%. A DIFFERENT CONSTRUCT. "
     "Never enter both in one model."),
    ("resolution_transparency", "csd_2026_customer_effort_full.xlsx",
     "transparent / partial / opaque. The literal string 'na' (897 rows) is treated as missing."),
    ("fr_*", "csd_2026_customer_effort_full.xlsx :: friction_points_1..3",
     "Nine binary indicators, OR'd across the multi-label columns."),
    ("conformance_status", "derived from csd_2026_effort_triangulation.xlsx",
     "Four levels: rule matches code / rule and code disagree / no rule applies / code no rule "
     "can claim. Only on the 12,000 sample, so only 625 respondents."),
    ("rule_grp / reason_grp", "triangulation :: rule_label, reason_label",
     "Collapsed to levels with enough support. Per-rule coefficients against customer-reported "
     "effort are NOT estimable at n=625 (92 not-easy events)."),
    ("w", "triangulation :: w", "Design weight N_h/n_h. Applies to the 12,000 stratified sample "
     "only; the 2,813 survey respondents span the whole corpus and are not design-weighted."),
    ("EXCLUDED - obs_effort_index", "csd_effort_features.csv",
     "Deliberately absent. It is the mean of percentile ranks of four columns already in the "
     "model, so it is collinear with its own parts."),
    ("EXCLUDED - CSAT_*", "metadata",
     "All survey-derived. CSAT_ANSWER_CODE correlates with the outcome at Spearman 0.731 and is "
     "the same instrument. They are also populated only on survey rows, so they encode "
     "response itself."),
    ("EXCLUDED - agent_group_name, customer_classification_product/role, status_desc", "metadata",
     "Near-zero variance among respondents (agent group is a single level)."),
]
pd.DataFrame(DD, columns=["column", "source", "meaning"]).to_csv(
    OUTDIR / "effort_model_dictionary.csv", index=False)

print(f"\nwrote {OUT_CSV}  ({df.shape[0]:,} x {df.shape[1]})")
print(f"wrote {OUTDIR / 'effort_model_dictionary.csv'}")
