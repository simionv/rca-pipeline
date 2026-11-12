"""Render the Scopus Content 2LS back-and-forth deck from runs/output/s2ls_deck/deck_data.json.

Run with the SYSTEM Python, which is the interpreter that has python-pptx:

    & "C:\\Program Files\\Python311\\python.exe" scripts\\build_s2ls_deck.py

Every number comes from deck_data.json, produced by scripts/build_s2ls_deck_data.R (the
analysis and regression models). This script only lays the numbers out: standard library +
python-pptx, no pandas, and all charts are native PowerPoint charts so they stay editable.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from pptx import Presentation
    from pptx.chart.data import CategoryChartData
    from pptx.dml.color import RGBColor
    from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
    from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
    from pptx.util import Inches, Pt
except ModuleNotFoundError:                                          # pragma: no cover
    sys.exit("python-pptx is not available on this interpreter.\n"
             'Run with:  & "C:\\Program Files\\Python311\\python.exe" scripts\\build_s2ls_deck.py')

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "runs" / "output" / "s2ls_deck" / "deck_data.json"
OUT = BASE / "runs" / "output" / "S2LS_2026_back_and_forth_customer_effort.pptx"

D = json.loads(DATA.read_text(encoding="utf-8"))
d, M = D["desc"], D["models"]

# ── palette: Elsevier navy dominant, orange as the single accent (back-and-forth),
# ── a one-hue blue ramp for the ordered effort levels, greys for context
NAVY = RGBColor(0x0B, 0x2A, 0x4A)
ORANGE = RGBColor(0xFF, 0x6C, 0x00)        # fills and large numbers only
ORANGE_TXT = RGBColor(0xC2, 0x41, 0x0C)    # small text: 5:1 on white
INK = RGBColor(0x1F, 0x29, 0x33)
MUTED = RGBColor(0x5B, 0x67, 0x70)
GRID = RGBColor(0xE1, 0xE0, 0xD9)
CARD = RGBColor(0xF2, 0xF4, 0xF6)
CONTEXT = RGBColor(0xB8, 0xC0, 0xC8)
ICE = RGBColor(0xCA, 0xDC, 0xFC)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
EFFORT_RAMP = [RGBColor(0xB7, 0xD3, 0xF6), RGBColor(0x6D, 0xA7, 0xEC),
               RGBColor(0x2A, 0x78, 0xD6), RGBColor(0x10, 0x42, 0x81)]
PATTERN_COLOURS = [CONTEXT, CONTEXT, NAVY, ORANGE, ORANGE]
FONT = "Calibri"

W, H = Inches(13.333), Inches(7.5)
MX = Inches(0.6)                            # side margin
BODY_W = W - 2 * MX

prs = Presentation()
prs.slide_width, prs.slide_height = W, H
BLANK = prs.slide_layouts[6]
_page = 0


# ───────────────────────────────────────────────────────────── formatting
def pct(x, dp=0):
    return f"{100 * x:.{dp}f}%"


def num(x):
    return f"{x:,.0f}"


def k(x):
    return f"{x / 1000:.1f}k" if x >= 1000 else f"{x:.0f}"


# ───────────────────────────────────────────────────────────── primitives
def text(slide, x, y, w, h, runs, size=14, color=INK, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, italic=False, spacing=None):
    """runs: a string, or a list of paragraphs; each paragraph a string or a list of
    (text, {size, color, bold, italic}) tuples."""
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    paras = runs if isinstance(runs, list) else [runs]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if spacing:
            p.space_after = Pt(spacing)
        for seg, fmt in (para if isinstance(para, list) else [(para, {})]):
            r = p.add_run()
            r.text = seg
            f = r.font
            f.name = FONT
            f.size = Pt(fmt.get("size", size))
            f.bold = fmt.get("bold", bold)
            f.italic = fmt.get("italic", italic)
            f.color.rgb = fmt.get("color", color)
    return box


def rect(slide, x, y, w, h, fill, shape=MSO_SHAPE.RECTANGLE, line=None):
    s = slide.shapes.add_shape(shape, x, y, w, h)
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
    s.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = 0.08
    return s


def new_slide(kicker=None, title=None, dark=False):
    global _page
    _page += 1
    s = prs.slides.add_slide(BLANK)
    if dark:
        rect(s, 0, 0, W, H, NAVY)
    if kicker:
        text(s, MX, Inches(0.42), BODY_W, Inches(0.3), kicker.upper(), size=12, bold=True,
             color=ORANGE if dark else ORANGE_TXT)
    if title:
        text(s, MX, Inches(0.72), BODY_W, Inches(0.9), title, size=28, bold=True,
             color=WHITE if dark else NAVY)
    if not dark:
        text(s, W - MX - Inches(3), H - Inches(0.42), Inches(3), Inches(0.25),
             f"Scopus Content 2LS  ·  {_page}", size=10, color=MUTED, align=PP_ALIGN.RIGHT)
    return s


def source(slide, msg):
    text(slide, MX, H - Inches(0.42), Inches(9.5), Inches(0.25), msg, size=10, color=MUTED)


def stat_tile(slide, x, y, w, h, big, label, sub=None, big_color=NAVY, fill=CARD):
    rect(slide, x, y, w, h, fill, MSO_SHAPE.ROUNDED_RECTANGLE)
    pad = Inches(0.25)
    text(slide, x + pad, y + Inches(0.2), w - 2 * pad, Inches(0.85), big, size=44, bold=True,
         color=big_color)
    text(slide, x + pad, y + Inches(1.08), w - 2 * pad, h - Inches(1.2),
         [[(label, {"bold": True, "size": 14})]] + ([[(sub, {"size": 12, "color": MUTED})]] if sub else []),
         size=14, spacing=3)


def number_badge(slide, x, y, n, fill=NAVY, color=WHITE, size=0.42):
    c = rect(slide, x, y, Inches(size), Inches(size), fill, MSO_SHAPE.OVAL)
    tf = c.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = str(n)
    r.font.name, r.font.size, r.font.bold, r.font.color.rgb = FONT, Pt(14), True, color
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    return c


# ───────────────────────────────────────────────────────────── charts
def _quiet_axes(chart, show_values=False, cat_size=12):
    va, ca = chart.value_axis, chart.category_axis
    va.has_major_gridlines = show_values
    if show_values:
        va.major_gridlines.format.line.color.rgb = GRID
        va.tick_labels.font.size = Pt(11)
        va.tick_labels.font.color.rgb = MUTED
    va.visible = show_values
    va.format.line.fill.background()
    ca.tick_labels.font.size = Pt(cat_size)
    ca.tick_labels.font.color.rgb = INK
    ca.tick_labels.font.name = FONT
    ca.format.line.color.rgb = CONTEXT
    ca.has_major_gridlines = False


def bar_chart(slide, x, y, w, h, cats, values, colours, fmt="0%", horizontal=False,
              title=None, label_size=12, gap=60, cat_size=12, vmax=None):
    cd = CategoryChartData()
    cd.categories = cats
    cd.add_series("value", values, number_format=fmt)
    kind = XL_CHART_TYPE.BAR_CLUSTERED if horizontal else XL_CHART_TYPE.COLUMN_CLUSTERED
    ch = slide.shapes.add_chart(kind, x, y, w, h, cd).chart
    ch.has_legend = False
    ch.font.name = FONT
    if title:
        ch.has_title = True
        ch.chart_title.text_frame.text = title
        tp = ch.chart_title.text_frame.paragraphs[0]
        tp.runs[0].font.size, tp.runs[0].font.bold = Pt(14), True
        tp.runs[0].font.color.rgb = INK
    else:
        ch.has_title = False
    plot = ch.plots[0]
    plot.gap_width = gap
    plot.vary_by_categories = False
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format, dl.number_format_is_linked = fmt, False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size, dl.font.color.rgb, dl.font.name = Pt(label_size), INK, FONT
    ser = plot.series[0]
    for i, col in enumerate(colours):
        pt = ser.points[i]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = col
        pt.format.line.fill.background()
    _quiet_axes(ch, cat_size=cat_size)
    if horizontal:
        ch.category_axis.reverse_order = True     # first category on top
    if vmax is not None:
        ch.value_axis.maximum_scale = vmax
    ch.value_axis.minimum_scale = 0
    return ch


def stacked_100(slide, x, y, w, h, cats, series, colours, min_label=0.05):
    cd = CategoryChartData()
    cd.categories = cats
    for name, vals in series:
        cd.add_series(name, vals, number_format="0%")
    ch = slide.shapes.add_chart(XL_CHART_TYPE.BAR_STACKED_100, x, y, w, h, cd).chart
    ch.font.name = FONT
    ch.has_title = False
    ch.has_legend = True
    ch.legend.position = XL_LEGEND_POSITION.TOP
    ch.legend.include_in_layout = False
    ch.legend.font.size, ch.legend.font.color.rgb = Pt(12), INK
    plot = ch.plots[0]
    plot.gap_width = 45
    plot.overlap = 100
    for si, ser in enumerate(plot.series):
        ser.format.fill.solid()
        ser.format.fill.fore_color.rgb = colours[si]
        ser.format.line.color.rgb = WHITE           # 2px-style surface gap between segments
        ser.format.line.width = Pt(1.5)
        vals = series[si][1]
        for pi, v in enumerate(vals):
            lab = ser.points[pi].data_label
            if v < min_label:
                lab.has_text_frame = True
                lab.text_frame.text = ""
                continue
            lab.has_text_frame = True
            lab.text_frame.text = f"{100 * v:.0f}%"
            run = lab.text_frame.paragraphs[0].runs[0]
            run.font.size = Pt(12)
            run.font.bold = True
            run.font.color.rgb = INK if si < 2 else WHITE
            lab.position = XL_LABEL_POSITION.CENTER
    _quiet_axes(ch, cat_size=13)
    ch.category_axis.reverse_order = True
    return ch


def table(slide, x, y, w, rows, col_w, header_fill=NAVY, size=12, row_h=0.42, bold_first_col=True,
          highlight_rows=()):
    shape = slide.shapes.add_table(len(rows), len(rows[0]), x, y, w, Inches(row_h * len(rows)))
    tbl = shape.table
    for ci, cw in enumerate(col_w):
        tbl.columns[ci].width = Inches(cw)
    for ri, row in enumerate(rows):
        tbl.rows[ri].height = Inches(row_h)
        for ci, val in enumerate(row):
            cell = tbl.cell(ri, ci)
            cell.margin_left = cell.margin_right = Inches(0.1)
            cell.margin_top = cell.margin_bottom = Inches(0.04)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            if ri == 0:
                cell.fill.fore_color.rgb = header_fill
            elif ri in highlight_rows:
                cell.fill.fore_color.rgb = RGBColor(0xFF, 0xE9, 0xD9)
            else:
                cell.fill.fore_color.rgb = WHITE if ri % 2 else CARD
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if ci == 0 else PP_ALIGN.CENTER
            r = p.add_run()
            r.text = str(val)
            r.font.name, r.font.size = FONT, Pt(size)
            r.font.bold = ri == 0 or (bold_first_col and ci == 0)
            r.font.color.rgb = WHITE if ri == 0 else INK
    return tbl


# ───────────────────────────────────────────────────────────── verbatim evidence slides
CUST_TINT = RGBColor(0xFF, 0xF1, 0xE6)
AGENT_TINT = RGBColor(0xEA, 0xF2, 0xFB)
EVID = D["evidence"]
EVID_NOTE = ("Verbatim sentences from the rebuilt transcripts (HTML and email signatures removed). Customer and agent "
             "quote in each row come from the same ticket; turn number (T) and date show where. Selected reproducibly "
             "by scripts/build_s2ls_deck_data.R: sentences carrying a greeting name, email, URL, DOI, long number, "
             "institution or quoted title are never eligible. Alternatives: sheet quote_candidates in "
             "runs/output/s2ls_deck/s2ls_effort_models.xlsx.")


def evidence_slide(kicker, title, rows):
    """rows: (evidence id, insight label, supporting number). One row per insight:
    label | customer quote | agent quote, both from the same ticket."""
    s = new_slide(kicker, title)
    top, bottom = Inches(1.8), H - Inches(0.62)
    gap = Inches(0.14)
    rh = int((bottom - top - gap * (len(rows) - 1)) / len(rows))
    lx, lw = MX, Inches(2.75)
    cx, cw = MX + Inches(2.95), Inches(4.6)
    ax, aw_ = cx + cw + Inches(0.17), W - MX - (cx + cw + Inches(0.17))
    qsize = 13 if len(rows) <= 3 else 12
    for i, (key, label, stat) in enumerate(rows):
        e = EVID[key]
        y = top + i * (rh + gap)
        text(s, lx, y + Inches(0.08), lw, rh - Inches(0.1),
             [[(label, {"bold": True, "size": 15, "color": NAVY})],
              [(stat, {"size": 13, "color": ORANGE_TXT, "bold": True})],
              [(f"Ticket {e['ticket']}", {"size": 10, "color": MUTED})]], spacing=2)
        for x, w, tint, who, tag_col, q in ((cx, cw, CUST_TINT, "CUSTOMER", ORANGE_TXT, e["customer"]),
                                            (ax, aw_, AGENT_TINT, "AGENT", NAVY, e["agent"])):
            rect(s, x, y, w, rh, tint, MSO_SHAPE.ROUNDED_RECTANGLE)
            text(s, x + Inches(0.2), y + Inches(0.1), w - Inches(0.4), rh - Inches(0.16),
                 [[(f"{who}  ·  T{q['turn']}  ·  {q['date']}", {"bold": True, "size": 10, "color": tag_col})],
                  [(f"“{q['quote']}”", {"size": qsize, "italic": True, "color": INK})]], spacing=3)
    source(s, "Verbatim from the transcripts; customer and agent quotes in a row come from the same ticket.")
    s.notes_slide.notes_text_frame.text = EVID_NOTE
    return s


# Page numbers of the evidence slides, for the executive summary's cross-references.
# Asserted against the built deck at the end, so a re-ordering cannot leave them stale.
EVID_PAGES = {"how_often": 5, "where": 7, "cost": 12}

# ───────────────────────────────────────────────────────────── derived numbers
PAT = {r["pattern"]: r for r in d["patterns"]}
BYP = {r["pattern"]: r for r in d["by_pattern"]}
PRED = M["predictions"]
EFF = {e["outcome"]: e for e in M["effects"]}
E_EFFORT = EFF["Higher customer-effort score"]
E_DAYS = EFF["Days open (first to last message)"]
E_MSGS = EFF["Customer messages"]
E_FUP = EFF["Customer follow-ups"]
DEC_R = M["decomposition"]["extra_handoffs"]
DEC_X = M["decomposition"]["extra_returns"]
BFT = {b["type"]: b for b in d["bf_types"]}
REROUTE, EXTRA = BFT["Re-routed to 2LS again"], BFT["Extra 2LS returns only"]
YEAR = {r["group"]: r for r in d["by_year"]}
SHORT = {"Not escalated": "Not escalated", "One-way": "One-way (nothing back)",
         "Round trip": "One round trip", "3 crossings": "3 crossings", "4+ crossings": "4+ crossings"}
PATTERNS = D["meta"]["patterns"]
bf_rc = [r for r in d["by_resolution_code"] if r["est"] >= 500]
bf_rc_volume = sorted(bf_rc, key=lambda r: -r["bf_of_all"] * r["est"])
top3_share = sum(r["bf_of_all"] * r["est"] for r in bf_rc_volume[:3]) / d["bf_est"]
SAMPLE_NOTE = (f"Weighted estimates from a stratified sample of {num(d['n_sampled'])} of "
               f"{num(d['N'])} tickets (Nov 2024 – Sep 2026).")

# ═════════════════════════════════════════════════════════════ 1. title
s = new_slide(dark=True)
text(s, MX, Inches(1.6), Inches(8), Inches(0.4), "SCOPUS CONTENT · 1LS ⇄ 2LS", size=13, bold=True,
     color=ORANGE)
text(s, MX, Inches(2.05), Inches(11.4), Inches(1.9),
     "Every extra trip between 1LS and 2LS costs the customer", size=44, bold=True, color=WHITE)
text(s, MX, Inches(3.95), Inches(10.5), Inches(1.0),
     "How often Scopus Content tickets go back and forth between the support tiers, "
     "and what each extra crossing does to customer effort", size=20, color=ICE)
text(s, MX, Inches(5.9), Inches(11), Inches(0.9),
     [[(f"{num(d['N'])} tickets escalated to 2LS · Nov 2024 – Sep 2026", {"bold": True})],
      [(f"{num(d['n_sampled'])} transcripts read in full, weighted to the population · "
        "regression modelling in R", {})]], size=14, color=ICE, spacing=2)
s.notes_slide.notes_text_frame.text = (
    "Scope: every Scopus Content ticket logged as escalated from 1LS to 2LS between Nov 2024 and Sep 2026 "
    "(IS_VALUE_ADD = TRUE, _merge = both). The LLM read a stratified sample of 5,760 transcripts; every "
    "population figure is weighted back to the 63,824. Analysis: notebooks/17_scopus_2ls_escalation_effort.ipynb "
    "(extraction) and scripts/build_s2ls_deck_data.R (statistics and models).")

# ═════════════════════════════════════════════════════════════ 2. executive summary
s = new_slide("Executive summary",
              "About 1 in 12 tickets bounces between the tiers, and each extra crossing "
              "sharply raises the effort the customer has to put in")
tw, th, ty, gap = Inches(2.86), Inches(2.25), Inches(1.95), Inches(0.22)
tiles = [
    (pct(d["escalated_share"]), "really escalated to 2LS",
     f"{pct(1 - d['escalated_share'])} were in fact handled by 1LS alone", NAVY),
    (pct(d["bf_share_all"], 1), "went back and forth",
     f"≈{num(d['bf_est'])} tickets needed 3+ crossings; {pct(REROUTE['share_all'], 1)} were re-routed to 2LS", ORANGE),
    (f"+{E_FUP['pct']:.0f}%", "customer follow-ups",
     f"per extra crossing, like-for-like (+{E_MSGS['pct']:.0f}% customer messages)", ORANGE),
    (f"+{E_DAYS['pct']:.0f}%", "longer open",
     f"per extra crossing; {PRED['Round trip']['days_open']:.0f} → {PRED['4+ crossings']['days_open']:.0f} "
     "typical days at 4+ crossings", ORANGE),
]
for i, (big, lab, sub, col) in enumerate(tiles):
    stat_tile(s, MX + i * (tw + gap), ty, tw, th, big, lab, sub, big_color=col)
y0 = Inches(4.55)
points = [
    ("Most escalations are clean.",
     f" {pct(PAT['Round trip']['share'])} of tickets make a single round trip: handed to 2LS once, answer back once."),
    ("Re-routing is the costly loop.",
     f" Sending a case to 2LS again multiplies the odds of a higher effort score by ×{DEC_R['effort']['ratio']:.0f} "
     f"and lengthens it by {DEC_R['days']['pct']:.0f}%; an extra return from 2LS adds {DEC_X['days']['pct']:.0f}%."),
    ("It shows up in outcomes.",
     f" Resolved at close falls from {pct(BYP['Round trip']['resolved'])} (one round trip) to "
     f"{pct(BYP['4+ crossings']['resolved'])} (4+ crossings); negative end sentiment rises from "
     f"{pct(BYP['Round trip']['sentiment_negative'], 1)} to {pct(BYP['4+ crossings']['sentiment_negative'])}."),
]
refs = [EVID_PAGES["how_often"], EVID_PAGES["where"], EVID_PAGES["cost"]]
for i, (head, body) in enumerate(points):
    number_badge(s, MX, y0 + Inches(0.62 * i), i + 1, fill=ORANGE)
    text(s, MX + Inches(0.6), y0 + Inches(0.62 * i) + Inches(0.06), BODY_W - Inches(0.6), Inches(0.55),
         [[(head, {"bold": True}), (body, {}),
           (f"  Verbatim: slide {refs[i]}", {"size": 12, "color": ORANGE_TXT, "bold": True})]],
         size=15)
source(s, SAMPLE_NOTE + " Effects: regression with controls (slide 9).")
s.notes_slide.notes_text_frame.text = (
    "Back-and-forth = 3 or more tier crossings (a crossing is one hand-off 1LS→2LS or one return 2LS→1LS). "
    f"Per-extra-crossing effects (95% CI): follow-ups ×{E_FUP['ratio']:.2f} [{E_FUP['ratio_lo']:.2f}–{E_FUP['ratio_hi']:.2f}], "
    f"customer messages ×{E_MSGS['ratio']:.2f} [{E_MSGS['ratio_lo']:.2f}–{E_MSGS['ratio_hi']:.2f}], "
    f"days open +{E_DAYS['pct']:.0f}% [{E_DAYS['pct_lo']:.0f}–{E_DAYS['pct_hi']:.0f}%], "
    f"effort score odds ×{E_EFFORT['ratio']:.1f} [{E_EFFORT['ratio_lo']:.1f}–{E_EFFORT['ratio_hi']:.1f}].")

# ═════════════════════════════════════════════════════════════ 3. how we measured
s = new_slide("How we measured it",
              "We read the transcripts, counted every crossing between the tiers, and modelled the effect")
steps = [
    ("Rebuild every conversation",
     f"{num(d['N'])} tickets rebuilt from the raw thread export: duplicates removed, dates and agent changes kept."),
    ("Draw a stratified sample",
     f"{num(d['n_sampled'])} tickets across 239 year × contact reason × resolution code cells, weighted back "
     "to the population."),
    ("Read each transcript with an LLM",
     f"Every judgement comes with a verbatim quote; at least {pct(int(d['grounded_min'] * 1000) / 1000, 1)} "
     "of quotes were found word-for-word in the transcript."),
    ("Model the effect in R",
     "Regression of four effort measures on the number of crossings, holding the ticket's context constant."),
]
for i, (head, body) in enumerate(steps):
    yy = Inches(1.95) + Inches(1.18 * i)
    number_badge(s, MX, yy, i + 1)
    text(s, MX + Inches(0.62), yy - Inches(0.02), Inches(5.3), Inches(1.1),
         [[(head, {"bold": True, "size": 16})], [(body, {"size": 13, "color": MUTED})]], spacing=2)
# crossing diagram
dx, dy = Inches(7.15), Inches(1.95)
rect(s, dx, dy, Inches(5.55), Inches(4.6), CARD, MSO_SHAPE.ROUNDED_RECTANGLE)
text(s, dx + Inches(0.3), dy + Inches(0.22), Inches(5), Inches(0.35), "What counts as a tier crossing",
     size=15, bold=True, color=NAVY)
bx1 = rect(s, dx + Inches(0.45), dy + Inches(0.8), Inches(1.5), Inches(0.8), NAVY, MSO_SHAPE.ROUNDED_RECTANGLE)
bx2 = rect(s, dx + Inches(3.6), dy + Inches(0.8), Inches(1.5), Inches(0.8), NAVY, MSO_SHAPE.ROUNDED_RECTANGLE)
for b, lab in ((bx1, "1LS"), (bx2, "2LS")):
    tf = b.text_frame
    tf.paragraphs[0].alignment = PP_ALIGN.CENTER
    r = tf.paragraphs[0].add_run()
    r.text = lab
    r.font.name, r.font.size, r.font.bold, r.font.color.rgb = FONT, Pt(20), True, WHITE
for yoff, lab, flip in ((0.98, "hand-off", False), (1.38, "return", True)):
    ln = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, dx + Inches(2.0), dy + Inches(yoff),
                                dx + Inches(3.55), dy + Inches(yoff))
    if flip:
        ln.begin_x, ln.end_x = ln.end_x, ln.begin_x
    ln.line.color.rgb = ORANGE
    ln.line.width = Pt(2.5)
    ln.line._get_or_add_ln().append(ln.line._get_or_add_ln().makeelement(
        "{http://schemas.openxmlformats.org/drawingml/2006/main}tailEnd", {"type": "triangle"}))
    text(s, dx + Inches(2.0), dy + Inches(yoff) - Inches(0.3), Inches(1.55), Inches(0.25), lab, size=11,
         color=ORANGE_TXT, align=PP_ALIGN.CENTER, bold=True)
defs = [("0", "Not escalated: 1LS handled it"), ("1", "One-way: handed off, nothing visible came back"),
        ("2", "One round trip: handed off, answer back"),
        ("3+", "Back-and-forth: re-routed to 2LS, or 2LS came back more than once")]
for i, (n_, lab) in enumerate(defs):
    yy = dy + Inches(1.95) + Inches(0.6 * i)
    number_badge(s, dx + Inches(0.4), yy, n_, fill=ORANGE if n_ == "3+" else NAVY, size=0.45)
    text(s, dx + Inches(1.0), yy + Inches(0.08), Inches(4.3), Inches(0.5), lab, size=13)
source(s, "Crossings are counted from the LLM's ordered event list; each event carries its own verbatim quote.")
s.notes_slide.notes_text_frame.text = (
    "Automated acknowledgements and 'ticket still open' reminders are never counted as crossings. A hand-off is an "
    "agent saying the case was raised/forwarded/sent to the technical team, second line, content team or supplier, "
    "including the 'I have initiated the process to add your paper' template (agreed business rule). A return is an "
    "agent relaying what 2LS said or did: an answer, a request for information, a rejection or a completion.")

# ═════════════════════════════════════════════════════════════ 4. how often
s = new_slide("How often it happens",
              f"Two-thirds of tickets make one clean round trip; {pct(d['bf_share_all'], 1)} go back and forth")
cats = [SHORT[p] for p in PATTERNS]
bar_chart(s, MX, Inches(1.85), Inches(7.6), Inches(4.75), cats, [PAT[p]["share"] for p in PATTERNS],
          PATTERN_COLOURS, fmt="0.0%", gap=55, label_size=14, cat_size=12)
cx = MX + Inches(8.0)
text(s, cx, Inches(1.95), Inches(4.1), Inches(0.35), "Inside the back-and-forth", size=16, bold=True,
     color=NAVY)
for i, (bt, head) in enumerate(((REROUTE, "Re-routed to 2LS again"), (EXTRA, "Extra returns from 2LS"))):
    yy = Inches(2.45) + Inches(1.5 * i)
    rect(s, cx, yy, Inches(4.1), Inches(1.32), CARD, MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, cx + Inches(0.22), yy + Inches(0.14), Inches(1.5), Inches(0.7), pct(bt["share_all"], 1), size=32,
         bold=True, color=ORANGE)
    text(s, cx + Inches(1.75), yy + Inches(0.18), Inches(2.2), Inches(1.1),
         [[(head, {"bold": True})],
          [(f"≈{num(bt['est'])} tickets · {pct(bt['effort_med_plus'])} medium-or-higher effort",
            {"size": 12, "color": MUTED})]], size=14, spacing=2)
y25, y26 = YEAR["2025"], YEAR["2026"]
text(s, cx, Inches(5.5), Inches(4.1), Inches(1.1),
     [[("Improving: ", {"bold": True}),
       (f"back-and-forth fell from {pct(y25['bf_of_all'], 1)} of tickets in 2025 to "
        f"{pct(y26['bf_of_all'], 1)} in 2026.", {})]], size=14)
source(s, SAMPLE_NOTE)
s.notes_slide.notes_text_frame.text = (
    f"Shares of all {num(d['N'])} tickets. Among escalated tickets, {pct(d['bf_share_escalated'], 1)} go back and "
    f"forth; mean crossings per escalated ticket = {d['mean_crossings_escalated']:.2f}. Re-routed = 2+ hand-offs to "
    "2LS. Extra returns only = one hand-off but 2LS came back more than once (interim updates relayed, information "
    "requests, rejections). The commonest back-and-forth sequence is escalated > answer > completed, i.e. an "
    "interim update then completion.")

# ═════════════════════════════════════════════════════════════ 4b. in their words: how often
evidence_slide(
    "In their words · how often it happens",
    "A clean escalation, a 1LS fix, a re-route and an extra return, as customers and agents put it",
    [("escalated", "Really escalated", f"{pct(d['escalated_share'], 1)} of tickets"),
     ("not_escalated", "Handled by 1LS alone", f"{pct(1 - d['escalated_share'], 1)} of tickets"),
     ("rerouted", "Re-routed to 2LS again", f"{pct(REROUTE['share_all'], 1)} of tickets"),
     ("extra_returns", "Extra returns from 2LS", f"{pct(EXTRA['share_all'], 1)} of tickets")])
assert _page == EVID_PAGES["how_often"], f"'how often' evidence landed on slide {_page}"

# ═════════════════════════════════════════════════════════════ 5. where
s = new_slide("Where it concentrates",
              f"Three resolution codes carry {pct(top3_share)} of the back-and-forth; "
              "incomplete information loops most often")
rc_sorted = sorted(bf_rc, key=lambda r: -r["bf_of_escalated"])
cats = [f"{r['group']} ({k(r['est'])})" for r in rc_sorted]
vals = [r["bf_of_escalated"] for r in rc_sorted]
bar_chart(s, MX, Inches(1.8), Inches(7.9), Inches(5.0), cats, vals,
          [ORANGE if v >= d["bf_share_escalated"] else CONTEXT for v in vals], fmt="0%", horizontal=True,
          gap=35, label_size=12, cat_size=11)
cx = MX + Inches(8.3)
text(s, cx, Inches(1.95), Inches(3.8), Inches(0.6),
     [[("Back-and-forth rate among escalated tickets", {"bold": True, "size": 15, "color": NAVY})],
      [(f"by resolution code (ticket volume); orange = above the {pct(d['bf_share_escalated'], 1)} average",
        {"size": 12, "color": MUTED})]], spacing=2)
rows = [["Resolution code", "Est. back-and-forth tickets"]]
for r in bf_rc_volume[:3]:
    rows.append([r["group"], num(r["bf_of_all"] * r["est"])])
table(s, cx, Inches(3.05), Inches(3.9), rows, [2.5, 1.4], size=12, row_h=0.5)
cr = [r for r in d["by_contact_reason"] if r["group"] != "Other contact reason"]
text(s, cx, Inches(5.25), Inches(3.9), Inches(1.4),
     [[("By contact reason: ", {"bold": True})]] +
     [[(f"{r['group']} {pct(r['bf_of_escalated'], 1)}", {"size": 13})] for r in cr],
     size=13, spacing=1)
source(s, SAMPLE_NOTE + " Resolution codes with 500+ tickets shown.")
s.notes_slide.notes_text_frame.text = (
    "Rates are the share of escalated tickets with 3+ crossings, weighted. 'Additional Customer Information Not Recd' "
    "has the highest rate: 2LS comes back asking for details the first submission lacked. Volume matters more than "
    "rate for impact: 'Correction Tool used' and 'Sent to Supplier-Missing article' are the two biggest queues.")

# ═════════════════════════════════════════════════════════════ 5b. in their words: where
RC = {r["group"]: r for r in d["by_resolution_code"]}
_info, _ctu = RC["Additional Customer Information Not Recd"], RC["Correction Tool used"]
evidence_slide(
    "In their words · where the loops come from",
    "Loops start with missing information, fixes that don't land, and cases sent round again",
    [("info_not_recd", "Information not received",
      f"{pct(_info['bf_of_escalated'])} of these escalations loop"),
     ("correction_tool", "Correction Tool cases",
      f"≈{num(_ctu['bf_of_all'] * _ctu['est'])} back-and-forth tickets"),
     ("rerouting_cost", "Re-routed, customer left waiting",
      f"+{DEC_R['days']['pct']:.0f}% time open per re-route")])
assert _page == EVID_PAGES["where"], f"'where' evidence landed on slide {_page}"

# ═════════════════════════════════════════════════════════════ 6. effort rises (descriptive)
s = new_slide("Customer effort, as the transcripts show it",
              "Effort climbs with every crossing: most 4+-crossing tickets are high effort")
labels = D["meta"]["effort_labels"]
series = [(labels[j], [BYP[p]["effort_mix"][j] for p in PATTERNS]) for j in range(4)]
stacked_100(s, MX, Inches(1.75), Inches(7.4), Inches(4.9), [SHORT[p] for p in PATTERNS], series, EFFORT_RAMP)
rows = [["", "One round trip", "3 crossings", "4+ crossings"]]
for lab, key, f in (("Resolved at close", "resolved", lambda v: pct(v)),
                    ("Negative end sentiment", "sentiment_negative", lambda v: pct(v, 1)),
                    ("Customer chases (avg)", "mean_chase", lambda v: f"{v:.1f}"),
                    ("Customer messages (avg)", "mean_customer_msgs", lambda v: f"{v:.1f}"),
                    ("Days open (median)", "median_days", lambda v: f"{v:.0f}"),
                    ("Cites a deadline", "deadline", lambda v: pct(v))):
    rows.append([lab] + [f(BYP[p][key]) for p in ("Round trip", "3 crossings", "4+ crossings")])
table(s, MX + Inches(7.75), Inches(1.95), Inches(4.4), rows, [1.55, 0.95, 0.95, 0.95], size=11, row_h=0.52)
text(s, MX + Inches(7.75), Inches(5.75), Inches(4.4), Inches(0.9),
     "Descriptive, before controls: harder tickets may also bounce more. The next two slides "
     "separate the crossings' own effect.", size=12, color=MUTED, italic=True)
source(s, SAMPLE_NOTE + " Effort score: LLM judgement from the transcript, with quoted evidence.")
s.notes_slide.notes_text_frame.text = (
    "Effort mix is weighted within each pattern. One-way tickets (handed off, nothing visible came back) carry more "
    "effort than clean round trips because the customer is left waiting without an answer; they are kept as their "
    "own group in the models so they do not distort the per-crossing slope.")

# ═════════════════════════════════════════════════════════════ 7. modelling approach
s = new_slide("Quantifying the impact",
              "Four regressions isolate what an extra crossing adds, holding the ticket's context constant")
rows = [["Effort measure", "Source", "Model", "Reads as"],
        ["Customer follow-ups after the first reply", "Message counts", "Poisson", "× more follow-ups"],
        ["Customer messages", "Message counts", "Poisson", "× more messages"],
        ["Days open, first to last message", "Timestamps", "Linear on log(1 + days)", "% longer"],
        ["Customer-effort score (4 levels)", "LLM reading, quoted", "Ordinal logit", "× odds of a higher score"]]
table(s, MX, Inches(1.9), Inches(8.0), rows, [3.1, 1.75, 1.75, 1.4], size=13, row_h=0.6)
text(s, MX, Inches(5.15), Inches(8.0), Inches(1.5),
     [[("Exposure: ", {"bold": True}),
       ("extra crossings beyond one round trip (0, 1, 2 …), with not-escalated and one-way tickets as separate groups.",
        {})],
      [("Held constant: ", {"bold": True}),
       ("year, contact reason, resolution code (the 239 sampling cells), channel, customer type.", {})],
      [("Robustness: ", {"bold": True}),
       ("robust (HC1) standard errors; a survey-weighted re-fit points the same way on all four measures.", {})]],
     size=13, spacing=6)
cx = MX + Inches(8.45)
rect(s, cx, Inches(1.9), Inches(3.7), Inches(4.75), CARD, MSO_SHAPE.ROUNDED_RECTANGLE)
text(s, cx + Inches(0.25), Inches(2.1), Inches(3.2), Inches(4.4),
     [[("Why lead with the measured outcomes", {"bold": True, "size": 15, "color": NAVY})],
      [("Follow-ups, messages and days open come straight from the ticket record, independent of the model that "
        "counted the crossings.", {"size": 13})],
      [("The LLM's effort scale itself mentions being passed around and waiting on 2LS, so its link to crossings is "
        "partly by construction. It is shown as corroboration, not as the headline.", {"size": 13})],
      [(f"All four effects are significant at p < 0.001 (n = {num(E_FUP['n'])}) and hold in the "
        "survey-weighted re-fit.", {"size": 13, "bold": True})]],
     spacing=8)
source(s, "Models: scripts/build_s2ls_deck_data.R (MASS::polr, lm, glm; sandwich HC1). n = "
          f"{num(E_FUP['n'])} tickets.")
s.notes_slide.notes_text_frame.text = (
    "Primary fits are unweighted with the sampling strata as fixed effects: because sampling depended only on the "
    "strata, which are controlled, the conditional effects need no weights. Days-open predictions are back-transformed "
    "without smearing, giving a typical (geometric-mean) figure; Duan smearing overstated observed means. The "
    "association is not proof of causation: unobserved complexity can raise both crossings and effort; the controls "
    "absorb what contact reason and resolution code explain.")

# ═════════════════════════════════════════════════════════════ 8. results
s = new_slide("What one extra crossing costs",
              f"Each extra crossing: +{E_FUP['pct']:.0f}% follow-ups, +{E_MSGS['pct']:.0f}% messages, "
              f"+{E_DAYS['pct']:.0f}% time open")
cards = [(E_FUP, "customer follow-ups"), (E_MSGS, "customer messages"), (E_DAYS, "time open"),
         (E_EFFORT, "odds of a higher effort score")]
cw, cg = Inches(2.86), Inches(0.22)
for i, (e, lab) in enumerate(cards):
    x = MX + i * (cw + cg)
    big = f"×{e['ratio']:.1f}" if e is E_EFFORT else f"+{e['pct']:.0f}%"
    ci = (f"95% CI ×{e['ratio_lo']:.1f}–{e['ratio_hi']:.1f}" if e is E_EFFORT
          else f"95% CI +{e['pct_lo']:.0f}% to +{e['pct_hi']:.0f}%")
    stat_tile(s, x, Inches(1.95), cw, Inches(2.1), big, lab, ci, big_color=ORANGE if i < 3 else NAVY)
text(s, MX, Inches(4.35), BODY_W, Inches(0.4), "Which kind of crossing drives it", size=16, bold=True,
     color=NAVY)
rows = [["Per extra …", "Follow-ups", "Messages", "Days open", "Effort-score odds", "Share of tickets"],
        ["Re-routing to 2LS", f"+{DEC_R['followups']['pct']:.0f}%", f"+{DEC_R['msgs']['pct']:.0f}%",
         f"+{DEC_R['days']['pct']:.0f}%", f"×{DEC_R['effort']['ratio']:.1f}", pct(REROUTE["share_all"], 1)],
        ["Return from 2LS", f"+{DEC_X['followups']['pct']:.0f}%", f"+{DEC_X['msgs']['pct']:.0f}%",
         f"+{DEC_X['days']['pct']:.0f}%", f"×{DEC_X['effort']['ratio']:.1f}", pct(EXTRA["share_all"], 1)]]
table(s, MX, Inches(4.85), BODY_W, rows, [2.8, 1.8, 1.8, 1.8, 2.0, 1.93], size=13, row_h=0.5, highlight_rows=(1,))
text(s, MX, Inches(6.45), BODY_W, Inches(0.35),
     "Re-routing costs roughly three times as much time as an extra return, and it happens on 2.6% of tickets.",
     size=13, color=MUTED, italic=True)
source(s, "Regression estimates per extra crossing beyond one round trip; controls as on the previous slide.")
s.notes_slide.notes_text_frame.text = (
    "Sensitivity (survey-weighted): " + "; ".join(
        f"{e['outcome']} ×{e['ratio']:.2f} [{e['ratio_lo']:.2f}–{e['ratio_hi']:.2f}]" for e in M["sensitivity"])
    + ". All p < 0.01. Decomposition model: extra hand-offs and extra returns entered separately, with a no-return "
      "indicator for escalated tickets where nothing came back.")

# ═════════════════════════════════════════════════════════════ 9. predictions
s = new_slide("The same customer, a different journey",
              "Model-predicted experience for an otherwise identical ticket, by number of crossings")
pl = ["Round trip", "3 crossings", "4+ crossings"]
cats = [SHORT[p] for p in pl]
cols = [NAVY, ORANGE, ORANGE]
chw, chg = Inches(3.9), Inches(0.2)
for i, (key, ttl, fmt) in enumerate((("p_medium_plus", "Chance of medium-or-higher effort", "0%"),
                                      ("customer_msgs", "Customer messages", "0.0"),
                                      ("days_open", "Typical days open", "0"))):
    x = MX + i * (chw + chg)
    rect(s, x, Inches(1.8), chw, Inches(4.35), CARD, MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, x + Inches(0.25), Inches(1.95), chw - Inches(0.5), Inches(0.35), ttl, size=15, bold=True,
         color=NAVY)
    vals = [PRED[p][key] for p in pl]
    bar_chart(s, x + Inches(0.15), Inches(2.35), chw - Inches(0.3), Inches(3.7), cats, vals, cols, fmt=fmt,
              gap=45, label_size=16, cat_size=12, vmax=(1.0 if key == "p_medium_plus" else max(vals) * 1.2))
ne, ow = PRED["Not escalated"], PRED["One-way"]
text(s, MX, Inches(6.3), BODY_W, Inches(0.5),
     [[("For reference: ", {"bold": True}),
       (f"not escalated {pct(ne['p_medium_plus'])} medium-or-higher effort, {ne['customer_msgs']:.1f} messages, "
        f"{ne['days_open']:.0f} days · one-way {pct(ow['p_medium_plus'])}, {ow['customer_msgs']:.1f} messages, "
        f"{ow['days_open']:.0f} days.", {})]], size=13, color=MUTED)
source(s, "Average model predictions: every ticket set to each journey, its other characteristics as observed, "
          "weighted to the population.")
s.notes_slide.notes_text_frame.text = (
    f"Probability of a HIGH effort score: round trip {pct(PRED['Round trip']['p_high'], 1)}, 3 crossings "
    f"{pct(PRED['3 crossings']['p_high'], 1)}, 4+ crossings {pct(PRED['4+ crossings']['p_high'], 1)}. "
    "Predictions come from the pattern-dummy versions of the ordinal, log-linear and Poisson models.")

# ═════════════════════════════════════════════════════════════ 9b. in their words: the cost
evidence_slide(
    "In their words · what it costs the customer",
    "Customers chase, wait and lose patience as the crossings add up",
    [("followups", "More follow-ups", f"+{E_FUP['pct']:.0f}% per extra crossing"),
     ("time_open", "Longer open", f"+{E_DAYS['pct']:.0f}% per extra crossing"),
     ("negative_end", "Worse endings",
      f"negative end: {pct(BYP['Round trip']['sentiment_negative'], 1)} → "
      f"{pct(BYP['4+ crossings']['sentiment_negative'])}"),
     ("deadline", "Higher stakes",
      f"cites a deadline: {pct(BYP['Round trip']['deadline'])} → {pct(BYP['4+ crossings']['deadline'])}")])
assert _page == EVID_PAGES["cost"], f"'cost' evidence landed on slide {_page}"

# ═════════════════════════════════════════════════════════════ 10. what a loop looks like
s = new_slide("What a loop looks like",
              "In the agents' own words: back and forth while the customer waits")
# One example of each kind of back-and-forth, chosen by reading the candidates the R script
# drew at random. Falls back to the first two candidates if a re-run draws different tickets.
PICK = [("260303-017037", "Re-routed: raised with 2LS three times"),
        ("260701-011017", "Extra return: an interim update, then the fix")]
by_ref = {q["ref"]: q for q in D["quotes"]}
qs = [(by_ref[r], cap) for r, cap in PICK if r in by_ref] or \
     [(q, f"Ticket {q['ref']}") for q in D["quotes"][:2]]
EVLAB = {"escalated": "Hand-off to 2LS", "re_escalated": "Re-routed to 2LS", "chased_2ls": "1LS chases 2LS",
         "info_request_from_2ls": "2LS needs more information", "answer_from_2ls": "Update from 2LS",
         "completed_by_2ls": "Completed by 2LS", "rejected_by_2ls": "Rejected by 2LS"}
colw = Inches(5.9)
for qi, (q, cap) in enumerate(qs):
    x = MX + qi * (colw + Inches(0.33))
    rect(s, x, Inches(1.85), colw, Inches(4.8), CARD, MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, x + Inches(0.3), Inches(2.0), colw - Inches(0.6), Inches(0.5),
         [[(cap, {"bold": True, "size": 15, "color": NAVY})],
          [(f"Ticket {q['ref']}", {"size": 11, "color": MUTED})]], spacing=1)
    seen_handoff = False
    for ei, ev in enumerate(q["events"][:4]):
        yy = Inches(2.75) + Inches(0.98 * ei)
        kind = ev["event"]
        label = EVLAB.get(kind, kind)
        if kind == "escalated" and seen_handoff:
            label = "Raised with 2LS again"
        is_back = kind != "escalated" or seen_handoff
        seen_handoff = seen_handoff or kind == "escalated"
        number_badge(s, x + Inches(0.3), yy, ei + 1, fill=ORANGE if is_back else NAVY, size=0.4)
        text(s, x + Inches(0.85), yy - Inches(0.02), colw - Inches(1.15), Inches(0.9),
             [[(label, {"bold": True, "size": 13})],
              [(f"“{ev['quote']}”", {"size": 12, "italic": True, "color": INK})]], spacing=1)
source(s, "Verbatim agent quotes from the transcripts, as extracted by the LLM and checked against the text.")
s.notes_slide.notes_text_frame.text = (
    "Quotes are picked at random among back-and-forth tickets whose first events contain no personal names or email "
    "addresses. Event labels are the LLM's classification of each crossing.")

# ═════════════════════════════════════════════════════════════ 11. caveats
s = new_slide("Reading these results",
              "What the numbers can and cannot tell you")
cav = [
    ("Association, not proof.", " Harder cases may both bounce and cost more. Controls for contact reason, resolution "
                                "code, year, channel and customer type absorb much of that, not all of it."),
    ("Transcript-visible only.", " A hand-off done silently in the ticketing system, with no trace in any message, "
                                 "is invisible here."),
    ("Interim updates count as returns.", " An extra return can be a status update relayed from 2LS. That is why "
                                          "re-routing and extra returns are reported separately."),
    ("The effort score is a model reading.", " It is corroborated by the measured outcomes, but there is no survey "
                                             "(CES/CSAT) ground truth in this data."),
    ("Sample estimates.", f" {num(d['n_sampled'])} of {num(d['N'])} tickets, weighted; cell-level figures are "
                          "reportable where 30+ tickets were read."),
]
for i, (head, body) in enumerate(cav):
    yy = Inches(1.8) + Inches(0.9 * i)
    number_badge(s, MX, yy, i + 1, fill=CONTEXT, color=INK)
    text(s, MX + Inches(0.62), yy + Inches(0.04), Inches(11.4), Inches(0.8),
         [[(head, {"bold": True}), (body, {})]], size=15)
source(s, "Full coefficient tables: runs/output/s2ls_deck/s2ls_effort_models.xlsx")

# ═════════════════════════════════════════════════════════════ 12. what to do
s = new_slide("Where to act", "Cut the loops, not the escalations", dark=True)
acts = [
    ("Get it complete before the first hand-off",
     "'Additional Customer Information Not Recd' loops most often. A checklist of what 2LS needs "
     "(DOIs, links, proof) at intake removes the information-request round trip."),
    ("Stop re-routing",
     f"Re-routing is {pct(REROUTE['share_all'], 1)} of tickets but the costliest crossing "
     f"(+{DEC_R['days']['pct']:.0f}% time open). Route to the right 2LS team first time."),
    ("Close the loop in one message",
     "Interim relays from 2LS each add a crossing. Where 2LS can reply to the customer directly or "
     "in one final message, do so."),
    ("Track crossings as a KPI",
     "Crossings per ticket can be counted from transcripts. Monitor it by resolution code, starting "
     "with 'Correction Tool used' and 'Multiple'."),
]
aw, ag = Inches(5.9), Inches(0.33)
for i, (head, body) in enumerate(acts):
    x = MX + (i % 2) * (aw + ag)
    y = Inches(1.95) + (i // 2) * Inches(1.95)
    rect(s, x, y, aw, Inches(1.7), RGBColor(0x14, 0x3A, 0x62), MSO_SHAPE.ROUNDED_RECTANGLE)
    number_badge(s, x + Inches(0.3), y + Inches(0.3), i + 1, fill=ORANGE)
    text(s, x + Inches(0.9), y + Inches(0.3), aw - Inches(1.2), Inches(1.6),
         [[(head, {"bold": True, "size": 17, "color": WHITE})], [(body, {"size": 13, "color": ICE})]], spacing=4)
text(s, MX, H - Inches(0.55), BODY_W, Inches(0.3),
     "Suggested actions follow from the patterns above; each should be tested against a baseline before roll-out.",
     size=11, color=ICE, italic=True)

prs.save(OUT)
print(f"Wrote {OUT.relative_to(BASE)} ({_page} slides)")
