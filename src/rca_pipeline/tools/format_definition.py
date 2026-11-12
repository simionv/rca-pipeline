"""
format_definition.py – make a pipeline definition workbook easy to edit
========================================================================
Adds guidance and guard-rails to a definition .xlsx WITHOUT changing any cell
value in the modules / fields / taxonomy sheets (so the build output is
unchanged):

  * a "Start here" sheet: what the workbook does, what to edit, how to rebuild,
    and a summary of the modules in this workbook
  * header notes explaining every column in plain language
  * header colours:  green = edit freely,  yellow = advanced,  grey = linking names
  * dropdowns for TRUE/FALSE, L1/L2 and field types; module_name must match the
    modules sheet
  * taxonomy: L1 (group) rows shaded, L2 rows with no description flagged amber
  * a "Change log" sheet

Safe to run more than once.

usage:  python -m rca_pipeline.tools.format_definition definitions/*.xlsx
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

GREEN, YELLOW, GREY = "C6EFCE", "FFEB9C", "D9D9D9"
L1_FILL, AMBER = "DDEBF7", "FCE4D6"
FIELD_TYPES = "code, str, bool, int, float, list, enum:value1,value2,..."

# (colour, plain-language note) for every column the build understands
COLUMNS: dict[str, dict[str, tuple[str, str]]] = {
    "modules": {
        "module_name": (GREY, "Short name of this classification step, e.g. contact_reason. Letters, numbers and _ only. "
                              "The fields and taxonomy sheets refer to it, so rename it there too."),
        "taxonomy_prefix": (YELLOW, "Letters used to build category codes, e.g. CR gives CR1, CR1.1 ... "
                                    "Leave empty if this step has no category list."),
        "taxonomy_file": (GREY, "File name the category list is saved under, e.g. contact_reason.json. "
                                "Leave empty if this step has no category list."),
        "reorder_group": (YELLOW, "Optional. Groups output columns together in the result file."),
        "reorder_order": (YELLOW, "Optional. Order of this group in the result file (1 = first)."),
        "enabled": (GREEN, "TRUE to run this step, FALSE to switch it off without deleting it."),
        "description": (GREEN, "What this step should do, in plain words. It is given to the AI as its task."),
        "discovery_mode": (YELLOW, "Optional. 'full' or 'extract_only' lets `rca discover` draft categories from data."),
        "extract_prompt": (YELLOW, "Optional. Extra instruction used only by `rca discover`."),
        "notes": (GREEN, "Free notes for people. Not used by the pipeline."),
    },
    "fields": {
        "module_name": (GREY, "Which step (from the modules sheet) this output column belongs to."),
        "field_name": (GREY, "Name of the output column, e.g. cr_code. Letters, numbers and _ only."),
        "field_type": (YELLOW, f"Kind of answer. One of: {FIELD_TYPES}. "
                               "'code' = a category from the taxonomy sheet; 'enum:' = one of the listed values."),
        "description": (GREEN, "Short explanation of the column for people reading the results."),
        "prompt_instruction": (GREEN, "The exact instruction the AI follows to fill this column. "
                                      "This has the biggest effect on accuracy — be specific and give examples."),
        "in_output": (YELLOW, "TRUE to keep this column in the result file, FALSE to hide it."),
        "explode_list": (YELLOW, "For list answers: TRUE splits the list into columns _1, _2, _3."),
        "validate_enum": (YELLOW, "For enum answers: TRUE blanks any value that is not in the allowed list."),
        "explode_keys": (YELLOW, "Advanced. For lists of objects: the keys of each item, e.g. code, verdict."),
        "notes": (GREEN, "Free notes for people. Not used by the pipeline."),
    },
    "taxonomy": {
        "module_name": (GREY, "Which step (from the modules sheet) this category belongs to."),
        "level": (GREEN, "L1 = a group heading. L2 = a category inside the group above it."),
        "label": (GREEN, "Category name, e.g. 'Password reset'."),
        "description": (GREEN, "When to use this category (and when not). Good L2 descriptions are the single "
                               "best way to improve accuracy."),
        "code": (YELLOW, "Normally leave EMPTY — codes are numbered automatically by row order. "
                         "Fill only to force a fixed code."),
        "notes": (GREEN, "Free notes for people. Not used by the pipeline."),
    },
}
WIDE = {"description": 60, "prompt_instruction": 80, "label": 40, "notes": 40, "extract_prompt": 50}

START_HERE = [
    ("Start here", "title"),
    ("This workbook defines one analysis: which questions the AI answers about each support "
     "ticket, and which categories it can choose from. Nothing here is code.", ""),
    ("", ""),
    ("The three sheets", "head"),
    ("modules — one row per classification step (for example 'contact reason').", ""),
    ("fields — one row per output column a step produces, with the instruction the AI follows.", ""),
    ("taxonomy — the category list for each step: L1 rows are groups, L2 rows are the categories inside them.", ""),
    ("", ""),
    ("Header colours", "head"),
    ("GREEN — edit freely: descriptions, instructions, category names, notes, on/off switches.", "green"),
    ("YELLOW — advanced: change only if you know what it does (hover over the header for help).", "yellow"),
    ("GREY — linking names: they connect the sheets. If you rename one, rename it everywhere.", "grey"),
    ("Hover over any column header to see what it means.", ""),
    ("", ""),
    ("Common tasks", "head"),
    ("Add a category: on the taxonomy sheet insert an L2 row under the right L1 group; fill label and description.", ""),
    ("Improve accuracy: sharpen L2 descriptions (when to use / when not to) and the prompt_instruction column.", ""),
    ("Switch a step off: set enabled to FALSE on the modules sheet.", ""),
    ("Never type codes — they are numbered automatically from the row order.", ""),
    ("Record every change on the 'Change log' sheet.", ""),
    ("", ""),
    ("After editing", "head"),
    ("Save and close the workbook, then in the use-case folder run:", ""),
    ("    rca validate      (checks the workbook and explains any problem in plain words)", "mono"),
    ("    rca build         (turns the workbook into the files the pipeline runs)", "mono"),
    ("", ""),
    ("Modules in this workbook", "head"),
]


def _style_header(ws, sheet: str) -> dict[str, int]:
    cols = {}
    for cell in ws[1]:
        name = str(cell.value or "").strip()
        if not name:
            continue
        cols[name] = cell.column
        colour, note = COLUMNS[sheet].get(name, (GREEN, ""))
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor=colour)
        cell.alignment = Alignment(vertical="top", wrap_text=True)
        if note:
            c = Comment(note, "rca-pipeline")
            c.width, c.height = 320, 140
            cell.comment = c
        ws.column_dimensions[cell.column_letter].width = WIDE.get(name, max(14, len(name) + 4))
        if name in WIDE:
            for row in ws.iter_rows(min_row=2, min_col=cell.column, max_col=cell.column):
                row[0].alignment = Alignment(vertical="top", wrap_text=True)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    return cols


def _add_validation(ws, col: int, dv: DataValidation) -> None:
    letter = get_column_letter(col)
    dv.add(f"{letter}2:{letter}5000")
    ws.add_data_validation(dv)


def _bool_dv() -> DataValidation:
    return DataValidation(type="list", formula1='"TRUE,FALSE"', allow_blank=True, showErrorMessage=True,
                          errorTitle="TRUE or FALSE", error="Please choose TRUE or FALSE.")


def format_workbook(path: Path) -> None:
    wb = load_workbook(path)
    for sheet in ("modules", "fields", "taxonomy"):
        if sheet not in wb.sheetnames:
            raise SystemExit(f"{path}: missing sheet '{sheet}'")
    for sheet in ("modules", "fields", "taxonomy"):
        wb[sheet].data_validations.dataValidation = []
        wb[sheet].conditional_formatting = type(wb[sheet].conditional_formatting)()

    n_modules = max(2, wb["modules"].max_row)
    module_list = f"modules!$A$2:$A${n_modules + 50}"

    for sheet in ("modules", "fields", "taxonomy"):
        ws = wb[sheet]
        cols = _style_header(ws, sheet)
        for name in ("enabled", "in_output", "explode_list", "validate_enum"):
            if name in cols:
                _add_validation(ws, cols[name], _bool_dv())
        if sheet != "modules" and "module_name" in cols:
            _add_validation(ws, cols["module_name"], DataValidation(
                type="list", formula1=module_list, allow_blank=True, showErrorMessage=True, errorStyle="warning",
                errorTitle="Unknown module", error="This name is not on the modules sheet. Check the spelling."))
        if sheet == "fields" and "field_type" in cols:
            ref = f"{get_column_letter(cols['field_type'])}2"
            formula = (f'OR({ref}="code",{ref}="str",{ref}="bool",{ref}="int",{ref}="float",{ref}="list",'
                       f'LEFT({ref},5)="enum:")')
            _add_validation(ws, cols["field_type"], DataValidation(
                type="custom", formula1=formula, allow_blank=True, showErrorMessage=True,
                errorTitle="Field type", error=f"Use one of: {FIELD_TYPES}"))
        if sheet == "taxonomy" and "level" in cols:
            _add_validation(ws, cols["level"], DataValidation(
                type="list", formula1='"L1,L2"', allow_blank=True, showErrorMessage=True,
                errorTitle="Level", error="Use L1 for a group or L2 for a category inside it."))
            lv = get_column_letter(cols["level"])
            last = get_column_letter(ws.max_column)
            ws.conditional_formatting.add(f"A2:{last}5000", FormulaRule(
                formula=[f'${lv}2="L1"'], fill=PatternFill("solid", fgColor=L1_FILL), font=Font(bold=True)))
            if "description" in cols:
                d = get_column_letter(cols["description"])
                ws.conditional_formatting.add(f"{d}2:{d}5000", FormulaRule(
                    formula=[f'AND(${lv}2="L2",LEN(TRIM(${d}2))=0)'], fill=PatternFill("solid", fgColor=AMBER)))

    _write_start_here(wb)
    _ensure_change_log(wb)
    wb.save(path)


def _write_start_here(wb) -> None:
    if "Start here" in wb.sheetnames:
        del wb["Start here"]
    ws = wb.create_sheet("Start here", 0)
    ws.column_dimensions["A"].width = 120
    fills = {"green": GREEN, "yellow": YELLOW, "grey": GREY}
    for i, (text, kind) in enumerate(START_HERE, start=1):
        c = ws.cell(row=i, column=1, value=text)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        if kind == "title":
            c.font = Font(bold=True, size=16)
        elif kind == "head":
            c.font = Font(bold=True, size=12)
        elif kind == "mono":
            c.font = Font(name="Courier New")
        elif kind in fills:
            c.fill = PatternFill("solid", fgColor=fills[kind])

    mods, fields, tax = (wb[s] for s in ("modules", "fields", "taxonomy"))
    hdr = {s: [str(c.value or "") for c in wb[s][1]] for s in ("modules", "fields", "taxonomy")}

    def rows(ws, s):
        for r in ws.iter_rows(min_row=2, values_only=True):
            yield dict(zip(hdr[s], r))

    n_fields, n_cats = {}, {}
    for r in rows(fields, "fields"):
        n_fields[r.get("module_name")] = n_fields.get(r.get("module_name"), 0) + 1
    for r in rows(tax, "taxonomy"):
        if str(r.get("level", "")).upper() == "L2":
            n_cats[r.get("module_name")] = n_cats.get(r.get("module_name"), 0) + 1

    start = len(START_HERE) + 1
    table = ["module", "on?", "output columns", "categories", "what it does"]
    for j, h in enumerate(table, start=1):
        ws.cell(row=start, column=j, value=h).font = Font(bold=True)
    for k, r in enumerate(rows(mods, "modules"), start=1):
        name = r.get("module_name")
        if not name:
            continue
        vals = [name, "yes" if str(r.get("enabled", "TRUE")).upper() in ("TRUE", "1", "1.0") else "no",
                n_fields.get(name, 0), n_cats.get(name, 0), r.get("description") or ""]
        for j, v in enumerate(vals, start=1):
            ws.cell(row=start + k, column=j, value=v).alignment = Alignment(wrap_text=True, vertical="top")
    for letter, w in zip("BCDE", (6, 14, 12, 90)):
        ws.column_dimensions[letter].width = w
    ws.column_dimensions["A"].width = 120 if ws.max_row <= len(START_HERE) else 32
    for i in range(1, len(START_HERE) + 1):
        ws.merge_cells(start_row=i, start_column=1, end_row=i, end_column=5)
    wb.active = 0


def _ensure_change_log(wb) -> None:
    if "Change log" in wb.sheetnames:
        return
    ws = wb.create_sheet("Change log")
    for j, (h, w) in enumerate([("date", 12), ("who", 18), ("sheet", 12), ("what changed", 60), ("why", 60)], 1):
        c = ws.cell(row=1, column=j, value=h)
        c.font, c.fill = Font(bold=True), PatternFill("solid", fgColor=GREEN)
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.append([date.today().isoformat(), "rca-pipeline", "all",
               "Added Start here sheet, column help, colours and dropdowns. No content changed.",
               "Make the workbook easier to maintain."])
    ws.freeze_panes = "A2"


def main(argv: list[str] | None = None) -> None:
    paths = [Path(p) for p in (sys.argv[1:] if argv is None else argv)]
    if not paths:
        raise SystemExit(__doc__)
    for p in paths:
        format_workbook(p)
        print(f"formatted {p}")


if __name__ == "__main__":
    main()
