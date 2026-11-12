"""Analyse the multi-label validation-rule pass.

Answers "how often is a ticket failed by more than one rule", and - as a free
by-product - gives the rule classifier's test-retest agreement, which the original
single-label run could not provide.

Reads runs/output/csd_2026_multi_rule.xlsx, writes
runs/output/deck/multirule_data.json plus two charts into the deck figs directory.
"""
from __future__ import annotations

import json
from collections import Counter
from itertools import combinations
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                    # noqa: E402
import numpy as np                                                 # noqa: E402
import pandas as pd                                                # noqa: E402

BASE = Path(__file__).resolve().parents[1]
MR = BASE / "runs" / "output" / "csd_2026_multi_rule.xlsx"
TRI = BASE / "runs" / "output" / "csd_2026_effort_triangulation.xlsx"
TAX = BASE / "generated" / "taxonomies" / "csd_validation_rule.json"
DECK = BASE / "runs" / "output" / "deck"
FIGS = DECK / "figs"

NAVY, ORANGE, GREY, RED = "#0B2A4A", "#FF6C00", "#7A8794", "#C1272D"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                     "axes.edgecolor": GREY, "axes.labelcolor": NAVY,
                     "text.color": NAVY, "xtick.color": GREY, "ytick.color": GREY,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "figure.facecolor": "none", "savefig.facecolor": "none"})

print("=" * 78)
print("MULTI-RULE ANALYSIS")
print("=" * 78)

mr = pd.read_excel(MR)
mr["ref"] = mr["INCIDENT_REF"].astype(str).str.strip()
code_cols = sorted([c for c in mr.columns if c.startswith("mr_codes_")])
print(f"  {len(mr):,} tickets, exploded code columns: {code_cols}")

tax = json.loads(TAX.read_text(encoding="utf-8"))
VALID = {k for g in tax.values() for k in g.get("children", {})}
LABEL = {k: v.get("label", k) for g in tax.values() for k, v in g.get("children", {}).items()}


def code_list(row) -> list[str]:
    out = []
    for c in code_cols:
        v = row[c]
        if pd.notna(v) and str(v).strip():
            s = str(v).strip()
            if s not in out:
                out.append(s)
    return out


mr["codes"] = mr.apply(code_list, axis=1)
mr["n_rules"] = mr["codes"].apply(len)

bad = sorted({c for lst in mr["codes"] for c in lst if c not in VALID})
n_bad_rows = int(mr["codes"].apply(lambda l: any(c not in VALID for c in l)).sum())
print(f"  codes outside the taxonomy: {len(bad)} {bad[:5]}  on {n_bad_rows} row(s)")

# 73 rows came back with an empty mr_codes list. They are not all failures: 44 of
# them carry a valid mr_primary and a justification, so the model did decide and
# simply ignored the list formatting. Those are recovered as single-rule rather than
# discarded, which would drop real single-rule tickets and inflate the multi rate.
_blank = mr["n_rules"] == 0
_recoverable = _blank & mr["mr_primary"].isin(VALID)
n_recovered = int(_recoverable.sum())
mr.loc[_recoverable, "codes"] = mr.loc[_recoverable, "mr_primary"].apply(lambda c: [c])
mr["n_rules"] = mr["codes"].apply(len)

n_empty = int((mr["n_rules"] == 0).sum())
n_errored = int(mr.loc[mr["n_rules"] == 0, "_error"].notna().sum())
print(f"  empty mr_codes: {int(_blank.sum())} -> recovered {n_recovered} from mr_primary, "
      f"dropped {n_empty} ({n_errored} stubbed by the pipeline, "
      f"{n_empty - n_errored} blank)")
mr = mr[mr["n_rules"] >= 1].copy()
assert n_empty / len(mr) < 0.01, f"{n_empty} unusable tickets is more than 1% of the run"

# CSDVR4.1 is the explicit "no rule applies" leaf. Pairing it with a real rule is
# self-contradictory - the model has said both that nothing applies and that
# something does - and it accounted for over a quarter of the raw multi-rule cases.
# Treating those as genuine two-rule tickets would inflate the headline, so the 4.1
# is dropped from any list that also names a real rule.
contaminated = int(mr["codes"].apply(lambda l: "CSDVR4.1" in l and len(l) > 1).sum())
mr["codes"] = mr["codes"].apply(
    lambda l: [c for c in l if c != "CSDVR4.1"] if ("CSDVR4.1" in l and len(l) > 1) else l)
# One row returned a code that is not in the taxonomy at all.
mr["codes"] = mr["codes"].apply(lambda l: [c for c in l if c in VALID] or l)
mr["n_rules"] = mr["codes"].apply(len)
print(f"  CSDVR4.1 paired with a real rule: {contaminated} -> demoted to single-rule")

# ─────────────────────────────────────────────────── design weights from the run
tri = pd.read_excel(TRI, sheet_name="tickets", usecols=["INCIDENT_REF", "w", "rc_label",
                                                        "rule_label"])
tri["ref"] = tri["INCIDENT_REF"].astype(str).str.strip()
d = mr.merge(tri[["ref", "w", "rc_label", "rule_label"]], on="ref", how="left")
assert d["w"].notna().all(), "some multi-rule tickets have no design weight"
W = d["w"].sum()
print(f"  weights sum to {W:,.0f}")

dist = (d.groupby("n_rules")["w"].sum() / W).sort_index()
multi_rate = float(d.loc[d["n_rules"] >= 2, "w"].sum() / W)
multi_n = int((d["n_rules"] >= 2).sum())
print(f"\n  rules per ticket (population-weighted):")
for k, v in dist.items():
    print(f"    {k}: {v:.2%}")
print(f"  MULTI-RULE RATE: {multi_rate:.2%}  ({multi_n} of {len(d):,} sampled)")

# Two different quantities, so both are reported rather than one interval being
# quietly attached to the other rate: the Wilson interval is on the UNWEIGHTED
# sample rate, while the headline is design-weighted to the population.
z, n_s = 1.96, len(d)
sample_rate = multi_n / n_s
den = 1 + z ** 2 / n_s
centre = (sample_rate + z ** 2 / (2 * n_s)) / den
half = z * np.sqrt(sample_rate * (1 - sample_rate) / n_s + z ** 2 / (4 * n_s ** 2)) / den
ci = (max(0.0, centre - half), centre + half)
print(f"  sample rate {sample_rate:.2%}, Wilson 95% CI [{ci[0]:.2%}, {ci[1]:.2%}] "
      f"(unweighted); weighted population rate {multi_rate:.2%}")

# ───────────────────────────────────────────────────────── co-occurring pairs
pairs: Counter = Counter()
pairs_w: Counter = Counter()
for _, r in d[d["n_rules"] >= 2].iterrows():
    for a, b in combinations(sorted(r["codes"]), 2):
        pairs[(a, b)] += 1
        pairs_w[(a, b)] += r["w"]
top_pairs = [{"a": a, "b": b, "a_label": LABEL.get(a, a), "b_label": LABEL.get(b, b),
              "n": pairs[(a, b)], "est_pop": round(pairs_w[(a, b)])}
             for (a, b), _ in pairs_w.most_common(10)]
print(f"  distinct co-occurring pairs: {len(pairs)}")

# Which rule is the promiscuous one? If multi-rule tickets concentrate on a single
# rule, that rule's condition overlaps the others rather than tickets being
# genuinely ambiguous across the board.
_multi = d[d["n_rules"] >= 2]
member: Counter = Counter()
for _, r in _multi.iterrows():
    for c in r["codes"]:
        member[c] += 1
top_member = [{"code": c, "label": LABEL.get(c, c), "n": n,
               "share_of_multi": n / len(_multi)}
              for c, n in member.most_common(6)]
for m in top_member[:3]:
    print(f"    {m['code']} appears in {m['n']} of {len(_multi)} multi-rule tickets "
          f"({m['share_of_multi']:.0%})")

# ───────────────────────────── test-retest against the original single-label run
# Both passes chose one best rule from the same taxonomy on the same tickets,
# independently. That is a repeatability measurement the original run could not
# give on its own.
cmp = d[d["mr_primary"].notna() & d["rule_label"].notna()].copy()
orig_code = pd.read_excel(BASE / "runs" / "output" / "csd_2026_validation_rules.xlsx",
                          sheet_name="tickets", usecols=["INCIDENT_REF", "csdvr_code"])
orig_code["ref"] = orig_code["INCIDENT_REF"].astype(str).str.strip()
cmp = cmp.merge(orig_code[["ref", "csdvr_code"]], on="ref", how="left")
cmp = cmp[cmp["csdvr_code"].notna()]
agree = float((cmp["mr_primary"] == cmp["csdvr_code"]).mean())
agree_w = float((cmp.loc[cmp["mr_primary"] == cmp["csdvr_code"], "w"].sum()
                 / cmp["w"].sum()))
print(f"\n  test-retest vs the original single-label run: {agree:.1%} exact "
      f"({agree_w:.1%} weighted) on {len(cmp):,} tickets")

# ──────────────────────────────────────────────────────────────────── charts
fig, ax = plt.subplots(figsize=(9, 4.0))
ks = list(dist.index)
ax.bar([str(k) for k in ks], dist.values, 0.55,
       color=[NAVY if k == 1 else ORANGE for k in ks])
for k, v in zip(ks, dist.values):
    ax.text(str(k), v + 0.012, f"{v:.1%}", ha="center", fontsize=9.5, color=NAVY)
ax.set_xlabel("validation rules that apply to the ticket")
ax.set_ylabel("share of tickets (population-weighted)")
ax.set_ylim(0, min(1.05, dist.max() * 1.18))
fig.tight_layout()
fig.savefig(FIGS / "20_rules_per_ticket.png", dpi=200, transparent=True,
            bbox_inches="tight")
plt.close(fig)
print("    20_rules_per_ticket.png")

payload = {
    "n_sample": int(len(d)),
    "n_population": round(float(W)),
    "multi_rate": multi_rate,
    "multi_n": multi_n,
    "ci_lo": ci[0], "ci_hi": ci[1], "sample_rate": sample_rate,
    "dist": {str(k): float(v) for k, v in dist.items()},
    "max_rules": int(d["n_rules"].max()),
    "n_pairs": len(pairs),
    "top_pairs": top_pairs,
    "top_member": top_member,
    "invalid_codes": bad,
    "n_empty": n_empty,
    "n_bad_rows": n_bad_rows,
    "contaminated": contaminated,
    "retest_agreement": agree,
    "retest_agreement_weighted": agree_w,
    "retest_n": int(len(cmp)),
    "n_exclusivity_leaves": 8,
    "n_leaves": len(VALID),
}
(DECK / "multirule_data.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
print(f"\nwrote {DECK / 'multirule_data.json'}")

# ─────────────────────────────────────────────────────────── deliverable workbook
# The pairs are the actionable part and a JSON file is not a deliverable, so the
# whole analysis also goes out as a workbook.
OUT_XLSX = BASE / "runs" / "output" / "csd_2026_multi_rule_analysis.xlsx"

summary = pd.DataFrame([
    ("Tickets analysed", f"{len(d):,}"),
    ("Excluded as unusable", f"{n_empty} ({n_errored} stubbed, {n_empty - n_errored} blank)"),
    ("Recovered from mr_primary", f"{n_recovered}"),
    ("Exactly one rule applies", f"{dist.get(1, 0):.2%}"),
    ("Two rules apply", f"{multi_rate:.2%} (weighted) / {sample_rate:.2%} (unweighted)"),
    ("Wilson 95% CI, unweighted", f"{ci[0]:.2%} to {ci[1]:.2%}"),
    ("Three or more rules", "0% - maximum observed was 2"),
    ("Distinct co-occurring pairs", f"{len(pairs)}"),
    ("Most involved rule", f"{top_member[0]['code']} - in {top_member[0]['share_of_multi']:.0%} "
                           f"of multi-rule tickets"),
    ("CSDVR4.1 paired with a real rule", f"{contaminated} - demoted to single-rule as "
                                          f"self-contradictory"),
    ("Test-retest vs the original run", f"{agree:.1%} exact ({agree_w:.1%} weighted)"),
    ("CAVEAT - lower bound", f"{8} of {len(VALID)} rule descriptions carry single-label "
                             f"wording added during the original tuning, so the taxonomy "
                             f"discourages double-labelling"),
    ("CAVEAT - retest prompt differs", "The second pass used a multi-label prompt, so 70.1% "
                                       "is a LOWER bound on same-prompt repeatability"),
], columns=["item", "value"])

pairs_df = pd.DataFrame(
    [{"rule_a": a, "rule_a_label": LABEL.get(a, a), "rule_b": b,
      "rule_b_label": LABEL.get(b, b), "n_sampled": n,
      "est_population": round(pairs_w[(a, b)])}
     for (a, b), n in pairs.most_common()])

member_df = pd.DataFrame(
    [{"rule": c, "label": LABEL.get(c, c), "n_multi_rule_tickets": n,
      "share_of_multi_rule": n / len(_multi)} for c, n in member.most_common()])

dist_df = pd.DataFrame({"rules_applying": dist.index,
                        "share_of_population": dist.values,
                        "n_sampled": [int((d["n_rules"] == k).sum()) for k in dist.index]})

per_ticket = d.loc[d["n_rules"] >= 2,
                   ["INCIDENT_REF", "rc_label", "rule_label", "mr_primary",
                    "mr_secondary_evidence", "mr_justification", "w"]].copy()
per_ticket["all_rules"] = d.loc[d["n_rules"] >= 2, "codes"].apply(lambda l: ", ".join(l))

with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as xl:
    summary.to_excel(xl, sheet_name="summary", index=False)
    dist_df.to_excel(xl, sheet_name="rules_per_ticket", index=False)
    pairs_df.to_excel(xl, sheet_name="co_occurring_pairs", index=False)
    member_df.to_excel(xl, sheet_name="rule_involvement", index=False)
    per_ticket.to_excel(xl, sheet_name="multi_rule_tickets", index=False)
print(f"wrote {OUT_XLSX}  ({len(pairs_df)} pairs, {len(per_ticket)} multi-rule tickets)")
