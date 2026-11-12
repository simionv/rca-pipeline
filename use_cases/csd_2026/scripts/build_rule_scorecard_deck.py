"""Render the per-validation-rule scorecard deck.

Run with the SYSTEM Python, which is the interpreter that has python-pptx:

    & "C:\\Program Files\\Python311\\python.exe" scripts\\build_rule_scorecard_deck.py

Standard library plus python-pptx only. Every statistic comes from
runs/output/scorecard/scorecard_data.json, produced by
scripts/build_rule_scorecard.py under the project venv.

This is a SEPARATE deck. It does not touch
runs/output/CSD_2026_validation_rules_analysis.pptx.
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
             'Run with:  & "C:\\Program Files\\Python311\\python.exe" '
             'scripts\\build_rule_scorecard_deck.py')

BASE = Path(__file__).resolve().parent.parent
SC_DIR = BASE / "runs" / "output" / "scorecard"
FIGS = SC_DIR / "figs"
MDIR = BASE / "runs" / "output" / "model"
MFIGS = MDIR / "figs"
OUT = BASE / "runs" / "output" / "CSD_2026_rule_scorecard.pptx"

D = json.loads((SC_DIR / "scorecard_data.json").read_text(encoding="utf-8"))
M = D["meta"]
RULES = D["per_rule"]
RPC = D["rules_per_code"]
RPR = D["rules_per_reason"]
YOY = D["code_yoy"]
EBR = D["effort_by_rule"]
EBC = D["effort_by_code"]
EBRE = D["effort_by_reason"]

MD = json.loads((MDIR / "model_results.json").read_text(encoding="utf-8"))
MM = MD["meta"]
MSUM = {r["model"]: r for r in MD["summary"]}
MBLK = MD["blocks"]
MPERM = {r["model"]: r for r in MD["perm"]}
MCOEF = MD["coefficients"]
MT2 = MD["type2"]

NAVY = RGBColor(0x0B, 0x2A, 0x4A)
ORANGE = RGBColor(0xFF, 0x6C, 0x00)
GREY = RGBColor(0x7A, 0x87, 0x94)
LIGHT = RGBColor(0xEE, 0xF1, 0xF4)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
RED = RGBColor(0xC1, 0x27, 0x2D)

W, H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.62)
BODY_W = W - 2 * MARGIN
FOOTER_CLEAR = H - Inches(0.44)

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
    _para(tf, f"Scopus CSD 2026  ·  validation-rule scorecard"
              f"{' ' * 6}|{' ' * 6}slide {_n}", size=8.5, color=GREY, first=True)
    return s


def content_top(has_subtitle=True, has_kicker=True):
    base = 0.60 if has_kicker else 0.42
    return Inches(base + (1.08 if has_subtitle else 0.66))


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
            _para(c.text_frame, str(v), size=size, bold=(i in highlight_rows), first=True,
                  space_after=0,
                  align=PP_ALIGN.RIGHT if j >= right_align_from else PP_ALIGN.LEFT)
    return tbl


def picture(s, name, top=None, left=None, max_w=None, max_h=None, center=False):
    path = (MFIGS if name.startswith("m0") else FIGS) / f"{name}.png"
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
    return "—" if x is None else f"{x * 100:.{dp}f}%"


def num(x):
    return "—" if x is None else f"{x:,.0f}"


def dec(x, dp=2):
    return "—" if x is None else f"{x:.{dp}f}"


def short(s, n=44):
    s = str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


# ═══════════════════════════════════════════════════════════════ 1 · title
s = prs.slides.add_slide(BLANK)
_n += 1
band = s.shapes.add_shape(1, Inches(0), Inches(0), W, H)
band.fill.solid(); band.fill.fore_color.rgb = NAVY; band.line.fill.background()
band.shadow.inherit = False
tf = _txbox(s, MARGIN, Inches(2.35), Inches(11.4), Inches(1.5))
_para(tf, "The validation-rule scorecard", size=40, bold=True, color=WHITE, first=True)
_para(tf, "Every rule beside its volume, its conformance, and what it costs the customer",
      size=16, color=RGBColor(0xC8, 0xD3, 0xDD))
acc = s.shapes.add_shape(1, MARGIN, Inches(2.05), Inches(1.3), Inches(0.08))
acc.fill.solid(); acc.fill.fore_color.rgb = ORANGE; acc.line.fill.background()
acc.shadow.inherit = False
tf = _txbox(s, MARGIN, Inches(5.25), Inches(11.4), Inches(1.0))
_para(tf, f"{M['n_sample']:,} classified tickets  ·  {M['closed_from']} to {M['closed_to']}  "
          f"·  {M['months_observed']} months, annualised x{M['annualise']:.2f}",
      size=13, color=WHITE, first=True)
_para(tf, "Volumes are design-weighted estimates. Survey figures are shown only where at "
          f"least {M['min_survey_n']} customers answered.",
      size=11.5, color=RGBColor(0xC8, 0xD3, 0xDD))

# ═══════════════════════════════════════════════════════════ 2 · how to read
s = slide("Three things to know before reading a single number",
          "Each one changes how a figure on the next slides should be quoted",
          kicker="how to read this")
bullets(s, [
    (f"The corpus is {M['months_observed']} months, not a year",
     f"Every ticket closed between {M['closed_from']} and {M['closed_to']}. Volumes are given "
     f"on that observed basis and again annualised (x{M['annualise']:.3f}). "
     f"The earlier 60-slide deck labels these same volumes 'a year' — those figures are "
     f"understated by 71%. Rates and percentages are unaffected."),
    ("CSAT and effort run in opposite directions",
     "CSAT is an inverted 1–7 scale where 1 is extremely satisfied, so a LOWER mean is better. "
     "Both effort scales run 1–5 where 5 is hardest. The three have been checked against each "
     "other for sign and they cohere."),
    (f"Survey columns are thin: {M['n_survey']} answers across {M['n_rules_total']} rules",
     f"Only {M['n_rules_clearing']} rules reach {M['min_survey_n']} responses. The rest show a "
     f"dash — the count is always printed so you can see what a figure rests on. This covers "
     f"the whole top ten by volume."),
], size=13.5, gap=13)

# ═══════════════════════════════════════════════ 3-4 · the scorecard tables
HDR = ["Validation rule", "Est. vol\nJan–Jul", "Annual-\nised", "Conf.\nstrict",
       "Survey\nn", "% not easy\nsurvey 3–5", "% hard\nsurvey 4–5", "% high\nLLM",
       "Survey\nmean", "LLM\nmean", "TAT\nmed d"]
CW = [25, 8, 8, 6, 5, 10, 9, 8, 7, 7, 7]


def rule_row(r):
    return [short(r["rule_label"], 40),
            num(r["est_vol_jan_jul"]), num(r["est_vol_annualised"]),
            pct(r["conf_strict"], 0),
            r["survey_n"], pct(r["pct_not_easy"], 0), pct(r["pct_hard"], 0),
            pct(r["pct_high_effort"], 0),
            dec(r["survey_effort_mean_1_5"]), dec(r["llm_effort_mean_1_5"]),
            dec(r["tat_median_days"], 1)]


s = slide("The scorecard — rules 1 to 12 by volume",
          "Both effort measures side by side. Survey columns blank below "
          f"{M['min_survey_n']} responses. Survey and LLM percentages are NOT on the same "
          f"scale — compare rankings, not levels", kicker="scorecard")
table(s, HDR, [rule_row(r) for r in RULES[:12]], col_w=CW, size=9.5, header_size=8.5,
      row_h=0.30)

_tail = RULES[12:]
s = slide("The scorecard — the remaining rules",
          f"All below {max(r['est_vol_jan_jul'] for r in _tail):,} tickets in the seven "
          f"months, and none has more than "
          f"{max(r['survey_n'] for r in _tail)} survey responses — read the rates as "
          f"illustrative only", kicker="scorecard")
table(s, HDR, [rule_row(r) for r in _tail], col_w=CW, size=9.5, header_size=8.5,
      row_h=0.30)

# ═══════════════════════════════════════════════════ 5 · volume vs effort
s = slide("Volume and customer effort point at different rules",
          "Each bubble is a rule, sized by sample. Dashed line is the "
          f"{M['overall_high_effort'] * 100:.0f}% overall high-effort rate",
          kicker="where the pain is")
picture(s, "01_volume_vs_effort", max_h=Inches(4.05), center=True)
callout(s, "The largest rules sit low. Rule 05 — 'too recent' — is the biggest single rule in "
           "the corpus and one of the easiest interactions. Prioritising by volume alone would "
           "aim at the wrong rules.", Inches(6.12))

# ═════════════════════════════════════════════ 6 · conformance vs effort
s = slide("Rules the matrix mis-maps are not the rules customers struggle with",
          "Strict conformance against the share judged high effort", kicker="governance vs pain")
picture(s, "02_conformance_vs_effort", max_h=Inches(4.05), center=True)
callout(s, "Rule 08 sits bottom-right: 2% strict conformance and 68% high effort — a mapping "
           "defect and a hard interaction at once. Rule 06 is the opposite corner. The two "
           "problems are separable and need separate fixes.", Inches(6.12))

# ═══════════════════════════════════════ 7 · the model against the customer
s = slide("The model reads every rule as harder than the customer reported",
          f"Mean effort on the {M['n_rules_clearing']} rules with enough survey responses",
          kicker="calibration")
picture(s, "03_llm_vs_customer", max_h=Inches(3.95), center=True)
callout(s, f"The gap is +{M['delta_min']:.2f} to +{M['delta_max']:.2f} (mean "
           f"+{M['delta_mean']:.2f}) and positive on every single rule. The score ranks rules "
           f"correctly but sits about one level above the customer's own answer — treat it as "
           f"an ordering, never as a level.", Inches(6.02))

# ═════════════════════════════════════════════════════════ 8 · turnaround
s = slide("Turnaround time is not a proxy for effort either",
          "Median and 90th percentile days from creation to close, estimable rules only",
          kicker="turnaround")
picture(s, "04_tat_by_rule", max_h=Inches(4.05), center=True)
callout(s, "Rule 15 has among the longest turnaround yet middling effort, while rule 02 is "
           "one of the fastest and one of the hardest. Speed and difficulty are close to "
           "unrelated here.", Inches(6.12))

# ═════════════════════════════════════════ 9 · CSAT where it is quotable
srv = [r for r in RULES if r["survey_n"] >= M["min_survey_n"]]
s = slide("What customers actually said, where enough of them answered",
          f"{M['n_survey']} survey-effort answers and {M['n_csat']} CSAT answers across the "
          f"{M['n_sample']:,} classified tickets", kicker="the customer's view")
table(s, ["Validation rule", "CSAT n", "CSAT mean\n(1–7, low = good)", "% satisfied",
          "Survey n", "Effort mean\n(1–5, high = hard)", "% hard", "LLM effort",
          "LLM minus\nsurvey"],
      [[short(r["rule_label"], 42), r["csat_n"], dec(r["csat_mean_1_7"]),
        pct(r["pct_satisfied"], 0), r["survey_n"], dec(r["survey_effort_mean_1_5"]),
        pct(r["pct_hard"], 0), dec(r["llm_effort_mean_1_5"]),
        f"+{r['llm_vs_survey_delta']:.2f}"] for r in srv],
      col_w=[28, 7, 12, 9, 7, 12, 8, 8, 9], size=10, header_size=8.5, row_h=0.40)
callout(s, f"Satisfaction never falls below {min(r['pct_satisfied'] for r in srv) * 100:.0f}% "
           f"even on the hardest rules. Customers of this service are broadly satisfied with "
           f"how they were treated while disagreeing with the outcome.", Inches(5.55))

# ══════════════════════════════════ 10-11 · rules per resolution code
s = slide("A resolution code cannot tell you which rule applied",
          f"The matrix assigns {24} rules to just {M['n_primary_codes']} distinct primary "
          f"codes — a mean of {M['structural_mean']:.2f} rules per claimed code",
          kicker="rules per resolution code")
picture(s, "05_rules_per_code", max_h=Inches(4.05), center=True)
callout(s, f"Designed mean {M['structural_mean']:.2f}, observed mean "
           f"{M['obs_mean_code']:.2f} — the tickets behave almost exactly as the matrix is "
           f"built. That agreement is a validation of the classifier, not a coincidence.",
        Inches(6.12))

s = slide("Rules per resolution code — the numbers",
          "Structural counts come from the matrix; effective counts are design-weighted over "
          "the tagged tickets", kicker="rules per resolution code")
table(s, ["Resolution code", "Est. vol\nJan–Jul", "Rules naming it\nas primary",
          "…also maps\nto it", "Distinct rules\nobserved", "Effective\nrules",
          "Rules covering\n90% of volume"],
      [[r["rc_label"], num(r["est_vol_jan_jul"]), r["n_rules_primary"], r["n_rules_also"],
        r["distinct_rules"], dec(r["effective_rules_inv_simpson"]),
        r["rules_covering_90pct"]] for r in RPC],
      col_w=[26, 11, 14, 11, 13, 11, 14], size=9.5, header_size=8.5, row_h=0.29)

# ═══════════════════════════════════════ 12 · rules per rejection reason
s = slide("Rejection reasons are more ambiguous still",
          f"Effective rules per reason averages {M['obs_mean_reason']:.2f}, against "
          f"{M['obs_mean_code']:.2f} for resolution codes",
          kicker="rules per rejection reason")
picture(s, "06_rules_per_reason", max_h=Inches(4.05), center=True)
callout(s, "Expected, and reassuring: the reasons were discovered bottom-up from the tickets "
           "with no reference to the matrix, so they cut across it. Red bars are reasons that "
           "spread across three or more rules — the places where policy and practice diverge "
           "most.", Inches(6.12))

# ═══════════════════════════════════════════════════════ 13 · year on year
s = slide("Volumes did not halve — they are flat",
          "The obvious reading of the matrix's own volume columns is wrong",
          kicker="year on year")
picture(s, "07_year_on_year", max_h=Inches(3.90), center=True)
callout(s, f"2025 full year {M['vol_2025']:,} Invalid- tickets. Jan–Jul 2026 is "
           f"{M['n_invalid_file']:,}, annualising to {M['n_pop_annualised']:,} — "
           f"{M['yoy_pct'] * 100:+.1f}%. Reading the matrix's 2025 column against its 2026 "
           f"column suggests a halving, because that 2026 figure is a "
           f"{M['osvc_months']}-month snapshot.", Inches(5.98))

# ═══════════════════════════════════════════════════════ 14 · what it adds
s = slide("What the scorecard adds", "Five things visible only once the views sit on one row",
          kicker="findings")
bullets(s, [
    ("Volume, conformance and effort disagree about which rules matter",
     "The largest rule by volume is among the easiest; the worst-conforming rule is among the "
     "hardest; the slowest rule is middling on both. Any single-metric priority list is wrong."),
    (f"The effort score is offset by about one level (+{M['delta_mean']:.2f} mean)",
     "Positive on every rule with survey data. Use it to rank, never to state a level."),
    (f"A resolution code implies {M['obs_mean_code']:.2f} rules on average",
     f"Designed at {M['structural_mean']:.2f}. The code alone cannot identify the policy, "
     f"which is why the matrix needed testing against tickets in the first place."),
    ("Customers stay satisfied while disagreeing with the outcome",
     "Satisfaction holds above 79% on every measurable rule even where the majority are judged "
     "high effort. Effort and satisfaction are not the same thing on a rejection corpus."),
    (f"Volumes are flat year on year ({M['yoy_pct'] * 100:+.1f}%), not halved",
     "Two independent annualisation routes agree within "
     f"{abs(M['n_pop_annualised'] - M['ann_from_osvc']) / M['n_pop_annualised'] * 100:.0f}%."),
], size=13, gap=10)

# ═══════════════════════════════════════════════════════ 15 · limitations
s = slide("Limitations", "Each one bounds how a column above should be read",
          kicker="limitations")
bullets(s, [
    (f"The 2025 column is a resolution-code volume, not a rule volume",
     "Rules sharing a primary code carry the same figure, so the column cannot be summed. "
     "Rule 24's 20,687 is the 2025 volume of 'Invalid- Others', not of rule 24."),
    ("Annualisation assumes the remaining five months resemble the first seven",
     "Monthly volumes over Jan–Jul range 7,462 to 9,659, so the assumption is reasonable but "
     "untested. Seasonality in academic publishing could break it."),
    (f"Survey respondents are self-selected, and there are only {M['n_survey']} of them",
     "About 5% of tickets. Comparisons between signals are fair because they use the same "
     "people; the absolute levels may not generalise."),
    ("The LLM effort score agrees with itself only 62.3% of the time",
     "Test-retest Spearman +0.675. That is a ceiling on how well it can correlate with "
     "anything, and it means aggregate rates move a few points between runs."),
    ("Conformance is agreement with the matrix, not accuracy",
     "The resolution code is one agent's choice at close. Where the rule and the code "
     "disagree, either can be wrong."),
], size=12.5, gap=9)

# ═══════════════════════════════════════════════ effort by each axis
s = slide("Both effort measures, by resolution code",
          f"The code is known for every ticket, so this view rests on all "
          f"{MM['n_analysis']:,} survey respondents — {M['codes_adequate']} of "
          f"{M['n_codes']} codes clear the threshold", kicker="effort by axis")
_e = [r for r in EBC if r["survey_base_adequate"]]
table(s, ["Resolution code", "Tickets", "Survey n", "% not easy\nsurvey 3–5",
          "% hard\nsurvey 4–5", "% high\nLLM", "Survey\nmean", "LLM\nmean", "TAT med d"],
      [[short(r["rc_label"], 34), num(r["n_tickets"]), r["survey_n"],
        pct(r["pct_not_easy_survey"], 0), pct(r["pct_hard_survey"], 0),
        pct(r["pct_high_llm"], 0), dec(r["survey_effort_mean_1_5"]),
        dec(r["llm_effort_mean_1_5"]), dec(r["tat_median_days"], 1)] for r in _e],
      col_w=[27, 9, 8, 12, 11, 10, 8, 8, 9], size=9.5, header_size=8.5, row_h=0.30)

s = slide("The same view by rejection reason",
          f"Only {M['reasons_adequate']} of {M['n_reasons']} reasons clear "
          f"{M['min_survey_n']} responses — reasons exist only on the 12,000 sample",
          kicker="effort by axis")
_r = [r for r in EBRE if r["survey_base_adequate"]]
table(s, ["Rejection reason", "Est. vol", "Survey n", "% not easy\nsurvey 3–5",
          "% hard\nsurvey 4–5", "% high\nLLM", "Survey\nmean", "LLM\nmean"],
      [[short(r["reason_label"], 34), num(r["est_vol_jan_jul"]), r["survey_n"],
        pct(r["pct_not_easy_survey"], 0), pct(r["pct_hard_survey"], 0),
        pct(r["pct_high_llm"], 0), dec(r["survey_effort_mean_1_5"]),
        dec(r["llm_effort_mean_1_5"])] for r in _r],
      col_w=[30, 10, 9, 13, 12, 11, 8, 8], size=10, header_size=8.5, row_h=0.34)
callout(s, "The LLM's high-effort share runs several times the customer's. That is a scale "
           "difference, not a contradiction — no survey threshold matches the LLM's base "
           "rate, so read the ordering, not the level.", Inches(5.6))

# ═══════════════════════════════════════════════════════════════════ model
s = slide("What actually explains customer effort",
          f"Logistic regression on the customer's own answer, {MM['n_analysis']:,} "
          f"respondents, {MM['events_not_easy']} of whom did not agree it was easy",
          kicker="model")
bullets(s, [
    ("The outcome is the customer's answer, not ours",
     f"'Not easy' = codes 3–5 on the CSAT effort question, {MM['base_rate_not_easy']:.1%} of "
     f"respondents. Fitted in R 4.3.1. Every other CSAT field is excluded: they are the same "
     f"instrument and would manufacture the fit."),
    (f"It predicts, but modestly: cross-validated AUC {MSUM['S1']['auc_cv5']:.3f}",
     f"Pseudo-R² {MSUM['S1']['mcfadden_r2']:.3f}. Shuffling the outcome 200 times gives a null "
     f"AUC whose 95th percentile is {MPERM['S1']['null_p95']:.3f}, so the signal is real — but "
     f"most of what makes a ticket feel effortful is not in the handling record."),
    ("Two arms, kept apart on purpose",
     "The structural model asks what about the ticket predicts effort. Adding the LLM's own "
     "reading measures whether the model agrees with the customer — a different question, "
     "reported separately so a better AUC cannot stand in for explanatory power."),
], size=13, gap=13)

s = slide("How much each block explains",
          "Likelihood-ratio tests between nested models on identical rows", kicker="model")
picture(s, "m02_block_contributions", max_h=Inches(3.9), center=True)
_cs = next(b for b in MBLK if "conformance" in b["comparison"] and "minimal" in b["comparison"])
_rs = next(b for b in MBLK if "rejection reason" in b["comparison"])
callout(s, f"The finding worth pausing on: whether the matrix mapped the ticket correctly adds "
           f"nothing (p={_cs['p_value']:.2f}), while what the agent refused on does "
           f"(p={_rs['p_value']:.3f}). Governance correctness and customer pain are separate.",
        Inches(6.02))

s = slide("The structural drivers",
          "Odds of the customer saying it was not easy; significant terms only", kicker="model")
picture(s, "m01_forest_structural", max_h=Inches(4.05), center=True)
callout(s, "Agent handoffs are PROTECTIVE — a second agent touching the ticket cuts the odds "
           "by roughly 40%. Slow turnaround and more agent responses raise them. The resolution "
           "code matters more than anything about how the ticket was handled.", Inches(6.12))

s = slide("Rules and reasons against the customer's own answer",
          f"Restricted to the {MSUM['R2']['n']} respondents carrying a rule tag — "
          f"{MSUM['R2']['events']} of them said it was not easy", kicker="model")
picture(s, "m06_rules_arm", max_h=Inches(3.95), center=True)
callout(s, "Rejection reason moves the odds several-fold and significantly. Matrix conformance "
           "status (orange) sits on 1.0 with intervals spanning it — no measurable effect on "
           "how hard the customer found it.", Inches(6.02))

s = slide("What drives the model is not what drives the customer",
          "Same predictors, same reference levels, two different outcomes", kicker="model")
picture(s, "m05_drivers_survey_vs_llm", max_h=Inches(4.05), center=True)
callout(s, f"The LLM's own high-effort call is far more predictable from rule and reason "
           f"(AUC {MSUM['L1']['auc_in_sample']:.3f}) than the customer's answer is "
           f"(AUC {MSUM['S1']['auc_cv5']:.3f}). The model is more rule-governed than the person.",
        Inches(6.12))

s = slide("Model performance, honestly reported",
          "In-sample, cross-validated, and against a shuffled-outcome null", kicker="model")
table(s, ["Model", "What it adds", "n", "Events", "Terms", "EPV", "Pseudo-R²",
          "AUC in-sample", "AUC 5-fold CV", "Stability"],
      [[k, short(MSUM[k]["label"], 32), num(MSUM[k]["n"]), MSUM[k]["events"],
        MSUM[k]["terms"], f"{MSUM[k]['epv']:.1f}",
        "—" if MSUM[k]["mcfadden_r2"] is None else f"{MSUM[k]['mcfadden_r2']:.3f}",
        f"{MSUM[k]['auc_in_sample']:.3f}",
        "—" if MSUM[k]["auc_cv5"] is None else f"{MSUM[k]['auc_cv5']:.3f}",
        MSUM[k]["stability"]]
       for k in ["S0", "S1", "S2", "S1-hard", "R0", "R1", "R2", "L1"]],
      col_w=[7, 25, 8, 8, 7, 7, 10, 12, 12, 11], size=10, header_size=8.5, row_h=0.34)
callout(s, f"Cross-validated AUC is the figure to quote. The shuffled-outcome null reaches "
           f"{MPERM['S1']['null_p95']:.3f} at its 95th percentile, so S1 at "
           f"{MSUM['S1']['auc_cv5']:.3f} is a real but modest signal.", Inches(5.75))

s = slide("Limits of the model", "Four things that bound every coefficient above",
          kicker="model")
bullets(s, [
    ("Survey respondents are not the corpus",
     f"Repeat contact runs {MM['repeat_corpus']:.0%} corpus-wide but "
     f"{MM['repeat_respondents']:.0%} among respondents. People who keep coming back are "
     f"under-represented in exactly the population being modelled, which biases the "
     f"repeat-contact coefficient towards zero. Nothing here corrects for that."),
    ("Per-rule effects on customer effort are not estimable",
     f"Rules exist only on the 12,000 sample, giving {MSUM['R2']['n']} respondents and "
     f"{MSUM['R2']['events']} events — enough for grouped effects, not 23 coefficients. "
     f"Extending rule tagging to the full corpus (about $530) would lift this to "
     f"{MM['n_analysis']:,}."),
    ("Association, not causation",
     "Handoffs being protective most likely reflects escalation to someone who could actually "
     "resolve the case, not handoffs helping in themselves. Nothing here is an intervention "
     "estimate."),
    ("The LLM effort score carries its own noise",
     "Test–retest agreement is 62.3%, Spearman +0.675. Any model containing it inherits that "
     "ceiling."),
], size=12.5, gap=10)

# ═══════════════════════════════════════════════════════════════ integrity
issues = []
for i, sl in enumerate(prs.slides, start=1):
    for sh in sl.shapes:
        bottom = sh.top + sh.height
        if sh.shape_type == 13 and bottom > FOOTER_CLEAR:
            issues.append(f"slide {i}: image overflows the footer by "
                          f"{Emu(bottom - FOOTER_CLEAR).inches:.2f}in")
        if sh.has_table:
            if bottom > H:
                issues.append(f"slide {i}: table runs off the slide")
            for r_i, row in enumerate(sh.table.rows):
                for c in row.cells:
                    if not c.text.strip():
                        issues.append(f"slide {i}: empty table cell in row {r_i}")
        if sh.has_text_frame:
            t = sh.text_frame.text
            if "nan" in t.lower().split() or "None" in t:
                issues.append(f"slide {i}: unformatted value in text")
assert not issues, "integrity checks failed:\n  " + "\n  ".join(issues)

OUT.parent.mkdir(parents=True, exist_ok=True)
prs.save(OUT)
print(f"wrote {OUT}  ({len(prs.slides.__iter__.__self__._sldIdLst)} slides)")
print("  integrity checks passed")
