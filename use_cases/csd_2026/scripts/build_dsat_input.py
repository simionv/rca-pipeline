"""Assemble the DSAT deep-dive population, reading sample and matched controls.

Population is every dissatisfied respondent (CSAT 5-7), split by their effort
answer so that "we made it hard" can be separated from "we said no".

Writes:
    runs/intermediate/csd_dsat_llm_input.csv    ticket id + transcript ONLY
    runs/intermediate/csd_dsat_population.csv   the 286 with all metadata
    runs/intermediate/csd_dsat_sample30.csv     the reading sample
    runs/intermediate/csd_dsat_controls.csv     matched satisfied comparators
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
META = BASE / "data" / "scopus content" / "scopus content_2026_metadata.tsv"
COLL = BASE / "data" / "scopus content" / "scopus content_2026_threads_collapsed.csv"
OBS = BASE / "runs" / "intermediate" / "csd_effort_features.csv"
EFFORT = BASE / "runs" / "output" / "csd_2026_customer_effort_full.xlsx"
TRI = BASE / "runs" / "output" / "csd_2026_effort_triangulation.xlsx"
INT = BASE / "runs" / "intermediate"

SEED = 20260904
N_SAMPLE = 30
MIN_CHARS = 500          # readable as an exchange, not a stub

print("=" * 78)
print("DSAT DEEP DIVE - POPULATION AND SAMPLE")
print("=" * 78)

meta = pd.read_csv(META, sep="\t", dtype=str)
meta["ref"] = meta["incident_reference"].astype(str).str.strip()
meta["csat"] = pd.to_numeric(meta["CSAT_ANSWER_CODE"], errors="coerce")
meta["effort"] = pd.to_numeric(meta["CSAT_EFFORT_CODE"], errors="coerce")
meta["tat_days"] = pd.to_numeric(meta["created_to_closed_days"], errors="coerce")
# Codes 0/8 (CSAT) and 0/6 (effort) are non-responses, not extreme answers. Treating
# ">= 5" as dissatisfied without this filter silently sweeps in "Do not know".
valid = meta["csat"].between(1, 7) & meta["effort"].between(1, 5)
print(f"  metadata {len(meta):,}   both survey questions answered: {int(valid.sum()):,}")

pop = meta[valid & (meta["csat"] >= 5)].copy()
pop["effort_band"] = np.select(
    [pop["effort"] >= 4, pop["effort"] == 3],
    ["hard", "mid"], default="easy")
print(f"  dissatisfied (CSAT 5-7): {len(pop)}   "
      f"{dict(pop['effort_band'].value_counts())}")
assert len(pop) == 286, f"expected 286 dissatisfied respondents, got {len(pop)}"
assert (pop["effort_band"] == "hard").sum() == 206

# ─────────────────────────────────────────────────────────────── transcripts
coll = pd.read_csv(COLL, usecols=["INCIDENT_REF", "Conversation"])
coll["ref"] = coll["INCIDENT_REF"].astype(str).str.strip()
coll = coll.drop_duplicates("ref")
pop = pop.merge(coll[["ref", "Conversation"]], on="ref", how="left")
pop["n_chars"] = pop["Conversation"].astype(str).str.len().where(
    pop["Conversation"].notna(), 0)
print(f"  with a transcript: {int(pop['Conversation'].notna().sum())} of {len(pop)}")

# ───────────────────────────────────────────── existing per-ticket enrichment
obs = pd.read_csv(OBS, usecols=["INCIDENT_REF", "obs_turns", "obs_customer_turns",
                                "obs_agent_handoffs", "obs_span_h"])
obs["ref"] = obs["INCIDENT_REF"].astype(str).str.strip()
eff = pd.read_excel(EFFORT, usecols=["INCIDENT_REF", "effort_score",
                                     "resolution_transparency", "friction_points_1",
                                     "friction_points_2", "friction_points_3",
                                     "effort_evidence"])
eff["ref"] = eff["INCIDENT_REF"].astype(str).str.strip()
tri = pd.read_excel(TRI, sheet_name="tickets",
                    usecols=["INCIDENT_REF", "rule_label", "reason_label"])
tri["ref"] = tri["INCIDENT_REF"].astype(str).str.strip()
for frame, cols in [(obs, ["obs_turns", "obs_customer_turns", "obs_agent_handoffs",
                           "obs_span_h"]),
                    (eff, ["effort_score", "resolution_transparency", "friction_points_1",
                           "friction_points_2", "friction_points_3", "effort_evidence"]),
                    (tri, ["rule_label", "reason_label"])]:
    pop = pop.merge(frame[["ref"] + cols], on="ref", how="left")
print(f"  with an LLM effort record: {int(pop['effort_score'].notna().sum())}   "
      f"with a validation rule: {int(pop['rule_label'].notna().sum())}")

# ═══════════════════════════════════════════════ the reading sample: 30 extreme
extreme = pop[(pop["csat"] == 7) & (pop["effort"] == 5)
              & (pop["n_chars"] >= MIN_CHARS)].copy()
print(f"\n  extreme corner (CSAT 7 + effort 5) with >={MIN_CHARS} chars: {len(extreme)}")
sample = extreme.sample(n=min(N_SAMPLE, len(extreme)), random_state=SEED).copy()
sample = sample.sort_values("n_chars", ascending=False)
print(f"  drawn: {len(sample)}")

# The extreme corner skews to Policy complaints. Report what the draw actually
# contains rather than letting the reader assume it covers every failure mode.
mix = sample["CSAT_DSAT_REASON"].fillna("(not stated)").value_counts()
print("  stated dissatisfaction reason in the drawn sample:")
for k, v in mix.items():
    print(f"    {k}: {v}")
missing_modes = [m for m in ["Policy", "Process/Procedure", "Communication Skills",
                             "Limitation"] if m not in set(mix.index)]
if missing_modes:
    print(f"  NOT REPRESENTED in the 30: {missing_modes} - stated in the deliverable")

# ═══════════════════════════════════════════════════════ matched controls 1:1
satisfied = meta[valid & (meta["csat"] <= 2)].copy()
satisfied = satisfied.merge(coll[["ref", "Conversation"]], on="ref", how="left")
satisfied["n_chars"] = satisfied["Conversation"].astype(str).str.len().where(
    satisfied["Conversation"].notna(), 0)
satisfied = satisfied[satisfied["n_chars"] >= MIN_CHARS]
print(f"\n  satisfied pool (CSAT 1-2, with transcript): {len(satisfied):,}")

rng = np.random.default_rng(SEED)
used: set[str] = set()
rows = []
for _, d in sample.iterrows():
    # Caliper: the wider of +/-1 day or +/-50%, because a 0.2-day ticket and a
    # 20-day ticket need very different tolerances.
    tat = d["tat_days"]
    if pd.isna(tat):
        lo, hi = -np.inf, np.inf
    else:
        w = max(1.0, abs(tat) * 0.5)
        lo, hi = tat - w, tat + w
    cand = satisfied[
        (satisfied["contact_reason_lvl2_desc"] == d["contact_reason_lvl2_desc"])
        & (satisfied["resolution_code_lvl1_desc"] == d["resolution_code_lvl1_desc"])
        & satisfied["tat_days"].between(lo, hi)
        & ~satisfied["ref"].isin(used)]
    tier = "reason+code+TAT"
    if cand.empty:
        # Relax the caliper before relaxing the categorical match - TAT barely
        # tracks satisfaction anyway, so it is the cheapest constraint to drop.
        cand = satisfied[
            (satisfied["contact_reason_lvl2_desc"] == d["contact_reason_lvl2_desc"])
            & (satisfied["resolution_code_lvl1_desc"] == d["resolution_code_lvl1_desc"])
            & ~satisfied["ref"].isin(used)]
        tier = "reason+code, TAT relaxed"
    if cand.empty:
        # Some level-2 reasons have no satisfied ticket anywhere - "Abstract" and
        # "Missing Article(s)" are rare enough that nobody in the pool used them.
        # Fall back to the level-1 family rather than abandoning the pair, and
        # record which tier each match came from so the reader can discount it.
        cand = satisfied[
            (satisfied["contact_reason_lvl1_desc"] == d["contact_reason_lvl1_desc"])
            & (satisfied["resolution_code_lvl1_desc"] == d["resolution_code_lvl1_desc"])
            & ~satisfied["ref"].isin(used)]
        tier = "reason LEVEL 1 + code"
    if cand.empty:
        cand = satisfied[
            (satisfied["resolution_code_lvl1_desc"] == d["resolution_code_lvl1_desc"])
            & ~satisfied["ref"].isin(used)]
        tier = "code only - weakest match"
    if cand.empty:
        rows.append({"dsat_ref": d["ref"], "control_ref": None, "match_tier": "UNMATCHED",
                     "tat_gap_days": np.nan})
        continue
    pick = cand.iloc[int(rng.integers(len(cand)))]
    used.add(pick["ref"])
    rows.append({"dsat_ref": d["ref"], "control_ref": pick["ref"], "match_tier": tier,
                 "tat_gap_days": (abs(pick["tat_days"] - tat)
                                  if pd.notna(tat) and pd.notna(pick["tat_days"])
                                  else np.nan)})

pairs = pd.DataFrame(rows)
print(f"  matched: {dict(pairs['match_tier'].value_counts())}")
print(f"  median TAT gap within pairs: {pairs['tat_gap_days'].median():.2f} days")
n_unmatched = int((pairs["match_tier"] == "UNMATCHED").sum())
n_weak = int(pairs["match_tier"].isin(["reason LEVEL 1 + code",
                                       "code only - weakest match"]).sum())
assert n_unmatched == 0, f"{n_unmatched} pairs could not be matched at any tier"
assert n_weak <= 8, f"{n_weak} pairs matched only at a coarse tier - check the pools"

controls = satisfied[satisfied["ref"].isin(pairs["control_ref"].dropna())].copy()
for frame, cols in [(obs, ["obs_turns", "obs_customer_turns", "obs_agent_handoffs",
                           "obs_span_h"]),
                    (eff, ["effort_score", "resolution_transparency",
                           "friction_points_1", "friction_points_2",
                           "friction_points_3"])]:
    controls = controls.merge(frame[["ref"] + cols], on="ref", how="left")

# ═══════════════════════════════════════════════════ blind LLM input, 286 rows
llm_in = pop.loc[pop["Conversation"].notna(), ["ref", "Conversation"]].copy()
llm_in.columns = ["INCIDENT_REF", "Conversation"]
out_llm = INT / "csd_dsat_llm_input.csv"
llm_in.to_csv(out_llm, index=False)

# Verify blindness against the file as written, not against the frame in memory.
_hdr = pd.read_csv(out_llm, nrows=0).columns.tolist()
assert _hdr == ["INCIDENT_REF", "Conversation"], f"input header leaks columns: {_hdr}"
_txt = " ".join(llm_in["Conversation"].astype(str).head(2000))
for token in ["CSAT_", "Extremely Dissatisfied", "Strongly Disagree", "DSAT_REASON"]:
    assert token not in _txt, f"survey wording '{token}' present in the transcript text"
print(f"\n  blind LLM input: {len(llm_in)} rows, columns {_hdr}  OK")

pop.to_csv(INT / "csd_dsat_population.csv", index=False)
sample.to_csv(INT / "csd_dsat_sample30.csv", index=False)
controls.to_csv(INT / "csd_dsat_controls.csv", index=False)
pairs.to_csv(INT / "csd_dsat_pairs.csv", index=False)
print(f"  wrote population ({len(pop)}), sample ({len(sample)}), "
      f"controls ({len(controls)}), pairs ({len(pairs)})")
