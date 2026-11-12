"""Render the CSD 2026 deck from runs/output/deck/deck_data.json.

Run with the SYSTEM Python, which is the interpreter that has python-pptx:

    & "C:\\Program Files\\Python311\\python.exe" scripts\\build_deck.py

This script deliberately imports no pandas or numpy - only the standard library
and python-pptx - so the system interpreter's broken pandas/NumPy pairing does
not matter. All statistics come from deck_data.json, produced by
scripts/build_deck_data.py under the project venv.
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
    sys.exit("python-pptx is not available on this interpreter.\n"
             'Run with:  & "C:\\Program Files\\Python311\\python.exe" scripts\\build_deck.py')

BASE = Path(__file__).resolve().parent.parent
DECK_DIR = BASE / "runs" / "output" / "deck"
FIGS = DECK_DIR / "figs"
OUT = BASE / "runs" / "output" / "CSD_2026_validation_rules_analysis.pptx"

D = json.loads((DECK_DIR / "deck_data.json").read_text(encoding="utf-8"))
M = D["meta"]

NAVY = RGBColor(0x0B, 0x2A, 0x4A)
ORANGE = RGBColor(0xFF, 0x6C, 0x00)
GREY = RGBColor(0x7A, 0x87, 0x94)
LIGHT = RGBColor(0xEE, 0xF1, 0xF4)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
RED = RGBColor(0xC1, 0x27, 0x2D)

W, H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.62)
BODY_W = W - 2 * MARGIN

prs = Presentation()
prs.slide_width, prs.slide_height = W, H
BLANK = prs.slide_layouts[6]

_n = 0


# ───────────────────────────────────────────────────────────── helpers
def _txbox(slide, left, top, width, height):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    return tf


def _para(tf, text, size=14, bold=False, color=NAVY, space_after=6, first=False,
          align=PP_ALIGN.LEFT, italic=False):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.space_after = Pt(space_after)
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    run.font.name = "Segoe UI"
    return p


def slide(title=None, subtitle=None, kicker=None):
    """A blank slide with the standard header band and footer."""
    global _n
    s = prs.slides.add_slide(BLANK)
    _n += 1
    if title:
        if kicker:
            tf = _txbox(s, MARGIN, Inches(0.34), BODY_W, Inches(0.24))
            _para(tf, kicker.upper(), size=10.5, bold=True, color=ORANGE, first=True)
            top = Inches(0.60)
        else:
            top = Inches(0.42)
        tf = _txbox(s, MARGIN, top, BODY_W, Inches(0.5))
        _para(tf, title, size=25, bold=True, first=True)
        if subtitle:
            tf2 = _txbox(s, MARGIN, top + Inches(0.52), BODY_W, Inches(0.42))
            _para(tf2, subtitle, size=12, color=GREY, first=True)
    bar = s.shapes.add_shape(1, Inches(0), H - Inches(0.30), W, Inches(0.30))
    bar.fill.solid(); bar.fill.fore_color.rgb = LIGHT; bar.line.fill.background()
    bar.shadow.inherit = False
    tf = _txbox(s, MARGIN, H - Inches(0.255), BODY_W, Inches(0.2))
    _para(tf, f"Scopus Content Service Desk 2026  ·  validation rules and rejection reasons"
              f"{' ' * 6}|{' ' * 6}slide {_n}", size=8.5, color=GREY, first=True)
    return s


def content_top(has_subtitle=True, has_kicker=True):
    base = 0.60 if has_kicker else 0.42
    return Inches(base + (1.08 if has_subtitle else 0.66))


def section(title, blurb):
    global _n
    s = prs.slides.add_slide(BLANK)
    _n += 1
    band = s.shapes.add_shape(1, Inches(0), Inches(0), W, H)
    band.fill.solid(); band.fill.fore_color.rgb = NAVY; band.line.fill.background()
    band.shadow.inherit = False
    tf = _txbox(s, MARGIN, Inches(2.9), BODY_W, Inches(0.9))
    _para(tf, title, size=34, bold=True, color=WHITE, first=True)
    tf2 = _txbox(s, MARGIN, Inches(3.85), Inches(9.2), Inches(1.0))
    _para(tf2, blurb, size=14, color=RGBColor(0xC8, 0xD3, 0xDD), first=True)
    accent = s.shapes.add_shape(1, MARGIN, Inches(2.62), Inches(1.1), Inches(0.075))
    accent.fill.solid(); accent.fill.fore_color.rgb = ORANGE; accent.line.fill.background()
    accent.shadow.inherit = False
    return s


def bullets(s, items, top=None, left=MARGIN, width=None, size=14, gap=11):
    tf = _txbox(s, left, top or content_top(), width or BODY_W, Inches(4.4))
    for i, item in enumerate(items):
        if isinstance(item, tuple):
            text, sub = item
            _para(tf, text, size=size, bold=True, space_after=2, first=(i == 0))
            _para(tf, sub, size=size - 2.5, color=GREY, space_after=gap)
        else:
            _para(tf, item, size=size, space_after=gap, first=(i == 0))
    return tf


def table(s, headers, rows, top=None, left=MARGIN, width=None, col_w=None,
          size=10, header_size=10, highlight_rows=(), right_align_from=1, row_h=0.32):
    """A native PowerPoint table. row_h is a request, not a guarantee - PowerPoint
    grows a row if its text needs more space - so long tables also need a smaller
    font, or they push through the footer."""
    top = top or content_top()
    width = width or BODY_W
    shape = s.shapes.add_table(len(rows) + 1, len(headers), left, top, width,
                               Inches(row_h) * (len(rows) + 1))
    tbl = shape.table
    tbl.first_row = True
    for r in tbl.rows:
        r.height = Inches(row_h)
    if col_w:
        total = sum(col_w)
        for i, frac in enumerate(col_w):
            tbl.columns[i].width = Emu(int(width * frac / total))
    for j, h in enumerate(headers):
        c = tbl.cell(0, j)
        c.text = ""
        c.fill.solid(); c.fill.fore_color.rgb = NAVY
        c.vertical_anchor = MSO_ANCHOR.MIDDLE
        c.margin_left = c.margin_right = Inches(0.05)
        _para(c.text_frame, str(h), size=header_size, bold=True, color=WHITE, first=True,
              space_after=0, align=PP_ALIGN.RIGHT if j >= right_align_from else PP_ALIGN.LEFT)
    for i, row in enumerate(rows, start=1):
        for j, v in enumerate(row):
            c = tbl.cell(i, j)
            c.text = ""
            c.fill.solid()
            c.fill.fore_color.rgb = LIGHT if (i in highlight_rows) else WHITE
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            c.margin_left = c.margin_right = Inches(0.05)
            c.margin_top = c.margin_bottom = Inches(0.01)
            bold = i in highlight_rows
            _para(c.text_frame, str(v), size=size, bold=bold, first=True, space_after=0,
                  align=PP_ALIGN.RIGHT if j >= right_align_from else PP_ALIGN.LEFT)
    return tbl


FOOTER_CLEAR = H - Inches(0.44)      # keep every image and table above the footer band


def picture(s, name, top=None, left=None, max_w=None, max_h=None, center=False):
    """Place a chart scaled to fit BOTH bounds, never overlapping the footer.

    Sizing by width alone is what pushed four charts under the footer band on the
    first build: a 2:1 chart at full body width is 5.5in tall, which does not fit
    below a title.
    """
    path = FIGS / f"{name}.png"
    assert path.exists(), f"missing chart: {path}"
    img = PPTXImage.from_file(str(path))
    aspect = img.size[1] / img.size[0]
    top = top if top is not None else content_top()
    max_w = max_w or BODY_W
    max_h = max_h or (FOOTER_CLEAR - top)
    w = max_w
    h = Emu(int(w * aspect))
    if h > max_h:
        h = max_h
        w = Emu(int(h / aspect))
    if left is None:
        left = MARGIN + Emu(int((max_w - w) / 2)) if center else MARGIN
    return s.shapes.add_picture(str(path), left, top, width=w, height=h)


def callout(s, text, top, color=ORANGE, left=MARGIN, width=None, size=12.5):
    width = width or BODY_W
    box = s.shapes.add_shape(1, left, top, Inches(0.055), Inches(0.62))
    box.fill.solid(); box.fill.fore_color.rgb = color; box.line.fill.background()
    box.shadow.inherit = False
    tf = _txbox(s, left + Inches(0.18), top + Inches(0.02), width - Inches(0.2), Inches(0.6))
    _para(tf, text, size=size, first=True)


def pct(x, dp=1):
    return f"{x * 100:.{dp}f}%"


def num(x):
    return f"{x:,.0f}"


def short(s, n=46):
    s = str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


HL = {h["metric"]: h for h in D["headlines"]}
POP_CODE = M["pop_by_code"]           # exact 2026 counts, not estimates
ADVICE, DISC, BOOK = ("Invalid- advice request", "Invalid- discontinued title",
                      "Invalid- book")
AIP, OUTCOV = "Invalid- AIP", "Invalid- Out of coverage"
NA_EST = HL["No applicable validation rule"]["population"] * M["n_population"]


def exact(code):
    """Exact classifiable-population count for a resolution code.

    Taken from the metadata for all 50,721 tickets, so it is a count and carries
    no interval. Anything derived from the 12,000 sample always shows one.
    """
    return POP_CODE[code]


# ═══════════════════════════════════════════════════════ 1 title
s = prs.slides.add_slide(BLANK)
_n += 1
bg = s.shapes.add_shape(1, Inches(0), Inches(0), W, H)
bg.fill.solid(); bg.fill.fore_color.rgb = NAVY; bg.line.fill.background()
bg.shadow.inherit = False
acc = s.shapes.add_shape(1, MARGIN, Inches(2.05), Inches(1.5), Inches(0.09))
acc.fill.solid(); acc.fill.fore_color.rgb = ORANGE; acc.line.fill.background()
acc.shadow.inherit = False
tf = _txbox(s, MARGIN, Inches(2.35), Inches(11.4), Inches(1.9))
_para(tf, "Why Scopus content requests are rejected", size=40, bold=True, color=WHITE,
      first=True, space_after=8)
_para(tf, "Validation rules, rejection reasons and resolution codes across the 2026 "
          "Content Service Desk corpus", size=17, color=RGBColor(0xC8, 0xD3, 0xDD))
tf2 = _txbox(s, MARGIN, Inches(5.25), Inches(11.4), Inches(1.2))
_para(tf2, f"{num(M['n_sample'])} tickets classified  ·  extrapolated to "
           f"{num(M['n_population'])} classifiable 2026 tickets", size=14, bold=True,
      color=ORANGE, first=True, space_after=4)
_para(tf2, "Every population figure in this deck is a stratified estimate with a 95% "
           "confidence interval, not a multiplied sample.", size=12,
      color=RGBColor(0xA8, 0xB6, 0xC4))

# ═══════════════════════════════════════════════════════ 2 executive summary
s = slide("Executive summary", "Five findings, in order of the ticket volume they affect",
          kicker="Overview")
cov = M["unmapped_n_classifiable"]
bullets(s, [
    (f"1 · Three resolution codes have no validation rule — {num(cov)} tickets a year",
     "advice request, book and discontinued title are used on live tickets but no rule in the "
     "triangulation matrix claims any of them as its primary code."),
    ("2 · Rule 08's designated code is 65× rarer than the code it actually gets",
     f"Rule 08 is logged as 'Out of coverage' by design ({num(exact(OUTCOV))} tickets) but is "
     f"used for 'discontinued title' ({num(exact(DISC))}). Strict conformance reads 2%; "
     f"loose reads 85%."),
    ("3 · Articles in Press have no general rule",
     f"Both AiP rules are narrow — MEDLINE-sourced, and missing volume/issue — yet "
     f"{num(exact(AIP))} tickets carry the AiP code. Requests simply about an AiP fit neither."),
    (f"4 · 17 candidate rules drafted for the gaps, covering an estimated "
     f"{num(NA_EST)} tickets a year",
     "Machine-drafted from the tickets no rule covered, in the matrix's own phrasing. "
     "They need Content sign-off, not adoption."),
    (f"5 · The rule the ticket shows matches the code the agent logged "
     f"{pct(HL['Conformance among mappable (headline)']['population'])} of the time",
     "Measured on tickets a rule could conform to, ±"
     f"{pct(HL['Conformance among mappable (headline)']['ci'])}. Where they differ, either "
     "side can be wrong — the codes are agent-assigned."),
], size=13.5, gap=9)

# ═══════════════════════════════════════════════════════ 3 what was done
s = slide("What this analysis did", "Three existing artefacts, none of them previously "
          "connected to actual tickets", kicker="Overview")
table(s, ["Input", "What it contributes", "Size"], [
    ["Triangulation Matrix", "The policy: conditions under which a request is invalid",
     f"{M['n_rules']} validation rules"],
    ["Ticket metadata", "The outcome: the resolution code the agent logged. Ground truth.",
     "15 codes, all Invalid-*"],
    ["CSD CheatSheet & Templates", "The wording agents paste into replies — used as "
     "recognition cues in the rule descriptions", "24 template tabs"],
    ["Ticket conversations", "The evidence: what the customer asked and what the agent answered",
     f"{num(M['n_total_file'])} threads"],
], col_w=[2.2, 6.4, 2.2], size=11.5, top=content_top(), right_align_from=99)
callout(s, "Output: every ticket carries a validation rule (or an explicit 'none applies'), a "
           "rejection reason discovered from the tickets themselves, and its known resolution "
           "code — so the three can finally be cross-tabulated.", Inches(4.35))

# ═══════════════════════════════════════════════════════ PART A
section("Part A · Concepts and definitions",
        "Four terms carry the whole analysis. Three of them sound interchangeable and are not.")

s = slide("The three artefacts, and why they disagree",
          "Each answers a different question about the same ticket", kicker="Definitions")
table(s, ["", "Validation rule", "Rejection reason", "Resolution code"], [
    ["Question it answers", "Which policy makes this request invalid?",
     "What ground did the agent actually give?", "What did the agent log in OSVC?"],
    ["Where it comes from", "Triangulation Matrix (top-down)",
     "Discovered from the tickets (bottom-up)", "Agent's own choice at close"],
    ["How many values", f"{M['n_rules']} + 'none applies'",
     f"{M['n_reason_leaves']} leaves in {M['n_reason_l1']} groups", "15"],
    ["Assigned by", "This analysis (LLM, from the reply)", "This analysis (LLM, from the reply)",
     "A human agent, at the time"],
    ["Role here", "The thing being tested", "The independent view",
     "The reference the other two are compared against"],
], col_w=[1.9, 2.9, 2.9, 2.9], size=10.5, right_align_from=99)
callout(s, "The rule is the policy; the reason is what was said. They agree where the matrix is "
           "complete and diverge where it is not — that divergence is finding 1.", Inches(4.7))

s = slide("Definition · Validation rule",
          f"{M['n_rules']} conditions from the Triangulation Matrix, plus one code for "
          f"'no rule applies'", kicker="Definitions")
bullets(s, [
    ("Plain English", "A statement of when a request of a given type is not valid — "
     "for example, 'published less than 4 weeks ago, so too recent to be indexed yet'."),
    ("In this analysis", "Each rule became one leaf of a classification taxonomy. Its "
     "description carries the rule text, the guideline reference (CCG/CAR), the wording an "
     "agent would use when replying under it, and the analyst's mapping notes."),
    ("The 'none applies' code", "CSDVR4.1 exists so the model can decline. Without it a model "
     "forces every ticket into some rule and the gaps in the matrix become invisible — which "
     "is exactly what happened on the first pass."),
    ("What was deliberately withheld", "The rule's expected resolution code was never shown to "
     "the model. That is the quantity being measured; showing it would make the measurement "
     "circular."),
], size=13)

s = slide("Definition · Rejection reason",
          f"{M['n_reason_leaves']} categories discovered from the tickets, not written in advance",
          kicker="Definitions")
bullets(s, [
    ("Plain English", "The substantive ground the agent gave for not actioning the request, "
     "in the agent's own terms rather than the policy's."),
    ("Why it is not the same as the rule", "The rule is what the policy says should apply. The "
     "reason is what the agent actually wrote. Where a reason has no rule, the matrix has a hole; "
     "where a rule has no reason, the policy is not being used."),
    ("How it was built", "A first pass extracted one abstract reason per ticket from a "
     "stratified sample of 353; a second pass normalised those into a two-level taxonomy. "
     "Two structurally required categories were added by hand because the corpus needs them: "
     "'status enquiry only' and 'no reason stated'."),
    ("Why bottom-up", "It is the only view in the analysis not derived from the matrix, so it "
     "is the only one that can show what the matrix is missing."),
], size=13)

s = slide("Definition · Resolution code", "The reference standard — and it is not a gold standard",
          kicker="Definitions")
bullets(s, [
    ("What it is", "The code the handling agent selected when closing the ticket. All 15 values "
     "in this corpus begin 'Invalid-', so every ticket in scope is a rejected request."),
    ("Why it is the reference", "It is the only label that already exists on all "
     f"{num(M['n_total_file'])} tickets and was produced independently of this analysis."),
    ("Why it is not truth", "It is one agent's choice under time pressure. 'Invalid- Others' "
     "carries 4,125 tickets and functions as a wastebasket. Where the model and the agent "
     "disagree, either can be wrong."),
    ("Consequence for reading this deck", "Conformance measures agreement with the matrix. "
     "It is not an accuracy score, and it should never be quoted as one."),
], size=13)

s = slide("Definition · Conformance", "Three rates, three different denominators, three "
          "different maxima", kicker="Definitions")
table(s, ["Rate", "Measured over", "Value (population)", "Maximum possible"], [
    ["Conformance among mappable  ← headline", "Rule-tagged tickets whose code some rule claims "
     "as primary", pct(HL["Conformance among mappable (headline)"]["population"]), "100%"],
    ["Conformance strict", "All rule-tagged tickets",
     pct(HL["Conformance strict, all rule-tagged"]["population"]),
     pct(HL["Mappable (code a rule claims as primary)"]["population"])],
    ["Conformance loose", "All rule-tagged; counts the matrix's 'also maps to' codes",
     pct(HL["Conformance loose (primary or also-maps-to)"]["population"]),
     pct(HL["Mappable (code a rule claims as primary)"]["population"])],
], col_w=[3.3, 4.6, 2.1, 2.1], size=11, right_align_from=2)
callout(s, "A rule-tagged ticket whose resolution code no rule claims can never conform — that "
           "is why strict has a maximum below 100%. The headline is already restricted to "
           "tickets that can conform, so its maximum is 100%.", Inches(3.55))
callout(s, f"Identity worth checking: "
           f"{pct(HL['Mappable (code a rule claims as primary)']['population'], 1)} × "
           f"{pct(HL['Conformance among mappable (headline)']['population'], 1)} = "
           f"{pct(HL['Conformance strict, all rule-tagged']['population'], 1)} = conformance "
           f"strict.", Inches(4.5), color=GREY)

s = slide("Definition · Matrix code coverage", "A property of the matrix — and the number most "
          "likely to be misread", kicker="Definitions")
bullets(s, [
    (f"Matrix code coverage = {pct(M['matrix_code_coverage'])}",
     "The share of all 2026 tickets whose resolution code some rule claims as its primary code."),
    ("It bounds conformance strict", "A ticket whose code no rule claims cannot conform, so the "
     "strict rate can never exceed the mappable share."),
    ("It does NOT bound the headline", "Conformance among mappable is already restricted to "
     "tickets that can conform. Its maximum is 100%."),
    ("Why this matters", f"The two numbers currently sit at {pct(M['matrix_code_coverage'])} and "
     f"{pct(HL['Conformance among mappable (headline)']['population'])}. Read side by side they "
     "invite the conclusion that the analysis has hit a ceiling and nothing more can be gained. "
     f"It has not: the headroom on the headline is "
     f"{pct(1 - HL['Conformance among mappable (headline)']['population'])}."),
], size=13)

# ═══════════════════════════════════════════════════════ PART B
section("Part B · Method",
        "How the tickets were classified, how the sample was drawn, and how it is projected "
        "to the full year.")

s = slide("The pipeline", "Four stages; only two of them cost anything", kicker="Method")
table(s, ["Stage", "What happens", "Scale", "Cost"], [
    ["1 · Build", "The matrix becomes a classification taxonomy; prompts are generated and "
     "checked verbatim against the source", f"{M['n_rules']} rules → 25 leaves", "free"],
    ["2 · Discover", "A stratified sample of tickets is read to induce the rejection-reason "
     "taxonomy bottom-up", "353 tickets", "$3"],
    ["3 · Tag", "Every sampled ticket receives a rule and a reason, each with a justification "
     "and a verbatim quote", f"{num(M['n_sample'])} tickets", f"${M['cost_main_run_usd']:,.0f}"],
    ["4 · Analyse", "Cross-tabulation, conformance, association, gap detection, extrapolation",
     f"{num(M['n_population'])} projected", "free"],
], col_w=[1.5, 6.3, 2.3, 1.2], size=11, right_align_from=3)
callout(s, f"Total spend across every gate and iteration: ${M['cost_usd_total']:,.2f}. "
           f"Classifying all {num(M['n_population'])} classifiable tickets rather than a sample "
           f"would cost roughly ${M['n_population'] * 0.0137:,.0f}.", Inches(4.5))

s = slide("From corpus to classified sample",
          f"{num(M['n_total_file'])} tickets in the 2026 file; "
          f"{num(M['n_population'])} of them can be classified", kicker="Method")
picture(s, "01_funnel", max_w=Inches(8.1), top=Inches(1.75))
tf = _txbox(s, Inches(9.0), Inches(1.85), Inches(3.7), Inches(3.6))
_para(tf, "Why 6,214 are excluded", size=13, bold=True, first=True, space_after=8)
for reason, n in sorted(M["exclusion_reasons"].items(), key=lambda kv: -kv[1]):
    _para(tf, f"{num(n)}  ·  {reason}", size=11, color=GREY, space_after=5)
_para(tf, "These are chat threads whose transcript was never captured, or tickets with almost "
          "no text. No model can classify them, so they are reported separately and never "
          "extrapolated over.", size=10.5, color=GREY, space_after=0)

s = slide("The exclusions are not random",
          "Advice-request tickets are nine times more likely to be unclassifiable than "
          "Not-Missing ones", kicker="Method")
rows = [[r[RC] if (RC := "resolution_code_lvl1_desc") in r else r.get("index", ""),
         num(r["total"]), num(r["excluded"]), pct(r["pct_excluded"], 1)]
        for r in D["exclusion_by_code"][:9]]
table(s, ["Resolution code", "2026 tickets", "Excluded", "% excluded"], rows,
      col_w=[5.0, 2.0, 2.0, 2.0], size=11)
callout(s, "This is why the deck never projects onto the full 56,935. Assuming the excluded "
           "tickets behave like the classified ones would overstate the rule-covered share, "
           "because the tickets most likely to be excluded are the ones least likely to have "
           "a rule.", Inches(4.75))

s = slide("How the sample was drawn",
          "Stratified by resolution code with a floor of 300 per code — deliberately not "
          "proportional", kicker="Method")
picture(s, "02_strata_share", max_w=Inches(7.9), top=Inches(1.72))
tf = _txbox(s, Inches(8.85), Inches(1.9), Inches(3.9), Inches(4.0))
_para(tf, "Why a floor", size=13, bold=True, first=True, space_after=8)
_para(tf, "'Invalid- Out of coverage' has 59 tickets in the whole year. A proportional sample "
          "of 12,000 would contain 14 of them, and nothing could be said about that code.",
      size=11.5, color=GREY, space_after=8)
_para(tf, "The floor guarantees every code is estimable. Two codes were so rare that the "
          "sample took all of them:", size=11.5, color=GREY, space_after=6)
for st in M["census_strata"]:
    _para(tf, f"·  {st}", size=11, bold=True, space_after=3)
_para(tf, "Those two are a census, not a sample — their figures carry no sampling error at all.",
      size=11, color=GREY, space_after=0)

s = slide("Extrapolating to the full year",
          "Design-weighted estimation, because the sample is stratified", kicker="Method")
bullets(s, [
    ("Each sampled ticket stands for w = N / n tickets in its own stratum",
     "N is the population count for that resolution code, n the sampled count. The weights "
     f"range from 1.00 (a census) to 5.27, and sum to exactly {num(M['n_population'])}."),
    ("Estimate:  p̂ = Σ Wₕ · pₕ",
     "The rate within each stratum, weighted by that stratum's true share of the population."),
    ("Interval:  Var(p̂) = Σ Wₕ² · pₕ(1−pₕ)/nₕ · (1 − nₕ/Nₕ)",
     "The last term is the finite-population correction. When a stratum is sampled in full it "
     "goes to zero: we measured that stratum, we did not estimate it."),
    ("Every population figure in Part C carries the resulting 95% interval",
     "Typically ±0.5 to ±0.6 percentage points on a rate — narrow, because 12,000 is a large "
     "sample against 50,721 and the correction is doing real work."),
], size=13)

s = slide("What each sampled ticket stands for",
          "Design weights by resolution code: how many population tickets one sampled ticket "
          "represents", kicker="Method")
picture(s, "03_weights", max_w=Inches(8.5), top=Inches(1.72))
tf = _txbox(s, Inches(9.3), Inches(2.0), Inches(3.5), Inches(3.8))
_para(tf, "Reading the weights", size=13, bold=True, first=True, space_after=8)
_para(tf, "A 'premature' ticket in the sample speaks for 5.27 tickets in the year, because that "
          "code was deliberately under-sampled relative to its size.", size=11.5, color=GREY,
      space_after=8)
_para(tf, "The two orange bars are the census strata. Their weight is exactly 1.00: every "
          "ticket with that code is already in the sample, so there is nothing to project and "
          "no sampling error to report.", size=11.5, color=GREY, space_after=8)
_para(tf, f"The weights sum to {num(M['n_population'])} — the classifiable population, "
          f"exactly.", size=11.5, bold=True, space_after=0)

s = slide("Why a single multiplier would be wrong",
          "The error from scaling the sample by 4.227 instead of weighting it", kicker="Method")
picture(s, "04_naive_error", max_w=Inches(8.6), top=Inches(1.7))
tf = _txbox(s, Inches(9.45), Inches(2.0), Inches(3.35), Inches(3.6))
_para(tf, "Worked example", size=13, bold=True, first=True, space_after=8)
_para(tf, "Invalid- Non-GenCAR", size=12, bold=True, space_after=4)
_para(tf, "307 in the population.\n301 of them sampled.", size=11.5, color=GREY, space_after=6)
_para(tf, "Naive:  301 × 4.227 = 1,272", size=11.5, color=RED, space_after=4)
_para(tf, "Correct:  301 × (307/301) = 307", size=11.5, bold=True, color=ORANGE, space_after=8)
_para(tf, "A four-fold overstatement, on a code that was almost entirely sampled. The same "
          "logic understates 'premature' — the largest code — by 20%.", size=11, color=GREY,
      space_after=0)

s = slide("How the classification was validated", "Four gates before the main run, and three "
          "rounds of prompt correction", kicker="Method")
table(s, ["Control", "What it caught"], [
    ["Blindness checks", "The resolution code never reaches the model: two-column input file, "
     "header verified on disk, and 1 ticket excluded for quoting its own code in the text"],
    ["40-ticket smoke test", "Valid codes only; the verbatim evidence quote must actually "
     "appear in the transcript for ≥80% of tickets"],
    ["1,000-ticket probe ×3", "Rule 05 recall 49% → 89%; rule 07 precision 37% → 73%; "
     "discontinued-title routing 23/70 → 56/70 correct"],
    ["Boilerplate audit", "Agents close most coverage replies with 'any journal may be subject "
     "to re-evaluation'. The model was reading that standing disclaimer as a finding on 44% of "
     "such tickets; a negative cue cut it to 24%"],
    ["Confidence intervals on the audits", "Wilson lower bounds, so a 2-point movement on an "
     "88-ticket stratum is not mistaken for a real change"],
], col_w=[2.6, 8.4], size=11, right_align_from=99)

# ═══════════════════════════════════════════════════════ PART C
section("Part C · Results",
        "Sample beside population estimate throughout. Where they differ, the difference is the "
        "stratification being undone.")

s = slide("Coverage", "Sample counts and the population they represent", kicker="Results")
table(s, ["", "Sample", "Share of sample", "Population estimate", "Share of population"], [
    ["Tickets classified", num(M["n_sample"]), "100%", num(M["n_population"]), "100%"],
    ["A validation rule applies",
     num(round(HL["A validation rule applies"]["sample"] * M["n_sample"])),
     pct(HL["A validation rule applies"]["sample"]),
     f"{num(HL['A validation rule applies']['population'] * M['n_population'])}  ± "
     f"{num(HL['A validation rule applies']['ci'] * M['n_population'])}",
     pct(HL["A validation rule applies"]["population"])],
    ["No applicable rule (CSDVR4.1)",
     num(round(HL["No applicable validation rule"]["sample"] * M["n_sample"])),
     pct(HL["No applicable validation rule"]["sample"]),
     f"{num(HL['No applicable validation rule']['population'] * M['n_population'])}  ± "
     f"{num(HL['No applicable validation rule']['ci'] * M['n_population'])}",
     pct(HL["No applicable validation rule"]["population"])],
    ["No reason stated in the ticket",
     num(round(HL["No reason stated in the ticket"]["sample"] * M["n_sample"])),
     pct(HL["No reason stated in the ticket"]["sample"]),
     f"{num(HL['No reason stated in the ticket']['population'] * M['n_population'])}  ± "
     f"{num(HL['No reason stated in the ticket']['ci'] * M['n_population'])}",
     pct(HL["No reason stated in the ticket"]["population"])],
], col_w=[3.4, 1.7, 2.0, 2.9, 2.1], size=11, highlight_rows=(1,))
callout(s, "Throughout this deck: a figure defined by a resolution code is an exact 2026 "
           "count; a figure defined by the classification is a design-weighted estimate and "
           "carries a ± interval.", Inches(3.55), color=GREY)
callout(s, f"Excluded as unclassifiable: {num(M['n_excluded'])} tickets "
           f"({pct(M['n_excluded'] / M['n_total_file'])} of the 2026 file). These are outside "
           f"every figure in this deck.", Inches(4.6), color=GREY)

s = slide("Headline rates", "Sample vs population estimate, with 95% intervals",
          kicker="Results")
picture(s, "05_conformance", max_w=Inches(8.5), top=Inches(1.75))
tf = _txbox(s, Inches(9.35), Inches(1.95), Inches(3.45), Inches(4.0))
_para(tf, "Reading the shift", size=13, bold=True, first=True, space_after=8)
_para(tf, "Loose conformance falls 3.2 points when weighted, because the codes it rescues — "
          "discontinued title above all — were over-sampled.", size=11.5, color=GREY,
      space_after=8)
_para(tf, "The headline rises 1.0 point.", size=11.5, color=GREY, space_after=8)
_para(tf, "Neither shift is large, but neither is zero — which is the argument for weighting "
          "rather than assuming the sample is representative.", size=11.5, color=GREY,
      space_after=0)

s = slide("Headline rates in full", "Every rate with its denominator, sample and population",
          kicker="Results")
rows = []
for h in D["headlines"]:
    rows.append([short(h["metric"], 40), short(h["denominator"], 42),
                 pct(h["sample"]), f"{pct(h['population'])} ± {pct(h['ci'])}",
                 f"{h['delta'] * 100:+.1f} pp"])
table(s, ["Metric", "Denominator", "Sample", "Population estimate", "Shift"], rows,
      col_w=[3.2, 3.6, 1.4, 2.3, 1.3], size=10.5, highlight_rows=(1,), right_align_from=2)

s = slide("Validation rules by volume",
          f"Sample share vs estimated population share; labels are estimated ticket counts "
          f"across {num(M['n_population'])}", kicker="Results")
picture(s, "06_rule_volumes", max_w=Inches(11.3), top=Inches(1.72), center=True)

s = slide("Validation rules — the numbers",
          f"Top 10 by estimated annual volume. Naive error is what a flat 4.227× would have "
          f"given.", kicker="Results")
rows = []
for r in D["rule_breakdown"][:10]:
    rows.append([short(r["label"], 52), num(r["sample_n"]), pct(r["sample_pct"]),
                 f"{num(r['pop_est'])} ± {num(r['pop_ci'])}", pct(r["pop_pct"]),
                 f"{r['naive_err'] * 100:+.0f}%"])
table(s, ["Validation rule", "Sample n", "Sample %", "Population estimate", "Pop %",
          "Naive error"], rows, col_w=[4.5, 1.2, 1.2, 2.3, 1.0, 1.3], size=10)

s = slide("Rejection reasons by volume",
          f"Discovered bottom-up from the tickets; labels are estimated ticket counts across "
          f"{num(M['n_population'])}", kicker="Results")
picture(s, "07_reason_volumes", max_w=Inches(11.3), top=Inches(1.72), center=True)

s = slide("Rejection reasons — the numbers", "Top 10 by estimated annual volume",
          kicker="Results")
rows = []
for r in D["reason_breakdown"][:10]:
    rows.append([short(r["label"], 46), num(r["sample_n"]), pct(r["sample_pct"]),
                 f"{num(r['pop_est'])} ± {num(r['pop_ci'])}", pct(r["pop_pct"]),
                 f"{r['naive_err'] * 100:+.0f}%"])
table(s, ["Rejection reason", "Sample n", "Sample %", "Population estimate", "Pop %",
          "Naive error"], rows, col_w=[4.5, 1.2, 1.2, 2.3, 1.0, 1.3], size=10)

s = slide("Validation rule × resolution code",
          "Weighted to the population and row-normalised: given the rule, which code did the "
          "agent log?", kicker="Results")
picture(s, "08_rule_x_code", max_w=Inches(11.2), top=Inches(1.7), center=True)

s = slide("Rejection reason × validation rule",
          "Weighted to the population and row-normalised: given the reason, which rule was "
          "assigned?", kicker="Results")
picture(s, "09_reason_x_rule", max_w=Inches(11.2), top=Inches(1.7), center=True)

s = slide("Rejection reason × resolution code",
          "Weighted to the population and row-normalised: given the reason the agent gave, "
          "which code did they log?", kicker="Results")
picture(s, "19_reason_x_code", max_w=Inches(11.2), top=Inches(1.7), center=True)

s = slide("The three-way relationship",
          f"Top combinations of reason × rule × code by estimated annual volume "
          f"(11 of {D['n_three_way_cells']} cells)", kicker="Results")
rows = []
for r in D["three_way_top"][:11]:
    rows.append([short(r["reason_label"], 28), short(r["rule_label"], 38),
                 short(r["rc_label"], 22), num(r["sample_n"]),
                 num(r["pop_est"]), pct(r["pop_pct"]),
                 "yes" if r["conf_strict"] >= 0.5 else "no"])
table(s, ["Rejection reason", "Validation rule", "Resolution code", "Sample n",
          "Est. population", "Pop %", "Conforms"], rows,
      col_w=[2.5, 3.4, 2.0, 0.9, 1.3, 0.8, 0.9], size=9.5, row_h=0.30, right_align_from=3)
callout(s, f"Design-weighted like every other population figure in this deck. All "
           f"{D['n_three_way_cells']} cells sum to {num(M['n_population'])}; the 11 shown "
           f"account for {pct(sum(r['pop_pct'] for r in D['three_way_top'][:11]))} of the year.",
        Inches(5.35), color=GREY, size=11)

s = slide("How strongly the three axes are related",
          "Cramér's V, bias-corrected; 0 is independence, 1 is a perfect relationship",
          kicker="Results")
picture(s, "12_association", max_w=Inches(8.3), top=Inches(1.9))
tf = _txbox(s, Inches(9.2), Inches(2.0), Inches(3.6), Inches(3.8))
_para(tf, "What this says", size=13, bold=True, first=True, space_after=8)
a = {r["pair"]: r for r in D["association"]}
rc = a["Validation rule x resolution code"]
_para(tf, f"Rule and code are the most strongly related pair (V = "
          f"{rc['pop_v_corrected']:.2f}) — as they should be, since the matrix asserts that "
          f"link.", size=11.5, color=GREY, space_after=8)
rr = a["Rejection reason x resolution code"]
_para(tf, f"Reason and code sit lower (V = {rr['pop_v_corrected']:.2f}): the discovered "
          f"reasons are not a restatement of the codes, which is what makes them useful as an "
          f"independent view.", size=11.5, color=GREY, space_after=8)
_para(tf, "All three associations are far from independence, so the matrix is describing "
          "something real — the question is only where it is incomplete.", size=11.5,
      color=GREY, space_after=0)

# ═══════════════════════════════════════════════════════ PART D
section("Part D · Findings",
        "What the classification revealed about the triangulation matrix itself.")

s = slide("Finding 1 · Three resolution codes no rule claims",
          f"{num(M['unmapped_n_classifiable'])} classifiable tickets a year fall outside the "
          f"matrix entirely — an exact count, not an estimate", kicker="Findings")
picture(s, "11_unmapped", max_w=Inches(7.6), top=Inches(1.8))
tf = _txbox(s, Inches(8.5), Inches(1.95), Inches(4.2), Inches(4.0))
_para(tf, "Why each is missing", size=13, bold=True, first=True, space_after=8)
_para(tf, f"advice request  —  {num(exact(ADVICE))}", size=11.5, bold=True, space_after=2)
_para(tf, "Status enquiries. Every rule is phrased about a request; an enquiry has no request "
          "to invalidate.", size=10.5, color=GREY, space_after=7)
_para(tf, f"discontinued title  —  {num(exact(DISC))}", size=11.5, bold=True, space_after=2)
_para(tf, "Appears only as an 'also maps to' on rule 08. See finding 2.", size=10.5,
      color=GREY, space_after=7)
_para(tf, f"book  —  {num(exact(BOOK))}", size=11.5, bold=True, space_after=2)
_para(tf, "Book and conference coverage sits outside the matrix's two request types.",
      size=10.5, color=GREY, space_after=7)
_para(tf, "The workbook already knows: it carries a sheet named \"Unmapped 'invalid' res "
          "codes\".", size=10.5, italic=True, color=GREY, space_after=0)

pr8 = next(r for r in D["per_rule"] if str(r["code"]) == "CSDVR1.8")
s = slide("Finding 2 · Rule 08's designated code is 65× rarer than the one it gets",
          "The strongest single argument for revising the matrix", kicker="Findings")
table(s, ["", "Code the matrix designates", "Code the tickets actually carry"], [
    ["Code", "Invalid- Out of coverage", "Invalid- discontinued title"],
    ["Status in the matrix", "Primary resolution code for rule 08", "'Also maps to' only"],
    ["Classifiable tickets, 2026", num(exact(OUTCOV)), num(exact(DISC))],
    ["Rule-08 conformance", f"strict  {pct(pr8['strict'])}", f"loose  {pct(pr8['loose'])}"],
], col_w=[2.6, 4.2, 4.2], size=12, highlight_rows=(3,), right_align_from=99)
callout(s, "Rule 08 is not performing badly. It is being measured against a code that is "
           "almost never used. The primary and the also-maps-to are the wrong way round.",
        Inches(4.2))
callout(s, "Recommended: swap them, or promote 'discontinued title' to a primary code of its "
           "own. Either change moves roughly 3,500 tickets a year from 'non-conforming' to "
           "'conforming' without touching a single ticket.", Inches(5.1), color=ORANGE)

DT = D["discontinued_title"]
_r0, _r1 = DT["top_rules"][0], DT["top_rules"][1]
_n0 = DT["top_reasons"][0]
s = slide("Deep dive · Invalid- discontinued title",
          f"{num(DT['est_pop'])} classifiable tickets — the largest unmapped code that is an "
          f"actual request rather than an enquiry", kicker="Findings")
table(s, ["", "What the data shows", "Why it matters"], [
    ["Status in the matrix", "'Also maps to' on rule 08 only — no rule claims it as primary",
     "Mappable 0%, so strict conformance can never exceed 0%"],
    ["What the classifier reads",
     f"{pct(_r0['share'], 0)} route to rule 08, {pct(_r1['share'], 0)} to rule 01",
     "The tickets are coherent: four fifths are one rule"],
    ["What the agent said",
     f"{pct(_n0['share'], 0)} give '{_n0['label']}' as the reason",
     "Reason and rule agree; only the mapping table disagrees"],
    ["Conformance",
     f"strict {pct(DT['conf_strict'], 0)}  ·  loose {pct(DT['conf_loose'], 0)}",
     "The whole gap is the primary/also-maps-to inversion"],
    ["Customer effort",
     "69% judged high effort; 30% of surveyed customers said it was not easy",
     "The highest-effort resolution code in the corpus"],
    # No year-on-year row here. The 2025 figure is a full calendar year and this
    # corpus is not, so any comparison stated in the deck's own "a year" framing
    # would read as a 46% collapse that is purely the period mismatch.
    ["What the fix buys",
     "Rule-08 conformance moves from 2% to 85% on the same tickets",
     "One cell in the mapping table; no ticket or agent is touched"],
], col_w=[2.3, 4.6, 4.1], size=10.5, highlight_rows=(1, 5), right_align_from=99, row_h=0.52)
callout(s, "One code, one rule, one reason, and the highest customer effort we measure. "
           "Promoting 'discontinued title' to a primary code on rule 08 fixes the largest "
           "single conformance defect in the matrix and touches nothing else.", Inches(5.55),
        color=ORANGE)

MR_PATH = DECK_DIR / "multirule_data.json"
if MR_PATH.exists():
    MR = json.loads(MR_PATH.read_text(encoding="utf-8"))
    _d = MR["dist"]
    _one = _d.get("1", 0.0)
    s = slide("How often is a ticket failed by more than one rule?",
              f"A separate multi-label pass over the same {num(MR['n_sample'])} tickets, "
              f"asking which rules apply rather than which fits best", kicker="Findings")
    _m0 = MR["top_member"][0]
    _p0 = MR["top_pairs"][0]
    rows = [
        ["Exactly one rule applies", pct(_one),
         "The matrix behaves as a set of alternatives, not overlapping conditions"],
        ["Two rules apply", pct(MR["multi_rate"]),
         f"{MR['multi_n']} of {num(MR['n_sample'])} sampled; unweighted "
         f"{pct(MR['sample_rate'])}, Wilson 95% CI {pct(MR['ci_lo'])}–{pct(MR['ci_hi'])}"],
        ["Three or more", "0%",
         f"The maximum observed anywhere in the run was {MR['max_rules']}"],
        ["Where the overlap sits", f"{_m0['code']}",
         f"Rule {_m0['label'][:2]} is in {pct(_m0['share_of_multi'])} of all multi-rule "
         f"tickets — the commonest pair is with rule {_p0['b_label'][:2] if _p0['a'] == _m0['code'] else _p0['a_label'][:2]} ({_p0['n']} tickets)"],
        ["Agreement with the original run", pct(MR["retest_agreement"]),
         f"An independent second pass over the same taxonomy on {num(MR['retest_n'])} "
         f"tickets — this is the rule classifier's test-retest figure"],
    ]
    table(s, ["", "Measured", "Reading"], rows, top=Inches(1.72),
          col_w=[3.0, 1.5, 6.5], size=11, right_align_from=1, row_h=0.42)
    picture(s, "20_rules_per_ticket", max_w=Inches(6.1), top=Inches(4.30), center=True)
    callout(s, f"Two caveats, both material. The rate is a LOWER BOUND: "
               f"{MR['n_exclusivity_leaves']} of {MR['n_leaves']} rule descriptions carry "
               f"single-label wording ('not this rule', 'do not use') added during the "
               f"original tuning, so the taxonomy discourages double-labelling. And at "
               f"{pct(MR['retest_agreement'])} agreement, the classifier disagrees with itself "
               f"far more often than tickets break two rules.", Inches(6.45), color=RED)

s = slide("Finding 3 · Articles in Press have no general rule",
          f"{num(exact(AIP))} tickets carry the AiP code; both AiP rules are narrower "
          f"than that",
          kicker="Findings")
table(s, ["Rule", "Condition", "Covers"], [
    ["14", "AiP requested for a MEDLINE-sourced title, or from a publisher not on the approved "
     "list", "A specific sourcing case"],
    ["22", "Missing volume / issue / page on an AiP — not an error", "A specific correction case"],
    ["—", "'My article is in press and is not in Scopus yet'", "Nothing. No rule fits."],
], col_w=[0.9, 7.4, 2.7], size=11.5, highlight_rows=(3,), right_align_from=99)
callout(s, "The classifier routes these to rule 05 (too recent), which is a defensible reading "
           "of the transcript but not what the agent logged. Adding a prompt cue would force "
           "them into the MEDLINE rule and make the crosstab wrong in a way that looks right.",
        Inches(3.9))
callout(s, "This is a matrix gap, not a model defect. It needs a general AiP rule.", Inches(4.8),
        color=ORANGE)

s = slide("Finding 4 · Candidate rules drafted for the gaps",
          "Machine-drafted from the tickets no rule covered, in the matrix's own phrasing — "
          "for Content review, not adoption", kicker="Findings")
_uncovered_total = sum(x["n_uncovered_in_run"] for x in D["proposed_rules"])
_scale = NA_EST / _uncovered_total

# The gap pass drafts one rule per rejection reason, so two reasons that need the
# same rule produce the same text twice. Merge them: otherwise the table looks
# like a duplication bug and the largest gap is split across two rows.
_merged = {}
for r in D["proposed_rules"]:
    key = str(r["Proposed Validation Rule"]).strip().lower()
    m = _merged.setdefault(key, {"rule": r["Proposed Validation Rule"],
                                 "type": r["Request Type"],
                                 "code": r["Primary Resolution Code (observed)"],
                                 "n": 0, "agree": 0.0, "reasons": 0})
    m["n"] += r["n_uncovered_in_run"]
    m["agree"] = max(m["agree"], r["agreement"])
    m["reasons"] += 1
_props = sorted(_merged.values(), key=lambda m: -m["n"])

rows = []
for r in _props[:6]:
    rows.append([short(r["type"], 18), short(r["rule"], 90),
                 short(str(r["code"]), 20), num(r["n"] * _scale),
                 pct(r["agree"], 0)])
table(s, ["Request type", "Proposed validation rule", "Code observed", "Est. tickets/yr",
          "Model agreement"], rows, col_w=[1.4, 6.8, 1.6, 1.15, 1.15], size=9.5,
      right_align_from=3)
_max_agree = max(r["agree"] for r in _props)
callout(s, "'Model agreement' is how consistently the same wording came back across tickets of "
           "that kind. Below 10% means the gap is well evidenced but the wording is not.",
        Inches(4.35), color=GREY, size=11)
callout(s, f"Every candidate is below that line — the highest across all {len(_props)} distinct "
           f"drafts is {pct(_max_agree, 0)}. Treat them as evidence that a rule is needed, "
           f"and as a starting draft, not as text to adopt.", Inches(5.2), color=ORANGE,
        size=11.5)

s = slide("Finding 5 · Where the classifier and the agents disagree",
          "Conformance is agreement with the matrix, not accuracy", kicker="Findings")
picture(s, "10_per_rule", max_w=Inches(8.2), top=Inches(1.75))
tf = _txbox(s, Inches(9.05), Inches(1.95), Inches(3.75), Inches(4.0))
_para(tf, "Three explanations, always", size=13, bold=True, first=True, space_after=8)
_para(tf, "1 · The model misread the ticket.", size=11.5, space_after=5)
_para(tf, "2 · The agent picked the wrong code — 'Invalid- Others' carries 4,125 tickets and "
          "acts as a wastebasket.", size=11.5, space_after=5)
_para(tf, "3 · The matrix has no right answer, so both parties improvised.", size=11.5,
      space_after=9)
_para(tf, "Conformance cannot distinguish these. Thirty disagreement cases with both "
          "justifications are in the deliverable workbook for manual review.", size=11,
      color=GREY, space_after=0)

# ═══════════════════════════════════════════════════════ PART E
section("Part E · Recommendations",
        "Ordered by the number of tickets each change affects in a year.")

s = slide("Recommendations", "Volumes are exact 2026 counts where a resolution code "
          "defines the group, and design-weighted estimates where the classification does",
          kicker="Recommendations")
table(s, ["#", "Action", "Owner", "Tickets affected / yr"], [
    ["1", "Swap rule 08's primary and also-maps-to codes, or give 'discontinued title' its own "
     "primary code", "Content policy", num(exact("Invalid- discontinued title"))],
    ["2", "Add a validation rule for status and coverage enquiries, which currently have none",
     "Content policy", num(exact("Invalid- advice request"))],
    ["3", "Add a general Article-in-Press rule alongside the two narrow ones",
     "Content policy", num(exact("Invalid- AIP"))],
    ["4", "Add a book / conference coverage rule", "Content policy",
     num(exact("Invalid- book"))],
    ["5", "Review the 17 machine-drafted candidate rules; adopt, rewrite or reject each",
     "Content policy + CSD", f"{num(NA_EST)} est."],
    ["6", "Sharpen the rule 15 / rule 06 boundary — 45% of rule 15's errors land on one code",
     "This analysis (prompt cue)",
     f"{num(next(r['pop_est'] for r in D['rule_breakdown'] if str(r['label']).startswith('15')))} est."],
    ["7", "Re-run over all 50,721 tickets once the matrix is revised, for a per-ticket tag",
     "This analysis", f"${M['n_population'] * 0.0137:,.0f} to run"],
], col_w=[0.5, 6.9, 2.3, 1.8], size=10.5, highlight_rows=(1, 2), right_align_from=3)

s = slide("What this cost, and what it would cost to complete",
          "Measured from the run's own token accounting", kicker="Recommendations")
table(s, ["Item", "Records", "Cost"], [
    ["Taxonomy discovery", "353 tickets", "$3"],
    ["Validation gates: smoke ×5, probe ×3", "~6,400 record-passes", "$56"],
    ["Main run: 12,000 tickets × 2 modules", "24,005 record-passes",
     f"${M['cost_main_run_usd']:,.2f}"],
    ["Candidate-rule gap pass", "1,625 tickets", "$8"],
    ["Total spent", "—", f"${M['cost_usd_total']:,.2f}"],
    ["Full corpus instead of a sample", f"{num(M['n_population'])} tickets",
     f"~${M['n_population'] * 0.0137:,.0f}"],
], col_w=[6.2, 3.0, 2.0], size=11.5, highlight_rows=(5,))
callout(s, "The sample was the right call: at ±0.6 points on the headline, a full run buys "
           "precision nobody would use. It is worth doing only if the deliverable must be a tag "
           "on every individual ticket.", Inches(4.3), color=GREY)

# ═══════════════════════════════════════════════════════ PART F · effort
EF = D.get("effort")
if EF:
    _high_pop = EF["high_pop"]
    _obs = EF["obs_medians"]

    section("Part F · Customer effort",
            "What the interaction cost the customer, and how that lines up with the rules and "
            "reasons.")

    s = slide("Two readings of the same interaction",
              "Neither is a customer telling us how hard it was", kicker="Effort")
    table(s, ["", "Observed effort", "Judged effort"], [
        ["Source", "The thread record: turns, agents, timestamps",
         "The transcript, read by the model"],
        ["What it gives", "How the interaction actually unfolded",
         "Effort level, friction points, themes, transparency"],
        ["Exact?", "Yes - counts and timestamps, no model",
         "No - a judgement, though grounded in a verbatim quote"],
        ["Blind to", "Why the customer was frustrated",
         "Anything not written in the transcript"],
        ["Covers", "All 56,935 incidents", f"The {num(M['n_sample'])} scored tickets"],
    ], col_w=[1.9, 4.6, 4.6], size=11, right_align_from=99)
    callout(s, "They are computed independently and compared on slide "
               f"{'x'}. Agreement between them is corroboration, not validation - no customer "
               "has told us how hard any of these tickets were. Survey data is expected; the "
               "notebook is built to accept it.", Inches(4.5), color=GREY)

    s = slide("How observed effort is measured",
              f"From {num(176083)} thread entries across all {num(M['n_total_file'])} incidents. "
              f"No model, no cost.", kicker="Effort")
    table(s, ["Signal", "Typical value", "Note"], [
        ["Turns in the thread", f"median {_obs['turns']:.0f}", "customer and agent messages"],
        ["Agent handoffs", f"mean {_obs['handoffs']:.2f}",
         "a second agent touching the ticket; 57% of incidents have one"],
        ["Resolution span", f"median {_obs['span_h']:,.0f}h", "first entry to last"],
        ["Repeat contact", f"{_obs['repeat_pct']:.0%}",
         "same customer, another ticket. Unknown for ~13% - recorded as unknown, not as no"],
        ["obs_effort_index", "0 to 1",
         "equal-weight mean of the four percentile-ranked signals above"],
    ], col_w=[2.4, 2.0, 6.7], size=11, right_align_from=99)
    callout(s, "The index is authored, not fitted - there is nothing to fit against until the "
               "survey lands. Its components are published so it can be reweighted rather than "
               "rebuilt.", Inches(4.4), color=GREY)

    s = slide("How much effort, overall",
              f"Judged effort across the {num(M['n_sample'])} scored tickets, extrapolated to "
              f"{num(M['n_population'])}", kicker="Effort")
    picture(s, "13_effort_distribution", max_w=Inches(8.6), top=Inches(1.8))
    tf = _txbox(s, Inches(9.4), Inches(2.0), Inches(3.4), Inches(3.6))
    _para(tf, "Reading this", size=13, bold=True, first=True, space_after=8)
    _para(tf, f"{pct(_high_pop)} of tickets are judged high or very high effort - an estimated "
              f"{num(_high_pop * M['n_population'])} a year.", size=11.5, color=GREY,
          space_after=8)
    _para(tf, "The extremes are thinly populated. Most of the signal lives in the low / medium / "
              "high band, which is where the incoming survey will matter most.", size=11.5,
          color=GREY, space_after=0)

    s = slide("Effort by rejection reason",
              f"Share judged high-effort. Dashed line is the {pct(_high_pop)} overall rate.",
              kicker="Effort")
    picture(s, "14_effort_by_reason", max_w=Inches(11.2), top=Inches(1.72), center=True)

    s = slide("Effort by validation rule",
              "Estimable rules only, ordered by estimated annual volume", kicker="Effort")
    rows = []
    for r in sorted([r for r in EF["by_rule"] if r.get("estimable")],
                    key=lambda r: -r["est_population"])[:11]:
        rows.append([short(r["rule_label"], 48), num(r["n"]), num(r["est_population"]),
                     pct(r["pct_high"]), f"{r['mean_effort']:.2f}",
                     f"{r['obs_span_h_median']:,.0f}h"])
    table(s, ["Validation rule", "Sample n", "Est. population", "% high effort",
              "Mean (1-5)", "Median span"], rows,
          col_w=[4.6, 1.1, 1.6, 1.4, 1.2, 1.2], size=10)

    s = slide("Where the friction is",
              "Normalised friction categories, estimated annual volume", kicker="Effort")
    picture(s, "15_friction_points", max_w=Inches(9.6), top=Inches(1.78))
    tf = _txbox(s, Inches(10.3), Inches(2.0), Inches(2.6), Inches(3.6))
    _para(tf, "The added category", size=13, bold=True, first=True, space_after=8)
    _para(tf, "The eight standard friction categories had no home for being told to take the "
              "request elsewhere.", size=11, color=GREY, space_after=8)
    _para(tf, "On a corpus that is entirely rejections, that is not an edge case - it is the "
              "outcome for a large minority.", size=11, color=GREY, space_after=0)

    s = slide("Does the matrix failing a ticket cost the customer effort?",
              "The question the rule analysis could not answer on its own", kicker="Effort")
    picture(s, "17_effort_vs_conformance", max_w=Inches(11.0), top=Inches(1.76), center=True)

    s = slide("Judged effort against observed effort",
              "Two independent readings of the same interaction", kicker="Effort")
    picture(s, "16_judged_vs_observed", max_w=Inches(8.4), top=Inches(1.82))
    tf = _txbox(s, Inches(9.2), Inches(2.0), Inches(3.6), Inches(3.8))
    _para(tf, "What it means", size=13, bold=True, first=True, space_after=8)
    if EF.get("spearman"):
        _para(tf, f"Spearman {EF['spearman']}", size=12, bold=True, space_after=6)
    _para(tf, "The model reads the transcript; the index counts turns, handoffs and elapsed "
              "time. They were computed with no knowledge of each other.", size=11.5,
          color=GREY, space_after=8)
    _para(tf, "That they move together is corroboration. It is not validation - neither one is "
              "a customer.", size=11.5, color=GREY, space_after=8)
    _para(tf, "The survey, when it arrives, is what settles whether the middle of the five-point "
              "scale carries information.", size=11.5, color=GREY, space_after=0)

    _sv = (EF.get("survey") or {}).get("validation")
    if _sv:
        s = slide("What actually predicts how hard the customer found it",
                  "Measured against the customer's own effort answer, from the CSAT survey",
                  kicker="Effort")
        picture(s, "18_survey_agreement", max_w=Inches(8.8), top=Inches(1.8))
        tf = _txbox(s, Inches(9.6), Inches(2.0), Inches(3.2), Inches(3.8))
        _para(tf, "The finding", size=13, bold=True, first=True, space_after=8)
        _best = max(_sv, key=lambda r: r["spearman"])
        _ops = [r for r in _sv if not str(r["signal"]).startswith("LLM")]
        _bestops = max(_ops, key=lambda r: r["spearman"]) if _ops else None
        _para(tf, f"Reading the conversation: {_best['spearman']:+.3f}", size=12, bold=True,
              space_after=4)
        if _bestops:
            _para(tf, f"Best handling metric: {_bestops['spearman']:+.3f}", size=12,
                  color=GREY, space_after=8)
        _para(tf, "Agent handoffs and repeat contact — the two metrics an operations team "
                  "reaches for first — are negatively signed. They do not measure what the "
                  "customer felt.", size=11, color=GREY, space_after=8)
        _para(tf, f"n = {_best['n']:,} customers who answered the effort question.", size=11,
              color=GREY, space_after=0)
        callout(s, "This is the only comparison in the deck against a customer rather than "
                   "against another estimate. Everything else is corroboration between two "
                   "views of the same ticket.", Inches(6.0), color=GREY, size=11)

    _rel = (EF.get("survey") or {}).get("reliability")
    if _rel:
        _d = {r["measure"]: r["value"] for r in _rel}
        s = slide("How repeatable is the effort score?",
                  "The 12,000 cohort was scored twice by the same prompt. The two runs "
                  "disagree.", kicker="Effort")
        table(s, ["Measure", "Value"], [[r["measure"], r["value"]] for r in _rel],
              col_w=[7.0, 4.0], size=11.5, right_align_from=1,
              highlight_rows=(4, 8))
        callout(s, "Two runs of the same prompt correlate at "
                   f"{_d.get('Spearman run 1 vs run 2', 'n/a')}. That is a ceiling on how well "
                   "this score can correlate with anything - including the customer.",
                Inches(4.45))
        callout(s, "The high-effort rate moved between runs by more than any confidence "
                   "interval in this deck. Those intervals describe sampling error only; they "
                   "do not include the model's own variability. Quote aggregate effort rates "
                   "to the nearest few points, and never treat one ticket's score as a fact "
                   "about that ticket.", Inches(5.35), color=RED)

    s = slide("What effort adds to the recommendations",
              "The rule and reason findings, re-read through customer cost", kicker="Effort")
    _ce = {r["segment"]: r for r in EF["conformance"]}
    _na = _ce.get("No applicable rule (CSDVR4.1)")
    _dis = _ce.get("Rule and code disagree")
    _base = _ce.get("Rule matches the logged code")
    bullets(s, [
        ("The matrix gaps are not only a governance problem",
         (f"Tickets no rule covers run at {pct(_na['pct_high'])} high-effort against "
          f"{pct(_base['pct_high'])} where rule and code agree - "
          f"{num(_na['est_population'])} tickets a year."
          if _na and _base else "See the conformance chart.")),
        ("Rule/code disagreement tracks a harder experience",
         (f"{pct(_dis['pct_high'])} high-effort, {(_dis['pct_high'] - _base['pct_high']) * 100:+.1f} "
          f"points against baseline. The bookkeeping mismatch is visible to the customer."
          if _dis and _base else "See the conformance chart.")),
        ("Being redirected elsewhere is a first-class outcome here",
         "It needed a friction category of its own, and it did not have one."),
        ("Operational effort metrics do not measure customer effort",
         "Against the customer's own answer, handoffs and repeat contact are negatively "
         "signed and the composite index is near zero. Reading the conversation is roughly "
         "twice as informative as anything the handling record offers."),
    ], size=13, gap=10)


# ═══════════════════════════════════════════════════════ APPENDIX
section("Appendix", "Full tables, method detail, and the limitations that bound every number "
                    "in this deck.")

for half, rows_src in (("1 of 2", D["per_rule"][:11]), ("2 of 2", D["per_rule"][11:])):
    s = slide(f"Appendix · Conformance by validation rule ({half})",
              "Sample figures. 'Estimable' marks rules with at least 30 sampled tickets.",
              kicker="Appendix")
    rows = []
    for r in rows_src:
        rows.append([str(r["code"]), short(r["rule"], 48), num(r["n"]),
                     short(str(r["expected"]), 22), pct(r["strict"], 0), pct(r["loose"], 0),
                     "yes" if r["estimable"] else "no"])
    table(s, ["Code", "Rule", "n", "Expected code", "Strict", "Loose", "Estimable"], rows,
          col_w=[0.9, 4.6, 0.8, 2.2, 0.9, 0.9, 0.9], size=9.5, right_align_from=2)

s = slide("Appendix · Conformance by resolution code",
          "'Mappable' means at least one rule claims this code as its primary", kicker="Appendix")
rows = []
for r in D["per_code"]:
    rows.append([short(r["resolution_code"], 34), num(r["n"]), pct(r["na_rate"], 0),
                 "yes" if r["mappable"] else "no", pct(r["strict"], 0), pct(r["loose"], 0)])
table(s, ["Resolution code", "Sample n", "No rule applies", "Mappable", "Strict", "Loose"],
      rows, col_w=[4.0, 1.4, 1.8, 1.3, 1.2, 1.2], size=9.5, row_h=0.29)

s = slide("Appendix · The rejection-reason taxonomy",
          f"{M['n_reason_leaves']} leaves in {M['n_reason_l1']} groups, discovered from the "
          f"tickets", kicker="Appendix")
vol = {r["label"]: r for r in D["reason_breakdown"]}
rows = []
for grp in D["reason_taxonomy"]:
    for leaf in grp["leaves"]:
        v = vol.get(leaf)
        rows.append([short(grp["l1"], 26), short(leaf, 40),
                     num(v["sample_n"]) if v else "0",
                     num(v["pop_est"]) if v else "0"])
table(s, ["Group", "Rejection reason", "Sample n", "Est. population"], rows,
      col_w=[2.6, 4.6, 1.5, 2.0], size=9, row_h=0.27, right_align_from=2)

s = slide("Appendix · Prompt corrections and their effect",
          "Three probe rounds of 1,000 tickets each, before the main run", kicker="Appendix")
table(s, ["Correction", "Metric", "Before", "After"], [
    ["Named the standing re-evaluation disclaimer as insufficient evidence",
     "False-positive rate on disclaimer-only tickets", "44%", "24%"],
    ["Told the model the generic indexing timeline is the premature rule, not the pipeline rule",
     "Rule 05 recall", "49%", "89%"],
    ["Same cue, other side", "Rule 07 precision", "37%", "73%"],
    ["Told the model a discontinued title is a coverage mismatch, not a re-evaluation",
     "Discontinued tickets routed to rule 08", "23 / 70", "56 / 70"],
], col_w=[6.0, 3.2, 1.0, 1.0], size=10.5, right_align_from=2)
callout(s, "The headline moved 67% → 75-79% across these rounds, but the differences between "
           "the last two probes were inside the ±3.1-point interval of a 1,000-ticket sample. "
           "Tuning stopped there deliberately.", Inches(4.4), color=GREY)

s = slide("Appendix · Limitations", "Each of these bounds how the numbers should be read",
          kicker="Appendix")
bullets(s, [
    ("The reference standard is agent-assigned", "Resolution codes are one agent's choice at "
     "close, under time pressure. 'Invalid- Others' carries 4,125 tickets. Conformance is "
     "agreement, not accuracy."),
    ("The matrix is one analyst's interpretation", f"Quoted from its own Legend sheet: "
     f"\"{short(M['legend_quote'], 155)}\""),
    (f"{num(M['n_excluded'])} tickets were never classified", "Chat threads whose transcript "
     "was not captured, and very short tickets. They are not extrapolated over, and they skew "
     "towards advice requests."),
    (f"The model returned a code outside the taxonomy on {M['n_invalid_code']} tickets "
     f"({pct(M['n_invalid_code'] / M['n_sample'], 2)})",
     f"{', '.join(f'{k} ×{v}' for k, v in M['invalid_codes'].items())}. They are reported as a "
     "separate bucket, not silently dropped."),
    ("Single model, single pass", "No second opinion and no human adjudication of the "
     "classifications themselves. The 30 disagreement cases in the workbook are the starting "
     "point for that."),
], size=12.5, gap=8)

s = slide("Appendix · Reproducibility", "Everything in this deck regenerates from two commands",
          kicker="Appendix")
table(s, ["Artefact", "Path"], [
    ["Notebook (all 19 sections)", "notebooks/08_csd_2026_validation_rules.ipynb"],
    ["Taxonomy definition (source of truth)", "definitions/csd_2026_pipeline_definition.xlsx"],
    ["Per-ticket output, 12,000 rows", "runs/output/csd_2026_validation_rules.xlsx"],
    ["Untruncated ticket text", "runs/output/csd_2026_validation_rules_full_text.csv"],
    ["Candidate rules", "runs/output/csd_2026_rule_proposals.xlsx"],
    ["Deck statistics and charts", "runs/output/deck/deck_data.json  +  deck/figs/"],
    ["This deck", "scripts/build_deck_data.py  →  scripts/build_deck.py"],
], col_w=[4.0, 7.0], size=11, right_align_from=99)
callout(s, f"Sample seed 0, stratified by resolution code, floor {300} per code. The run is "
           f"resumable and re-running it with an unchanged prompt makes no further LLM calls.",
        Inches(4.5), color=GREY)

# ═══════════════════════════════════════════════════════ save
OUT.parent.mkdir(parents=True, exist_ok=True)
prs.save(str(OUT))
print(f"Wrote {OUT.relative_to(BASE)}  ({_n} slides, {OUT.stat().st_size / 1024:.0f} KB)")
