"""Figures for the repo manual / methodology document (October 2026).

    .venv\\Scripts\\python.exe scripts\\build_usecase_review_figs.py

Reads runs/usecase_review/content.json and writes PNGs to runs/usecase_review/figs/.
The deck draws its own native shapes and charts; these images are for the Word file.
"""
from __future__ import annotations

import json
import textwrap
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Polygon  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
C = json.loads((BASE / "runs" / "usecase_review" / "content.json").read_text(encoding="utf-8"))
FIGS = BASE / "runs" / "usecase_review" / "figs"
FIGS.mkdir(parents=True, exist_ok=True)

NAVY, MID, ORANGE, GREY, LIGHT, INK = "#0B2A4A", "#1B4C7A", "#FF6C00", "#7A8794", "#EEF1F4", "#26323F"
FAMILY_COL = {"A": MID, "B": "#2E7D5B", "C": ORANGE, "D": "#6B4C9A", "E": "#0E7C86"}
plt.rcParams.update({"font.family": "Segoe UI", "font.size": 9, "text.color": INK})


def skeleton():
    sk, lad = C["proposal"]["skeleton"], C["proposal"]["ladder"]
    fig, ax = plt.subplots(figsize=(11, 5.2), dpi=200)
    ax.set_xlim(0, 12); ax.set_ylim(0, 6.2); ax.axis("off")
    w = 12 / len(sk)
    for i, st in enumerate(sk):
        x = i * w
        pts = [(x, 4.9), (x + w - 0.25, 4.9), (x + w + 0.05, 5.35), (x + w - 0.25, 5.8), (x, 5.8)]
        if i:
            pts.append((x + 0.3, 5.35))
        ax.add_patch(Polygon(pts, closed=True, color=NAVY if i % 2 == 0 else MID))
        ax.text(x + w / 2, 5.35, st["name"], ha="center", va="center", color="white",
                fontsize=12, fontweight="bold")
        ax.text(x + 0.12, 4.7, textwrap.fill(st["what"], 26), ha="left", va="top", fontsize=8)
    ax.text(0, 3.15, "SPEND LADDER — each gate must pass before the next spend", color=ORANGE,
            fontsize=9, fontweight="bold")
    lw = 12 / len(lad)
    fills = [LIGHT, "#C9D6E3", MID, NAVY]
    for i, g in enumerate(lad):
        x, h = i * lw, 1.25 + 0.45 * i
        ax.add_patch(FancyBboxPatch((x + 0.05, 0.05), lw - 0.2, h, boxstyle="round,pad=0,rounding_size=0.08",
                                    color=fills[i]))
        dark = i >= 2
        ax.text(x + 0.2, 0.05 + h - 0.22, f"{g['gate']}  {g['name']}", fontsize=10, fontweight="bold",
                color="white" if dark else NAVY, va="top")
        ax.text(x + 0.2, 0.05 + h - 0.55, textwrap.fill(g["what"], 34), fontsize=7.5,
                color="white" if dark else INK, va="top")
        ax.text(x + 0.2, 0.2, g["cost"], fontsize=8.5, fontweight="bold", color=ORANGE)
    fig.savefig(FIGS / "fig_skeleton.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def timeline():
    tl = sorted(C["timeline"], key=lambda e: e["date"])
    d0, d1 = date(2026, 3, 1), date(2026, 10, 10)
    fig, ax = plt.subplots(figsize=(11, 5.6), dpi=200)
    ax.set_xlim(-0.02, 1.02); ax.set_ylim(-3.6, 3.6); ax.axis("off")
    ax.plot([0, 1], [0, 0], color=NAVY, lw=2)
    for m in range(3, 11):
        x = (date(2026, m, 1) - d0).days / (d1 - d0).days
        ax.plot([x, x], [-0.08, 0.08], color=NAVY, lw=1.5)
        ax.text(x, -0.3, date(2026, m, 1).strftime("%b"), ha="center", va="top", fontsize=9,
                fontweight="bold", color=NAVY)
    levels = [1.0, -1.0, 2.0, -2.0, 3.0, -3.0]
    placed = {lv: [] for lv in levels}
    width = 0.13
    for e in tl:
        d = date.fromisoformat(e["date"][:10])
        x = (d - d0).days / (d1 - d0).days
        for lv in levels:
            if all(abs(x - p) > width for p in placed[lv]):
                break
        placed[lv].append(x)
        col = FAMILY_COL.get((e.get("family") or "A")[:1].upper(), GREY)
        ax.plot([x, x], [0, lv * 0.82], color=col, lw=0.7)
        ax.plot(x, 0, "o", color=col, ms=5)
        ax.text(x, lv * 0.82 + (0.05 if lv > 0 else -0.05),
                f"{d.day} {d.strftime('%b')}\n" + textwrap.fill(e["label"], 22),
                ha="center", va="bottom" if lv > 0 else "top", fontsize=6.8, color=INK,
                bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=col, lw=0.6))
    for i, f in enumerate(C["families"]):
        ax.plot(0.01 + i * 0.2, -3.45, "o", color=FAMILY_COL[f["key"]], ms=6)
        ax.text(0.022 + i * 0.2, -3.45, textwrap.shorten(f["name"], 34, placeholder="…"), va="center",
                fontsize=7.5)
    fig.savefig(FIGS / "fig_timeline.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


skeleton()
timeline()
print("wrote", sorted(p.name for p in FIGS.glob("*.png")))
