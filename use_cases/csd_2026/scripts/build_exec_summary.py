"""Charts and figures for the 3-slide executive summary.

Everything here is a re-presentation of numbers already produced and verified in
scripts/build_rule_scorecard.py and scripts/effort_model.R. Nothing is recomputed,
so the exec slides cannot drift from the detailed decks.

Writes runs/output/exec/figs/*.png and runs/output/exec/exec_data.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                    # noqa: E402
import numpy as np                                                 # noqa: E402

BASE = Path(__file__).resolve().parents[1]
SC = json.loads((BASE / "runs" / "output" / "scorecard" / "scorecard_data.json")
                .read_text(encoding="utf-8"))
MD = json.loads((BASE / "runs" / "output" / "model" / "model_results.json")
                .read_text(encoding="utf-8"))
OUT = BASE / "runs" / "output" / "exec"
FIGS = OUT / "figs"
FIGS.mkdir(parents=True, exist_ok=True)

NAVY, ORANGE, GREY = "#0B2A4A", "#FF6C00", "#7A8794"
RED, GREEN = "#C1272D", "#2E7D5B"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                     "axes.edgecolor": GREY, "axes.labelcolor": NAVY,
                     "text.color": NAVY, "xtick.color": GREY, "ytick.color": GREY,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "figure.facecolor": "none", "savefig.facecolor": "none"})

SUM = {r["model"]: r for r in MD["summary"]}
COEF = {c["term"]: c for c in MD["coefficients"] if c["model"] == "S1"}
BLOCKS = {b["comparison"]: b for b in MD["blocks"]}


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIGS / f"{name}.png", dpi=220, transparent=True, bbox_inches="tight")
    plt.close(fig)
    print(f"    {name}.png")


# ══════════════════════════════════════════ 1 · what drives customer effort
# Odds ratios restated as "x times more likely to say it was not easy", which is
# the only framing of a logistic coefficient a non-specialist audience can use.
DRIVERS = [
    ("What we tell them", "We say the title was discontinued",
     "resolution_codeInvalid- discontinued title"),
    ("What we tell them", "We say the title was never covered",
     "resolution_codeInvalid- Title not covered"),
    ("What we tell them", "We say the source is not authentic",
     "resolution_codeInvalid- not authentic"),
    ("What we tell them", "We say the journal is under re-evaluation",
     "resolution_codeInvalid- reevaluation"),
    ("How we handled it", "Each extra day to close", "log_tat_days"),
    ("How we handled it", "Each extra reply we send", "obs_responses"),
    ("How we handled it", "Passing it to a second agent", "obs_agent_handoffs"),
]
rows = [(grp, lab, COEF[t]["odds_ratio"], COEF[t]["or_lo"], COEF[t]["or_hi"])
        for grp, lab, t in DRIVERS if t in COEF]
rows.sort(key=lambda r: r[2])

fig, ax = plt.subplots(figsize=(11.2, 5.0))
y = np.arange(len(rows))
cols = [GREEN if r[2] < 1 else RED for r in rows]
for i, (_, _, orr, lo, hi) in enumerate(rows):
    ax.hlines(i, lo, hi, color=cols[i], lw=2.2, alpha=.35)
ax.scatter([r[2] for r in rows], y, s=150, color=cols, zorder=3)
for i, (_, _, orr, lo, hi) in enumerate(rows):
    # Outside the marker, past the interval, so nothing is clipped by the dot.
    ax.annotate(f"{orr:.1f}x" if orr >= 1 else f"{orr:.2f}x",
                (hi, i), textcoords="offset points", xytext=(9, -4),
                ha="left", fontsize=12, color=cols[i], fontweight="bold")
ax.axvline(1, color=NAVY, ls="--", lw=1.4)
ax.set_yticks(y)
ax.set_yticklabels([r[1] for r in rows], fontsize=11)
ax.set_xscale("log")
ax.set_xticks([0.5, 1, 2, 4, 8])
ax.set_xticklabels(["half as\nlikely", "no\nchange", "2x", "4x", "8x"], fontsize=10)
ax.set_xlabel("How much more likely the customer is to say it was NOT easy", fontsize=11)
ax.text(0.62, len(rows) - 0.35, "EASIER", color=GREEN, fontsize=11, fontweight="bold")
ax.text(4.4, len(rows) - 0.35, "HARDER", color=RED, fontsize=11, fontweight="bold")
ax.set_xlim(0.42, 16)
ax.set_ylim(-0.7, len(rows) - 0.15)
save(fig, "e1_drivers")

# The "how much can we explain" figure is carried as a sentence on slide 3 rather
# than a chart, so no second figure is generated here - an unplaced PNG is dead
# output that later reads as a chart someone forgot to add.

payload = {
    "top_rules": SC["per_rule"][:10],
    # Every rule with at least 30 sampled tickets, for the policy-level view.
    "all_rules": [r for r in SC["per_rule"] if r["sample_n"] >= 30],
    "min_survey_n": SC["meta"]["min_survey_n"],
    "n_survey": MD["meta"]["n_analysis"],
    "auc": SUM["S1"]["auc_cv5"],
    "r2": SUM["S1"]["mcfadden_r2"],
    "r2_handling": SUM["S0"]["mcfadden_r2"],
    "base_rate": MD["meta"]["base_rate_not_easy"],
    "handoff_or": COEF["obs_agent_handoffs"]["odds_ratio"],
    "tat_or": COEF["log_tat_days"]["odds_ratio"],
    "replies_or": COEF["obs_responses"]["odds_ratio"],
    "worst_code_or": COEF["resolution_codeInvalid- discontinued title"]["odds_ratio"],
    "conformance_p": BLOCKS["minimal -> + conformance status (n=625)"]["p_value"],
    "reason_p": BLOCKS["conformance -> + rejection reason (n=625)"]["p_value"],
    "n_rules_clearing": SC["meta"]["n_rules_clearing"],
    "n_rules_total": SC["meta"]["n_rules_total"],
}
(OUT / "exec_data.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
print(f"wrote {OUT / 'exec_data.json'}")
