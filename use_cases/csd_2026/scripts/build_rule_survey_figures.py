"""Three figures for the per-validation-rule survey table.

Reads the finished table rather than recomputing anything, so the figures cannot
drift from runs/output/csd_2026_rule_survey_table.xlsx.

    f1_deviation  volume beside deviation-from-benchmark  (the recommendation)
    f2_slope      CSAT -> CES -> ASAT, one line per rule
    f3_bubble     volume against CSAT, bubble area = response count

Why deviation rather than level on f1: the three scores span only 14-17 points and
all sit between 77% and 94%. As absolute bars they read flat, and truncating the
axis to 75-100% to fix that is the classic misleading chart. Deviation has a real
zero, so a zoomed axis is honest.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                    # noqa: E402
import numpy as np                                                 # noqa: E402
import pandas as pd                                                # noqa: E402
from matplotlib.ticker import FuncFormatter                        # noqa: E402

BASE = Path(__file__).resolve().parents[1]
TABLE = BASE / "runs" / "output" / "csd_2026_rule_survey_table.xlsx"
META = BASE / "data" / "scopus content" / "scopus content_2026_metadata.tsv"
FIGS = BASE / "runs" / "output" / "figures"
FIGS.mkdir(parents=True, exist_ok=True)

NAVY, ORANGE, GREY = "#0B2A4A", "#FF6C00", "#7A8794"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                     "axes.edgecolor": GREY, "axes.labelcolor": NAVY,
                     "text.color": NAVY, "xtick.color": GREY, "ytick.color": GREY,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "figure.facecolor": "none", "savefig.facecolor": "none"})

# Each measure keeps one colour and one marker shape across all three figures, so
# nothing depends on colour alone.
SERIES = [("CSAT", "#2a78d6", "o"), ("CES", "#eb6834", "s"), ("ASAT", "#1baf7a", "^")]
MIN_N = 30
NL = chr(10)

FRIENDLY = {
    "CSDVR1.5": "Too recent", "CSDVR1.6": "Already in Scopus",
    "CSDVR4.1": "No rule covers this", "CSDVR1.2": "Under re-evaluation",
    "CSDVR1.7": "In the pipeline", "CSDVR1.1": "Never covered",
    "CSDVR1.8": "Coverage mismatch", "CSDVR2.1": "Matches published version",
    "CSDVR1.3": "Unauthentic publisher", "CSDVR1.14": "Article in Press",
    "CSDVR3.1": "OA change unverifiable", "CSDVR1.9": "Document type out of scope",
}


def save(fig, name):
    for ax in fig.axes:
        assert ax.collections or ax.patches or ax.lines, f"{name}: empty axes"
    fig.tight_layout()
    fig.savefig(FIGS / f"{name}.png", dpi=220, transparent=True, bbox_inches="tight")
    plt.close(fig)
    print(f"    {name}.png")


def declash(items, min_gap):
    """Nudge label y-positions apart while keeping their order.

    Several rules share a CSAT value to within a tenth of a point, so their names
    land on top of each other. Sort, then push each label up to min_gap above the
    previous one.
    """
    out = []
    for key, yv in sorted(items, key=lambda p: p[1]):
        if out and yv - out[-1][1] < min_gap:
            yv = out[-1][1] + min_gap
        out.append((key, yv))
    return dict(out)


print("=" * 78)
print("RULE SURVEY FIGURES")
print("=" * 78)

t = pd.read_excel(TABLE, sheet_name="per_rule_survey")
t["short"] = t["csdvr_code"].map(FRIENDLY).fillna(t["validation_rule"].astype(str).str[:24])

# Benchmarks are recomputed from source rather than carried as constants, so a
# refreshed extract cannot leave the reference lines silently stale.
m = pd.read_csv(META, sep="\t", dtype=str,
                usecols=["CSAT_ANSWER_CODE", "CSAT_EFFORT_CODE", "AGENT_CSAT_CODE"])
BENCH = {}
for lab, col, hi, th in [("CSAT", "CSAT_ANSWER_CODE", 7, 3),
                         ("CES", "CSAT_EFFORT_CODE", 5, 2),
                         ("ASAT", "AGENT_CSAT_CODE", 5, 2)]:
    v = pd.to_numeric(m[col], errors="coerce")
    v = v[v.between(1, hi)]
    BENCH[lab] = float((v <= th).mean())
print("  benchmarks: " + "  ".join(f"{k} {v:.1%}" for k, v in BENCH.items()))
for k, expect in [("CSAT", 0.878), ("CES", 0.867), ("ASAT", 0.914)]:
    assert abs(BENCH[k] - expect) < 0.001, f"{k} benchmark moved to {BENCH[k]:.3f}"

est = t[t["CSAT_n"] >= MIN_N].sort_values("est_population", ascending=False).reset_index(
    drop=True)
rest = t[t["CSAT_n"] < MIN_N]
print(f"  rules plotted: {len(est)}   collapsed: {len(rest)} "
      f"({int(rest.est_population.sum()):,} tickets)")
assert len(est) == 8, f"expected 8 estimable rules, got {len(est)}"
_tot = int(est["est_population"].sum() + rest["est_population"].sum())
assert abs(_tot - 50714) <= 2, f"volumes sum to {_tot:,}, expected 50,714"

# ════════════════════════════════════════════ 1 · volume beside deviation
n = len(est)
y = np.arange(n)[::-1]
fig, (axv, axd) = plt.subplots(
    1, 2, figsize=(12.4, 5.4), gridspec_kw={"width_ratios": [1, 2.1], "wspace": 0.04})

axv.barh(y, est["est_population"], 0.55, color=NAVY)
for yy, v in zip(y, est["est_population"]):
    axv.text(v + 250, yy, f"{int(v):,}", va="center", fontsize=9.5, color=GREY)
axv.barh([-1], [rest["est_population"].sum()], 0.55, color="#B4B2A9")
axv.text(rest["est_population"].sum() + 250, -1,
         f"{int(rest.est_population.sum()):,}", va="center", fontsize=9.5, color=GREY)
axv.set_yticks(list(y) + [-1])
axv.set_yticklabels(list(est["short"]) + [f"{len(rest)} other rules"], fontsize=10.5)
axv.set_xlim(0, est["est_population"].max() * 1.30)
axv.set_xticks([])
axv.spines["bottom"].set_visible(False)
axv.spines["left"].set_visible(False)
axv.set_xlabel("tickets (Jan–Jul 2026)", fontsize=10, color=GREY)
axv.tick_params(axis="y", length=0, pad=6)

n_suppressed = 0
axd.axvline(0, color=NAVY, lw=1.4, zorder=2)
for yy in list(y) + [-1]:
    axd.axhline(yy, color="#E1E0D9", lw=0.7, zorder=1)
for lab, col, mk in SERIES:
    xs, ys = [], []
    for i, yy in enumerate(y):
        r = est.iloc[i]
        if r[f"{lab}_n"] >= MIN_N and pd.notna(r[f"{lab}_pct"]):
            xs.append((r[f"{lab}_pct"] - BENCH[lab]) * 100)
            ys.append(yy)
    axd.scatter(xs, ys, s=95, marker=mk, color=col, label=f"{lab} vs {BENCH[lab]:.0%}",
                zorder=3)
for i, yy in enumerate(y):
    missing = [lab for lab, _, _ in SERIES if est.iloc[i][f"{lab}_n"] < MIN_N]
    if missing:
        n_suppressed += 1
        axd.text(10.4, yy, f"{'/'.join(missing)} n<{MIN_N}", va="center", fontsize=8.5,
                 color=GREY, style="italic")
axd.text(10.4, -1, f"no rule reaches {MIN_N} responses", va="center", fontsize=8.5,
         color=GREY, style="italic")
axv.set_ylim(-1.8, n - 0.3)
axd.set_ylim(-1.8, n - 0.3)
axd.set_xlim(-13, 15.5)
axd.set_yticks([])
axd.spines["left"].set_visible(False)
axd.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:+.0f}" if v else "0"))
axd.set_xlabel("percentage points vs the corpus benchmark", fontsize=10)
axd.text(-11.5, n - 0.55, "WORSE", fontsize=10, color="#A32D2D", fontweight="bold")
axd.text(6.2, n - 0.55, "BETTER", fontsize=10, color="#3B6D11", fontweight="bold")
axd.legend(frameon=False, fontsize=9.5, loc="lower right", ncol=3,
           bbox_to_anchor=(1.0, -0.20), handletextpad=0.3, columnspacing=1.4)
save(fig, "f1_deviation")
print(f"      rows carrying an n<{MIN_N} note: {n_suppressed}")
assert n_suppressed == int((est["ASAT_n"] < MIN_N).sum()), "suppression labels miscounted"

# ════════════════════════════════════════════════════════════ 2 · slope
fig, ax = plt.subplots(figsize=(9.4, 6.2))
xpos = {"CSAT": 0, "CES": 1, "ASAT": 2}
lines = []
for _, r in est.iterrows():
    pts = [(xpos[lab], r[f"{lab}_pct"] * 100) for lab, _, mk in SERIES
           if r[f"{lab}_n"] >= MIN_N and pd.notna(r[f"{lab}_pct"])]
    lines.append((r["short"], pts, pts[0][1] < BENCH["CSAT"] * 100))

# Labels are placed on de-collided positions but leader lines still point at the
# true value, so nudging a label never misstates a number.
left_y = declash([(s, p[0][1]) for s, p, _ in lines], 0.95)
right_y = declash([(s, p[-1][1]) for s, p, _ in lines if p[-1][0] == 2], 0.95)

for short, pts, below in lines:
    c = "#A32D2D" if below else "#8A9299"
    ax.plot([x for x, _ in pts], [v for _, v in pts], "-", color=c,
            lw=2.0 if below else 1.4, alpha=0.95 if below else 0.7,
            zorder=3 if below else 2)
    for (x, v), (lab, _, mk) in zip(pts, SERIES):
        ax.plot(x, v, mk, color=c, ms=6.5, zorder=4)
    # The de-collided position is in DATA units, so the label must be placed in data
    # coordinates too - passing it as a point offset silently does almost nothing.
    ax.annotate(short, xy=(0, pts[0][1]), xytext=(-0.07, left_y[short]),
                textcoords="data", fontsize=9.5, color=c, ha="right", va="center",
                annotation_clip=False,
                arrowprops=dict(arrowstyle="-", color=c, lw=0.7, alpha=0.5,
                                shrinkA=2, shrinkB=4))
    if pts[-1][0] == 2:
        ax.annotate(f"{pts[-1][1]:.0f}%", xy=(2, pts[-1][1]),
                    xytext=(2.10, right_y[short]), textcoords="data",
                    fontsize=9.5, color=NAVY, va="center", ha="left",
                    annotation_clip=False,
                    arrowprops=dict(arrowstyle="-", color=GREY, lw=0.7, alpha=0.5,
                                    shrinkA=2, shrinkB=4))
    else:
        ax.annotate("ASAT n<30", (pts[-1][0], pts[-1][1]), xytext=(10, 0),
                    textcoords="offset points", fontsize=8.5, color=GREY,
                    style="italic", va="center")

for lab, col, _ in SERIES:
    ax.plot([xpos[lab] - 0.17, xpos[lab] + 0.17], [BENCH[lab] * 100] * 2, "--",
            color=col, lw=1.5, zorder=1)
ax.set_xticks([0, 1, 2])
ax.set_xticklabels([f"CSAT{NL}benchmark {BENCH['CSAT']:.0%}",
                    f"CES{NL}benchmark {BENCH['CES']:.0%}",
                    f"ASAT{NL}benchmark {BENCH['ASAT']:.0%}"], fontsize=10.5)
ax.set_xlim(-1.05, 2.42)
ax.set_ylim(74, 102)
ax.set_ylabel("% positive")
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
ax.spines["bottom"].set_visible(False)
ax.tick_params(axis="x", length=0)
save(fig, "f2_slope")

# ═══════════════════════════════════════════════════════════ 3 · bubble
fig, ax = plt.subplots(figsize=(10.2, 5.8))
ax.axhline(BENCH["CSAT"] * 100, color="#2a78d6", ls="--", lw=1.4)
ax.text(est["est_population"].max() * 1.5, BENCH["CSAT"] * 100 + 0.35,
        f"benchmark {BENCH['CSAT']:.1%}", fontsize=9.5, color="#2a78d6")
ax.scatter(est["est_population"], est["CSAT_pct"] * 100, s=est["CSAT_n"] * 6,
           color="#2a78d6", alpha=0.45, zorder=3)
ax.scatter(est["est_population"], est["CSAT_pct"] * 100, s=14, color="#2a78d6", zorder=4)
# Labels default to below the bubble. Two rules sit almost on top of each other
# (both ~84% at ~3,700 tickets), so anything placed blind overlaps. Place them one
# at a time and flip to above whenever the rendered box hits one already down.
# Two bubbles touch at 84%, so a centred label alone does not say which is which.
LEADER = dict(arrowstyle="-", color="#b9c2cc", lw=0.8, shrinkA=1, shrinkB=6)
_placed = []
fig.canvas.draw()
for _, r in est.sort_values("est_population").iterrows():
    clear = 16 + np.sqrt(r["CSAT_n"] * 6) / 2
    xy = (r["est_population"], r["CSAT_pct"] * 100)
    for dy, va in [(-clear, "top"), (clear, "bottom")]:
        a = ax.annotate(f"{r['short']}  (n={int(r.CSAT_n)})", xy, fontsize=9,
                        color=NAVY, xytext=(0, dy), textcoords="offset points",
                        ha="center", va=va, arrowprops=LEADER)
        fig.canvas.draw()
        bb = a.get_window_extent()
        if not any(bb.overlaps(o) for o in _placed):
            _placed.append(bb)
            break
        a.remove()
    else:
        a = ax.annotate(f"{r['short']}  (n={int(r.CSAT_n)})", xy, fontsize=9,
                        color=NAVY, xytext=(0, clear), textcoords="offset points",
                        ha="center", va="bottom", arrowprops=LEADER)
        fig.canvas.draw()
        _placed.append(a.get_window_extent())
ax.set_xscale("log")
ax.set_xlim(1600, est["est_population"].max() * 2.6)
ax.set_ylim(74, 99)
ax.set_xlabel("tickets, Jan–Jul 2026 (log scale)")
ax.set_ylabel("CSAT % satisfied")
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
ax.set_xticks([2000, 4000, 8000, 12000])
ax.set_xticklabels(["2,000", "4,000", "8,000", "12,000"])
ax.text(1750, 96.6, "bubble area = number of survey responses", fontsize=9, color=GREY,
        style="italic")
save(fig, "f3_bubble")

print(f"\nwrote 3 figures to {FIGS}")
