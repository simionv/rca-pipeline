"""Use-case review and streamlining proposal deck (October 2026).

    & "C:\\Program Files\\Python311\\python.exe" scripts\\build_usecase_review_deck.py

Every word on the slides comes from runs/usecase_review/content.json, which was
written from, and fact-checked against, the read-only survey of this repo (see
the appendix slide "How this review was produced"). Same house style as
scripts/build_exec_deck.py: navy / orange, Segoe UI, 16:9.
"""
from __future__ import annotations

import json
import math
import re
import sys
from datetime import date
from pathlib import Path

try:
    from lxml import etree
    from pptx import Presentation
    from pptx.chart.data import CategoryChartData
    from pptx.dml.color import RGBColor
    from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
    from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
    from pptx.oxml.ns import qn
    from pptx.util import Emu, Inches, Pt
except ModuleNotFoundError:                                          # pragma: no cover
    sys.exit('Run with:  & "C:\\Program Files\\Python311\\python.exe" '
             'scripts\\build_usecase_review_deck.py')

BASE = Path(__file__).resolve().parent.parent
SRC = BASE / "runs" / "usecase_review" / "content.json"
OUT = BASE / "docs" / "RCA_UseCase_Review_2026.pptx"
C = json.loads(SRC.read_text(encoding="utf-8"))

NAVY = RGBColor(0x0B, 0x2A, 0x4A)
ORANGE = RGBColor(0xFF, 0x6C, 0x00)
GREY = RGBColor(0x7A, 0x87, 0x94)
LIGHT = RGBColor(0xEE, 0xF1, 0xF4)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
RED = RGBColor(0xC1, 0x27, 0x2D)
GREEN = RGBColor(0x2E, 0x7D, 0x5B)
MID = RGBColor(0x1B, 0x4C, 0x7A)
PALE_NAVY = RGBColor(0xC9, 0xD6, 0xE3)
INK = RGBColor(0x26, 0x32, 0x3F)

FAMILY_COL = {"A": MID, "B": GREEN, "C": ORANGE,
              "D": RGBColor(0x6B, 0x4C, 0x9A), "E": RGBColor(0x0E, 0x7C, 0x86)}
MATURITY = {   # label, fill
    "exploratory": ("Exploratory", GREY),
    "repeatable-with-effort": ("Repeatable with effort", RGBColor(0xC7, 0x7C, 0x02)),
    "repeatable": ("Repeatable", GREEN),
    "productionisable": ("Productionisable", NAVY),
    "proposal": ("Proposal", RGBColor(0x9A, 0xA5, 0xB1)),
}
TIER_FILL = {"A": RGBColor(0xD8, 0xEE, 0xE1), "B": RGBColor(0xE4, 0xF1, 0xE8),
             "C": RGBColor(0xFF, 0xE8, 0xCC), "D": RGBColor(0xF6, 0xE1, 0xE1)}
FONT = "Segoe UI"
MONO = "Consolas"

W, H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.62)
BODY_W = W - 2 * MARGIN
FOOT = "RCA pipeline  ·  use-case review and streamlining proposal  ·  October 2026"

prs = Presentation()
prs.slide_width, prs.slide_height = W, H
BLANK = prs.slide_layouts[6]
_footers: list = []


# ───────────────────────────────────────────────────────────── text helpers
def clean(t) -> str:
    """Slides carry no markdown: drop **, backticks and stray whitespace."""
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", str(t))
    t = t.replace("`", "").replace("->", "→").replace("<-", "←")
    return re.sub(r"\s+", " ", t).strip()


def est_height(texts, w_in, size, gap_pt=4, bold=False, indent_in=0.0, lh=1.22):
    """Rough rendered height (inches) of wrapped paragraphs in Segoe UI."""
    cw = (0.56 if bold else 0.53) * size / 72          # average glyph width, inches
    cpl = max(8, int((w_in - indent_in) / cw))
    lines = 0
    for t in texts:
        words, cur, n = clean(t).split(" "), 0, 1
        for wd in words:
            add = len(wd) + (1 if cur else 0)
            if cur + add > cpl and cur:
                n, cur = n + 1, len(wd)
            else:
                cur += add
        lines += n
    return (lines * size * lh + gap_pt * max(0, len(texts) - 1)) / 72


def fit(texts, w_in, h_in, sizes=(12, 11.5, 11, 10.5, 10, 9.5, 9, 8.5), **kw):
    for s in sizes:
        if est_height(texts, w_in, s, **kw) <= h_in:
            return s
    return sizes[-1]


def _tx(s, left, top, width, height, anchor=MSO_ANCHOR.TOP):
    box = s.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    return tf


def _p(tf, text, size=14, bold=False, color=NAVY, after=6, first=False,
       align=PP_ALIGN.LEFT, italic=False, font=FONT):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.space_after = Pt(after)
    r = p.add_run()
    r.text = clean(text) if font == FONT else str(text)
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.color.rgb = color
    r.font.name = font
    return p


def _bullet(p, char="•", color=None, indent=0.17, num=False):
    pPr = p._p.get_or_add_pPr()
    pPr.set("marL", str(int(Inches(indent))))
    pPr.set("indent", str(-int(Inches(indent))))
    if color is not None:
        clr = etree.SubElement(pPr, qn("a:buClr"))
        srgb = etree.SubElement(clr, qn("a:srgbClr"))
        srgb.set("val", str(color))
    if num:
        bu = etree.SubElement(pPr, qn("a:buFont")); bu.set("typeface", FONT)
        an = etree.SubElement(pPr, qn("a:buAutoNum")); an.set("type", "arabicPeriod")
    else:
        bu = etree.SubElement(pPr, qn("a:buFont")); bu.set("typeface", "Arial")
        ch = etree.SubElement(pPr, qn("a:buChar")); ch.set("char", char)


def bullets(s, items, left, top, width, height, color=INK, bullet_color=None,
            sizes=(12, 11.5, 11, 10.5, 10, 9.5, 9, 8.5), num=False, char="•",
            after=4, bold_first=False):
    items = [clean(i) for i in items if clean(i)]
    size = fit(items, width / 914400, height / 914400, sizes, gap_pt=after,
               indent_in=0.2)
    tf = _tx(s, left, top, width, height)
    indent = 0.1 + size * 0.0105 + (0.06 if num or char != "•" else 0)
    for i, it in enumerate(items):
        p = _p(tf, it, size=size, color=color, after=after, first=(i == 0))
        _bullet(p, char=char, color=bullet_color or color, num=num, indent=indent)
    return size


def para(s, text, left, top, width, height, color=INK,
         sizes=(14, 13, 12, 11.5, 11, 10.5, 10, 9.5, 9), bold=False,
         align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, italic=False):
    size = fit([text], width / 914400, height / 914400, sizes, bold=bold)
    tf = _tx(s, left, top, width, height, anchor)
    _p(tf, text, size=size, bold=bold, color=color, first=True, after=0,
       align=align, italic=italic)
    return size


def label(s, text, left, top, width=Inches(4), color=ORANGE, size=9.5):
    _p(_tx(s, left, top, width, Inches(0.22)), text.upper(), size=size,
       bold=True, color=color, first=True, after=0)


# ──────────────────────────────────────────────────────────── shape helpers
def box(s, left, top, width, height, fill=LIGHT, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
        radius=0.05):
    sh = s.shapes.add_shape(shape, left, top, width, height)
    if fill is None:
        sh.fill.background()
    else:
        sh.fill.solid(); sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line; sh.line.width = Pt(1)
    sh.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        sh.adjustments[0] = radius
    return sh


def chip(s, text, left, top, fill, color=WHITE, size=9, height=Inches(0.26), pad=0.14):
    width = Inches(len(text) * size * 0.56 / 72 + 2 * pad)
    sh = box(s, left, top, width, height, fill=fill, radius=0.5)
    tf = sh.text_frame
    tf.margin_left = tf.margin_right = Inches(pad * 0.6)
    tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    _p(tf, text, size=size, bold=True, color=color, first=True, after=0, align=PP_ALIGN.CENTER)
    return width


def circle(s, text, left, top, d, fill, color=WHITE, size=12):
    sh = box(s, left, top, d, d, fill=fill, shape=MSO_SHAPE.OVAL)
    tf = sh.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    _p(tf, text, size=size, bold=True, color=color, first=True, after=0, align=PP_ALIGN.CENTER)
    return sh


def line(s, x1, y1, x2, y2, color=GREY, width=1.0):
    ln = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
    ln.line.color.rgb = color
    ln.line.width = Pt(width)
    return ln


def table(s, rows, left, top, width, col_fracs, row_h=Inches(0.27), size=9,
          header_fill=NAVY, fills=None, bold_col0=True, aligns=None, header_size=None):
    n, m = len(rows), len(rows[0])
    gf = s.shapes.add_table(n, m, left, top, width, row_h * n)
    tbl = gf.table
    tbl.first_row = True
    tbl.horz_banding = False
    for j, f in enumerate(col_fracs):
        tbl.columns[j].width = Emu(int(width * f / sum(col_fracs)))
    for i, r in enumerate(rows):
        tbl.rows[i].height = min(row_h, Inches(0.36)) if i == 0 else row_h
        for j, v in enumerate(r):
            c = tbl.cell(i, j)
            c.text = ""
            c.fill.solid()
            if i == 0:
                c.fill.fore_color.rgb = header_fill
            else:
                c.fill.fore_color.rgb = (fills[i][j] if fills and fills[i] and fills[i][j]
                                         else (WHITE if i % 2 else LIGHT))
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            c.margin_left = c.margin_right = Inches(0.06)
            c.margin_top = c.margin_bottom = Inches(0.02)
            al = aligns[j] if aligns else PP_ALIGN.LEFT
            _p(c.text_frame, v, size=(header_size or size) if i == 0 else size,
               bold=(i == 0) or (bold_col0 and j == 0),
               color=WHITE if i == 0 else INK, first=True, after=0, align=al)
    return tbl


# ───────────────────────────────────────────────────────────── slide frames
def slide(title, subtitle=None, kicker=None, title_size=27):
    s = prs.slides.add_slide(BLANK)
    top = Inches(0.34)
    if kicker:
        _p(_tx(s, MARGIN, top, BODY_W, Inches(0.24)), kicker.upper(), size=11,
           bold=True, color=ORANGE, first=True)
        top = Inches(0.62)
    size = fit([title], BODY_W / 914400, 0.5, (title_size, 25, 23, 21), bold=True)
    _p(_tx(s, MARGIN, top, BODY_W, Inches(0.55)), title, size=size, bold=True, first=True)
    if subtitle:
        para(s, subtitle, MARGIN, top + Inches(0.56), BODY_W, Inches(0.42), color=GREY,
             sizes=(13, 12, 11.5, 11))
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), H - Inches(0.30), W, Inches(0.30))
    bar.fill.solid(); bar.fill.fore_color.rgb = LIGHT; bar.line.fill.background()
    bar.shadow.inherit = False
    tf = _tx(s, MARGIN, H - Inches(0.255), BODY_W, Inches(0.2))
    _footers.append(tf)
    return s


def dark_slide():
    s = prs.slides.add_slide(BLANK)
    bg = s.background.fill
    bg.solid(); bg.fore_color.rgb = NAVY
    _footers.append(None)
    return s


def notes(s, *chunks):
    text = "\n\n".join(clean(c) for c in chunks if c)
    if text:
        s.notes_slide.notes_text_frame.text = text


# ─────────────────────────────────────────────────────────────── content
EXEC = C["exec"]
FAMS = {f["key"]: f for f in C["families"]}
UCS = C["deck_ucs"]
UC_BY_ID = {u["id"]: u for u in UCS}
DOC_BY_ID = {u["id"]: u for u in C["doc_ucs"]}
PROP = C["proposal"]


def fam_of(uc_id: str) -> str:
    m = re.match(r"UC-([A-E])\d", uc_id)
    return m.group(1) if m else "A"


SHORT = {
    "UC-A1-MENDELEY-RCA": ("Mendeley access RCA", "Mendeley"),
    "UC-A2-MENDELEY-DRILLDOWNS": ("Mendeley identity drill-downs", "Mendeley"),
    "UC-A3-MENDELEY-DELETION-AUDIT": ("Mendeley deletion keyword audit", "Mendeley"),
    "UC-A4-SCOPUS-ACCESS-SAM": ("Scopus access RCA + suspicious-activity audit", "Scopus"),
    "UC-B1-LEAPSPACE-CR-RC": ("LeapSpace CR → RC (gold set, two-step)", "LeapSpace"),
    "UC-B2-EVOLVE-CR-RC": ("Evolve CR → RC (11 × 54)", "Evolve"),
    "UC-B3-SD-TWO-STAGE": ("ScienceDirect two-stage CR → RC", "ScienceDirect"),
    "UC-B4-SD-ACCESSING-CONTENT": ("SD 'Accessing Content' (spec-driven)", "ScienceDirect"),
    "UC-C1-SCOPUS-CONTENT-EFFORT": ("Scopus Content effort vs CES", "Scopus Content"),
    "UC-C2-CSD-EFFORT": ("CSD customer effort + driver model", "Scopus CSD"),
    "UC-C3-CSD-DSAT": ("CSD DSAT deep dive", "Scopus CSD"),
    "UC-C4-SCOPUS-2LS-ESCALATION": ("Scopus 2LS escalation back-and-forth", "Scopus 2LS"),
    "UC-D1-SCOPUS-POLICY-AREAS": ("Scopus policy areas (PA0–PA18)", "Scopus Content"),
    "UC-D2-SCOPUS-POLICY-RULES": ("Scopus 49 atomic policy rules", "Scopus Content"),
    "UC-D3-CSD-VALIDATION-RULES": ("CSD validation-rule conformance", "Scopus CSD"),
    "UC-E1-EMAIL-REGISTRATION": ("Email registration (LeapSpace, Embase)", "LeapSpace, Embase"),
    "UC-E2-REGID-BULKID": ("Registration ID / BulkID", "ID+, ClinicalKey, STATdx"),
    "UC-E3-CKAI-PHI-SCREENING": ("ClinicalKey AI PHI screening", "ClinicalKey AI"),
}
FAM_SHORT = {"A": "Access RCA & audits", "B": "SME codebook CR → RC", "C": "Effort & survey",
             "D": "Policy & rule conformance", "E": "Gate-then-classify"}


def short_title(u):
    return SHORT.get(u["id"], (clean(u["title"]).split(":")[0], ""))[0]


def short_product(u):
    return SHORT.get(u["id"], ("", clean(u["product"])[:30]))[1]


# ═══════════════════════════════════════════════════════ 1 · title
s = dark_slide()
circle(s, "", Inches(10.6), Inches(-1.2), Inches(4.2), MID)
circle(s, "", Inches(11.9), Inches(4.9), Inches(2.6), ORANGE)
_p(_tx(s, MARGIN, Inches(1.55), Inches(9.6), Inches(0.3)), "RCA PIPELINE  ·  CUSTOM TAXONOMY",
   size=13, bold=True, color=ORANGE, first=True)
para(s, EXEC["title"], MARGIN, Inches(1.95), Inches(9.4), Inches(1.7), color=WHITE,
     sizes=(40, 38, 36, 34, 32), bold=True)
para(s, EXEC["subtitle"], MARGIN, Inches(3.75), Inches(9.0), Inches(0.9), color=PALE_NAVY,
     sizes=(18, 17, 16, 15))
_p(_tx(s, MARGIN, Inches(5.9), Inches(8), Inches(0.3)),
   "October 2026  ·  built from a read-only review of the repository (notebooks 00–19, scripts, "
   "engine code, run artefacts)", size=11, color=PALE_NAVY, first=True)

# ═══════════════════════════════════════════════════════ 2 · executive summary
s = slide("Executive summary", kicker="what we have built since March 2026")
k = EXEC["kpis"]
gap = Inches(0.18)
tw = int((BODY_W - gap * (len(k) - 1)) / len(k))
for i, kp in enumerate(k):
    x = MARGIN + i * (tw + gap)
    box(s, x, Inches(1.22), tw, Inches(1.22), fill=LIGHT)
    para(s, kp["value"], x + Inches(0.15), Inches(1.30), tw - Inches(0.3), Inches(0.6),
         color=ORANGE if i == 0 else NAVY, sizes=(30, 28, 26, 24, 22), bold=True)
    para(s, kp["label"], x + Inches(0.15), Inches(1.88), tw - Inches(0.3), Inches(0.5),
         color=GREY, sizes=(11, 10.5, 10, 9.5))
label(s, "What we found", MARGIN, Inches(2.75))
tk = EXEC["takeaways"]
y = Inches(3.05)
avail = Inches(3.75)
size = fit(tk, 7.0, avail / 914400 - 0.25 * len(tk), (14, 13.5, 13, 12.5, 12, 11.5, 11), gap_pt=0)
for i, t in enumerate(tk):
    circle(s, str(i + 1), MARGIN, y + Inches(0.02), Inches(0.34), NAVY, size=12)
    h = Inches(est_height([t], 6.8, size) + 0.22)
    para(s, t, MARGIN + Inches(0.5), y, Inches(6.8), h, sizes=(size,))
    y += h
px = MARGIN + Inches(7.75)
pw = BODY_W - Inches(7.75)
box(s, px, Inches(2.75), pw, Inches(4.0), fill=NAVY)
label(s, "What we propose", px + Inches(0.3), Inches(2.95), color=ORANGE)
para(s, EXEC["headline"], px + Inches(0.3), Inches(3.25), pw - Inches(0.6), Inches(1.55),
     color=WHITE, sizes=(16, 15, 14, 13, 12.5), bold=True)
sk = [x["name"] for x in PROP["skeleton"]]
para(s, "  ›  ".join(sk), px + Inches(0.3), Inches(4.95), pw - Inches(0.6), Inches(0.55),
     color=PALE_NAVY, sizes=(12, 11.5, 11, 10.5))
para(s, clean(PROP["min_cut"]), px + Inches(0.3), Inches(5.55), pw - Inches(0.6), Inches(1.05),
     color=PALE_NAVY, sizes=(11, 10.5, 10, 9.5, 9))
notes(s, *EXEC["takeaways"], EXEC["headline"])

# ═══════════════════════════════════════════════════════ 3 · timeline
s = slide("Eighteen use cases in seven months",
          "One lane per family. Runs before 4 June predate cost tracking; git history starts on 3 August.",
          kicker="portfolio timeline")
tl = sorted(C.get("timeline_deck") or C["timeline"], key=lambda e: e["date"])
d0, d1 = date(2026, 3, 1), date(2026, 10, 10)
GUT = Inches(1.95)
x0, x1 = MARGIN + GUT, W - MARGIN - Inches(0.1)
LW = Inches(1.62)
lane_top, lane_h = Inches(1.75), Inches(1.0)


def xpos(dstr):
    d = date.fromisoformat(dstr[:10])
    return int(x0 + (x1 - x0) * (d - d0).days / (d1 - d0).days)


for mth in range(3, 11):
    xm = xpos(f"2026-{mth:02d}-01")
    line(s, xm, lane_top - Inches(0.12), xm, lane_top + lane_h * 5, color=PALE_NAVY, width=0.75)
    _p(_tx(s, xm + Inches(0.04), lane_top - Inches(0.36), Inches(0.8), Inches(0.22)),
       date(2026, mth, 1).strftime("%b"), size=10, bold=True, color=NAVY, first=True, after=0)
for li, fk in enumerate("ABCDE"):
    col = FAMILY_COL[fk]
    cy = lane_top + lane_h * li + lane_h // 2
    if li % 2 == 0:
        box(s, MARGIN, lane_top + lane_h * li, BODY_W, lane_h, fill=RGBColor(0xF6, 0xF8, 0xFA),
            shape=MSO_SHAPE.RECTANGLE)
    circle(s, fk, MARGIN + Inches(0.05), cy - Inches(0.17), Inches(0.34), col, size=12)
    para(s, FAM_SHORT[fk], MARGIN + Inches(0.48), cy - Inches(0.2), GUT - Inches(0.55), Inches(0.42),
         color=NAVY, bold=True, sizes=(10, 9.5, 9), anchor=MSO_ANCHOR.MIDDLE)
    line(s, x0, cy, x1, cy, color=col, width=1.25)
    # greedy placement: alternate above/below; merge into the previous label on that
    # side when they would overlap, so nothing collides
    groups = {-1: [], 1: []}
    side = -1

    def _left(x):
        return min(x - Inches(0.06), W - MARGIN - LW)

    def _clash(g, xc):
        return g is not None and _left(xc) < _left(g["x0"]) + LW + Inches(0.08)

    for e in [e for e in tl if (e.get("family") or "A")[:1].upper() == fk]:
        xc = xpos(e["date"])
        prev = groups[side][-1] if groups[side] else None
        if _clash(prev, xc):
            other = groups[-side][-1] if groups[-side] else None
            if not _clash(other, xc):
                side = -side
            else:
                prev["items"].append(e)
                continue
        groups[side].append({"x0": xc, "items": [e]})
        side = -side
    for sd, gl_ in groups.items():
        for g in gl_:
            for e in g["items"]:
                circle(s, "", xpos(e["date"]) - Inches(0.06), cy - Inches(0.06), Inches(0.12), col)
            ds = [date.fromisoformat(e["date"][:10]) for e in g["items"]]
            dl = (f"{ds[0].day} {ds[0].strftime('%b')}" if len(set(ds)) == 1 else
                  f"{ds[0].day}–{ds[-1].day} {ds[-1].strftime('%b')}" if ds[0].month == ds[-1].month else
                  f"{ds[0].day} {ds[0].strftime('%b')}–{ds[-1].day} {ds[-1].strftime('%b')}")
            txt = "; ".join(clean(e.get("label_short") or e["label"]) for e in g["items"])
            lx = _left(g["x0"])
            ly = cy - Inches(0.47) if sd < 0 else cy + Inches(0.09)
            tf = _tx(s, lx, ly, LW, Inches(0.40), MSO_ANCHOR.BOTTOM if sd < 0 else MSO_ANCHOR.TOP)
            fs = fit([dl + "  " + txt], LW / 914400, 0.40, (9, 8.5, 8, 7.5))
            p_ = _p(tf, dl + "  ", size=fs, bold=True, color=col, first=True, after=0)
            r_ = p_.add_run(); r_.text = "  " + txt; r_.font.size = Pt(fs); r_.font.name = FONT
            r_.font.color.rgb = INK

# ═══════════════════════════════════════════════════════ 4 · skeleton + spend ladder
s = slide("Every use case is the same six-step skeleton",
          "The skeleton is a reference for the manual and for new work, not a framework to build.",
          kicker="what the use cases share")
n = len(PROP["skeleton"])
cw_ = int(BODY_W / n)
sk_size = min(fit([st["what"]], cw_ / 914400 - 0.3, 1.0, (11.5, 11, 10.5, 10, 9.5))
              for st in PROP["skeleton"])
for i, st in enumerate(PROP["skeleton"]):
    x = MARGIN + i * cw_
    sh = s.shapes.add_shape(MSO_SHAPE.CHEVRON if i else MSO_SHAPE.PENTAGON, x, Inches(1.45),
                            cw_ + Inches(0.1), Inches(0.78))
    sh.fill.solid(); sh.fill.fore_color.rgb = NAVY if i % 2 == 0 else MID
    sh.line.fill.background(); sh.shadow.inherit = False
    tf = sh.text_frame; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    _p(tf, st["name"], size=15, bold=True, color=WHITE, first=True, after=0, align=PP_ALIGN.CENTER)
    para(s, st["what"], x + Inches(0.22), Inches(2.38), cw_ - Inches(0.3), Inches(1.0),
         sizes=(sk_size,))
label(s, "Wrapped by a spend ladder: each gate must pass before the next spend", MARGIN,
      Inches(3.55), width=BODY_W)
lad = PROP["ladder"]
lw = int((BODY_W - Inches(0.2) * 3) / 4)
for i, g in enumerate(lad):
    x = MARGIN + i * (lw + Inches(0.2))
    hh = Inches(1.45 + 0.42 * i)
    top = Inches(6.85) - hh
    box(s, x, top, lw, hh, fill=[LIGHT, PALE_NAVY, MID, NAVY][i])
    dark = i >= 2
    _p(_tx(s, x + Inches(0.18), top + Inches(0.12), lw - Inches(0.3), Inches(0.4)),
       f"{g['gate']}  {g['name']}", size=14, bold=True, color=WHITE if dark else NAVY,
       first=True, after=0)
    para(s, g["what"], x + Inches(0.18), top + Inches(0.52), lw - Inches(0.36), hh - Inches(0.95),
         color=WHITE if dark else INK, sizes=(11, 10.5, 10, 9.5, 9))
    _p(_tx(s, x + Inches(0.18), top + hh - Inches(0.38), lw - Inches(0.3), Inches(0.26)),
       g["cost"], size=10.5, bold=True, color=ORANGE, first=True, after=0)

# ═══════════════════════════════════════════════════════ 5 · families overview
s = slide("Five families of use cases", kicker="the portfolio by pattern",
          subtitle="Grouped by the analytical pattern they share. Dot colour = maturity.")
fw = int((BODY_W - Inches(0.16) * 4) / 5)
for i, fk in enumerate("ABCDE"):
    f = FAMS[fk]
    x = MARGIN + i * (fw + Inches(0.16))
    top = Inches(1.55)
    box(s, x, top, fw, Inches(5.3), fill=LIGHT)
    hb = box(s, x, top, fw, Inches(0.78), fill=FAMILY_COL[fk])
    tf = hb.text_frame; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = tf.margin_right = Inches(0.12)
    nm = re.sub(r"^[A-E]\.\s*", "", clean(f["name"]))
    _p(tf, f"{fk}  ·  {nm}", size=fit([nm], fw / 914400 - 0.3, 0.66, (13, 12, 11.5, 11, 10.5, 10),
                                      bold=True), bold=True, color=WHITE, first=True, after=0)
    para(s, f["pattern"], x + Inches(0.14), top + Inches(0.92), fw - Inches(0.28), Inches(2.05),
         sizes=(10, 9.5, 9, 8.5, 8), color=INK)
    yy = top + Inches(3.05)
    ids = [u["id"] for u in UCS if fam_of(u["id"]) == fk]
    hper = Inches(2.15 / max(1, len(ids)))
    for uid in ids:
        u = UC_BY_ID[uid]
        mcol = MATURITY.get(u["maturity"], ("", GREY))[1]
        circle(s, "", x + Inches(0.14), yy + Inches(0.06), Inches(0.13), mcol)
        para(s, short_title(u), x + Inches(0.36), yy, fw - Inches(0.48), hper - Inches(0.04),
             sizes=(10, 9.5, 9, 8.5), color=NAVY, bold=True)
        yy += hper
lx = MARGIN
for key in ("exploratory", "repeatable-with-effort", "repeatable", "proposal"):
    lab, col = MATURITY[key]
    circle(s, "", lx, Inches(6.93), Inches(0.13), col)
    _p(_tx(s, lx + Inches(0.19), Inches(6.88), Inches(2.2), Inches(0.22)), lab, size=9,
       color=INK, first=True, after=0)
    lx += Inches(2.2)

# ═══════════════════════════════════════════════════════ 6 · evaluation & maturity matrix
s = slide("How far each use case can be trusted and repeated",
          "Tier A held-out gold · B SME spot review · C proxy agreement · D exploratory. Spend = list-price "
          "estimate, excl. discovery; + = extra passes not included.",
          kicker="evaluation coverage and maturity")
ev = {e["uc"]: e for e in C["charts"]["eval"]}
cost = {}
for e in C["charts"]["cost"]:
    cost[e["uc"]] = e
rows = [["ID", "Use case", "Product", "Maturity", "Tier", "Headline measure", "Spend (est.)"]]
fills = [None]
for u in UCS:
    e = ev.get(u["id"], {})
    c_ = cost.get(u["id"])
    lab, mcol = MATURITY.get(u["maturity"], (u["maturity"], GREY))
    rows.append([u["id"].split("-")[1], short_title(u), short_product(u), lab,
                 e.get("tier", "–"), clean(e.get("metric", "not measured")),
                 (f"${c_['usd']:,.0f}" + ("+" if re.search(r"\+~?\$|only", c_["note"]) else "")
                  if c_ and c_.get("usd") else "not recorded")])
    tier_col = {"A": RGBColor(0xD8, 0xEE, 0xE1), "B": RGBColor(0xE4, 0xF1, 0xE8),
                "C": RGBColor(0xFF, 0xF2, 0xE0), "D": RGBColor(0xF6, 0xE1, 0xE1)}.get(e.get("tier"))
    fills.append([None, None, None, None, tier_col, None, None])
table(s, rows, MARGIN, Inches(1.55), BODY_W, [4, 24, 13, 13, 4, 33, 9], row_h=Inches(0.27),
      size=9, fills=fills,
      aligns=[PP_ALIGN.LEFT] * 4 + [PP_ALIGN.CENTER, PP_ALIGN.LEFT, PP_ALIGN.RIGHT])


# ═══════════════════════════════════════════════════════ family dividers + use cases
def family_divider(fk):
    f = FAMS[fk]
    s = dark_slide()
    circle(s, fk, MARGIN, Inches(0.9), Inches(1.1), FAMILY_COL[fk], size=40)
    nm = re.sub(r"^[A-E]\.\s*", "", clean(f["name"]))
    para(s, nm, MARGIN + Inches(1.45), Inches(0.92), Inches(10.3), Inches(1.1), color=WHITE,
         sizes=(34, 32, 30, 28), bold=True, anchor=MSO_ANCHOR.MIDDLE)
    para(s, f["pattern"], MARGIN, Inches(2.35), BODY_W, Inches(1.0), color=PALE_NAVY,
         sizes=(16, 15, 14, 13))
    cw2 = int((BODY_W - Inches(0.4)) / 2)
    for j, (key, ttl, col) in enumerate((("pros", "What works", GREEN), ("cons", "What hurts", RED))):
        x = MARGIN + j * (cw2 + Inches(0.4))
        _p(_tx(s, x, Inches(3.55), cw2, Inches(0.3)), ttl.upper(), size=11, bold=True,
           color=ORANGE, first=True)
        bullets(s, f[key], x, Inches(3.9), cw2, Inches(1.45), color=WHITE, bullet_color=ORANGE,
                sizes=(13, 12.5, 12, 11.5, 11, 10.5))
    _p(_tx(s, MARGIN, Inches(5.65), BODY_W, Inches(0.3)), "USE CASES IN THIS FAMILY", size=11,
       bold=True, color=ORANGE, first=True)
    x, y = MARGIN, Inches(6.0)
    for u in [u for u in UCS if fam_of(u["id"]) == fk]:
        t = f"{u['id'].split('-')[1]}  {short_title(u)}"
        need = Inches(len(t) * 10.5 * 0.56 / 72 + 0.28)
        if x + need > W - MARGIN:
            x, y = MARGIN, y + Inches(0.48)
        wdt = chip(s, t, x, y, MID, size=10.5, height=Inches(0.36))
        x += wdt + Inches(0.15)
    return s


def usecase_slide(u):
    fk = fam_of(u["id"])
    f = FAMS[fk]
    nm = re.sub(r"^[A-E]\.\s*", "", clean(f["name"]))
    s = slide(u["title"], kicker=f"{u['id'].split('-')[1]}  ·  family {fk}  ·  {nm}",
              title_size=24)
    # meta row
    lab, mcol = MATURITY.get(u["maturity"], (u["maturity"], GREY))
    wdt = chip(s, lab, MARGIN, Inches(1.25), mcol, size=9)
    tier = {e["uc"]: e["tier"] for e in C["charts"]["eval"]}.get(u["id"])
    if tier:
        tname = {"A": "held-out gold", "B": "SME spot review", "C": "agreement, not accuracy",
                 "D": "exploratory"}[tier]
        wdt += chip(s, f"Tier {tier} · {tname}", MARGIN + wdt + Inches(0.1), Inches(1.25),
                    TIER_FILL[tier], color=INK, size=9) + Inches(0.1)
    meta = "   ·   ".join(clean(x) for x in (u["product"], u["period"], u["volume"],
                                              u["status_label"]) if clean(x))
    para(s, meta, MARGIN + wdt + Inches(0.15), Inches(1.24), BODY_W - wdt - Inches(0.15),
         Inches(0.36), color=GREY, sizes=(10.5, 10, 9.5, 9, 8.5, 8))
    LX, LW_ = MARGIN, Inches(5.3)
    RX = MARGIN + Inches(5.55)
    RW = BODY_W - Inches(5.55)
    top = Inches(1.68)
    # left: question, approach, numbers
    label(s, "Business question", LX, top)
    para(s, u["question"], LX, top + Inches(0.24), LW_, Inches(0.78), color=NAVY,
         sizes=(12, 11.5, 11, 10.5, 10, 9.5))
    label(s, "Approach", LX, top + Inches(1.1))
    bullets(s, u["approach"], LX, top + Inches(1.34), LW_, Inches(1.62), num=True,
            bullet_color=ORANGE, sizes=(11, 10.5, 10, 9.5, 9, 8.5), after=3)
    kn = u["key_numbers"][:4]
    kw = int((LW_ - Inches(0.12) * (len(kn) - 1)) / len(kn))
    ky = top + Inches(3.04)
    for i, kv in enumerate(kn):
        x = LX + i * (kw + Inches(0.12))
        box(s, x, ky, kw, Inches(0.98), fill=LIGHT)
        para(s, kv["value"], x + Inches(0.08), ky + Inches(0.04), kw - Inches(0.16), Inches(0.36),
             color=ORANGE, sizes=(20, 18, 16, 15, 14, 13, 12, 11, 10), bold=True)
        lab_sz = fit([kv["label"]], (kw - Inches(0.16)) / 914400 - 0.08, 0.5, (9, 8.5, 8, 7.5, 7))
        para(s, kv["label"], x + Inches(0.08), ky + Inches(0.42), kw - Inches(0.16), Inches(0.54),
             color=INK, sizes=(lab_sz,))
    # right: pros / cons
    pw_ = int((RW - Inches(0.15)) / 2)
    for j, (key, ttl, col, ch) in enumerate((("pros", "Pros", GREEN, "+"),
                                             ("cons", "Cons", RED, "–"))):
        x = RX + j * (pw_ + Inches(0.15))
        box(s, x, top, pw_, Inches(3.96), fill=LIGHT)
        circle(s, ch, x + Inches(0.15), top + Inches(0.14), Inches(0.3), col, size=13)
        _p(_tx(s, x + Inches(0.55), top + Inches(0.15), pw_ - Inches(0.7), Inches(0.3)), ttl,
           size=13, bold=True, color=col, first=True, after=0)
        bullets(s, u[key], x + Inches(0.17), top + Inches(0.6), pw_ - Inches(0.32),
                Inches(3.25), bullet_color=col, sizes=(11, 10.5, 10, 9.5, 9, 8.5), after=5)
    # bottom band
    by = Inches(5.78)
    bh = Inches(1.3)
    ex = [clean(e) for e in u["examples"]]
    ex_w = LW_ - Inches(0.3)
    if len(ex) > 1 and est_height(ex, ex_w / 914400, 9, gap_pt=3, indent_in=0.2) > 0.98:
        ex = ex[:1]
    cards = [("Example", ex, LX, LW_, NAVY), ("Extend", u["extend"], RX, pw_, MID),
             ("Optimise", u["optimise"], RX + pw_ + Inches(0.15), pw_, ORANGE)]
    for ttl, items, x, wdt, col in cards:
        box(s, x, by, wdt, bh, fill=WHITE, line=PALE_NAVY)
        label(s, ttl, x + Inches(0.15), by + Inches(0.1), color=col)
        bullets(s, items, x + Inches(0.15), by + Inches(0.34), wdt - Inches(0.3),
                bh - Inches(0.42), bullet_color=col, sizes=(10, 9.5, 9, 8.5, 8), after=2)
    d = DOC_BY_ID.get(u["id"])
    notes(s, d["summary"] if d else "", "Question: " + u["question"],
          "Notebook / entry point: " + u["notebook"])
    return s


for fk in "ABCDE":
    family_divider(fk)
    for u in [u for u in UCS if fam_of(u["id"]) == fk]:
        usecase_slide(u)

# ═══════════════════════════════════════════════════════ lessons
LES = C["lessons"]
for part, chunk in enumerate((LES[:4], LES[4:8])):
    if not chunk:
        continue
    s = slide("What the portfolio taught us" + (" (continued)" if part else ""),
              kicker="cross-cutting lessons")
    cw2 = int((BODY_W - Inches(0.3)) / 2)
    ch2 = Inches(2.48)
    for i, les in enumerate(chunk):
        x = MARGIN + (i % 2) * (cw2 + Inches(0.3))
        y = Inches(1.35) + (i // 2) * (ch2 + Inches(0.25))
        box(s, x, y, cw2, ch2, fill=LIGHT)
        circle(s, str(part * 4 + i + 1), x + Inches(0.22), y + Inches(0.22), Inches(0.44), NAVY, size=15)
        para(s, les["title"], x + Inches(0.82), y + Inches(0.22), cw2 - Inches(1.0), Inches(0.5),
             color=NAVY, bold=True, sizes=(15, 14, 13, 12))
        para(s, les["body"], x + Inches(0.82), y + Inches(0.78), cw2 - Inches(1.05), ch2 - Inches(0.95),
             sizes=(13, 12.5, 12, 11.5, 11, 10.5))

# ═══════════════════════════════════════════════════════ proposal
s = dark_slide()
_p(_tx(s, MARGIN, Inches(2.2), BODY_W, Inches(0.4)), "PART 2", size=14, bold=True, color=ORANGE, first=True)
para(s, "Generalising and streamlining the pipeline", MARGIN, Inches(2.65), Inches(11), Inches(1.0),
     color=WHITE, sizes=(40, 38, 36), bold=True)
para(s, PROP["headline"], MARGIN, Inches(3.8), Inches(10.5), Inches(1.2), color=PALE_NAVY,
     sizes=(20, 19, 18, 17, 16))

# defects
s = slide("Fix what fails silently before anything else",
          "Correctness first: each defect has already produced a wrong or missing number in a delivered use case.",
          kicker="the problem")
dfs = PROP["defects"]
cols = 3
cw3 = int((BODY_W - Inches(0.25) * (cols - 1)) / cols)
rows_n = math.ceil(len(dfs) / cols)
ch3 = Inches(2.55 if rows_n == 2 else 5.3)
for i, dfx in enumerate(dfs):
    x = MARGIN + (i % cols) * (cw3 + Inches(0.25))
    y = Inches(1.55) + (i // cols) * (ch3 + Inches(0.2))
    box(s, x, y, cw3, ch3, fill=LIGHT)
    circle(s, str(i + 1), x + Inches(0.18), y + Inches(0.18), Inches(0.4), RED, size=14)
    para(s, dfx["title"], x + Inches(0.7), y + Inches(0.16), cw3 - Inches(0.85), Inches(0.5),
         color=NAVY, bold=True, sizes=(13, 12.5, 12, 11.5, 11))
    para(s, dfx["evidence"], x + Inches(0.2), y + Inches(0.72), cw3 - Inches(0.4), Inches(1.0),
         sizes=(11, 10.5, 10, 9.5, 9))
    tf = _tx(s, x + Inches(0.2), y + ch3 - Inches(0.78), cw3 - Inches(0.4), Inches(0.66))
    fs = fit(["Fix: " + dfx["fix"]], cw3 / 914400 - 0.4, 0.66, (10.5, 10, 9.5, 9, 8.5))
    p = _p(tf, "Fix: ", size=fs, bold=True, color=GREEN, first=True, after=0)
    r = p.add_run(); r.text = " " + clean(dfx["fix"]); r.font.size = Pt(fs); r.font.name = FONT
    r.font.color.rgb = INK

# duplication evidence (native chart)
s = slide("The same plumbing is copied into up to nine notebooks",
          clean(PROP["duplication_note"]), kicker="the cost of copy-paste")
dup = sorted(C["charts"]["duplication"], key=lambda d: -d["notebooks"])[:10]
cd = CategoryChartData()
cd.categories = [d["helper"] for d in dup]
cd.add_series("Notebooks holding a copy", [d["notebooks"] for d in dup])
cd.add_series("Distinct variants", [d["variants"] for d in dup])
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, MARGIN, Inches(1.6), Inches(8.2), Inches(5.3), cd)
ch = gf.chart
ch.font.name = FONT; ch.font.size = Pt(10); ch.font.color.rgb = INK
ch.has_legend = True; ch.legend.position = XL_LEGEND_POSITION.TOP; ch.legend.include_in_layout = False
ch.legend.font.size = Pt(10)
plot = ch.plots[0]
plot.gap_width = 60; plot.overlap = -10
plot.has_data_labels = True
plot.data_labels.font.size = Pt(9); plot.data_labels.font.color.rgb = INK
plot.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
for sr, col in zip(plot.series, (NAVY, ORANGE)):
    sr.format.fill.solid(); sr.format.fill.fore_color.rgb = col
ch.category_axis.reverse_order = True
ch.category_axis.tick_labels.font.size = Pt(10)
ch.category_axis.format.line.color.rgb = PALE_NAVY
ch.value_axis.visible = False
ch.value_axis.has_major_gridlines = False
rx = MARGIN + Inches(8.5)
rw = BODY_W - Inches(8.5)
box(s, rx, Inches(1.6), rw, Inches(5.3), fill=NAVY)
label(s, "Why it matters", rx + Inches(0.25), Inches(1.8), color=ORANGE)
why = [x for x in C.get("dup_points", [])] or [
    "250–400 near-identical lines of plumbing per 2026 notebook",
    "Fixes travel by hand and unevenly between copies",
    "Every new use case starts by copying the last notebook",
]
bullets(s, why, rx + Inches(0.25), Inches(2.15), rw - Inches(0.5), Inches(4.5), color=WHITE,
        bullet_color=ORANGE, sizes=(14, 13, 12.5, 12, 11.5, 11), after=10)

# what changes / what stays
s = slide("Small, targeted changes; the analyst's tools stay",
          "Each change closes a named defect or deletes named copied code, and has a check that needs no LLM calls.",
          kicker="target state")
rows = [["Component", "What changes", "Replaces"]] + [[c["component"], c["change"], c["replaces"]]
                                                     for c in PROP["changes"]]
rh = Inches(min(0.62, 4.9 / len(rows)))
table(s, rows, MARGIN, Inches(1.6), Inches(8.6), [20, 46, 34], row_h=rh, size=9.5)
rx = MARGIN + Inches(8.85)
rw = BODY_W - Inches(8.85)
box(s, rx, Inches(1.6), rw, Inches(5.25), fill=LIGHT)
label(s, "What deliberately stays", rx + Inches(0.22), Inches(1.78))
bullets(s, PROP["stays"], rx + Inches(0.22), Inches(2.1), rw - Inches(0.44), Inches(4.6),
        bullet_color=GREEN, sizes=(12.5, 12, 11.5, 11, 10.5, 10), after=8)

# tiers + card
s = slide("Honest evaluation and a one-page card per use case",
          "Report the tier with every number; write the card before spending at G3.",
          kicker="quality standard")
ty = Inches(1.6)
tcol = [GREEN, RGBColor(0x5E, 0x9E, 0x7E), ORANGE, RED]
for i, t in enumerate(PROP["tiers"]):
    y = ty + i * Inches(1.32)
    box(s, MARGIN, y, Inches(6.2), Inches(1.18), fill=LIGHT)
    circle(s, t["tier"], MARGIN + Inches(0.2), y + Inches(0.3), Inches(0.58), tcol[i % 4], size=18)
    _p(_tx(s, MARGIN + Inches(1.0), y + Inches(0.12), Inches(5.0), Inches(0.3)), t["name"],
       size=13, bold=True, color=NAVY, first=True, after=0)
    para(s, t["meaning"], MARGIN + Inches(1.0), y + Inches(0.44), Inches(5.0), Inches(0.7),
         sizes=(10.5, 10, 9.5, 9))
cx = MARGIN + Inches(6.5)
cw4 = BODY_W - Inches(6.5)
box(s, cx, Inches(1.6), cw4, Inches(5.18), fill=RGBColor(0xF7, 0xF8, 0xFA), line=PALE_NAVY)
label(s, "Example card · ScienceDirect 2026 two-stage", cx + Inches(0.22), Inches(1.75), width=cw4)
lines_ = [str(x) for x in PROP["card_example"]]
fs = 10
while fs > 7 and (len(lines_) * fs * 1.25 / 72 > 4.55 or
                  max(len(x) for x in lines_) * 0.6 * fs / 72 > cw4 / 914400 - 0.45):
    fs -= 0.5
tf = _tx(s, cx + Inches(0.22), Inches(2.08), cw4 - Inches(0.4), Inches(4.6))
for i, ln_ in enumerate(lines_):
    _p(tf, ln_, size=fs, color=INK, first=(i == 0), after=1, font=MONO)

# roadmap overview
s = slide("Roadmap: three phases, each useful on its own",
          "The ~16-day minimum cut (● items, ◐ partly) already removes silent failures, lost rows and stale replays.",
          kicker="how we get there")
_p(_tx(s, MARGIN, Inches(6.9), BODY_W, Inches(0.22)),
   "● in the ~16-day minimum cut   ◐ partly in the minimum cut", size=9, color=GREY, first=True)
rm = PROP["roadmap"]
cw5 = int((BODY_W - Inches(0.25) * 2) / 3)
pcol = [NAVY, MID, GREY]
for i, ph in enumerate(rm):
    x = MARGIN + i * (cw5 + Inches(0.25))
    hb = box(s, x, Inches(1.6), cw5, Inches(1.05), fill=pcol[i])
    _p(_tx(s, x + Inches(0.2), Inches(1.68), cw5 - Inches(0.4), Inches(0.35)), ph["phase"],
       size=14, bold=True, color=WHITE, first=True, after=0)
    _p(_tx(s, x + Inches(0.2), Inches(2.05), cw5 - Inches(0.4), Inches(0.5)),
       f"{clean(ph['weeks'])}  ·  {clean(ph['days'])}", size=11, color=PALE_NAVY if i < 2 else WHITE,
       first=True, after=0)
    box(s, x, Inches(2.75), cw5, Inches(4.1), fill=LIGHT)
    para(s, ph["goal"], x + Inches(0.2), Inches(2.88), cw5 - Inches(0.4), Inches(0.8), color=NAVY,
         bold=True, sizes=(11, 10.5, 10, 9.5, 9))
    bullets(s, [it["item"] for it in ph["items"]], x + Inches(0.2), Inches(3.75), cw5 - Inches(0.4),
            Inches(3.0), bullet_color=pcol[i] if i < 2 else ORANGE,
            sizes=(11, 10.5, 10, 9.5, 9, 8.5), after=3)

# roadmap detail (success checks), split over slides if long
allrows = [[ph["phase"].split(":")[0], it["item"], it["effort"], it["check"]]
           for ph in rm for it in ph["items"]]
per = 12
for k0 in range(0, len(allrows), per):
    chunk = allrows[k0:k0 + per]
    s = slide("Roadmap detail: effort and a zero-LLM success check per item"
              + (" (continued)" if k0 else ""), kicker="how we will know it worked",
              subtitle="● in the ~16-day minimum cut · ◐ partly in the minimum cut")
    rows = [["Phase", "Item", "Effort", "Success check (no LLM calls)"]] + chunk
    table(s, rows, MARGIN, Inches(1.6), BODY_W, [9, 36, 9, 46],
          row_h=Inches(min(0.42, 5.3 / len(rows))), size=9)

# quick wins
s = slide("Quick wins for the first two weeks", kicker="start here")
qw = PROP["quick_wins"]
cw2 = int((BODY_W - Inches(0.3)) / 2)
per_col = math.ceil(len(qw) / 2)
qh = Inches(min(1.2, 4.7 / per_col))
for i, q in enumerate(qw):
    x = MARGIN + (i // per_col) * (cw2 + Inches(0.3))
    y = Inches(1.35) + (i % per_col) * (qh + Inches(0.1))
    box(s, x, y, cw2, qh, fill=LIGHT)
    circle(s, "✓", x + Inches(0.18), y + qh // 2 - Inches(0.18), Inches(0.36), GREEN, size=13)
    para(s, q, x + Inches(0.7), y + Inches(0.08), cw2 - Inches(0.85), qh - Inches(0.16),
         sizes=(12, 11.5, 11, 10.5, 10, 9.5), anchor=MSO_ANCHOR.MIDDLE)
para(s, PROP["min_cut"], MARGIN, Inches(6.55), BODY_W, Inches(0.5), color=GREY, italic=True,
     sizes=(11, 10.5, 10, 9.5))

# family mapping
s = slide("How each family maps onto the proposal", kicker="what changes for each use case",
          subtitle="Finished and legacy use cases are documented, not migrated; others adopt the library at their next refresh.")
rows = [["Family", "How it maps", "What stays custom"]] + [[m["family"], m["how"], m["custom"]]
                                                          for m in PROP["mapping"]]
table(s, rows, MARGIN, Inches(1.6), BODY_W, [18, 50, 32], row_h=Inches(min(0.72, 5.2 / len(rows))),
      size=10)

# metrics + risks
s = slide("How we will measure progress, and what could go wrong", kicker="metrics and risks")
rows = [["Metric", "Baseline", "Target"]] + [[m["metric"], m["baseline"], m["target"]]
                                            for m in PROP["metrics"]]
table(s, rows, MARGIN, Inches(1.35), Inches(6.55), [36, 38, 26],
      row_h=Inches(min(0.68, 5.4 / len(rows))), size=9)
rows = [["Risk", "Mitigation"]] + [[r["risk"], r["mitigation"]] for r in PROP["risks"]]
table(s, rows, MARGIN + Inches(6.8), Inches(1.35), BODY_W - Inches(6.8), [45, 55],
      row_h=Inches(min(0.8, 5.4 / len(rows))), size=9, header_fill=MID)

# not-do + decisions
s = dark_slide()
_p(_tx(s, MARGIN, Inches(0.55), BODY_W, Inches(0.3)), "SCOPE AND NEXT STEPS", size=12, bold=True,
   color=ORANGE, first=True)
para(s, "What we will not do, and what we need from you", MARGIN, Inches(0.9), BODY_W, Inches(0.7),
     color=WHITE, bold=True, sizes=(30, 28, 26))
cw2 = int((BODY_W - Inches(0.5)) / 2)
_p(_tx(s, MARGIN, Inches(1.95), cw2, Inches(0.3)), "WE WILL NOT", size=12, bold=True,
   color=PALE_NAVY, first=True)
bullets(s, PROP["not_do"], MARGIN, Inches(2.35), cw2, Inches(4.4), color=WHITE, bullet_color=RED,
        char="✕", sizes=(14, 13, 12.5, 12, 11.5, 11), after=9)
x = MARGIN + cw2 + Inches(0.5)
box(s, x, Inches(1.95), cw2, Inches(4.85), fill=MID)
_p(_tx(s, x + Inches(0.3), Inches(2.15), cw2 - Inches(0.6), Inches(0.3)), "DECISIONS NEEDED",
   size=12, bold=True, color=ORANGE, first=True)
bullets(s, PROP["decisions"], x + Inches(0.3), Inches(2.55), cw2 - Inches(0.6), Inches(4.1),
        color=WHITE, bullet_color=ORANGE, num=True, sizes=(15, 14, 13, 12.5, 12, 11.5), after=12)

# ═══════════════════════════════════════════════════════ appendix
s = dark_slide()
_p(_tx(s, MARGIN, Inches(2.6), BODY_W, Inches(0.4)), "APPENDIX", size=14, bold=True, color=ORANGE, first=True)
para(s, "Capabilities, engine issues, glossary and method", MARGIN, Inches(3.05), Inches(11),
     Inches(1.0), color=WHITE, sizes=(36, 34, 32), bold=True)

caps = C["capabilities_short"]
half = math.ceil(len(caps) / 2)
for part, chunk in enumerate((caps[:half], caps[half:])):
    s = slide("Reusable capabilities in the repo" + (" (continued)" if part else ""),
              kicker="appendix · what exists today")
    rows = [["Capability", "What it does", "Where"]] + [[c["name"], c["what"], c["where"]] for c in chunk]
    table(s, rows, MARGIN, Inches(1.35), BODY_W, [24, 52, 24],
          row_h=Inches(min(0.62, 5.4 / len(rows))), size=9.5)

ki = C["appendix"]["known_issues"]
s = slide("Engine issues found in the review", kicker="appendix · technical detail",
          subtitle="From the architecture survey, after its adversarial check. Most are addressed by the roadmap.")
rows = [["Issue", "Impact", "Fix"]] + [[k_["issue"], k_["impact"], k_["fix"]] for k_ in ki]
table(s, rows, MARGIN, Inches(1.6), BODY_W, [38, 36, 26], row_h=Inches(min(0.45, 5.25 / len(rows))),
      size=8.5)

gl = sorted([g for g in C["glossary"] if len(g["definition"]) <= 175],
            key=lambda g: g["term"].lower())
half = math.ceil(len(gl) / 2)
s = slide("Glossary", kicker="appendix")
for j, chunk in enumerate((gl[:half], gl[half:])):
    rows = [["Term", "Meaning"]] + [[g["term"], g["definition"]] for g in chunk]
    table(s, rows, MARGIN + j * int(BODY_W / 2 + Inches(0.1)), Inches(1.35),
          int(BODY_W / 2 - Inches(0.1)), [26, 74], row_h=Inches(min(0.4, 5.45 / len(rows))), size=8.5)

s = slide("How this review was produced", kicker="appendix · method and provenance")
bullets(s, C["appendix"]["method"], MARGIN, Inches(1.4), Inches(7.6), Inches(5.3),
        bullet_color=ORANGE, sizes=(14, 13, 12.5, 12, 11.5, 11), after=10)
box(s, MARGIN + Inches(8.0), Inches(1.4), BODY_W - Inches(8.0), Inches(5.3), fill=LIGHT)
label(s, "Companion document", MARGIN + Inches(8.25), Inches(1.6))
para(s, "docs/RCA_Repo_Manual_and_Methodology_2026.docx: the repo manual, the methodology and "
        "reproduction steps for all 18 use cases, the capabilities reference and the full proposal.",
     MARGIN + Inches(8.25), Inches(1.95), BODY_W - Inches(8.5), Inches(1.6), sizes=(13, 12, 11.5, 11))
label(s, "Sources", MARGIN + Inches(8.25), Inches(3.75))
para(s, "Notebooks 00–19, eda, gold_set_evaluation; scripts/; rca_pipeline/; run_pipeline.py; "
        "build_pipeline.py; profiles/; definitions/; runs/ (cost reports, checkpoints, logs, outputs); "
        "docs/ and specs/.", MARGIN + Inches(8.25), Inches(4.1), BODY_W - Inches(8.5), Inches(2.3),
     sizes=(12, 11.5, 11, 10.5))

# ───────────────────────────────────────────────────────────── footers
N = len(prs.slides)
for i, tf in enumerate(_footers, start=1):
    if tf is not None:
        _p(tf, f"{FOOT}{' ' * 6}|{' ' * 6}{i} of {N}", size=8.5, color=GREY, first=True)

OUT.parent.mkdir(parents=True, exist_ok=True)
prs.save(OUT)
print(f"wrote {OUT}  ({N} slides)")
