"""Render the CKAI PHI-screening approach deck (for early Security / Legal feedback).

Run with the SYSTEM Python, which is the interpreter that has python-pptx:

    & "C:\\Program Files\\Python311\\python.exe" scripts\\build_ckai_phi_deck.py

Content only - no data is read. House style follows scripts/build_deck.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
    from pptx.oxml.ns import qn
    from pptx.util import Inches, Pt
except ModuleNotFoundError:                                          # pragma: no cover
    sys.exit("python-pptx is not available on this interpreter.\n"
             'Run with:  & "C:\\Program Files\\Python311\\python.exe" scripts\\build_ckai_phi_deck.py')

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "docs" / "CKAI_PHI_screening_approach.pptx"

NAVY = RGBColor(0x0B, 0x2A, 0x4A)
ORANGE = RGBColor(0xFF, 0x6C, 0x00)
GREY = RGBColor(0x5F, 0x6B, 0x77)
LIGHT = RGBColor(0xEE, 0xF1, 0xF4)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
RED = RGBColor(0xC1, 0x27, 0x2D)
RED_TINT = RGBColor(0xFB, 0xE9, 0xEA)
TEAL = RGBColor(0x00, 0x7A, 0x78)
TEAL_TINT = RGBColor(0xE6, 0xF3, 0xF2)
GREEN = RGBColor(0x2E, 0x7D, 0x32)
GREEN_TINT = RGBColor(0xE8, 0xF3, 0xE9)
ICE = RGBColor(0xC8, 0xD3, 0xDD)

W, H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.62)
BODY_W = W - 2 * MARGIN
FONT = "Segoe UI"

prs = Presentation()
prs.slide_width, prs.slide_height = W, H
BLANK = prs.slide_layouts[6]
_n = 0


# ───────────────────────────────────────────────────────────── helpers
def _emu(*vals):
    """PowerPoint rejects non-integer EMU coordinates (e.g. from dividing a length by 2)."""
    return [int(v) for v in vals]


def _txbox(slide, left, top, width, height, anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(*_emu(left, top, width, height))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    return tf


def _para(tf, text, size=14, bold=False, color=NAVY, space_after=6, first=False,
          align=PP_ALIGN.LEFT, italic=False):
    """One paragraph. `text` may be a list of (text, bold) runs."""
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.space_after = Pt(space_after)
    runs = text if isinstance(text, list) else [(text, bold)]
    for t, b in runs:
        run = p.add_run()
        run.text = t
        run.font.size = Pt(size)
        run.font.bold = b
        run.font.italic = italic
        run.font.color.rgb = color
        run.font.name = FONT
    return p


def _bg(s, color):
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = color


def box(s, left, top, width, height, fill=WHITE, line=None, rounded=True, dashed=False,
        line_w=1.25):
    shp = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE,
                             *_emu(left, top, width, height))
    if rounded:
        shp.adjustments[0] = 0.06
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid(); shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(line_w)
        if dashed:
            shp.line.dash_style = 4  # MSO_LINE.DASH
    shp.shadow.inherit = False
    return shp


def circle(s, left, top, d, fill, text, size=14, color=WHITE):
    c = s.shapes.add_shape(MSO_SHAPE.OVAL, *_emu(left, top, d, d))
    c.fill.solid(); c.fill.fore_color.rgb = fill
    c.line.fill.background(); c.shadow.inherit = False
    tf = c.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    _para(tf, text, size=size, bold=True, color=color, first=True, align=PP_ALIGN.CENTER,
          space_after=0)
    return c


def arrow(s, x1, y1, x2, y2, color=NAVY, width=2.0):
    c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, *_emu(x1, y1, x2, y2))
    c.line.color.rgb = color
    c.line.width = Pt(width)
    ln = c.line._get_or_add_ln()
    tail = ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"})
    ln.append(tail)
    return c


def slide(title, kicker=None, subtitle=None, dark=False):
    global _n
    s = prs.slides.add_slide(BLANK)
    _n += 1
    fg = WHITE if dark else NAVY
    if dark:
        _bg(s, NAVY)
    top = Inches(0.42)
    if kicker:
        tf = _txbox(s, MARGIN, Inches(0.36), BODY_W, Inches(0.26))
        _para(tf, kicker.upper(), size=11, bold=True, color=ORANGE, first=True)
        top = Inches(0.66)
    tf = _txbox(s, MARGIN, top, BODY_W, Inches(0.6))
    _para(tf, title, size=28, bold=True, color=fg, first=True)
    if subtitle:
        tf = _txbox(s, MARGIN, top + Inches(0.62), BODY_W, Inches(0.4))
        _para(tf, subtitle, size=14, color=ICE if dark else GREY, first=True)
    tf = _txbox(s, MARGIN, H - Inches(0.36), BODY_W, Inches(0.22))
    _para(tf, f"CKAI PHI screening  ·  draft for early feedback  ·  not for onward distribution"
              f"{' ' * 6}|{' ' * 6}{_n}", size=9, color=ICE if dark else GREY, first=True)
    return s


def card(s, left, top, width, height, heading, lines, fill=LIGHT, line=None,
         head_color=NAVY, size=13, head_size=16, pad=0.22):
    box(s, left, top, width, height, fill=fill, line=line)
    p = Inches(pad)
    tf = _txbox(s, left + p, top + p, width - 2 * p, height - 2 * p)
    _para(tf, heading, size=head_size, bold=True, color=head_color, first=True, space_after=8)
    for ln in lines:
        _para(tf, ln, size=size, space_after=5)
    return tf


# ───────────────────────────────────────────────────────────── 1. title
s = prs.slides.add_slide(BLANK); _n += 1
_bg(s, NAVY)
tf = _txbox(s, MARGIN, Inches(1.35), BODY_W, Inches(0.3))
_para(tf, "CLINICALKEY AI  ·  PRIVACY & SECURITY EARLY REVIEW", size=12, bold=True,
      color=ORANGE, first=True)
tf = _txbox(s, MARGIN, Inches(1.8), Inches(11), Inches(1.4))
_para(tf, "Screening CKAI support tickets for PHI", size=40, bold=True, color=WHITE, first=True)
tf = _txbox(s, MARGIN, Inches(2.75), Inches(10.5), Inches(0.9))
_para(tf, "A proposed way to learn from CKAI support tickets without using any protected "
          "health information (PHI). Shared for early feedback from Data Security, Legal and "
          "the PIA approvers.", size=16, color=ICE, first=True)

tiles = [("2026", "fresh CKAI ticket extract;\nvolume to be confirmed"),
         ("1", "yes / no decision per ticket:\n“does it contain PHI?”"),
         ("0", "PHI kept after processing\n(design goal)")]
tw, tg, ty = Inches(3.55), Inches(0.35), Inches(4.35)
for i, (big, small) in enumerate(tiles):
    x = MARGIN + i * (tw + tg)
    box(s, x, ty, tw, Inches(1.75), fill=RGBColor(0x14, 0x3A, 0x60))
    tf = _txbox(s, x + Inches(0.3), ty + Inches(0.2), tw - Inches(0.6), Inches(0.8))
    _para(tf, big, size=36, bold=True, color=ORANGE, first=True, space_after=2)
    for line in small.split("\n"):
        _para(tf, line, size=13, color=WHITE, space_after=0)

tf = _txbox(s, MARGIN, Inches(6.55), BODY_W, Inches(0.3))
_para(tf, "What we need today: a first thumbs-up (or red flags) from Data Security before "
          "we complete the PIA form.", size=13, bold=True, color=WHITE, first=True)
tf = _txbox(s, MARGIN, H - Inches(0.36), BODY_W, Inches(0.22))
_para(tf, "Draft for discussion  ·  September 2026", size=9, color=ICE, first=True)


# ───────────────────────────────────────────────────────────── 2. approach
s = slide("Screen and exclude, rather than de-identify",
          kicker="The approach",
          subtitle="Tickets that contain PHI are removed completely. The rest are analysed as they are.")

cw, ch, cy = Inches(5.85), Inches(3.0), Inches(1.95)
gap = BODY_W - 2 * cw
card(s, MARGIN, cy, cw, ch, "Option A: De-identify every ticket",
     ["Find and remove all 18 HIPAA identifier types from free-text conversations.",
      "Contracts differ by customer, and the data has no customer field, so we "
      "can't reliably tell which tickets we are allowed to de-identify.",
      "Partly redacted text can still leave rare details that identify a patient."],
     fill=LIGHT, head_color=GREY)
tf = _txbox(s, MARGIN + Inches(0.22), cy + ch - Inches(0.5), cw, Inches(0.3))
_para(tf, "Complex, and hard to prove complete", size=12, bold=True, color=GREY, first=True,
      italic=True)

x2 = MARGIN + cw + gap
card(s, x2, cy, cw, ch, "Option B (proposed): Screen and exclude",
     ["An LLM reads each ticket once, inside a HIPAA-secure environment, and answers one "
      "question: does this ticket contain PHI?",
      "Tickets with PHI, or any doubt, are dropped entirely. Nothing is edited, so nothing "
      "is left half-redacted.",
      "Only PHI-free tickets ever reach the analysis environment."],
     fill=TEAL_TINT, line=TEAL, head_color=TEAL)
tf = _txbox(s, x2 + Inches(0.22), cy + ch - Inches(0.5), cw, Inches(0.3))
_para(tf, "Simpler, and it fails safe", size=12, bold=True, color=TEAL, first=True, italic=True)

cy2 = cy + ch + Inches(0.5)
box(s, MARGIN, cy2, BODY_W, Inches(0.95), fill=RGBColor(0xFF, 0xF1, 0xE6))
circle(s, MARGIN + Inches(0.25), cy2 + Inches(0.2), Inches(0.55), ORANGE, "!", size=20)
tf = _txbox(s, MARGIN + Inches(1.05), cy2 + Inches(0.12), BODY_W - Inches(1.3), Inches(0.75),
            anchor=MSO_ANCHOR.MIDDLE)
_para(tf, [("Key assumption to test: ", True),
           ("only a minority of tickets contain PHI, so excluding them won't skew the "
            "analysis. We will measure the excluded share and check it before relying on "
            "the results.", False)], size=14, first=True, space_after=0)


# ───────────────────────────────────────────────────────────── 3. flow
s = slide("How a ticket flows through the screen",
          kicker="End-to-end flow",
          subtitle="Everything inside the dashed boundary runs in a HIPAA-secure environment "
                   "covered by the BAA (service to be confirmed).")

by, bh = Inches(1.95), Inches(4.75)
bx, bw = Inches(2.75), Inches(7.75)
box(s, bx, by, bw, bh, fill=TEAL_TINT, line=TEAL, dashed=True, line_w=2)
tf = _txbox(s, bx + Inches(0.25), by + Inches(0.15), bw - Inches(0.5), Inches(0.3))
_para(tf, "HIPAA-SECURE ENVIRONMENT  ·  covered by the BAA  ·  named staff only",
      size=11, bold=True, color=TEAL, first=True)

sy, sh = Inches(2.6), Inches(2.2)

# source
sx, sw = MARGIN - Inches(0.2), Inches(1.95)
box(s, sx, sy, sw, sh, fill=LIGHT)
tf = _txbox(s, sx + Inches(0.15), sy + Inches(0.2), sw - Inches(0.3), sh - Inches(0.4))
_para(tf, "Source", size=11, bold=True, color=GREY, first=True, space_after=4)
_para(tf, "Oracle Service Cloud", size=15, bold=True, space_after=6)
_para(tf, "Ticket export sent straight to the secure environment, never via laptops.", size=11)

steps = [
    ("1", "Rules pre-screen",
     "Pattern checks for strong identifiers: SSNs, medical record numbers, dates of birth. "
     "Any match means the ticket is excluded."),
    ("2", "LLM classifier",
     "Reads each ticket once. Returns only PHI / no PHI / uncertain, plus which of the 18 "
     "identifier types it saw. It never quotes the text."),
    ("3", "Fail-safe decision",
     "No PHI: keep.\nPHI or uncertain: exclude.\nOnly the ticket ID and label are "
     "written out."),
]
stw, stg = Inches(2.3), Inches(0.2)
stx0 = bx + Inches(0.25)
for i, (num, head, body) in enumerate(steps):
    x = stx0 + i * (stw + stg)
    box(s, x, sy, stw, sh, fill=WHITE, line=TEAL, line_w=1)
    circle(s, x + Inches(0.18), sy + Inches(0.18), Inches(0.42), TEAL, num, size=14)
    tf = _txbox(s, x + Inches(0.7), sy + Inches(0.2), stw - Inches(0.85), Inches(0.42),
                anchor=MSO_ANCHOR.MIDDLE)
    _para(tf, head, size=13, bold=True, first=True, space_after=0)
    tf = _txbox(s, x + Inches(0.18), sy + Inches(0.78), stw - Inches(0.36), sh - Inches(0.9))
    for j, line in enumerate(body.split("\n")):
        _para(tf, line, size=11, first=(j == 0), space_after=3)
    if i < len(steps) - 1:
        arrow(s, x + stw, sy + sh / 2, x + stw + stg, sy + sh / 2, color=TEAL)
arrow(s, sx + sw, sy + sh / 2, stx0, sy + sh / 2)

# destination
dx = bx + bw + Inches(0.3)
dw = W - dx - Inches(0.42)
box(s, dx, sy, dw, sh, fill=GREEN_TINT, line=GREEN)
tf = _txbox(s, dx + Inches(0.15), sy + Inches(0.2), dw - Inches(0.3), sh - Inches(0.4))
_para(tf, "Kept", size=11, bold=True, color=GREEN, first=True, space_after=4)
_para(tf, "Analysis environment", size=15, bold=True, space_after=6)
_para(tf, "PHI-free tickets only, plus the ticket ID and label.", size=11)
last_x = stx0 + 2 * (stw + stg)
arrow(s, last_x + stw, sy + sh / 2, dx, sy + sh / 2, color=GREEN)

# excluded path
ey, eh = Inches(5.25), Inches(1.2)
ex = stx0 + (stw + stg)
ew = last_x + stw - ex
box(s, ex, ey, ew, eh, fill=RED_TINT, line=RED)
tf = _txbox(s, ex + Inches(0.2), ey + Inches(0.14), ew - Inches(0.4), eh - Inches(0.28),
            anchor=MSO_ANCHOR.MIDDLE)
_para(tf, "Excluded: PHI or uncertain", size=13, bold=True, color=RED, first=True,
      space_after=3)
_para(tf, "Never leaves the boundary. Deleted with the raw export at the end of the run. "
          "Only counts are reported.", size=11, space_after=0)
arrow(s, last_x + stw / 2, sy + sh, last_x + stw / 2, ey, color=RED)
arrow(s, stx0 + stw / 2, sy + sh, stx0 + stw / 2, ey + eh / 2, color=RED, width=1.5)
arrow(s, stx0 + stw / 2, ey + eh / 2, ex, ey + eh / 2, color=RED, width=1.5)

tf = _txbox(s, stx0 + stw / 2 + Inches(0.12), ey + eh / 2 - Inches(0.3), Inches(1.5),
            Inches(0.25))
_para(tf, "match found", size=10, italic=True, color=RED, first=True, space_after=0)


# ───────────────────────────────────────────────────────────── 4. controls
s = slide("Controls against the two requirements",
          kicker="Security & retention",
          subtitle="Proposed controls. Security to confirm the environment and the evidence "
                   "needed for the PIA.")

rows = [
    ("(i)  HIPAA-secure\nenvironment", "Covered by the BAA",
     "LLM service and storage are HIPAA-eligible and under Elsevier's BAA",
     "Provider BAA, service configuration"),
    ("", "Network and access",
     "Private endpoint with no public internet; encrypted in transit and at rest; "
     "named, trained staff only",
     "Architecture diagram, access list"),
    ("", "No model training", "Provider terms: our data is never used to train models",
     "Contract terms"),
    ("(ii)  No PHI\nretained", "Zero retention by the provider",
     "Zero data retention: the provider's abuse-monitoring logging is switched off",
     "Provider approval"),
    ("", "Nothing in our logs",
     "What we send to the model and what it returns is not logged or cached; outputs hold "
     "only the ticket ID and label",
     "Code review, example output"),
    ("", "Deletion after the run",
     "Raw export and excluded tickets are deleted when the run finishes",
     "Deletion record"),
    ("", "No local copies",
     "Processing happens only in the secure environment, never on laptops or shared drives",
     "Access logs"),
]
headers = ["Requirement", "Control", "What it means", "Evidence for the PIA"]
col_w = [Inches(2.0), Inches(2.55), Inches(4.95), Inches(2.59)]
ty = Inches(1.95)
tbl = s.shapes.add_table(len(rows) + 1, 4, MARGIN, ty, sum(col_w, Inches(0)),
                         Inches(0.42) * (len(rows) + 1)).table
for j, w in enumerate(col_w):
    tbl.columns[j].width = w


def _cell(c, text, size=11.5, bold=False, color=NAVY, fill=WHITE):
    c.fill.solid(); c.fill.fore_color.rgb = fill
    c.margin_left = c.margin_right = Inches(0.1)
    c.margin_top = c.margin_bottom = Inches(0.05)
    c.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf = c.text_frame
    tf.word_wrap = True
    for k, line in enumerate(text.split("\n")):
        _para(tf, line, size=size, bold=bold, color=color, first=(k == 0), space_after=0)


for j, h in enumerate(headers):
    _cell(tbl.cell(0, j), h, size=12, bold=True, color=WHITE, fill=NAVY)
for i, (req, ctrl, what, ev) in enumerate(rows, start=1):
    band = TEAL_TINT if i <= 3 else RGBColor(0xFF, 0xF1, 0xE6)
    _cell(tbl.cell(i, 0), req, bold=True, color=TEAL if i <= 3 else ORANGE, fill=band)
    _cell(tbl.cell(i, 1), ctrl, bold=True)
    _cell(tbl.cell(i, 2), what)
    _cell(tbl.cell(i, 3), ev, color=GREY)
tbl.cell(1, 0).merge(tbl.cell(3, 0))
tbl.cell(4, 0).merge(tbl.cell(7, 0))


cy2 = Inches(5.95)
box(s, MARGIN, cy2, BODY_W, Inches(0.8), fill=TEAL_TINT)
circle(s, MARGIN + Inches(0.25), cy2 + Inches(0.15), Inches(0.5), TEAL, "✓", size=16)
tf = _txbox(s, MARGIN + Inches(1.0), cy2, BODY_W - Inches(1.25), Inches(0.8),
            anchor=MSO_ANCHOR.MIDDLE)
_para(tf, [("In short: ", True),
           ("ticket text only ever exists inside the secure boundary. The only things that "
            "leave it are the PHI-free tickets, ticket IDs, labels and counts.", False)],
      size=14, first=True, space_after=0)


# ───────────────────────────────────────────────────────────── 5. validation
s = slide("Proving it works, before we rely on it",
          kicker="Validation & bias check",
          subtitle="Both checks run inside the secure environment. Thresholds are for "
                   "approvers to agree.")

cw = (BODY_W - Inches(0.4)) / 2
cy = Inches(1.95)
for k, (head, tiles_, bullets_) in enumerate([
    ("1  Does the screen catch PHI?",
     [("Human", "check of the screen's decisions"), ("Catch rate", "to be agreed with approvers")],
     ["Authorised reviewers check the screen's decisions inside the secure environment.",
      "We compare their labels with the screen and measure how many PHI tickets it misses.",
      "We accept excluding some safe tickets in exchange for missing almost no PHI."]),
    ("2  Does excluding tickets skew the data?",
     [("3", "comparisons: contact reason, channel, month"), ("Every run", "excluded share reported with the results")],
     ["We compare the kept and excluded tickets on each dimension.",
      "We report the excluded share with the results.",
      "If exclusion is large, or concentrated in some topics, we revisit the approach."]),
]):
    x = MARGIN + k * (cw + Inches(0.4))
    box(s, x, cy, cw, Inches(4.4), fill=LIGHT)
    tf = _txbox(s, x + Inches(0.3), cy + Inches(0.25), cw - Inches(0.6), Inches(0.4))
    _para(tf, head, size=17, bold=True, first=True)
    tw_ = (cw - Inches(0.6) - Inches(0.25)) / 2
    for t, (big, small) in enumerate(tiles_):
        tx = x + Inches(0.3) + t * (tw_ + Inches(0.25))
        box(s, tx, cy + Inches(0.85), tw_, Inches(1.35), fill=WHITE)
        tf = _txbox(s, tx + Inches(0.2), cy + Inches(0.95), tw_ - Inches(0.4), Inches(1.2))
        _para(tf, big, size=30, bold=True, color=TEAL, first=True, space_after=0)
        _para(tf, small, size=11.5, color=GREY, space_after=0)
    tf = _txbox(s, x + Inches(0.3), cy + Inches(2.45), cw - Inches(0.6), Inches(2.2))
    for b, line in enumerate(bullets_):
        _para(tf, "•  " + line, size=13, first=(b == 0), space_after=8)


# ───────────────────────────────────────────────────────────── 6. open questions
s = slide("Open questions and next steps", kicker="Feedback we need", dark=True)

qs = [
    ("For Data Security", [
        "Which HIPAA-eligible LLM environment do we use (Azure OpenAI, AWS Bedrock, an internal "
        "platform), and is it covered by the BAA?",
        "What evidence does the PIA need for zero retention and deletion?",
        "We'll use a fresh 2026 extract. How should the older CKAI exports already held be "
        "secured or deleted?"]),
    ("For Legal & Privacy", [
        "Is screening itself permitted processing under every contract (e.g. Atrium), or do "
        "we screen only customers that allow secondary use?",
        "Does a ticket with no PHI still count as permitted use under restrictive contracts?",
        "How much missed PHI is acceptable, and who signs off on validation?"]),
]
cw = (BODY_W - Inches(0.4)) / 2
cy = Inches(1.45)
for k, (head, items) in enumerate(qs):
    x = MARGIN + k * (cw + Inches(0.4))
    box(s, x, cy, cw, Inches(3.3), fill=RGBColor(0x14, 0x3A, 0x60))
    tf = _txbox(s, x + Inches(0.3), cy + Inches(0.25), cw - Inches(0.6), Inches(3.3))
    _para(tf, head, size=17, bold=True, color=ORANGE, first=True, space_after=10)
    for i, q in enumerate(items, start=1):
        _para(tf, [(f"{i}.  ", True), (q, False)], size=13, color=WHITE, space_after=9)

steps = ["Security\nfirst review", "Complete the\nPIA form", "Pilot\nrun",
         "Validation\nsign-off", "Full run"]
ny = Inches(5.55)
sw_ = (BODY_W - Inches(0.35) * (len(steps) - 1)) / len(steps)
for i, st in enumerate(steps):
    x = MARGIN + i * (sw_ + Inches(0.35))
    fill = ORANGE if i == 0 else RGBColor(0x14, 0x3A, 0x60)
    box(s, x, ny, sw_, Inches(0.95), fill=fill)
    tf = _txbox(s, x + Inches(0.1), ny, sw_ - Inches(0.2), Inches(0.95), anchor=MSO_ANCHOR.MIDDLE)
    for j, line in enumerate(st.split("\n")):
        _para(tf, line, size=13, bold=True, color=WHITE, first=(j == 0),
              align=PP_ALIGN.CENTER, space_after=0)
    if i < len(steps) - 1:
        arrow(s, x + sw_ + Inches(0.04), ny + Inches(0.475), x + sw_ + Inches(0.31),
              ny + Inches(0.475), color=ORANGE)
tf = _txbox(s, MARGIN, ny - Inches(0.35), BODY_W, Inches(0.3))
_para(tf, "NEXT STEPS  ·  we are here ↓", size=10.5, bold=True, color=ICE, first=True)


OUT.parent.mkdir(parents=True, exist_ok=True)
prs.save(str(OUT))
print(f"Saved {OUT}  ({_n} slides)")
