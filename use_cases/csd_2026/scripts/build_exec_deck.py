"""Three-slide executive summary.

    & "C:\\Program Files\\Python311\\python.exe" scripts\\build_exec_deck.py

Written for a senior audience: no odds ratios, no pseudo-R2, no confidence
intervals in the body. Every figure comes from runs/output/exec/exec_data.json,
which is a straight lift from the verified detailed outputs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.parts.image import Image as PPTXImage
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
    from pptx.util import Emu, Inches, Pt
except ModuleNotFoundError:                                          # pragma: no cover
    sys.exit('Run with:  & "C:\\Program Files\\Python311\\python.exe" '
             'scripts\\build_exec_deck.py')

BASE = Path(__file__).resolve().parent.parent
EX = BASE / "runs" / "output" / "exec"
FIGS = EX / "figs"
OUT = BASE / "runs" / "output" / "CSD_2026_executive_summary.pptx"
D = json.loads((EX / "exec_data.json").read_text(encoding="utf-8"))

NAVY = RGBColor(0x0B, 0x2A, 0x4A)
ORANGE = RGBColor(0xFF, 0x6C, 0x00)
GREY = RGBColor(0x7A, 0x87, 0x94)
LIGHT = RGBColor(0xEE, 0xF1, 0xF4)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
RED = RGBColor(0xC1, 0x27, 0x2D)
GREEN = RGBColor(0x2E, 0x7D, 0x5B)

W, H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.62)
BODY_W = W - 2 * MARGIN
FOOTER_CLEAR = H - Inches(0.44)

prs = Presentation()
prs.slide_width, prs.slide_height = W, H
BLANK = prs.slide_layouts[6]
_n = 0
N_SLIDES = 4          # three exec slides plus the policy-level supplement

# Policy wording is unreadable on an exec slide, so each rule gets a plain name.
FRIENDLY = {
    "05": "Too recent — not indexed yet",
    "06": "Already in Scopus",
    "02": "Journal under re-evaluation",
    "07": "Already in the pipeline",
    "01": "Journal never covered",
    "08": "Outside the covered years",
    "15": "Already matches the published version",
    "03": "Unauthentic publisher site",
    "14": "Article in Press — sourcing rule",
    "24": "Open-access change unverifiable",
    "09": "Document type out of scope",
}


def friendly(label: str) -> str:
    lab = str(label)
    if lab.startswith("No applicable"):
        return "No rule covers this request"
    return FRIENDLY.get(lab[:2], lab[:38])


def _tx(s, left, top, width, height):
    box = s.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    return tf


def _p(tf, text, size=14, bold=False, color=NAVY, after=6, first=False,
       align=PP_ALIGN.LEFT):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.space_after = Pt(after)
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.color.rgb = color
    r.font.name = "Segoe UI"
    return p


def slide(title, subtitle=None, kicker=None):
    global _n
    s = prs.slides.add_slide(BLANK)
    _n += 1
    top = Inches(0.34)
    if kicker:
        _p(_tx(s, MARGIN, top, BODY_W, Inches(0.24)), kicker.upper(), size=11,
           bold=True, color=ORANGE, first=True)
        top = Inches(0.62)
    _p(_tx(s, MARGIN, top, BODY_W, Inches(0.55)), title, size=27, bold=True, first=True)
    if subtitle:
        _p(_tx(s, MARGIN, top + Inches(0.56), BODY_W, Inches(0.4)), subtitle,
           size=13, color=GREY, first=True)
    bar = s.shapes.add_shape(1, Inches(0), H - Inches(0.30), W, Inches(0.30))
    bar.fill.solid(); bar.fill.fore_color.rgb = LIGHT; bar.line.fill.background()
    bar.shadow.inherit = False
    _p(_tx(s, MARGIN, H - Inches(0.255), BODY_W, Inches(0.2)),
       f"Scopus Content Service Desk 2026  ·  executive summary"
       f"{' ' * 6}|{' ' * 6}{_n} of {N_SLIDES}", size=8.5, color=GREY, first=True)
    return s


def heat(v, lo, hi):
    """Pale to strong red. Colour carries the ranking so the eye finds it first."""
    if v is None:
        return LIGHT
    t = max(0.0, min(1.0, (v - lo) / (hi - lo) if hi > lo else 0))
    return RGBColor(int(255 - 40 * t), int(238 - 150 * t), int(230 - 175 * t))


def heat_good(v, lo, hi):
    """Green scale for satisfaction, which runs the opposite way to effort.

    A single red scale across both would read as if high satisfaction were bad.
    """
    if v is None:
        return LIGHT
    t = max(0.0, min(1.0, (v - lo) / (hi - lo) if hi > lo else 0))
    return RGBColor(int(240 - 55 * t), int(250 - 20 * t), int(243 - 30 * t))


def bignum(s, left, top, value, label, color=NAVY, width=Inches(3.5)):
    _p(_tx(s, left, top, width, Inches(0.8)), value, size=40, bold=True,
       color=color, first=True)
    _p(_tx(s, left, top + Inches(0.72), width, Inches(0.8)), label, size=12,
       color=GREY, first=True)


def pct(x, dp=0):
    return "—" if x is None else f"{x * 100:.{dp}f}%"


# ═════════════════════════════════════════════════ 1 · the rule scorecard
rules = D["top_rules"]
s = slide("The ten rules that carry the work",
          "12,000 tickets classified, projected to the 50,714 classifiable requests "
          "closed Jan–Jul 2026. Colour marks difficulty — deeper is harder.",
          kicker="where the volume is")

N_SAMPLE, N_POP = 12000, 50714
hdr = ["What we told the customer", "Sample\nn", "Sample\n%", "Full population\nestimate",
       "Pop.\n%", "Rule matches\nlogged code", "CSAT\nreplies", "CSAT\n% satisfied",
       "SURVEY\nreplies", "SURVEY\nsaid not easy", "MODEL\njudged high", "Days to\nclose"]
cw = [19, 5.5, 5, 9, 5, 8.5, 5, 8.5, 5.5, 9.5, 8.5, 6]
n_rows = len(rules) + 2                       # header + ten rules + a total line
shape = s.shapes.add_table(n_rows, len(hdr), MARGIN, Inches(1.60),
                           BODY_W, Inches(0.325) * n_rows)
tbl = shape.table
for i, frac in enumerate(cw):
    tbl.columns[i].width = Emu(int(BODY_W * frac / sum(cw)))
for j, h in enumerate(hdr):
    c = tbl.cell(0, j)
    c.text = ""
    c.fill.solid()
    # The two effort columns are the point of the slide, so their headers are a
    # shade lighter to separate them from the volume block at a glance.
    c.fill.fore_color.rgb = RGBColor(0x1B, 0x4C, 0x7A) if j in (6, 7, 8, 9, 10) else NAVY
    c.vertical_anchor = MSO_ANCHOR.MIDDLE
    _p(c.text_frame, h, size=8.5, bold=True, color=WHITE, first=True, after=0,
       align=PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER)

_ne = [r["pct_not_easy"] for r in rules if r["pct_not_easy"] is not None]
_hi = [r["pct_high_effort"] for r in rules]
_cs = [r["pct_satisfied"] for r in rules if r["pct_satisfied"] is not None]
for i, r in enumerate(rules, start=1):
    tbl.rows[i].height = Inches(0.325)
    vals = [friendly(r["rule_label"]),
            f"{r['sample_n']:,}", pct(r["sample_n"] / N_SAMPLE),
            f"{r['est_vol_jan_jul']:,}", pct(r["pct_of_population"]),
            pct(r["conf_strict"]),
            f"{r['csat_n']}", pct(r["pct_satisfied"]),
            f"{r['survey_n']}", pct(r["pct_not_easy"]),
            pct(r["pct_high_effort"]), f"{r['tat_median_days']:.1f}"]
    fills = [WHITE, WHITE, WHITE, WHITE, WHITE, WHITE,
             WHITE, heat_good(r["pct_satisfied"], min(_cs), max(_cs)),
             WHITE, heat(r["pct_not_easy"], min(_ne), max(_ne)),
             heat(r["pct_high_effort"], min(_hi), max(_hi)), WHITE]
    for j, (v, f) in enumerate(zip(vals, fills)):
        c = tbl.cell(i, j)
        c.text = ""
        c.fill.solid(); c.fill.fore_color.rgb = f
        c.vertical_anchor = MSO_ANCHOR.MIDDLE
        c.margin_left = c.margin_right = Inches(0.05)
        _p(c.text_frame, v, size=9.5, bold=(j == 0), first=True, after=0,
           align=PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER)

# Total line, so it is obvious how much of the corpus these ten cover.
_ts = sum(r["sample_n"] for r in rules)
_tp = sum(r["est_vol_jan_jul"] for r in rules)
_tc = sum(r["csat_n"] for r in rules)
_tv = sum(r["survey_n"] for r in rules)
tot = ["These ten rules", f"{_ts:,}", pct(_ts / N_SAMPLE), f"{_tp:,}", pct(_tp / N_POP),
       "·", f"{_tc}", "·", f"{_tv}", "·", "·", "·"]
tbl.rows[n_rows - 1].height = Inches(0.325)
for j, v in enumerate(tot):
    c = tbl.cell(n_rows - 1, j)
    c.text = ""
    c.fill.solid(); c.fill.fore_color.rgb = LIGHT
    c.vertical_anchor = MSO_ANCHOR.MIDDLE
    c.margin_left = c.margin_right = Inches(0.05)
    _p(c.text_frame, v, size=9.5, bold=True, first=True, after=0,
       color=GREY if v == "·" else NAVY,
       align=PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER)

box = s.shapes.add_shape(1, MARGIN, Inches(5.56), Inches(0.06), Inches(0.66))
box.fill.solid(); box.fill.fore_color.rgb = ORANGE; box.line.fill.background()
box.shadow.inherit = False
tf = _tx(s, MARGIN + Inches(0.2), Inches(5.56), BODY_W - Inches(0.3), Inches(0.7))
_p(tf, "Volume and difficulty point at different rules.", size=15, bold=True, first=True)
_p(tf, "The two biggest rules — 'too recent' and 'already in Scopus' — are among the easiest "
       "interactions we have. Prioritising by ticket count alone would aim at the wrong work.",
   size=12, color=GREY)

# Exact code definitions. Without them a reader reconciling against a differently
# cut CSAT report finds a gap and cannot tell whether it is a threshold or an error.
fn = _tx(s, MARGIN, Inches(6.26), BODY_W, Inches(0.76))
_p(fn, "How each column is defined  ·  'No Value' and 'Do Not Know' are excluded throughout",
   size=9, bold=True, color=NAVY, first=True, after=3)
_p(fn, "CSAT % satisfied = CSAT_ANSWER_CODE 1–3, extremely / very / satisfied — Neutral (4) "
       "counts as NOT satisfied.     SURVEY said not easy = CSAT_EFFORT_CODE 3–5 on "
       "'the request was easy to handle' — neither (3), disagree (4), strongly disagree (5); "
       "the stricter 4–5 cut is in the workbook.", size=8, color=GREY, after=2)
_p(fn, f"MODEL judged high = effort_score of high or very_high.     Dashes = fewer than "
       f"{D['min_survey_n']} replies, too few to quote.     The survey and model effort columns use different "
       f"scales — compare down a column, not across.", size=8, color=GREY)

# ══════════════════════════════════════ 2 · what drives customer effort
s = slide("What actually makes a request feel hard",
          f"Measured against {D['n_survey']:,} customers who told us, in their own words, "
          f"how easy it was", kicker="key drivers")
img = PPTXImage.from_file(str(FIGS / "e1_drivers.png"))
asp = img.size[1] / img.size[0]
w = Inches(8.6)
s.shapes.add_picture(str(FIGS / "e1_drivers.png"), MARGIN, Inches(1.58),
                     width=w, height=Emu(int(w * asp)))

tf = _tx(s, MARGIN + w + Inches(0.25), Inches(1.62),
         BODY_W - w - Inches(0.25), Inches(4.6))
_p(tf, "What we say matters more\nthan how we handle it", size=15, bold=True, first=True)
_p(tf, "The four strongest drivers are all about the answer the customer received, not "
       "the process behind it.", size=11.5, color=GREY, after=14)
_p(tf, "A second agent helps", size=15, bold=True, color=GREEN)
_p(tf, f"Passing a ticket on cuts the odds of a bad experience by "
       f"{(1 - D['handoff_or']) * 100:.0f}%. It usually means reaching someone who could "
       f"actually resolve it.", size=11.5, color=GREY, after=14)
_p(tf, "Speed matters, but less", size=15, bold=True)
_p(tf, f"Each extra day makes 'not easy' {D['tat_or']:.1f}x more likely — real, but "
       f"smaller than the effect of the answer itself.", size=11.5, color=GREY)

# ══════════════════════════════════════════════════ 3 · what this means
s = slide("What this means", "Three conclusions, and one honest limit",
          kicker="so what")

bignum(s, MARGIN, Inches(1.55), pct(D["base_rate"], 0),
       "of customers said their request\nwas not easy to handle", color=NAVY)
bignum(s, MARGIN + Inches(4.3), Inches(1.55), f"{D['worst_code_or']:.1f}x",
       "more likely when we tell them\na title was discontinued", color=RED)
bignum(s, MARGIN + Inches(8.6), Inches(1.55), f"{(1 - D['handoff_or']) * 100:.0f}%",
       "lower odds of a bad experience\nwhen a second agent steps in", color=GREEN)

tf = _tx(s, MARGIN, Inches(3.35), BODY_W, Inches(3.0))
_p(tf, "1 · Improve the answer, not just the process", size=15, bold=True, first=True)
_p(tf, "Effort tracks what we tell people far more than how quickly we tell them. The "
       "wins are in the four outcomes on the previous slide — clearer explanations of "
       "coverage decisions, not faster handling.", size=11.5, color=GREY, after=9)
_p(tf, "2 · Stop treating handoffs as a failure", size=15, bold=True)
_p(tf, "Escalating to a second agent is associated with a better experience, not a worse "
       "one. Any target that penalises handoffs pushes against the customer's interest.",
   size=11.5, color=GREY, after=9)
_p(tf, "3 · Compliance and customer pain are different problems", size=15, bold=True)
_p(tf, "Whether a ticket was mapped correctly against the policy matrix has no measurable "
       "effect on how hard the customer found it. Both are worth fixing — but fixing the "
       "matrix will not, on its own, improve the experience.", size=11.5, color=GREY, after=9)

box = s.shapes.add_shape(1, MARGIN, Inches(6.33), Inches(0.06), Inches(0.62))
box.fill.solid(); box.fill.fore_color.rgb = GREY; box.line.fill.background()
box.shadow.inherit = False
tf = _tx(s, MARGIN + Inches(0.2), Inches(6.33), BODY_W - Inches(0.3), Inches(0.7))
_p(tf, f"The limit: everything we record about a ticket explains about "
       f"{D['r2'] * 100:.0f}% of why customers find requests hard. We can rank which kinds "
       f"of request cause difficulty; we cannot predict any individual case.",
   size=11.5, color=GREY, first=True)

# ══════════════════════════ 4 · the same table at policy-rule granularity
# Slide 1 names the customer-facing outcome. This is the matrix's own view of the
# same tickets: rule number, guideline reference, and the code the rule is
# designated to produce against the code agents actually log.
allr = D["all_rules"]


def code_short(c):
    return "—" if not c or c == "(NA leaf)" else str(c).replace("invalid-", "").strip()


def rule_text(r):
    lab = str(r["rule_label"])
    if lab.startswith("No applicable"):
        return "No rule in the matrix covers the request"
    return lab[3:] if lab[:2].isdigit() else lab


s = slide("The same tickets, at policy-rule level",
          f"Every validation rule with at least 30 sampled tickets "
          f"({len(allr)} of {D['n_rules_total']}). Where the designated and logged codes "
          f"differ, the rule cannot conform however well it is applied.",
          kicker="supplementary · matrix view")

hdr2 = ["Rule", "Validation rule as written in the matrix", "Guideline",
        "Code the matrix\ndesignates", "Code agents\nactually log", "Match",
        "Tickets", "CSAT\n% sat.", "SURVEY\nnot easy", "MODEL\nhigh", "Days"]
cw2 = [7, 27, 8, 12, 12, 5, 7, 6, 7, 6, 4]
nr2 = len(allr) + 1
sh2 = s.shapes.add_table(nr2, len(hdr2), MARGIN, Inches(1.70), BODY_W,
                         Inches(0.265) * nr2)
t2 = sh2.table
for i, frac in enumerate(cw2):
    t2.columns[i].width = Emu(int(BODY_W * frac / sum(cw2)))
for j, h in enumerate(hdr2):
    c = t2.cell(0, j)
    c.text = ""
    c.fill.solid()
    c.fill.fore_color.rgb = RGBColor(0x1B, 0x4C, 0x7A) if j >= 7 else NAVY
    c.vertical_anchor = MSO_ANCHOR.MIDDLE
    c.margin_left = c.margin_right = Inches(0.04)
    _p(c.text_frame, h, size=8, bold=True, color=WHITE, first=True, after=0,
       align=PP_ALIGN.LEFT if j in (0, 1) else PP_ALIGN.CENTER)

for i, r in enumerate(allr, start=1):
    t2.rows[i].height = Inches(0.265)
    no = "—" if r["rule_no"] is None else f"{int(r['rule_no']):02d}"
    mismatch = (r["expected_primary"] and r["modal_actual"]
                and r["expected_primary"] != r["modal_actual"])
    vals = [no, rule_text(r)[:62], str(r["guideline_ref"] or "—")[:12],
            code_short(r["expected_primary"]), code_short(r["modal_actual"]),
            pct(r["conf_strict"]), f"{r['est_vol_jan_jul']:,}",
            pct(r["pct_satisfied"]), pct(r["pct_not_easy"]),
            pct(r["pct_high_effort"]), f"{r['tat_median_days']:.1f}"]
    # Amber marks a rule whose designated code is not the one it produces - the
    # governance defect this slide exists to expose.
    warn = RGBColor(0xFF, 0xF2, 0xE0)
    fills = [WHITE, WHITE, WHITE,
             warn if mismatch else WHITE, warn if mismatch else WHITE,
             warn if mismatch else WHITE, WHITE, WHITE, WHITE, WHITE, WHITE]
    for j, (v, f) in enumerate(zip(vals, fills)):
        c = t2.cell(i, j)
        c.text = ""
        c.fill.solid(); c.fill.fore_color.rgb = f
        c.vertical_anchor = MSO_ANCHOR.MIDDLE
        c.margin_left = c.margin_right = Inches(0.04)
        _p(c.text_frame, v, size=8, bold=(j == 0), first=True, after=0,
           color=RED if (mismatch and j == 5) else NAVY,
           align=PP_ALIGN.LEFT if j in (0, 1) else PP_ALIGN.CENTER)

_mm = [r for r in allr if r["expected_primary"] and r["modal_actual"]
       and r["expected_primary"] != r["modal_actual"]]
_mmvol = sum(r["est_vol_jan_jul"] for r in _mm)
fn2 = _tx(s, MARGIN, Inches(6.12), BODY_W, Inches(0.88))
_p(fn2, f"Shaded rows: {len(_mm)} rules where the code the matrix designates is not the "
        f"code agents actually log — {_mmvol:,} tickets", size=10, bold=True, color=NAVY,
   first=True, after=3)
_p(fn2, "Rule 08 is the clearest case: designated 'out of coverage', a code used 59 times "
        "all year, while its own tickets are logged 'discontinued title'. Those rules cannot "
        "conform however well agents apply them — the match rate measures the mapping table, "
        "not the practice. Column definitions as slide 1; guideline references are the "
        "matrix's own CCG citations.", size=8.5, color=GREY)

# ═══════════════════════════════════════════════════════════════ integrity
def est_text_height(tf, width_in):
    """Approximate rendered height. A textbox's declared height is not honoured by
    PowerPoint, so overflow is invisible to a geometry check on shape.height."""
    h = 0.0
    for para in tf.paragraphs:
        txt = "".join(r.text for r in para.runs)
        sizes = [r.font.size.pt for r in para.runs if r.font.size]
        sz = max(sizes) if sizes else 12.0
        chars_per_line = max(1, int(width_in * 96 / (sz * 0.52)))
        lines = max(1, -(-len(txt) // chars_per_line))
        h += lines * sz * 1.25 / 72
        h += (para.space_after.pt if para.space_after else 0) / 72
    return h


issues = []
for i, sl in enumerate(prs.slides, start=1):
    for sh in sl.shapes:
        bottom = sh.top + sh.height
        if sh.shape_type == 13 and bottom > FOOTER_CLEAR:
            issues.append(f"slide {i}: image overflows footer by "
                          f"{Emu(bottom - FOOTER_CLEAR).inches:.2f}in")
        if sh.has_table:
            if bottom > FOOTER_CLEAR:
                issues.append(f"slide {i}: table reaches the footer")
            for ri, row in enumerate(sh.table.rows):
                for c in row.cells:
                    if not c.text.strip():
                        issues.append(f"slide {i}: empty cell row {ri}")
        if sh.has_text_frame:
            t = sh.text_frame.text
            if "None" in t or "nan" in t.lower().split():
                issues.append(f"slide {i}: unformatted value")
            if t.strip() and "Service Desk 2026" not in t:
                end = Emu(sh.top).inches + est_text_height(
                    sh.text_frame, Emu(sh.width).inches)
                if end > Emu(FOOTER_CLEAR).inches:
                    issues.append(
                        f"slide {i}: text starting '{t.strip()[:30]}' reflows to "
                        f"{end:.2f}in, past the {Emu(FOOTER_CLEAR).inches:.2f}in footer")
        # Full-width decoration (the footer bar) is intentional; anything else must
        # stay inside the body margins.
        right = sh.left + sh.width
        if sh.width < W - Inches(0.5) and right > W - MARGIN + Inches(0.02):
            issues.append(f"slide {i}: {sh.shape_type} runs "
                          f"{Emu(right - (W - MARGIN)).inches:.2f}in past the right margin")
assert not issues, "integrity checks failed:\n  " + "\n  ".join(issues)
assert len(prs.slides.__iter__.__self__._sldIdLst) == N_SLIDES, (
    f"expected exactly {N_SLIDES} slides")

prs.save(OUT)
print(f"wrote {OUT}  ({N_SLIDES} slides)")
print("  integrity checks passed")
