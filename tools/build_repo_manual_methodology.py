"""Repo manual and per-use-case methodology (Word, October 2026).

    & "C:\\Program Files\\Python311\\python.exe" scripts\\build_repo_manual_methodology.py

Reads runs/usecase_review/content.json (written from, and fact-checked against,
the read-only survey of this repo) and the figures from
scripts/build_usecase_review_figs.py. The table of contents is a Word field:
open the file and press F9 (or let Word update fields on open) to refresh it.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_BREAK, WD_PARAGRAPH_ALIGNMENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor
except ModuleNotFoundError:                                          # pragma: no cover
    sys.exit('Run with:  & "C:\\Program Files\\Python311\\python.exe" '
             'scripts\\build_repo_manual_methodology.py')

BASE = Path(__file__).resolve().parent.parent
SRC = BASE / "runs" / "usecase_review" / "content.json"
FIGS = BASE / "runs" / "usecase_review" / "figs"
OUT = BASE / "docs" / "RCA_Repo_Manual_and_Methodology_2026.docx"
C = json.loads(SRC.read_text(encoding="utf-8"))

NAVY = RGBColor(0x0B, 0x2A, 0x4A)
ORANGE = RGBColor(0xFF, 0x6C, 0x00)
GREY = RGBColor(0x7A, 0x87, 0x94)
INK = RGBColor(0x26, 0x32, 0x3F)
BODY_FONT, HEAD_FONT, MONO = "Calibri", "Segoe UI", "Consolas"
TEXT_W = Cm(17.0)          # A4 minus 2 x 2 cm margins

doc = Document()


# ───────────────────────────────────────────────────────────── styles
def _style_font(st, name, size, bold=None, color=None):
    st.font.name = name
    st.font.size = Pt(size)
    if bold is not None:
        st.font.bold = bold
    if color is not None:
        st.font.color.rgb = color
    rpr = st.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts"); rpr.append(rfonts)
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(a), name)


styles = doc.styles
_style_font(styles["Normal"], BODY_FONT, 10.5, color=INK)
styles["Normal"].paragraph_format.space_after = Pt(6)
styles["Normal"].paragraph_format.line_spacing = 1.12
for lvl, size, before, after in ((1, 20, 18, 8), (2, 15, 16, 6), (3, 12, 12, 4), (4, 11, 10, 3)):
    st = styles[f"Heading {lvl}"]
    _style_font(st, HEAD_FONT, size, bold=True, color=NAVY if lvl != 4 else INK)
    st.paragraph_format.space_before = Pt(before)
    st.paragraph_format.space_after = Pt(after)
    st.paragraph_format.keep_with_next = True
_style_font(styles["List Bullet"], BODY_FONT, 10.5, color=INK)
styles["List Bullet"].paragraph_format.space_after = Pt(3)
_style_font(styles["Title"], HEAD_FONT, 30, bold=True, color=NAVY)

code_st = styles.add_style("Code Block", 1)
code_st.base_style = styles["Normal"]
_style_font(code_st, MONO, 8.5, color=INK)
code_st.paragraph_format.space_after = Pt(0)
code_st.paragraph_format.line_spacing = 1.0
code_st.paragraph_format.left_indent = Cm(0.3)

step_st = styles.add_style("Step", 1)
step_st.base_style = styles["Normal"]
step_st.paragraph_format.left_indent = Cm(0.75)
step_st.paragraph_format.first_line_indent = Cm(-0.75)
step_st.paragraph_format.space_after = Pt(3)
step_st.paragraph_format.tab_stops.add_tab_stop(Cm(0.75))

sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
sec.left_margin = sec.right_margin = Cm(2.0)
sec.top_margin, sec.bottom_margin = Cm(2.0), Cm(1.8)


# ───────────────────────────────────────────────────────────── helpers
_INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`)")


def runs(p, text, size=None, color=None, bold=False, italic=False):
    """Add text to a paragraph, honouring **bold** and `code` spans."""
    for part in _INLINE.split(str(text)):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            r = p.add_run(part[2:-2]); r.bold = True
        elif part.startswith("`") and part.endswith("`"):
            r = p.add_run(part[1:-1]); r.font.name = MONO
            r._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:hAnsi"), MONO)
            r.font.size = Pt((size or 10.5) - 1)
        else:
            r = p.add_run(part)
            if bold:
                r.bold = True
        if italic:
            r.italic = True
        if size:
            r.font.size = Pt(size)
        if color is not None:
            r.font.color.rgb = color
    return p


def para(text, style=None, **kw):
    p = doc.add_paragraph(style=style)
    return runs(p, text, **kw)


def shade(el, hex_fill):
    pr = el.get_or_add_tcPr() if el.tag.endswith("tc") else el.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), hex_fill)
    pr.append(shd)


def bullets(items):
    for it in items:
        if str(it).strip():
            para(it, style="List Bullet")


def steps(items):
    for i, it in enumerate([x for x in items if str(x).strip()], start=1):
        p = doc.add_paragraph(style="Step")
        r = p.add_run(f"{i}.\t"); r.bold = True; r.font.color.rgb = ORANGE
        runs(p, re.sub(r"^\s*(step\s*)?\d+[.)]\s*", "", str(it), flags=re.I))


def code(lines):
    lines = [str(x) for x in lines if str(x).strip()]
    if not lines:
        return
    for ln in lines:
        for sub in ln.split("\n"):
            p = doc.add_paragraph(style="Code Block")
            p.add_run(sub)
            shade(p._p, "F2F4F7")
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def table(headers, rows, widths=None, size=9):
    rows = [r + [""] * (len(headers) - len(r)) for r in rows]
    t = doc.add_table(rows=1 + len(rows), cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    if widths is None:
        # size columns by their typical text length, clamped so no column starves
        widths = []
        for j in range(len(headers)):
            cells = [str(r[j]) for r in rows if j < len(r)] + [str(headers[j])]
            avg = sum(min(len(c), 120) for c in cells) / len(cells)
            widths.append(max(4.0, min(avg, 60.0)))
    tot = sum(widths)
    for j, h in enumerate(headers):
        c = t.cell(0, j)
        c.text = ""
        runs(c.paragraphs[0], h, size=size, color=RGBColor(0xFF, 0xFF, 0xFF), bold=True)
        shade(c._tc, "0B2A4A")
    trpr = t.rows[0]._tr.get_or_add_trPr()
    hdr = OxmlElement("w:tblHeader"); hdr.set(qn("w:val"), "true"); trpr.append(hdr)
    for i, r in enumerate(rows, start=1):
        for j, v in enumerate(r[:len(headers)]):
            c = t.cell(i, j)
            c.text = ""
            runs(c.paragraphs[0], v, size=size, bold=(j == 0 and len(headers) == 2))
            if i % 2 == 0:
                shade(c._tc, "EEF1F4")
    for row in t.rows:
        for j, c in enumerate(row.cells):
            c.width = int(TEXT_W * widths[j] / tot)
            for p in c.paragraphs:
                p.paragraph_format.space_after = Pt(1)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def section_block(sec, level=3):
    """Render one content section: heading, paragraphs, bullets, steps, table, code."""
    if sec.get("heading"):
        doc.add_heading(sec["heading"], level=level)
    for t in sec.get("paragraphs") or []:
        para(t)
    steps(sec.get("steps") or [])
    tb = sec.get("table")
    if tb and tb.get("headers") and tb.get("rows"):
        n = len(tb["headers"])
        widths = [3, 9] if n == 2 else None
        if n == 6 and tb["headers"][0].strip() == "#":
            widths = [0.6, 3, 2, 3.2, 3, 4]
        table(tb["headers"], tb["rows"], widths=widths)
    bullets(sec.get("bullets") or [])
    code(sec.get("code") or [])


def figure(name, caption, width=Cm(16.5)):
    path = FIGS / name
    if not path.exists():
        return
    doc.add_picture(str(path), width=width)
    doc.paragraphs[-1].alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    p = para(caption, size=9, color=GREY, italic=True)
    p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER


def field(p, instr, placeholder=""):
    r = p.add_run()
    b = OxmlElement("w:fldChar"); b.set(qn("w:fldCharType"), "begin"); r._r.append(b)
    r = p.add_run()
    it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve"); it.text = instr
    r._r.append(it)
    r = p.add_run()
    s_ = OxmlElement("w:fldChar"); s_.set(qn("w:fldCharType"), "separate"); r._r.append(s_)
    p.add_run(placeholder)
    r = p.add_run()
    e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), "end"); r._r.append(e)


def page_break():
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


# ───────────────────────────────────────────────────────────── footer
fp = sec.footer.paragraphs[0]
fp.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
runs(fp, "RCA Pipeline · Repo Manual & Use-Case Methodology · October 2026 · page ", size=8, color=GREY)
field(fp, "PAGE", "1")
for r in fp.runs:
    r.font.size = Pt(8); r.font.color.rgb = GREY

# ───────────────────────────────────────────────────────────── cover
for _ in range(5):
    doc.add_paragraph()
para("RCA PIPELINE · CUSTOM TAXONOMY", size=12, color=ORANGE, bold=True)
t = doc.add_paragraph(style="Title")
t.add_run("Repo Manual & Use-Case Methodology")
para("How to run the repository, and how the 18 use cases from March to September 2026 "
     "(17 delivered, 1 proposal) were built, evaluated and can be reproduced.", size=14, color=GREY)
doc.add_paragraph()
para("Version 1.0 · October 2026 · Draft for review", size=11, color=NAVY, bold=True)
para("Companion to docs/RCA_UseCase_Review_2026.pptx. Supplements, and does not replace, "
     "docs/RCA_Pipeline_Manual_v3.docx and docs/RCA_Pipeline_Methodology_v3.docx (May 2026), "
     "which remain the reference for the generic 19-module engine.", size=10, color=GREY)
page_break()

doc.add_heading("Document control", level=1)
table(["Item", "Detail"], [
    ["Title", "RCA Pipeline: Repo Manual & Use-Case Methodology"],
    ["Version / date", "1.0 · 1 October 2026"],
    ["Status", "Draft for review"],
    ["Scope", "Repository custom_taxonomy_v1: notebooks 00–19, eda and gold_set_evaluation, scripts/, "
              "rca_pipeline/, run_pipeline.py, build_pipeline.py, profiles/, definitions/, runs/ artefacts"],
    ["Companion", "docs/RCA_UseCase_Review_2026.pptx (use-case review and streamlining proposal)"],
    ["Related", "docs/RCA_Pipeline_Manual_v3.docx and docs/RCA_Pipeline_Methodology_v3.docx (generic engine, "
                "May 2026); docs/ARCHITECTURE.md; docs/IMPROVEMENT_SPEC.md; docs/NOTEBOOKS.md"],
    ["How facts were sourced", "Read-only review of the repository with per-record adversarial fact-checking "
                               "(see Appendix C). Costs are CostTracker list-price estimates, not billed spend."],
], widths=[3.5, 13])

doc.add_heading("Contents", level=1)
field(doc.add_paragraph(), 'TOC \\o "1-2" \\h \\z \\u',
      "Right-click and choose Update Field (or press F9) to build the table of contents.")
page_break()

# ───────────────────────────────────────────────────────────── Part I
doc.add_heading("Part I — Overview", level=1)
for s_ in C["doc_overview"]["sections"]:
    section_block(s_, level=2)
    h = s_.get("heading", "").lower()
    if "skeleton" in h:
        figure("fig_skeleton.png", "Figure 1. The shared skeleton and the spend ladder.")
    if h.startswith("timeline"):
        figure("fig_timeline.png", "Figure 2. Portfolio timeline, March–September 2026, by family.")
page_break()

# ───────────────────────────────────────────────────────────── Part II
doc.add_heading("Part II — Repo manual", level=1)
para("This part explains how to set up, build, run and troubleshoot the repository as it is used today. "
     "Where behaviour differs from the v3 Manual (May 2026), this part takes precedence.")
for i, ch in enumerate(C["manual"]["chapters"], start=1):
    title = re.sub(r"^M?\d+\s*[·.:-]?\s*", "", ch["title"]).strip()
    doc.add_heading(f"M{i}. {title}", level=2)
    if ch.get("intro"):
        para(ch["intro"])
    for s_ in ch.get("sections", []):
        section_block(s_, level=3)
page_break()

# ───────────────────────────────────────────────────────────── Part III
doc.add_heading("Part III — Use-case methodology", level=1)
para("One chapter per use case, grouped by family. Every chapter follows the same eleven headings, so "
     "chapters can be compared side by side. 'Evaluation tier' uses the ladder defined in chapter M10 "
     "and Part V: A held-out gold · B SME spot review · C proxy agreement (CRM codes, survey, "
     "test-retest; never called accuracy) · D exploratory, no measure.")
DOC_BY_ID = {u["id"]: u for u in C["doc_ucs"]}
for f in C["families"]:
    fk = f["key"]
    nm = re.sub(r"^[A-E]\.\s*", "", f["name"])
    doc.add_heading(f"Family {fk} — {nm}", level=2)
    para(f["pattern"])
    para("What works", bold=True, color=NAVY)
    bullets(f["pros"])
    para("What hurts", bold=True, color=NAVY)
    bullets(f["cons"])
    for u in [u for u in C["deck_ucs"] if u["id"] in f["ids"] or u["id"].startswith(f"UC-{fk}")]:
        d = DOC_BY_ID.get(u["id"])
        if not d:
            continue
        title = re.sub(r"^UC-[A-E]\d+\s*[·:.-]?\s*", "", d["title"]).strip()
        doc.add_heading(f"{u['id'].split('-')[1]} · {title}", level=2)
        para(d["summary"], italic=True, color=GREY)
        for s_ in d["sections"]:
            section_block(s_, level=3)
page_break()

# ───────────────────────────────────────────────────────────── Part IV
doc.add_heading("Part IV — Capabilities reference", level=1)
para("Reusable building blocks that already exist in the repository, what they do, where they live and "
     "which use cases rely on them.")
for cap in C["capabilities"]:
    doc.add_heading(cap["name"], level=2)
    for lab, key in (("What it does", "what"), ("Where it lives", "where"),
                     ("Used by", "used_by"), ("Notes", "notes")):
        if cap.get(key):
            p = doc.add_paragraph()
            r = p.add_run(f"{lab}: "); r.bold = True; r.font.color.rgb = NAVY
            runs(p, cap[key])
page_break()

# ───────────────────────────────────────────────────────────── Part V
doc.add_heading("Part V — Generalising and streamlining the pipeline", level=1)
p5 = C["doc_part5"]
if p5.get("intro"):
    para(p5["intro"])
for s_ in p5["sections"]:
    section_block(s_, level=2)
page_break()

# ───────────────────────────────────────────────────────────── appendices
doc.add_heading("Appendix A — Glossary", level=1)
table(["Term", "Meaning"], [[g["term"], g["definition"]] for g in C["glossary"]], widths=[3.5, 13])

doc.add_heading("Appendix B — Artefact index", level=1)
para("Key files per use case. Paths are relative to the repository root; runs/ and data/ are gitignored "
     "and exist only on the analyst's machine.")
for u in C["catalogue_artefacts"]:
    doc.add_heading(f"{u['id'].split('-')[1]} · {u['title']}", level=3)
    bullets(u["artefacts"])

doc.add_heading("Appendix C — How this document was produced", level=1)
bullets(C["appendix"]["method"])

OUT.parent.mkdir(parents=True, exist_ok=True)
doc.save(OUT)
print(f"wrote {OUT}")
