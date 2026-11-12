"""Sample of tickets where the customer was satisfied DESPITE reporting high effort.

The pure cell - satisfied (CSAT 1-2) and hard (effort 4-5) - contains only 13
tickets in the whole corpus, so 30 cannot be drawn from it. The sample is banded
and every row carries its band, so a reader can discard the weaker tiers.

    A  satisfied 1-2  x  hard 4-5      13   happy despite genuine difficulty
    B  satisfied 3    x  hard 4-5      11   positive despite genuine difficulty
    C  satisfied 1-2  x  neutral 3      6   happy, effort neither easy nor hard

Writes runs/intermediate/csd_sathigh_sample30.csv and the blind LLM input.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
META = BASE / "data" / "scopus content" / "scopus content_2026_metadata.tsv"
COLL = BASE / "data" / "scopus content" / "scopus content_2026_threads_collapsed.csv"
OBS = BASE / "runs" / "intermediate" / "csd_effort_features.csv"
EFFORT = BASE / "runs" / "output" / "csd_2026_customer_effort_full.xlsx"
TRI = BASE / "runs" / "output" / "csd_2026_effort_triangulation.xlsx"
INT = BASE / "runs" / "intermediate"

SEED = 20260909
MIN_CHARS = 500

print("=" * 78)
print("SATISFIED-BUT-HIGH-EFFORT SAMPLE")
print("=" * 78)

meta = pd.read_csv(META, sep="\t", dtype=str)
meta["ref"] = meta["incident_reference"].astype(str).str.strip()
meta["csat"] = pd.to_numeric(meta["CSAT_ANSWER_CODE"], errors="coerce")
meta["effort"] = pd.to_numeric(meta["CSAT_EFFORT_CODE"], errors="coerce")
meta["tat_days"] = pd.to_numeric(meta["created_to_closed_days"], errors="coerce")
ok = meta["csat"].between(1, 7) & meta["effort"].between(1, 5)

coll = pd.read_csv(COLL, usecols=["INCIDENT_REF", "Conversation"])
coll["ref"] = coll["INCIDENT_REF"].astype(str).str.strip()
coll = coll.drop_duplicates("ref")
meta = meta.merge(coll[["ref", "Conversation"]], on="ref", how="left")
meta["n_chars"] = meta["Conversation"].astype(str).str.len().where(
    meta["Conversation"].notna(), 0)

N_TARGET = 30
BANDS = [
    ("A - satisfied, genuinely hard", ok & meta["csat"].between(1, 2)
     & meta["effort"].between(4, 5)),
    ("B - positive, genuinely hard", ok & (meta["csat"] == 3)
     & meta["effort"].between(4, 5)),
    ("C - satisfied, effort neutral", ok & meta["csat"].between(1, 2)
     & (meta["effort"] == 3)),
]

parts = []
for i, (label, mask) in enumerate(BANDS):
    band = meta[mask & (meta["n_chars"] >= MIN_CHARS)].copy()
    in_corpus, with_text = int(mask.sum()), len(band)
    # A and B are taken whole - they are the scarce, interesting cells. C is the
    # filler and is capped at whatever is still needed to reach 30.
    if i == len(BANDS) - 1:
        need = max(0, N_TARGET - sum(len(p) for p in parts))
        if len(band) > need:
            band = band.sample(n=need, random_state=SEED)
    band["band"] = label
    parts.append(band)
    print(f"  {label:32s} in corpus {in_corpus:4d}   with transcript "
          f"{with_text:4d}   taken {len(band)}")

sample = pd.concat(parts, ignore_index=True).sort_values(
    ["band", "csat", "effort"], ascending=[True, True, False])
print(f"\n  sample: {len(sample)}")

# ─────────────────────────────────────── attach the existing per-ticket enrichment
obs = pd.read_csv(OBS, usecols=["INCIDENT_REF", "obs_turns", "obs_customer_turns",
                                "obs_agent_handoffs", "obs_span_h"])
obs["ref"] = obs["INCIDENT_REF"].astype(str).str.strip()
eff = pd.read_excel(EFFORT, usecols=["INCIDENT_REF", "effort_score",
                                     "resolution_transparency", "friction_points_1",
                                     "friction_points_2", "friction_points_3"])
eff["ref"] = eff["INCIDENT_REF"].astype(str).str.strip()
tri = pd.read_excel(TRI, sheet_name="tickets",
                    usecols=["INCIDENT_REF", "rule_label", "reason_label"])
tri["ref"] = tri["INCIDENT_REF"].astype(str).str.strip()
for frame, cols in [(obs, ["obs_turns", "obs_customer_turns", "obs_agent_handoffs",
                           "obs_span_h"]),
                    (eff, ["effort_score", "resolution_transparency",
                           "friction_points_1", "friction_points_2",
                           "friction_points_3"]),
                    (tri, ["rule_label", "reason_label"])]:
    sample = sample.merge(frame[["ref"] + cols], on="ref", how="left")

print(f"  with an LLM effort record: {int(sample['effort_score'].notna().sum())}")
print(f"  median TAT {sample['tat_days'].median():.2f} days   "
      f"median turns {sample['obs_turns'].median():.0f}")

llm_in = sample[["ref", "Conversation"]].copy()
llm_in.columns = ["INCIDENT_REF", "Conversation"]
out_llm = INT / "csd_sathigh_llm_input.csv"
llm_in.to_csv(out_llm, index=False)
_hdr = pd.read_csv(out_llm, nrows=0).columns.tolist()
assert _hdr == ["INCIDENT_REF", "Conversation"], f"input header leaks: {_hdr}"
print(f"  blind LLM input: {len(llm_in)} rows, columns {_hdr}  OK")

sample.to_csv(INT / "csd_sathigh_sample30.csv", index=False)
assert len(sample) == 30, f"expected 30, built {len(sample)}"
print(f"  wrote {INT / 'csd_sathigh_sample30.csv'}")
