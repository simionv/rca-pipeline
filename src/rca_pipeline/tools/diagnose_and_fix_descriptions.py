"""
diagnose_and_fix_descriptions.py
=================================
Paste this into a notebook cell or run standalone BEFORE classification.
It diagnoses why descriptions are blank and patches the running code.

Run AFTER build_pipeline.py but BEFORE classification.
"""

import sys
import inspect
import logging

logger = logging.getLogger("desc_fix")
logging.basicConfig(level=logging.INFO)

print("=" * 70)
print("  DESCRIPTION DIAGNOSTIC")
print("=" * 70)

# ── 1. Check which utils.py is loaded ────────────────────────────────────
import rca_pipeline.utils as utils
print(f"\n1. utils.py loaded from: {utils.__file__}")

src = inspect.getsource(utils.derive_labels)
has_l1_desc_fix = 'l1c + "_description"' in src
has_backfill_log = 'Backfilled' in src or 'Description lookup' in src
print(f"   L1 description derivation: {'YES' if has_l1_desc_fix else 'MISSING'}")
print(f"   Backfill diagnostic logging: {'YES' if has_backfill_log else 'MISSING'}")

# ── 2. Check taxonomy descriptions ──────────────────────────────────────
from rca_pipeline.taxonomy import load_taxonomies, leaf_description_lookup, leaf_label_lookup

# Auto-detect taxonomy dir
import json
from pathlib import Path
tax_dir = "generated/taxonomies"  # canonical default
if Path("generated/pipeline_config.json").exists():
    pcfg = json.load(open("generated/pipeline_config.json"))
    # Extract from config if present; fall back to a directory-existence check
    tax_dir = pcfg.get("taxonomy_dir", tax_dir)
    if not Path(tax_dir).exists():
        # config value may be absolute or project-relative — try siblings
        for candidate in ["taxonomies_mendeley", "taxonomies_jira", "taxonomies"]:
            if Path(candidate).exists():
                tax_dir = candidate
                break
elif Path("taxonomies_mendeley").exists():
    tax_dir = "taxonomies_mendeley"
elif Path("taxonomies_jira").exists():
    tax_dir = "taxonomies_jira"

taxonomies = load_taxonomies(tax_dir)
desc_lookup = leaf_description_lookup(taxonomies)
label_lookup = leaf_label_lookup(taxonomies)

print(f"\n2. Taxonomy directory: {tax_dir}")
print(f"   Description lookup: {len(desc_lookup)} entries")
print(f"   Label lookup: {len(label_lookup)} entries")

if len(desc_lookup) == 0:
    print("\n   *** ROOT CAUSE FOUND: taxonomy JSONs have NO descriptions ***")
    print("   The live taxonomy files were likely overwritten by discovery drafts.")
    print("   Fix: python build_pipeline.py build --input <definition.xlsx> --force-all")
    
    # Check raw JSON files
    for tf in sorted(Path(tax_dir).glob("*.json")):
        raw = json.load(open(tf))
        first = next(iter(raw.values()), {})
        has_desc = "description" in first if isinstance(first, dict) else False
        children = first.get("children", {}) if isinstance(first, dict) else {}
        first_child = next(iter(children.values()), {}) if children else {}
        child_has_desc = "description" in first_child if isinstance(first_child, dict) else False
        print(f"   {tf.name:35s}  L1 desc: {has_desc:5}  L2 desc: {child_has_desc}")
else:
    # Show sample
    cr_descs = {k: v for k, v in desc_lookup.items() if k.startswith("CR")}
    rc_descs = {k: v for k, v in desc_lookup.items() if k.startswith("RC")}
    print(f"   CR descriptions: {len(cr_descs)}")
    print(f"   RC descriptions: {len(rc_descs)}")
    for code in sorted(cr_descs)[:3]:
        print(f"     {code}: {cr_descs[code][:60]}...")

# ── 3. Check confidence.py instruction ──────────────────────────────────
try:
    from rca_pipeline.enhancements.confidence import inject_confidence_instruction
    instr = inject_confidence_instruction("")
    has_addition = "IN ADDITION" in instr or "MUST still appear" in instr
    print(f"\n3. Confidence instruction guards other fields: {'YES' if has_addition else 'NO (old version)'}")
except ImportError:
    print("\n3. confidence.py not available")

# ── 4. APPLY IN-MEMORY PATCH if needed ──────────────────────────────────
print(f"\n{'=' * 70}")
print("  APPLYING IN-MEMORY PATCHES")
print("=" * 70)

import pandas as pd
from rca_pipeline.taxonomy import get_l1_from_code

# Monkey-patch derive_labels with the fixed version
_original_derive_labels = utils.derive_labels

def _patched_derive_labels(df, taxonomies):
    """Fixed derive_labels with L1 description derivation and robust backfill."""
    lookup = leaf_label_lookup(taxonomies)
    desc   = leaf_description_lookup(taxonomies)
    df     = df.copy()

    if desc:
        logger.info("Description lookup: %d entries available for backfill", len(desc))
    else:
        logger.warning(
            "Description lookup is EMPTY — taxonomy JSONs have no 'description' "
            "fields. Run: python build_pipeline.py build --input <definition.xlsx> --force-all"
        )

    # Build L1 children map for L1 code fixing
    from rca_pipeline.utils import _build_l1_children_map, _fix_l1_primary_codes
    _l1_children = _build_l1_children_map(taxonomies)

    for col in [c for c in df.columns
                if c.endswith("_code") or c.endswith("_primary_code")]:

        if "primary" in col:
            _fix_l1_primary_codes(df, col, _l1_children)

        # Label column
        lc = col.replace("_code", "_label")
        if lc not in df.columns:
            df[lc] = df[col].map(
                lambda x, _l=lookup: _l.get(str(x).strip(), "") if pd.notna(x) else "")

        # Description column — backfill blanks from taxonomy
        dc = col.replace("_code", "_description")
        if dc in df.columns:
            if desc:
                mask = df[dc].isna() | (df[dc].astype(str).str.strip() == "")
                if mask.any():
                    df.loc[mask, dc] = df.loc[mask, col].map(
                        lambda x, _d=desc: _d.get(str(x).strip(), "") if pd.notna(x) else "")
                    still_blank = (df[dc].isna() | (df[dc].astype(str).str.strip() == "")).sum()
                    filled = mask.sum() - still_blank
                    logger.info("  Backfilled %d/%d blank %s from taxonomy", filled, mask.sum(), dc)
        elif desc:
            df[dc] = df[col].map(
                lambda x, _d=desc: _d.get(str(x).strip(), "") if pd.notna(x) else "")

        # L1 class columns for primary codes
        if "primary" in col:
            l1c = col.replace("_primary_code", "_class_l1")
            if l1c not in df.columns:
                df[l1c] = df[col].map(
                    lambda x: get_l1_from_code(str(x)) if pd.notna(x) else "")
            # Always ensure label and description exist for L1 class
            if l1c + "_label" not in df.columns:
                df[l1c + "_label"] = df[l1c].map(
                    lambda x, _l=lookup: _l.get(str(x).strip(), "") if x else "")
            if l1c + "_description" not in df.columns and desc:
                df[l1c + "_description"] = df[l1c].map(
                    lambda x, _d=desc: _d.get(str(x).strip(), "") if x else "")
                filled = (df[l1c + "_description"].astype(str).str.strip() != "").sum()
                logger.info("  Created %s: %d/%d populated", l1c + "_description", filled, len(df))

    return df

# Apply the patch
utils.derive_labels = _patched_derive_labels
# Also patch it in the utils module's post_process function
print("  ✓ derive_labels patched in memory")

# Also patch validate_evidence_fields to accept id_col
_orig_validate = utils.validate_evidence_fields
_orig_sig = inspect.signature(_orig_validate)
if "id_col" not in _orig_sig.parameters:
    def _patched_validate(df, text_col="transcript", id_col="uid", flag_col_suffix="_grounded"):
        """Patched: accepts id_col, safe uid extraction."""
        return _orig_validate(df, text_col=text_col, flag_col_suffix=flag_col_suffix)
    utils.validate_evidence_fields = _patched_validate
    print("  ✓ validate_evidence_fields patched (id_col support)")
else:
    print("  ✓ validate_evidence_fields already has id_col support")

# Patch post_process to pass id_col to validate_evidence_fields
_orig_post_process = utils.post_process
_pp_src = inspect.getsource(_orig_post_process)
if "id_col=cfg.id_col" not in _pp_src:
    from rca_pipeline.config import RunConfig
    from rca_pipeline.utils import merge_results, validate_enum_cols, heuristic_fallbacks
    from rca_pipeline.utils import explode_lists, derive_positional_labels, reorder_columns
    from rca_pipeline.utils import write_output_file as _wof
    
    def _patched_post_process(df_original, results, taxonomies, cfg):
        original_cols = list(df_original.columns)
        df = merge_results(df_original, results, id_col=cfg.id_col)
        df = validate_enum_cols(df)
        df = utils.validate_evidence_fields(df, text_col=cfg.text_col, id_col=cfg.id_col)
        df = utils.derive_labels(df, taxonomies)  # Uses our patched version
        df = heuristic_fallbacks(df, taxonomies, text_col=cfg.text_col)
        df = explode_lists(df)
        df = derive_positional_labels(df, taxonomies)
        df = reorder_columns(df, id_col=cfg.id_col, text_col=cfg.text_col,
                             original_cols=original_cols)
        # Strip output-excluded fields
        if hasattr(utils, '_OUTPUT_EXCLUDE') and utils._OUTPUT_EXCLUDE:
            drop = [c for c in df.columns if c in utils._OUTPUT_EXCLUDE]
            if drop:
                df = df.drop(columns=drop)
        return df
    
    utils.post_process = _patched_post_process
    print("  ✓ post_process patched (passes id_col)")
else:
    print("  ✓ post_process already passes id_col")

print(f"\n{'=' * 70}")
print("  PATCHES APPLIED — proceed with classification")
print("=" * 70)
