"""
convert_taxonomy.py – Taxonomy Spreadsheet → JSON Converter
==============================================================
Reads a taxonomy from an Excel or CSV file and generates the JSON
taxonomy files expected by the pipeline.

INPUT FORMAT (spreadsheet):
  The spreadsheet must have these columns (names are flexible):
    - Group column:         L1 category name (e.g., "Signing in & authentication")
    - Sub-category column:  Leaf item name (e.g., "Login blocked")
    - Root Cause column:    Semicolon-separated root causes (optional)
    - Description column:   Description of the contact driver (optional)

  Example:
    Group                        | Sub-categories       | Root Cause                        | Description
    Signing in & authentication  | Login blocked        | Incorrect password; Cloudflare    | Requests where the user cannot sign in...
    Signing in & authentication  | Password             | Forgot password; Reset email...   | Requests about forgotten password...
    Account creation & setup     | Registration failed  | Account already exists; ...       | Requests where the user cannot create...

OUTPUT:
  Two JSON files:
    - contact_reason.json  (or custom name) — CR1, CR1.1, CR1.2, ...
    - root_cause.json      (or custom name) — RC1, RC1.1, RC1.2, ...

USAGE:
  # Basic — auto-detect columns
  python convert_taxonomy.py --input taxonomy.xlsx --output-dir taxonomies/

  # Specify column names
  python convert_taxonomy.py --input taxonomy.xlsx \\
      --group-col "Group" \\
      --subcategory-col "Sub-categories (contact drivers)" \\
      --rootcause-col "Root Cause" \\
      --description-col "Description of the contact driver" \\
      --cr-prefix CR \\
      --rc-prefix RC \\
      --output-dir taxonomies/

  # From Python
  from convert_taxonomy import convert_spreadsheet_to_taxonomies
  cr_tax, rc_tax = convert_spreadsheet_to_taxonomies("taxonomy.xlsx")
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s │ %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("convert_taxonomy")


# ---------------------------------------------------------------------------
# Core conversion logic
# ---------------------------------------------------------------------------
def convert_spreadsheet_to_taxonomies(
    filepath: str | Path,
    group_col: Optional[str] = None,
    subcategory_col: Optional[str] = None,
    rootcause_col: Optional[str] = None,
    description_col: Optional[str] = None,
    cr_prefix: str = "CR",
    rc_prefix: str = "RC",
    sheet_name: int | str = 0,
) -> tuple[dict, dict]:
    """
    Convert a spreadsheet taxonomy into pipeline JSON format.

    Parameters
    ----------
    filepath : path to Excel (.xlsx) or CSV file
    group_col : column name for L1 group (auto-detected if None)
    subcategory_col : column name for leaf sub-category (auto-detected if None)
    rootcause_col : column name for root causes (auto-detected if None)
    description_col : column name for descriptions (auto-detected if None)
    cr_prefix : prefix for contact reason codes (default: "CR")
    rc_prefix : prefix for root cause codes (default: "RC")
    sheet_name : sheet name or index for Excel files

    Returns
    -------
    (contact_reason_taxonomy, root_cause_taxonomy) — both as dicts
    """
    # Load the spreadsheet
    filepath = Path(filepath)
    if filepath.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(filepath, sheet_name=sheet_name, engine="openpyxl")
    else:
        df = pd.read_csv(filepath)

    logger.info(f"Loaded {len(df)} rows from {filepath.name}")
    logger.info(f"Columns: {list(df.columns)}")

    # Auto-detect columns if not specified
    cols = list(df.columns)
    if group_col is None:
        group_col = _auto_detect_col(cols, ["group", "category", "l1", "level 1", "level1"])
    if subcategory_col is None:
        subcategory_col = _auto_detect_col(cols, ["sub", "subcategor", "driver", "contact driver", "l2", "level 2", "level2", "leaf"])
    if rootcause_col is None:
        rootcause_col = _auto_detect_col(cols, ["root cause", "rootcause", "root_cause", "cause", "reason"])
    if description_col is None:
        description_col = _auto_detect_col(cols, ["description", "desc", "definition", "detail"])

    logger.info(f"Using columns:")
    logger.info(f"  Group:         {group_col}")
    logger.info(f"  Sub-category:  {subcategory_col}")
    logger.info(f"  Root Cause:    {rootcause_col or '(not found)'}")
    logger.info(f"  Description:   {description_col or '(not found)'}")

    if not group_col or not subcategory_col:
        raise ValueError(
            f"Could not auto-detect required columns. "
            f"Available: {cols}. Specify --group-col and --subcategory-col."
        )

    # Build contact reason taxonomy
    cr_taxonomy = _build_contact_reason_taxonomy(
        df, group_col, subcategory_col, rootcause_col, description_col, cr_prefix
    )

    # Build root cause taxonomy
    rc_taxonomy = _build_root_cause_taxonomy(
        df, rootcause_col, rc_prefix, group_col=group_col
    )

    return cr_taxonomy, rc_taxonomy


def _auto_detect_col(columns: list[str], keywords: list[str]) -> Optional[str]:
    """Find the first column whose name contains any of the keywords."""
    for col in columns:
        col_lower = col.lower().strip()
        for kw in keywords:
            if kw in col_lower:
                return col
    return None


def _parse_semicolon_list(text: str) -> list[str]:
    """Split a semicolon-separated string into a clean list."""
    if not text or pd.isna(text):
        return []
    items = [item.strip() for item in str(text).split(";")]
    return [item for item in items if item]


def _build_contact_reason_taxonomy(
    df: pd.DataFrame,
    group_col: str,
    subcategory_col: str,
    rootcause_col: Optional[str],
    description_col: Optional[str],
    prefix: str,
) -> dict:
    """Build a contact reason taxonomy from the spreadsheet data."""
    taxonomy = {}
    l1_counter = 0
    group_to_code = {}

    for _, row in df.iterrows():
        group = str(row[group_col]).strip()
        subcategory = str(row[subcategory_col]).strip()

        if not group or not subcategory or group == "nan" or subcategory == "nan":
            continue

        # Assign L1 code if new group
        if group not in group_to_code:
            l1_counter += 1
            l1_code = f"{prefix}{l1_counter}"
            group_to_code[group] = l1_code
            taxonomy[l1_code] = {
                "label": group,
                "children": {},
            }

        l1_code = group_to_code[group]
        leaf_num = len(taxonomy[l1_code]["children"]) + 1
        leaf_code = f"{l1_code}.{leaf_num}"

        leaf_entry = {"label": subcategory}

        # Add description if available
        if description_col and description_col in df.columns:
            desc = str(row.get(description_col, "")).strip()
            if desc and desc != "nan":
                leaf_entry["description"] = desc

        # Add root causes if available
        if rootcause_col and rootcause_col in df.columns:
            rcs = _parse_semicolon_list(row.get(rootcause_col, ""))
            if rcs:
                leaf_entry["root_causes"] = rcs

        taxonomy[l1_code]["children"][leaf_code] = leaf_entry

    logger.info(
        f"Contact reason taxonomy: {len(taxonomy)} L1 categories, "
        f"{sum(len(v['children']) for v in taxonomy.values())} leaf codes"
    )
    return taxonomy


def _build_root_cause_taxonomy(
    df: pd.DataFrame,
    rootcause_col: Optional[str],
    prefix: str,
    group_col: Optional[str] = None,
) -> dict:
    """
    Build a root cause taxonomy by extracting unique root causes
    and assigning codes.

    Grouping strategy (in priority order):
      1. If group_col is provided AND the spreadsheet has root causes per row,
         group root causes under the same L1 group as the contact reason row
         they appear in.  This is data-driven and works for any domain.
      2. Otherwise, place all root causes under a single "Root Causes" L1 group
         (flat list — no hardcoded keyword matching).
    """
    if not rootcause_col or rootcause_col not in df.columns:
        logger.warning("No root cause column found — skipping root cause taxonomy")
        return {}

    # ── Strategy 1: group by the contact-reason group column ──────────────
    if group_col and group_col in df.columns:
        # Collect root causes per group
        group_causes: dict[str, list[str]] = {}
        seen_global: dict[str, str] = {}  # lowercase → original casing

        for _, row in df.iterrows():
            group = str(row[group_col]).strip()
            if not group or group == "nan":
                group = "Other"
            causes = _parse_semicolon_list(row.get(rootcause_col, ""))
            for cause in causes:
                key = cause.lower().strip()
                if not key:
                    continue
                if key not in seen_global:
                    seen_global[key] = cause
                    group_causes.setdefault(group, []).append(cause)

        if group_causes:
            taxonomy: dict = {}
            l1_counter = 0
            for group_name, causes in group_causes.items():
                l1_counter += 1
                l1_code = f"{prefix}{l1_counter}"
                children = {}
                for i, cause in enumerate(causes, 1):
                    children[f"{l1_code}.{i}"] = {"label": cause}
                # Use a fixed .99 code so "Other" never shifts when causes are added
                children[f"{l1_code}.99"] = {
                    "label": f"Other {group_name} Issues"
                }
                taxonomy[l1_code] = {"label": group_name, "children": children}

            logger.info(
                f"Root cause taxonomy: {len(taxonomy)} L1 categories, "
                f"{sum(len(v['children']) for v in taxonomy.values())} leaf codes"
            )
            return taxonomy

    # ── Strategy 2: flat list (no grouping) ───────────────────────────────
    all_causes: list[str] = []
    for val in df[rootcause_col].dropna():
        all_causes.extend(_parse_semicolon_list(val))

    # Deduplicate (case-insensitive)
    seen: dict[str, str] = {}
    for cause in all_causes:
        key = cause.lower().strip()
        if key and key not in seen:
            seen[key] = cause

    unique_causes = list(seen.values())

    if not unique_causes:
        logger.warning("No root causes found in data")
        return {}

    l1_code = f"{prefix}1"
    children = {}
    for i, cause in enumerate(unique_causes, 1):
        children[f"{l1_code}.{i}"] = {"label": cause}
    children[f"{l1_code}.99"] = {"label": "Other / Uncategorised"}

    taxonomy = {l1_code: {"label": "Root Causes", "children": children}}

    logger.info(
        f"Root cause taxonomy: {len(taxonomy)} L1 categories, "
        f"{sum(len(v['children']) for v in taxonomy.values())} leaf codes"
    )
    return taxonomy


# ---------------------------------------------------------------------------
# Save helpers
# ---------------------------------------------------------------------------
def save_taxonomy(taxonomy: dict, filepath: str | Path) -> Path:
    """Save a taxonomy dict to a JSON file."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(taxonomy, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved taxonomy to {filepath}")
    return filepath


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Convert taxonomy spreadsheet to pipeline JSON files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-detect columns
  python convert_taxonomy.py --input taxonomy.xlsx --output-dir taxonomies/

  # Specify columns explicitly
  python convert_taxonomy.py --input taxonomy.xlsx \\
      --group-col "Group" \\
      --subcategory-col "Sub-categories (contact drivers)" \\
      --rootcause-col "Root Cause" \\
      --description-col "Description of the contact driver"
        """,
    )
    parser.add_argument("--input", "-i", required=True, help="Input Excel or CSV file")
    parser.add_argument("--output-dir", "-o", default="taxonomies", help="Output directory for JSON files")
    parser.add_argument("--group-col", default=None, help="Column name for L1 group")
    parser.add_argument("--subcategory-col", default=None, help="Column name for leaf sub-category")
    parser.add_argument("--rootcause-col", default=None, help="Column name for root causes")
    parser.add_argument("--description-col", default=None, help="Column name for descriptions")
    parser.add_argument("--cr-prefix", default="CR", help="Prefix for contact reason codes")
    parser.add_argument("--rc-prefix", default="RC", help="Prefix for root cause codes")
    parser.add_argument("--cr-filename", default="contact_reason.json", help="Output filename for contact reasons")
    parser.add_argument("--rc-filename", default="root_cause.json", help="Output filename for root causes")
    parser.add_argument("--sheet-name", default="0", help="Sheet name or index (default: first sheet)")

    args = parser.parse_args()

    # Parse sheet name
    try:
        sheet = int(args.sheet_name)
    except ValueError:
        sheet = args.sheet_name

    cr_tax, rc_tax = convert_spreadsheet_to_taxonomies(
        filepath=args.input,
        group_col=args.group_col,
        subcategory_col=args.subcategory_col,
        rootcause_col=args.rootcause_col,
        description_col=args.description_col,
        cr_prefix=args.cr_prefix,
        rc_prefix=args.rc_prefix,
        sheet_name=sheet,
    )

    output_dir = Path(args.output_dir)

    if cr_tax:
        save_taxonomy(cr_tax, output_dir / args.cr_filename)
    if rc_tax:
        save_taxonomy(rc_tax, output_dir / args.rc_filename)

    print(f"\nDone! Files saved to {output_dir}/")


if __name__ == "__main__":
    main()
