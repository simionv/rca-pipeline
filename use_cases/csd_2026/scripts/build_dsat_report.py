"""Assemble runs/output/csd_2026_dsat_deepdive.xlsx.

Nine sheets answering, in order, the six questions asked: the reading sample and
its matched controls, the structured themes across every dissatisfied ticket, the
handling-process evidence, the OSvC taxonomy, and the TAT-versus-satisfaction test.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

BASE = Path(__file__).resolve().parents[1]
META = BASE / "data" / "scopus content" / "scopus content_2026_metadata.tsv"
OSVC = BASE / "data" / "scopus content" / "resolution codes osvc-Copy.xlsx"
REVIEW = BASE / "runs" / "output" / "csd_2026_dsat_review.xlsx"
INT = BASE / "runs" / "intermediate"
OUT = BASE / "runs" / "output" / "csd_2026_dsat_deepdive.xlsx"

DR = ["dr_asked_for", "dr_we_said", "dr_driver", "dr_easier_how",
      "dr_response_problem", "dr_pending_at_close", "dr_redirected_to", "dr_evidence"]

print("=" * 78)
print("DSAT DEEP DIVE - REPORT")
print("=" * 78)

pop = pd.read_csv(INT / "csd_dsat_population.csv", dtype=str)
pop["ref"] = pop["ref"].astype(str)
for c in ["csat", "effort", "tat_days", "n_chars", "obs_turns", "obs_customer_turns",
          "obs_agent_handoffs", "obs_span_h"]:
    pop[c] = pd.to_numeric(pop[c], errors="coerce")

rev = pd.read_excel(REVIEW, usecols=["INCIDENT_REF"] + DR)
rev["ref"] = rev["INCIDENT_REF"].astype(str).str.strip()
pop = pop.merge(rev[["ref"] + DR], on="ref", how="left")
print(f"  population {len(pop)}   with a structured read: {int(pop['dr_driver'].notna().sum())}")

sample = pd.read_csv(INT / "csd_dsat_sample30.csv", dtype=str)
sample["ref"] = sample["ref"].astype(str)
controls = pd.read_csv(INT / "csd_dsat_controls.csv", dtype=str)
controls["ref"] = controls["ref"].astype(str)
pairs = pd.read_csv(INT / "csd_dsat_pairs.csv", dtype=str)

SHOW = ["ref", "csat", "CSAT_ANSWER_DESC", "effort", "CSAT_EFFORT_DESC",
        "CSAT_DSAT_REASON", "CSAT_REDFLAG_STATUS", "contact_reason_lvl1_desc",
        "contact_reason_lvl2_desc", "resolution_code_lvl1_desc",
        "customer_classification_type", "channel_desc", "tat_days",
        "created_to_initial_response_days", "number_of_responses",
        "obs_turns", "obs_customer_turns", "obs_agent_handoffs",
        "effort_score", "resolution_transparency", "friction_points_1",
        "friction_points_2", "rule_label", "reason_label"]


def view(df, extra=()):
    cols = [c for c in SHOW if c in df.columns] + [c for c in extra if c in df.columns]
    return df[cols + (["Conversation"] if "Conversation" in df.columns else [])]


# ═══════════════════════════════════════════ 1-3 · sample, controls, pairs
s30 = sample.merge(pop[["ref"] + DR], on="ref", how="left")
s30 = s30.merge(pairs.rename(columns={"dsat_ref": "ref"})[["ref", "control_ref",
                                                           "match_tier", "tat_gap_days"]],
                on="ref", how="left")
read30 = view(s30, extra=DR + ["control_ref", "match_tier"])

ctrl = view(controls)

_d = s30.set_index("ref")
_c = controls.set_index("ref")
side_rows = []
for _, pr in pairs.iterrows():
    d = _d.loc[pr["dsat_ref"]] if pr["dsat_ref"] in _d.index else None
    c = _c.loc[pr["control_ref"]] if pr.get("control_ref") in _c.index else None
    if d is None:
        continue
    side_rows.append({
        "pair_match_tier": pr["match_tier"],
        "contact_reason": d.get("contact_reason_lvl2_desc"),
        "resolution_code": d.get("resolution_code_lvl1_desc"),
        "DSAT_ref": pr["dsat_ref"], "DSAT_csat": d.get("CSAT_ANSWER_DESC"),
        "DSAT_effort": d.get("CSAT_EFFORT_DESC"),
        "DSAT_stated_reason": d.get("CSAT_DSAT_REASON"),
        "DSAT_tat_days": d.get("tat_days"), "DSAT_turns": d.get("obs_turns"),
        "DSAT_transparency": d.get("resolution_transparency"),
        "DSAT_what_they_asked": d.get("dr_asked_for"),
        "DSAT_what_we_said": d.get("dr_we_said"),
        "DSAT_driver": d.get("dr_driver"),
        "DSAT_response_problem": d.get("dr_response_problem"),
        "DSAT_easier_how": d.get("dr_easier_how"),
        "CONTROL_ref": pr.get("control_ref"),
        "CONTROL_csat": c.get("CSAT_ANSWER_DESC") if c is not None else None,
        "CONTROL_effort": c.get("CSAT_EFFORT_DESC") if c is not None else None,
        "CONTROL_tat_days": c.get("tat_days") if c is not None else None,
        "CONTROL_turns": c.get("obs_turns") if c is not None else None,
        "CONTROL_transparency": (c.get("resolution_transparency")
                                 if c is not None else None),
        "tat_gap_days": pr.get("tat_gap_days"),
    })
side = pd.DataFrame(side_rows)

# ══════════════════════════════════════════════════════ 4 · themes
def band_table(col):
    # 13 of the 286 have no transcript, so no structured read. Label them rather
    # than letting a NaN row imply a missing category.
    lab = pop[col].fillna("(no transcript - not reviewed)")
    ct = pd.crosstab(lab, pop["effort_band"], dropna=False)
    for b in ["hard", "mid", "easy"]:
        if b not in ct.columns:
            ct[b] = 0
    ct = ct[["hard", "mid", "easy"]]
    ct["total"] = ct.sum(axis=1)
    ct["pct_of_all"] = (ct["total"] / ct["total"].sum()).round(4)
    return ct.sort_values("total", ascending=False).reset_index()


themes = pd.concat([
    band_table("dr_driver").assign(question="What the exchange turned on"),
    band_table("dr_response_problem").assign(question="What in the reply made it worse"),
    band_table("dr_pending_at_close").assign(question="Still outstanding at close"),
], ignore_index=True)
themes = themes.rename(columns={"dr_driver": "value"})
for c in ["dr_response_problem", "dr_pending_at_close"]:
    if c in themes.columns:
        themes["value"] = themes["value"].fillna(themes[c])
        themes = themes.drop(columns=c)
themes = themes[["question", "value", "hard", "mid", "easy", "total", "pct_of_all"]]

# Does the model's read of the reply line up with the customer's own stated reason?
agree = pd.crosstab(pop["dr_response_problem"],
                    pop["CSAT_DSAT_REASON"].fillna("(not stated)")).reset_index()

easier = (pop["dr_easier_how"].fillna("").str.strip().str.lower()
          .replace("", np.nan).dropna().value_counts().head(25).reset_index())
easier.columns = ["suggested change", "tickets"]

redirected = (pop["dr_redirected_to"].fillna("").str.strip()
              .replace("", np.nan).dropna().value_counts().reset_index())
redirected.columns = ["told to contact", "tickets"]

per_ticket = view(pop, extra=DR + ["effort_band"])

# ═══════════════════════════════════════════════ 5 · handling process
meta = pd.read_csv(META, sep="\t", dtype=str)
meta["tat"] = pd.to_numeric(meta["created_to_closed_days"], errors="coerce")
meta["nresp"] = pd.to_numeric(meta["number_of_responses"], errors="coerce")
grp = meta.groupby("agent_group_name").agg(
    tickets=("incident_reference", "size"),
    with_csat=("CSAT_ANSWER_CODE", lambda s: pd.to_numeric(s, errors="coerce")
               .between(1, 7).sum()),
    median_days_to_close=("tat", "median")).sort_values("tickets", ascending=False)
grp = grp.reset_index()

pending_yes = int((pop["dr_pending_at_close"] == "yes").sum())
handling = pd.DataFrame([
    ("Documented process (CheatSheet 'OSVC Best Practices - Status')",
     "Parent incident stays 'In progress' while a Task sits with 2LS; only after "
     "'Confirmed Completed - YES' does the flow say respond then Solve."),
    ("What the extract can show", "Terminal states only. status_desc is Solved 57,815 / "
     "Closed 61, and every row has a close timestamp."),
    ("What is missing", "The two places pending work would appear are both absent: "
     "THREAD_ENTRY_TYPE has only Staff Account / Customer / Customer Proxy with no note "
     "type, and INCIDENT_TYPE is constant 'Incident' so child Tasks are not exported."),
    ("Tickets ending in a 2LS group", "600 of 57,876 (1.0%); only 1 of them has a CSAT "
     "response, so the survey is effectively blind to escalated work."),
    ("Tickets LLM-flagged 'Escalation required'", "5,890"),
    ("Tickets LLM-flagged 'Redirected to another party'", "6,167"),
    ("Reading of that gap", "Escalation and redirect language appears roughly ten times "
     "more often than a ticket actually ends with a 2LS group. Properly escalated work "
     "carries an 'Out' action code (Sent to Supplier-*) and is absent from this corpus "
     "entirely, so the gap most likely reflects customers being told to pursue it "
     "themselves rather than internal escalation going unrecorded."),
    ("Tickets closed with no agent response at all", "1,337"),
    (f"Structured read: something still outstanding at close",
     f"{pending_yes} of {int(pop['dr_pending_at_close'].notna().sum())} dissatisfied "
     f"tickets ({pending_yes / max(1, int(pop['dr_pending_at_close'].notna().sum())):.0%}). "
     f"The remaining 90% were concluded - by a refusal."),
    ("Median days to close, 1LS vs 2LS", "1LS 2.34 days; Scopus Gen CHN 2LS 11.70 days; "
     "AFT ~26 days."),
], columns=["item", "finding"])

# ══════════════════════════════════════════════════════ 6 · OSvC taxonomy
tree = (meta.groupby(["contact_reason_lvl1_desc", "contact_reason_lvl2_desc"])
        .size().reset_index(name="tickets")
        .sort_values(["tickets"], ascending=False))

osvc = pd.read_excel(OSVC, sheet_name="Sheet1", header=1)
osvc = osvc.dropna(subset=[osvc.columns[1]])
flagcols = list(osvc.columns[4:7])
codes = osvc[[osvc.columns[0], osvc.columns[1], 2025, 2026] + flagcols].copy()
codes.columns = (["in_out", "resolution_code", "vol_2025", "vol_2026_partial"]
                 + ["flag_coverage_policy", "flag_capturing_guideline", "flag_process"])
live = meta["resolution_code_lvl1_desc"].value_counts().rename("tickets_in_corpus")
codes["tickets_in_corpus"] = codes["resolution_code"].map(live)

cats = []
for col in ["customer_classification_role", "customer_classification_type",
            "customer_classification_product", "channel_desc", "agent_group_name",
            "status_desc"]:
    vc = meta[col].value_counts()
    for k, v in vc.items():
        cats.append({"field": col, "value": k, "tickets": v})
categories = pd.DataFrame(cats)

# ═════════════════════════════════════════════ 7 · TAT vs satisfaction
meta["csat"] = pd.to_numeric(meta["CSAT_ANSWER_CODE"], errors="coerce")
meta["eff"] = pd.to_numeric(meta["CSAT_EFFORT_CODE"], errors="coerce")
rows = []
for lab, col, rng in [("CSAT (1 best .. 7 worst)", "csat", range(1, 8)),
                      ("Effort (1 easy .. 5 hard)", "eff", range(1, 6))]:
    for k in rng:
        s = meta.loc[meta[col] == k, "tat"]
        rows.append({"scale": lab, "code": k, "n": len(s),
                     "median_days": round(s.median(), 2),
                     "mean_days": round(s.mean(), 2),
                     "p90_days": round(s.quantile(0.9), 2)})
tat = pd.DataFrame(rows)

_a = meta[meta["csat"].between(1, 7)]
_b = meta[meta["eff"].between(1, 5)]
r1 = spearmanr(_a["csat"], _a["tat"], nan_policy="omit")
r2 = spearmanr(_b["eff"], _b["tat"], nan_policy="omit")
tat_test = pd.DataFrame([
    ("Spearman, TAT vs CSAT code", round(r1.statistic, 4), f"{r1.pvalue:.2g}", len(_a)),
    ("Spearman, TAT vs effort code", round(r2.statistic, 4), f"{r2.pvalue:.2g}", len(_b)),
], columns=["test", "rho", "p_value", "n"])
verdict = pd.DataFrame([(
    "Verdict",
    f"DSAT does NOT meaningfully track turnaround. Both correlations are about 0.06 - "
    f"detectable only because n is large, explaining well under 1% of variance. Medians "
    f"move from 2.1 to 3.3 days across the whole satisfaction range; the mean gap is a "
    f"right tail of outliers. Independently corroborated by the customers themselves: "
    f"only 3 of 206 dissatisfied-and-high-effort respondents chose 'Delayed Response' as "
    f"their reason.")], columns=["item", "finding"])

DD = [
    ("Population", "286 respondents with CSAT 5-7 and a valid effort answer: 206 who "
     "found it hard (effort 4-5), 31 mid, 49 who found it easy. 273 have a transcript "
     "and carry a structured read."),
    ("read_these_30", "Drawn from the 92 tickets at CSAT 7 + effort 5 with at least 500 "
     "characters of transcript, seed 20260904. Stated-reason mix: Policy 10, "
     "Process/Procedure 9, not stated 5, Limitation 4, Communication Skills 1, "
     "Delayed response 1 - all four failure modes represented."),
    ("matched_controls", "One CSAT 1-2 ticket per DSAT ticket. 25 matched on contact "
     "reason level 2 + resolution code + a TAT caliper; 1 with the caliper relaxed; 4 at "
     "contact reason level 1 because no satisfied ticket exists with that level-2 reason. "
     "match_tier records which."),
    ("dr_* fields", "A structured read of the transcript by an LLM that never saw the "
     "CSAT score, the effort answer or the stated reason - the input file carried ticket "
     "id and transcript only, asserted against the file on disk."),
    ("dr_driver", "What the exchange turned on. Note only 1 ticket was coded 'how it was "
     "explained' even though 123 were coded 'no reason given' on the wording field - the "
     "driver field anchors on the substantive dispute, so read it alongside "
     "dr_response_problem rather than instead of it."),
    ("dr_easier_how", "Deliberately permits 'nothing - the process was already direct' so "
     "the field cannot manufacture improvements. That answer is common and is correct."),
    ("Survey coverage", "3,227 of 57,876 tickets (5.6%) answered both survey questions, "
     "and respondents are self-selected."),
    ("CSAT and effort are not independent", "They correlate at Spearman 0.731, so the "
     "hard/easy split separates degrees of the same reaction more than two distinct ones."),
    ("Half the outcome space is absent", "All 15 resolution codes here begin 'Invalid-'. "
     "The OSvC reference lists 74 'Out' action codes - Sent to Supplier-Missing article "
     "(10,779 in 2026), Correction Tool used (9,511) - none of which appear. No actioned "
     "ticket is available for comparison."),
    ("Corpus period", "Close dates 2026-01-01 to 2026-07-31 - seven months, not a year."),
]

# ═══════════════════════ 8 · satisfied DESPITE high effort - the mirror image
# Only 13 tickets in the whole corpus are satisfied (CSAT 1-2) AND hard (effort
# 4-5), so 30 cannot be drawn from that cell alone. The sample is banded and every
# row says which band it came from.
SAT = INT / "csd_sathigh_sample30.csv"
SAT_REVIEW = BASE / "runs" / "output" / "csd_2026_sathigh_review.xlsx"
sat = pd.read_csv(SAT, dtype=str)
sat["ref"] = sat["ref"].astype(str)
for c in ["csat", "effort", "tat_days", "obs_turns", "obs_customer_turns",
          "obs_agent_handoffs"]:
    sat[c] = pd.to_numeric(sat[c], errors="coerce")
_sr = pd.read_excel(SAT_REVIEW, usecols=["INCIDENT_REF"] + DR)
_sr["ref"] = _sr["INCIDENT_REF"].astype(str).str.strip()
sat = sat.merge(_sr[["ref"] + DR], on="ref", how="left")
sat_view = view(sat, extra=["band"] + DR)

# Bands A and B are the genuinely-hard cells; C is filler to reach 30 and is
# excluded from the comparison so it cannot flatter the contrast.
sat_core = sat[sat["band"].str.startswith(("A", "B"))]
dsat_hard = pop[pop["effort_band"] == "hard"]


def _share(frame, col, val):
    s = frame[col].dropna()
    return round((s == val).mean(), 4) if len(s) else np.nan


def _friction_share(frame, val):
    cols = [c for c in ["friction_points_1", "friction_points_2", "friction_points_3"]
            if c in frame.columns]
    hit = pd.Series(False, index=frame.index)
    for c in cols:
        hit |= frame[c].astype(str).str.strip().eq(val)
    return round(hit.mean(), 4)


rows = [("n", len(sat_core), len(dsat_hard))]
for lab, col, val in [
        ("LLM scored the ticket high effort", "effort_score", "high"),
        ("Reply opaque", "resolution_transparency", "opaque"),
        ("Reply transparent", "resolution_transparency", "transparent"),
        ("Reply gave no reason (structured read)", "dr_response_problem",
         "no reason given"),
        ("Nothing wrong with the reply", "dr_response_problem", "nothing wrong"),
        ("Exchange turned on the decision", "dr_driver", "the decision itself"),
        ("Exchange turned on the process", "dr_driver", "the process")]:
    rows.append((lab, _share(sat_core, col, val), _share(dsat_hard, col, val)))
for f in ["Repeated issue explanation", "Slow response / long wait",
          "Redirected to another party", "Escalation required",
          "Lack of transparency"]:
    rows.append((f"Friction: {f}", _friction_share(sat_core, f),
                 _friction_share(dsat_hard, f)))
compare = pd.DataFrame(rows, columns=["measure", "satisfied_despite_hard",
                                      "dissatisfied_and_hard"])

with pd.ExcelWriter(OUT, engine="openpyxl") as xl:
    read30.to_excel(xl, sheet_name="read_these_30", index=False)
    sat_view.to_excel(xl, sheet_name="read_these_30_satisfied", index=False)
    compare.to_excel(xl, sheet_name="satisfied_vs_dsat", index=False)
    side.to_excel(xl, sheet_name="side_by_side", index=False)
    ctrl.to_excel(xl, sheet_name="matched_controls", index=False)
    themes.to_excel(xl, sheet_name="themes_all_273", index=False)
    agree.to_excel(xl, sheet_name="llm_vs_customer_reason", index=False)
    easier.to_excel(xl, sheet_name="what_would_be_easier", index=False)
    redirected.to_excel(xl, sheet_name="told_to_contact", index=False)
    per_ticket.to_excel(xl, sheet_name="per_ticket_286", index=False)
    handling.to_excel(xl, sheet_name="handling_process", index=False)
    grp.to_excel(xl, sheet_name="agent_groups", index=False)
    tree.to_excel(xl, sheet_name="tax_contact_reasons", index=False)
    codes.to_excel(xl, sheet_name="tax_resolution_codes", index=False)
    categories.to_excel(xl, sheet_name="tax_other_fields", index=False)
    pd.concat([tat_test, verdict.rename(columns={"item": "test", "finding": "rho"})],
              ignore_index=True).to_excel(xl, sheet_name="tat_vs_satisfaction_test",
                                          index=False)
    tat.to_excel(xl, sheet_name="tat_by_score", index=False)
    pd.DataFrame(DD, columns=["item", "note"]).to_excel(
        xl, sheet_name="data_dictionary", index=False)

assert len(read30) == 30 and len(ctrl) == 30 and len(side) == 30
assert len(sat_view) == 30, f"satisfied sample is {len(sat_view)}, expected 30"
assert len(per_ticket) == 286
print(f"\nwrote {OUT}")
print(f"  sample {len(read30)} | pairs {len(side)} | population {len(per_ticket)} | "
      f"themes {len(themes)} rows")
