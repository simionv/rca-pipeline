"""
validate.py – check a definition workbook and explain problems in plain words
==============================================================================
    rca validate [--input definitions/<file>.xlsx]

Problems are reported with the sheet and Excel row number:
  ERROR    the build would fail or produce wrong results — fix before building
  WARNING  works, but likely to hurt accuracy or confuse people
Profiles in profiles/ are also checked against the workbook.
Exit code is 1 when there are errors.  `rca build` runs this check first.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

REQUIRED = {
    "modules": ["module_name", "enabled", "description"],
    "fields": ["module_name", "field_name", "field_type", "prompt_instruction"],
    "taxonomy": ["module_name", "level", "label"],
}
BOOL_COLS = {"modules": ["enabled"], "fields": ["in_output", "explode_list", "validate_enum"]}
BOOL_OK = {"TRUE", "FALSE", "1", "0", "1.0", "0.0"}
SIMPLE_TYPES = {"code", "str", "bool", "int", "float", "list"}
NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _text(v) -> str:
    return "" if pd.isna(v) else str(v).strip()


NOTE_PREFIXES = ("Green", "Edit", "L1", "L2", "level", "module_name")  # same rule as build._clean_df
KEY_COLUMN = {"modules": "enabled", "fields": "field_name", "taxonomy": "level"}


def _rows(df: pd.DataFrame, sheet: str):
    """(excel_row, row) for every data row, skipping blank rows and guidance notes."""
    key = KEY_COLUMN[sheet]
    for i, row in df.iterrows():
        first = _text(row.iloc[0])
        if not first or first.startswith(NOTE_PREFIXES):
            continue
        if " " in first and key in df.columns and not _text(row[key]):
            continue  # a sentence typed into the first column, e.g. editing tips
        yield i + 2, row


def check_definition(path: Path) -> tuple[list[str], list[str], dict]:
    errors: list[str] = []
    warnings: list[str] = []
    if not path.exists():
        return [f"File not found: {path}"], [], {}
    try:
        sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
    except Exception as exc:  # unreadable / open in Excel with a lock
        return [f"Cannot open {path.name}: {exc}. Is it still open in Excel?"], [], {}

    for sheet, cols in REQUIRED.items():
        if sheet not in sheets:
            errors.append(f"The workbook has no '{sheet}' sheet. It needs sheets called modules, fields and taxonomy.")
            continue
        missing = [c for c in cols if c not in sheets[sheet].columns]
        if missing:
            errors.append(f"Sheet '{sheet}' is missing the column(s): {', '.join(missing)}. Check the header row (row 1).")
    if errors:
        return errors, warnings, {}

    mods, fields, tax = sheets["modules"], sheets["fields"], sheets["taxonomy"]

    # ---- modules
    modules: dict[str, dict] = {}
    for r, row in _rows(mods, "modules"):
        name = _text(row["module_name"])
        where = f"modules, row {r}"
        if not NAME_RE.match(name):
            errors.append(f"{where}: module name '{name}' may only use letters, numbers and _ (no spaces).")
        if name in modules:
            errors.append(f"{where}: module '{name}' is listed twice (also row {modules[name]['row']}).")
        enabled = _text(row["enabled"]).upper() or "TRUE"
        prefix = _text(row.get("taxonomy_prefix", ""))
        tfile = _text(row.get("taxonomy_file", ""))
        if bool(prefix) != bool(tfile):
            errors.append(f"{where}: '{name}' has a taxonomy_prefix or a taxonomy_file but not both. "
                          "Fill both (it uses a category list) or leave both empty.")
        if not _text(row["description"]) and enabled in ("TRUE", "1", "1.0"):
            warnings.append(f"{where}: '{name}' has no description. The description is the AI's task — add one.")
        modules[name] = {"row": r, "enabled": enabled in ("TRUE", "1", "1.0"), "has_taxonomy": bool(prefix),
                         "taxonomy_file": tfile}

    for sheet, cols in BOOL_COLS.items():
        df = sheets[sheet]
        for col in cols:
            if col not in df.columns:
                continue
            for r, row in _rows(df, sheet):
                v = _text(row[col]).upper()
                if v and v not in BOOL_OK:
                    warnings.append(f"{sheet}, row {r}: column {col} should be TRUE or FALSE, not '{row[col]}'. "
                                    "The default will be used.")

    # ---- fields
    seen_fields: dict[str, int] = {}
    code_fields: dict[str, int] = {}
    for r, row in _rows(fields, "fields"):
        where = f"fields, row {r}"
        mod, fname, ftype = _text(row["module_name"]), _text(row["field_name"]), _text(row["field_type"]).lower()
        if mod not in modules:
            errors.append(f"{where}: module '{mod}' is not on the modules sheet. Check the spelling.")
            continue
        if not NAME_RE.match(fname):
            errors.append(f"{where}: field name '{fname}' may only use letters, numbers and _ (no spaces).")
        if fname in seen_fields:
            warnings.append(f"{where}: field '{fname}' is used twice (also row {seen_fields[fname]}). "
                            "Both write to the same output column, so one overwrites the other.")
        seen_fields[fname] = r
        if ftype.startswith("enum:"):
            opts = [o.strip() for o in ftype[5:].split(",") if o.strip()]
            if len(opts) < 2:
                errors.append(f"{where}: '{fname}' is an enum with fewer than two values. "
                              "Write it like enum:yes,no,unclear")
        elif ftype not in SIMPLE_TYPES:
            warnings.append(f"{where}: field type '{row['field_type']}' is not recognised, so it is treated as "
                            "free text. Use code, str, bool, int, float, list or enum:value1,value2")
        if ftype == "code":
            code_fields[mod] = code_fields.get(mod, 0) + 1
            if not modules[mod]["has_taxonomy"]:
                errors.append(f"{where}: '{fname}' is a code field, but module '{mod}' has no category list "
                              "(no taxonomy_prefix / taxonomy_file on the modules sheet).")
        if not _text(row["prompt_instruction"]):
            warnings.append(f"{where}: '{fname}' has no prompt_instruction. The AI will have to guess what to write.")

    # ---- taxonomy
    tax_rows: dict[str, list[tuple[int, str, str, str]]] = {}
    for r, row in _rows(tax, "taxonomy"):
        mod = _text(row["module_name"])
        if mod not in modules:
            errors.append(f"taxonomy, row {r}: module '{mod}' is not on the modules sheet. Check the spelling.")
            continue
        level = _text(row["level"]).upper()
        if level not in ("L1", "L2"):
            errors.append(f"taxonomy, row {r}: level must be L1 (group) or L2 (category), not '{row['level']}'.")
            continue
        tax_rows.setdefault(mod, []).append((r, level, _text(row["label"]), _text(row.get("description", ""))))

    for mod, rows in tax_rows.items():
        if not modules[mod]["has_taxonomy"]:
            warnings.append(f"taxonomy: module '{mod}' has categories but no taxonomy_prefix / taxonomy_file "
                            f"on the modules sheet (row {modules[mod]['row']}), so they are ignored.")
        if rows[0][1] != "L1":
            errors.append(f"taxonomy, row {rows[0][0]}: the first category of '{mod}' is L2. "
                          "Start with an L1 group row above it.")
        labels: dict[str, int] = {}
        l1_row, l1_label, l1_children = None, "", 0
        for r, level, label, desc in rows + [(None, "L1", "", "")]:
            if level == "L1":
                if l1_row is not None and l1_children == 0:
                    warnings.append(f"taxonomy, row {l1_row}: group '{l1_label}' ({mod}) has no L2 categories under it.")
                l1_row, l1_label, l1_children = r, label, 0
                continue
            l1_children += 1
            if not label:
                errors.append(f"taxonomy, row {r}: an L2 row of '{mod}' has no label.")
            if not desc:
                warnings.append(f"taxonomy, row {r}: L2 '{label}' ({mod}) has no description — "
                                "add one to improve accuracy.")
            key = label.lower()
            if key in labels:
                warnings.append(f"taxonomy, row {r}: '{label}' appears twice in '{mod}' (also row {labels[key]}).")
            labels[key] = r

    files_built_here = {modules[m]["taxonomy_file"] for m in tax_rows}
    for mod, info in modules.items():
        if info["enabled"] and info["has_taxonomy"] and mod not in tax_rows:
            tfile = info["taxonomy_file"]
            if tfile not in files_built_here and not (Path("generated/taxonomies") / tfile).exists():
                warnings.append(f"modules, row {info['row']}: '{mod}' uses the category list {tfile}, but the "
                                "taxonomy sheet has no rows for it and the file is not in generated/taxonomies.")
        if info["enabled"] and info["has_taxonomy"] and not code_fields.get(mod):
            warnings.append(f"modules, row {info['row']}: '{mod}' has a category list but no field of type 'code' "
                            "on the fields sheet, so no category will be assigned.")
    return errors, warnings, modules


def check_profiles(profile_dir: Path, modules: dict) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    enabled = {m for m, i in modules.items() if i["enabled"]}
    for prof in sorted(profile_dir.glob("*.json")):
        try:
            cfg = json.loads(prof.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"profile {prof.name}: not valid JSON ({exc.msg}, line {exc.lineno}).")
            continue
        unknown = [m for m in cfg.get("modules") or [] if m not in enabled]
        if unknown:
            warnings.append(f"profile {prof.name}: module(s) {', '.join(unknown)} are not enabled in the "
                            "definition, so this profile cannot run as-is.")
        inp = cfg.get("input")
        if inp and not Path(inp).exists():
            warnings.append(f"profile {prof.name}: input file '{inp}' not found "
                            "(fine if another step creates it first).")
    return errors, warnings


def default_definition() -> Path | None:
    files = sorted(p for p in Path("definitions").glob("*.xlsx") if not p.name.startswith("~$"))
    return files[0] if len(files) == 1 else None


def run(path: Path, quiet_ok: bool = False) -> bool:
    errors, warnings, modules = check_definition(path)
    if not errors and Path("profiles").is_dir():
        e2, w2 = check_profiles(Path("profiles"), modules)
        errors += e2
        warnings += w2
    for e in errors:
        print(f"ERROR    {e}")
    for w in warnings:
        print(f"WARNING  {w}")
    if errors:
        print(f"\n{path.name}: {len(errors)} error(s), {len(warnings)} warning(s). Fix the errors, save, and run again.")
    elif not quiet_ok or warnings:
        print(f"\n{path.name}: OK — no errors, {len(warnings)} warning(s).")
    return not errors


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="rca validate", description="Check a definition workbook.")
    p.add_argument("--input", "-i", default=None, help="Definition Excel (default: the only .xlsx in definitions/)")
    args = p.parse_args(argv)
    path = Path(args.input) if args.input else default_definition()
    if path is None:
        p.error("which definition? pass --input definitions/<file>.xlsx")
    sys.exit(0 if run(path) else 1)


if __name__ == "__main__":
    main()
