"""
rca build – Pipeline Definition Builder
=================================================
Reads pipeline_definition.xlsx and manages all generated artefacts.

COMMANDS
--------
Normal build (default):
  rca build --input pipeline_definition.xlsx

  For each enabled module:
    • Taxonomy JSON   — always written from Excel (Excel wins)
    • Module .py      — generated only if MISSING; warns if stale; skips if current
    • pipeline_config.json — always regenerated
    • build_manifest.json  — always updated

Force-regenerate specific module(s):
  rca build --input pipeline_definition.xlsx --force contact_reason root_cause

Force-regenerate ALL .py files:
  rca build --input pipeline_definition.xlsx --force-all

Discovery cold-start (no taxonomy exists):
  rca discover
      --input pipeline_definition.xlsx
      --data  data/transcripts.csv
      --modules contact_reason root_cause
      --sample-n 100

  Writes drafts to taxonomies/drafts/<module>_draft.json, then pauses for review.

Promote drafts to live:
  rca promote-drafts --input pipeline_definition.xlsx

Dry-run (show what would happen, write nothing):
  rca build --input pipeline_definition.xlsx --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("build_pipeline")

# Bump this version whenever a fix changes the output of generate_module_py.
# If the version in the manifest doesn't match, all .py files are treated as
# stale and a --force is recommended.
_GENERATOR_VERSION = "1.7.0"  # 1.7.0: drop bogus brace escaping in baked prompts


# ═══════════════════════════════════════════════════════════════════════════
# 1 · Excel reader
# ═══════════════════════════════════════════════════════════════════════════

def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
    """Drop note/header rows and NaN-first-column rows."""
    first = df.columns[0]
    df = df[df[first].notna()].copy()
    df = df[~df[first].astype(str).str.strip().str.startswith(("Green", "Edit", "L1", "L2",
                                                                "level", "module_name"))]
    df = df[df[first].astype(str).str.strip() != ""]
    return df.reset_index(drop=True)


def load_definition(path: Path) -> dict[str, pd.DataFrame]:
    if not path.exists():
        logger.error("File not found: %s", path)
        sys.exit(1)
    sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
    for required in ("modules", "fields", "taxonomy"):
        if required not in sheets:
            logger.error("Missing sheet '%s' in %s", required, path)
            sys.exit(1)
    return {k: _clean_df(v) for k, v in sheets.items()}


# ═══════════════════════════════════════════════════════════════════════════
# 2 · Manifest  (build_manifest.json)
# ═══════════════════════════════════════════════════════════════════════════

def load_manifest(path: Path) -> dict:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            manifest = json.load(f)
        stored_version = manifest.get("generator_version", "0.0.0")
        if stored_version != _GENERATOR_VERSION:
            logger.warning(
                "build_manifest.json was created by generator v%s but current "
                "version is v%s. Existing .py files may be stale.\n"
                "  Run with --force-all to regenerate all module files.",
                stored_version, _GENERATOR_VERSION,
            )
        return manifest
    return {"modules": {}}


def save_manifest(manifest: dict, path: Path) -> None:
    manifest["generated_at"]    = datetime.now(timezone.utc).isoformat()
    manifest["generator_version"] = _GENERATOR_VERSION
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def _hash_rows(rows_dict: dict) -> str:
    """SHA-256 of the canonical JSON representation of a module's definition rows."""
    canonical = json.dumps(rows_dict, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def module_hash(mod_name: str, modules_df: pd.DataFrame,
                fields_df: pd.DataFrame, taxonomy_df: pd.DataFrame) -> str:
    mod_rows  = modules_df[modules_df["module_name"] == mod_name].to_dict("records")
    fld_rows  = fields_df[fields_df["module_name"] == mod_name].to_dict("records")
    tax_rows  = taxonomy_df[taxonomy_df["module_name"] == mod_name].to_dict("records")
    return _hash_rows({"module": mod_rows, "fields": fld_rows, "taxonomy": tax_rows})


# ═══════════════════════════════════════════════════════════════════════════
# 3 · Taxonomy JSON builder
# ═══════════════════════════════════════════════════════════════════════════

def build_taxonomy_json(mod_name: str, prefix: str, tax_df: pd.DataFrame) -> dict:
    """
    Build a 2-level taxonomy dict from the taxonomy sheet rows for one module.

    Rules:
      - L1 rows → top-level groups, codes PREFIX1, PREFIX2, …
      - L2 rows → children of the most recent L1, codes PREFIX1.1, PREFIX1.2, …
      - Codes assigned by row order; never read from the sheet.
    """
    rows = tax_df[tax_df["module_name"] == mod_name].copy()
    if rows.empty:
        return {}

    taxonomy: dict[str, Any] = {}
    current_l1_code: str | None = None
    l1_counter  = 0
    l2_counter  = 0

    for _, row in rows.iterrows():
        level = str(row.get("level", "")).strip().upper()
        label = str(row.get("label", "")).strip()
        desc  = str(row.get("description", "")).strip()
        # Optional explicit code: if the taxonomy sheet has a "code" column and
        # the cell is filled, that value is used verbatim instead of the
        # auto-assigned PREFIX+counter code.  Useful when the LLM prompt uses
        # fixed reference codes (e.g. PA0–PA9) that differ from the module prefix.
        raw_code = str(row.get("code", "")).strip()
        explicit_code = "" if raw_code in ("", "nan") else raw_code
        if not label or label == "nan":
            continue

        if level == "L1":
            l1_counter += 1
            l2_counter  = 0
            current_l1_code = explicit_code if explicit_code else f"{prefix}{l1_counter}"
            entry: dict[str, Any] = {"label": label, "children": {}}
            if desc and desc != "nan":
                entry["description"] = desc
            taxonomy[current_l1_code] = entry

        elif level == "L2":
            if current_l1_code is None:
                logger.warning("L2 row '%s' has no parent L1 — skipping", label)
                continue
            l2_counter += 1
            leaf_code = explicit_code if explicit_code else f"{current_l1_code}.{l2_counter}"
            leaf: dict[str, Any] = {"label": label}
            if desc and desc != "nan":
                leaf["description"] = desc
            taxonomy[current_l1_code]["children"][leaf_code] = leaf

    n_l1   = len(taxonomy)
    n_leaf = sum(len(v["children"]) for v in taxonomy.values())
    logger.info("  Taxonomy built: %d L1 groups, %d leaf codes", n_l1, n_leaf)
    return taxonomy


def write_taxonomy(taxonomy: dict, path: Path, dry_run: bool = False) -> None:
    if not taxonomy:
        logger.info("  (empty taxonomy — nothing to write)")
        return
    if dry_run:
        logger.info("  [dry-run] would write %s", path.name)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(taxonomy, f, indent=2, ensure_ascii=False)
    logger.info("  Written: %s", path)


# ═══════════════════════════════════════════════════════════════════════════
# 4 · Module .py generator
# ═══════════════════════════════════════════════════════════════════════════

def _json_example(field_type: str, field_name: str, tax_prefix: str = "", explode_keys: str = "") -> str:
    ft = str(field_type).lower().strip()
    if ft == "bool":   return "true"
    if ft == "int":    return "0"
    if ft == "float":  return "0.0"
    if ft == "list":
        keys = [k.strip() for k in explode_keys.split(",") if k.strip()] if explode_keys else []
        if keys:
            obj = ", ".join(f'"{k}": "<{k}>"' for k in keys)
            return f"[{{{obj}}}]"
        return '["<item1>", "<item2>"]'
    if ft.startswith("enum:"):
        opts = " | ".join(o.strip() for o in ft[5:].split(","))
        return f'"<{opts}>"'
    if ft == "code":
        pfx = tax_prefix if tax_prefix else field_name[:2].upper()
        return f'"<{pfx}_code>"'
    return '"<string>"'

def _output_schema(fields: list[dict], tax_prefix: str = "") -> str:
    lines = ["[", "  {", '    "uid": "<record uid>",']
    for i, f in enumerate(fields):
        comma = "," if i < len(fields) - 1 else ""
        ek    = f.get("explode_keys", "")
        ek    = "" if ek in ("nan", "") else ek
        ex    = _json_example(f["field_type"], f["field_name"], tax_prefix, ek)
        lines.append(f'    "{f["field_name"]}": {ex}{comma}')
    lines += ["  }", "]"]
    return "\n".join(lines)


def _field_instructions(fields: list[dict]) -> str:
    lines = []
    for i, f in enumerate(fields, 1):
        inst = str(f.get("prompt_instruction", "")).strip()
        if inst:
            lines.append(f"{i}. {inst} → `{f['field_name']}`")
    return "\n".join(lines)


def _enum_validator_code(fields: list[dict]) -> tuple[str, str]:
    """Return (parse_fn source, parse_fn arg string) for enum fields."""
    enum_fields = [f for f in fields
                   if str(f.get("field_type", "")).lower().startswith("enum:")]
    if not enum_fields:
        return "", ""

    lines = ["def _validate_record(record: dict) -> dict:",
             '    """Validate enum fields and normalise casing."""']
    for ef in enum_fields:
        ft      = ef["field_type"]
        fname   = ef["field_name"]
        options = ft[5:].split(",") if ft.startswith("enum:") else []
        opts_r  = repr(frozenset(o.strip() for o in options))
        lines += [
            f"    _VALID_{fname.upper()} = {opts_r}",
            f'    _v = str(record.get("{fname}", "")).strip().lower()',
            f"    if _v not in _VALID_{fname.upper()}:",
            f'        logger.warning(',
            f'            "uid=%s: invalid {fname} %r — setting to blank. Allowed: %s",',
            f'            record.get("uid","?"), _v, sorted(_VALID_{fname.upper()})',
            f'        )',
            f'        record["{fname}"] = ""',
            f"    else:",
            f'        record["{fname}"] = _v',
        ]
    lines.append("    return record")
    return "\n".join(lines), "parse_fn=_validate_record,"


def generate_module_py(module: dict, fields: list[dict], has_taxonomy: bool) -> str:
    mod_name    = module["module_name"]
    prefix      = str(module.get("taxonomy_prefix", "")).strip()
    tax_file    = str(module.get("taxonomy_file", "")).strip()
    description = str(module.get("description", "")).strip()
    # Escape triple-quotes in description to prevent breaking generated string literals
    description = description.replace('"""', '\\"\\"\\"')
    tax_key     = tax_file.replace(".json", "") if tax_file and tax_file != "nan" else mod_name

    field_names   = ", ".join(f["field_name"] for f in fields)
    schema        = _output_schema(fields, tax_prefix=prefix)
    instructions  = _field_instructions(fields)
    parse_fn, parse_fn_arg = _enum_validator_code(fields)

    # ── System prompt ──────────────────────────────────────────────────────
    if has_taxonomy and prefix:
        tax_import = "from rca_pipeline.taxonomy import taxonomy_to_rich_prompt"
        # Pre-indent all three lines so they sit correctly inside the async function body
        _raw = (
            f'tax = taxonomies.get("{tax_key}", {{}})\n'
            f'tax_prompt = taxonomy_to_rich_prompt(tax, "{prefix}")\n'
            f'system_prompt = _build_system_prompt(tax_prompt)'
        )
        tax_load_block = textwrap.indent(_raw, "    ")

        # schema and instructions are baked in as plain text at generation time.
        # taxonomy_prompt is the only runtime variable, and _build_system_prompt()
        # injects it by plain concatenation — str.format() is never applied to the
        # system prompt (llm_client.py uses it verbatim, and substitutes
        # {records_json} in the user prompt via str.replace). So braces must NOT
        # be doubled here, or the LLM receives literal {{ }} in the JSON schema.
        system_prompt_def = (
            f'def _build_system_prompt(taxonomy_prompt: str) -> str:\n'
            f'    _BEFORE = """You are an expert classifier for Elsevier support tickets.\n'
            f'Your task: {description}\n\n'
            f'## Taxonomy\n"""\n'
            f'    _AFTER = """\n\n'
            f'## Instructions\n'
            + instructions.replace('"""', '\\"""')  + '\n\n'
            + '## Output Format\n'
            + 'Return a JSON array — one object per record:\n'
            + schema.replace('"""', '\\"""') + '\n\n'
            + 'IMPORTANT: Return ONLY valid JSON. No markdown fences. Every input uid MUST appear in output.\n'
            + 'CRITICAL: Always use LEAF-level codes (with a dot, e.g. CR4.1), NEVER L1 group codes (e.g. CR4)."""\n'
            + '    return _BEFORE + taxonomy_prompt + _AFTER\n'
        )
        inline_prompt = ""

    else:
        tax_import     = ""
        tax_load_block = "    system_prompt = _SYSTEM_PROMPT"
        system_prompt_def = ""
        # schema and instructions baked in as plain text — no runtime f-string
        # and no .format() downstream, so braces stay single (see note above).
        inline_prompt = (
            f'_SYSTEM_PROMPT = """You are an expert classifier for Elsevier support tickets.\n'
            f'Your task: {description}\n\n'
            f'## Instructions\n'
            + instructions + '\n\n'
            + '## Output Format\n'
            + 'Return a JSON array — one object per record:\n'
            + schema + '\n\n'
            + 'IMPORTANT: Return ONLY valid JSON. No markdown fences. Every input uid MUST appear in output.\n'
        + 'CRITICAL: Always use LEAF-level codes (with a dot, e.g. CE1.1), NEVER L1 group codes (e.g. CE1)."""\n'
        )

    code = f'''\
"""
{mod_name}.py
AUTO-GENERATED by build_pipeline.py — do not edit by hand.
Source: pipeline_definition.xlsx
To update: edit the Excel and re-run:
  rca build --input definitions/<file>.xlsx --force {mod_name}

Output fields: {field_names}
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from rca_pipeline.config import RunConfig
{tax_import}
from rca_pipeline.llm_client import process_batches_async

logger = logging.getLogger(__name__)

MODULE_NAME = "{mod_name}"

{inline_prompt}
{system_prompt_def}

_USER_PROMPT_TEMPLATE = """Classify the following support transcripts.

{{records_json}}

Return a JSON array with one object per record.
Each object must have: uid, {field_names}"""


{parse_fn}


async def classify_{mod_name}(
    batches: list[list[dict[str, str]]],
    taxonomies: dict[str, dict],
    cfg: RunConfig,
) -> list[dict[str, Any]]:
    """Run {mod_name} classification on all batches."""
{tax_load_block}

    results = await process_batches_async(
        batches,
        system_prompt,
        _USER_PROMPT_TEMPLATE,
        cfg,
        {parse_fn_arg}
    )

    logger.info("{mod_name}: classified %d records", len(results))
    return results


def run(batches, taxonomies, cfg):
    """Synchronous wrapper."""
    return asyncio.run(classify_{mod_name}(batches, taxonomies, cfg))
'''
    return code


# ═══════════════════════════════════════════════════════════════════════════
# 5 · pipeline_config.json builder
# ═══════════════════════════════════════════════════════════════════════════

def build_pipeline_config(modules_df: pd.DataFrame, fields_df: pd.DataFrame) -> dict:
    config: dict[str, Any] = {
        "modules":            {},
        "enrichment_prefixes": [],
        "reorder_groups":     {},
        "enum_validators":    {},
        "list_fields":        [],      # flat scalar-list fields to explode (explode_list=TRUE)
        "object_list_fields": {},      # list-of-object fields to explode (explode_list=TRUE + explode_keys)
        "code_fields":        [],      # fields for label derivation
        "output_exclude":     [],      # fields to strip from output (in_output=FALSE)
    }

    prefixes: list[str] = []
    reorder:  dict[str, int] = {}

    for _, mod in modules_df.iterrows():
        name     = str(mod["module_name"]).strip()
        prefix   = str(mod.get("taxonomy_prefix", "")).strip()
        tax_file = str(mod.get("taxonomy_file", "")).strip()
        rgroup   = str(mod.get("reorder_group", name)).strip()
        rorder   = int(float(str(mod.get("reorder_order", 99)).strip() or 99))
        enabled  = str(mod.get("enabled", "TRUE")).strip().upper() in ("TRUE", "1", "1.0")
        desc     = str(mod.get("description", "")).strip()
        disc_mode = str(mod.get("discovery_mode", "")).strip().lower()
        if disc_mode not in ("full", "extract_only"):
            disc_mode = ""
        ext_prompt = str(mod.get("extract_prompt", "")).strip()
        if ext_prompt == "nan":
            ext_prompt = ""

        if not enabled:
            continue

        tax_key = tax_file.replace(".json", "") if tax_file and tax_file != "nan" else ""

        config["modules"][name] = {
            "taxonomy_prefix": prefix if prefix != "nan" else "",
            "taxonomy_file":   tax_file if tax_file not in ("nan", "") else "",
            "taxonomy_key":    tax_key,
            "reorder_group":   rgroup,
            "reorder_order":   rorder,
            "description":     desc,
            "classify_fn":     f"classify_{name}",
            "code_field":      None,  # filled in below when the first code field is found
            "discovery_mode":  disc_mode,
            "extract_prompt":  ext_prompt,
        }

        mod_fields = fields_df[fields_df["module_name"] == name]
        for _, frow in mod_fields.iterrows():
            fname = str(frow["field_name"]).strip()
            ft    = str(frow.get("field_type", "")).lower().strip()
            if fname not in prefixes:
                prefixes.append(fname)
            _in_val       = str(frow.get("in_output",     "TRUE")).strip().upper()
            in_output     = _in_val not in ("FALSE", "0", "0.0")
            explode_list  = str(frow.get("explode_list",  "FALSE")).strip().upper() in ("TRUE", "1", "1.0")
            _ve_val       = str(frow.get("validate_enum", "TRUE")).strip().upper()
            validate_enum = _ve_val not in ("FALSE", "0", "0.0")
            _ek_val       = str(frow.get("explode_keys", "")).strip()
            explode_keys  = [] if _ek_val in ("", "nan") else [k.strip() for k in _ek_val.split(",") if k.strip()]

            # in_output=FALSE → add to output_exclude so post_process strips it
            if not in_output and fname not in config["output_exclude"]:
                config["output_exclude"].append(fname)

            # explode_list=TRUE + explode_keys set → list of {key: value} objects, explode per-key
            # explode_list=TRUE alone → flat scalar list, explode as a single column per slot
            if explode_list and explode_keys:
                config["object_list_fields"][fname] = explode_keys
            elif explode_list and fname not in config["list_fields"]:
                config["list_fields"].append(fname)

            # code fields always get label derivation; first one is the primary code field
            if ft == "code":
                if config["modules"][name]["code_field"] is None:
                    config["modules"][name]["code_field"] = fname
                if fname not in config["code_fields"]:
                    config["code_fields"].append(fname)

            # validate_enum=FALSE → skip adding to enum_validators even if field_type is enum:
            if ft.startswith("enum:") and validate_enum:
                config["enum_validators"][fname] = [
                    o.strip() for o in ft[5:].split(",")
                ]

        reorder[rgroup] = rorder

    config["enrichment_prefixes"] = prefixes
    config["reorder_groups"] = dict(sorted(reorder.items(), key=lambda x: x[1]))
    return config


# ═══════════════════════════════════════════════════════════════════════════
# 6 · Main build logic
# ═══════════════════════════════════════════════════════════════════════════

def run_build(args: argparse.Namespace) -> None:
    input_path   = Path(args.input)
    tax_dir      = Path(args.taxonomy_dir)
    module_dir   = Path(args.module_dir)
    if not args.dry_run:
        module_dir.mkdir(parents=True, exist_ok=True)
    config_path  = Path(args.config_file)
    manifest_path = Path(args.manifest_file)
    dry_run      = args.dry_run
    force_all    = getattr(args, "force_all", False)
    force_mods   = set(getattr(args, "force", None) or [])

    sheets      = load_definition(input_path)
    modules_df  = sheets["modules"]
    fields_df   = sheets["fields"]
    taxonomy_df = sheets["taxonomy"]
    manifest    = load_manifest(manifest_path)

    # Filter enabled modules (accept "TRUE" or numeric 1/1.0)
    modules_df = modules_df[
        modules_df["enabled"].apply(
            lambda v: str(v).strip().upper() in ("TRUE", "1", "1.0")
        )
    ].reset_index(drop=True)

    logger.info("Processing %d enabled modules", len(modules_df))

    stats = {"tax_written": 0, "py_generated": 0, "py_skipped": 0,
             "py_stale": 0, "py_forced": 0}

    for _, mod in modules_df.iterrows():
        name     = str(mod["module_name"]).strip()
        prefix   = str(mod.get("taxonomy_prefix", "")).strip()
        tax_file = str(mod.get("taxonomy_file", "")).strip()
        has_tax  = bool(prefix and prefix != "nan" and tax_file and tax_file != "nan")

        logger.info("─" * 50)
        logger.info("Module: %s", name)

        current_hash = module_hash(name, modules_df, fields_df, taxonomy_df)

        # ── Taxonomy JSON ────────────────────────────────────────────────
        if has_tax:
            tax = build_taxonomy_json(name, prefix, taxonomy_df)
            write_taxonomy(tax, tax_dir / tax_file, dry_run=dry_run)
            if not dry_run:
                manifest.setdefault("modules", {}).setdefault(name, {})[
                    "taxonomy_hash"] = current_hash
                manifest["modules"][name]["taxonomy_written_at"] = \
                    datetime.now(timezone.utc).isoformat()
            stats["tax_written"] += 1
        else:
            logger.info("  No taxonomy for %s — skipping JSON", name)

        # ── Module .py ───────────────────────────────────────────────────
        py_path        = module_dir / f"{name}.py"
        manifest_hash  = manifest.get("modules", {}).get(name, {}).get("py_hash", "")
        mod_fields     = [
            {k: str(v).strip() for k, v in r.items()}
            for _, r in fields_df[fields_df["module_name"] == name].iterrows()
        ]

        if not mod_fields:
            logger.warning("  No fields defined for %s — skipping .py", name)
            continue

        should_force = force_all or (name in force_mods)

        if not py_path.exists():
            logger.info("  Generating %s.py (new)", name)
            code = generate_module_py(dict(mod), mod_fields, has_taxonomy=has_tax)
            if not dry_run:
                py_path.write_text(code, encoding="utf-8")
                manifest.setdefault("modules", {}).setdefault(name, {})[
                    "py_hash"] = current_hash
                manifest["modules"][name]["py_generated_at"] = \
                    datetime.now(timezone.utc).isoformat()
            else:
                logger.info("  [dry-run] would write %s.py", name)
            stats["py_generated"] += 1

        elif should_force:
            logger.info("  Force-regenerating %s.py", name)
            code = generate_module_py(dict(mod), mod_fields, has_taxonomy=has_tax)
            if not dry_run:
                py_path.write_text(code, encoding="utf-8")
                manifest.setdefault("modules", {}).setdefault(name, {})[
                    "py_hash"] = current_hash
                manifest["modules"][name]["py_generated_at"] = \
                    datetime.now(timezone.utc).isoformat()
            stats["py_forced"] += 1

        elif current_hash == manifest_hash:
            logger.info("  %s.py is up to date — skipping", name)
            stats["py_skipped"] += 1

        else:
            logger.warning(
                "  ⚠ %s.py is STALE (Excel definition changed since last generation).\n"
                "    Re-run with:  --force %s  to regenerate.\n"
                "    Your hand-edits will be lost — back up first if needed.",
                name, name
            )
            stats["py_stale"] += 1

    # ── pipeline_config.json ─────────────────────────────────────────────
    logger.info("─" * 50)
    cfg = build_pipeline_config(modules_df, fields_df)
    if not dry_run:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        logger.info("pipeline_config.json written")
        save_manifest(manifest, manifest_path)
        logger.info("build_manifest.json updated")
    else:
        logger.info("[dry-run] would write pipeline_config.json and build_manifest.json")

    # ── Summary ──────────────────────────────────────────────────────────
    logger.info("═" * 50)
    logger.info("Build complete%s", " (dry run)" if dry_run else "")
    logger.info("  Taxonomy JSONs written : %d", stats["tax_written"])
    logger.info("  .py files generated   : %d", stats["py_generated"])
    logger.info("  .py files up to date  : %d", stats["py_skipped"])
    logger.info("  .py files forced      : %d", stats["py_forced"])
    if stats["py_stale"]:
        logger.warning("  .py files STALE       : %d  ← run with --force", stats["py_stale"])


# ═══════════════════════════════════════════════════════════════════════════
# 7 · Discovery cold-start
# ═══════════════════════════════════════════════════════════════════════════

async def _run_discovery_async(args: argparse.Namespace) -> None:
    import importlib
    sys.path.insert(0, str(Path(args.module_dir).resolve()))

    try:
        discovery = importlib.import_module("rca_pipeline.discovery")
        config_mod = importlib.import_module("rca_pipeline.config")
        utils_mod  = importlib.import_module("rca_pipeline.utils")
    except ModuleNotFoundError as e:
        logger.error("Cannot import pipeline modules: %s", e)
        logger.error("Run the normal build first to generate module files.")
        sys.exit(1)

    RunConfig   = config_mod.RunConfig

    input_path  = Path(args.input)
    data_path   = Path(args.data)
    draft_dir   = Path(args.taxonomy_dir) / "drafts"
    draft_dir.mkdir(parents=True, exist_ok=True)

    sheets      = load_definition(input_path)
    modules_df  = sheets["modules"]
    tax_dir     = Path(args.taxonomy_dir)

    # Bug fix 1: match the same enabled filter used by run_build() — Excel stores
    # numeric 1 / 1.0 for TRUE checkboxes, not the string "TRUE".
    enabled = modules_df[
        modules_df["enabled"].apply(
            lambda v: str(v).strip().upper() in ("TRUE", "1", "1.0")
        )
    ]

    if args.modules:
        # Explicit --modules list: honour it as long as the module is enabled
        targets = [m for m in args.modules if m in enabled["module_name"].values]
    else:
        # Bug fix 2: the previous check was "taxonomy JSON file does not exist on disk",
        # which skips every module once build has run (even if the JSON is just a
        # placeholder written from the Excel taxonomy rows).
        # The correct signal is discovery_mode — that column explicitly marks which
        # modules should have their taxonomy content generated by LLM discovery.
        targets = []
        for _, mod in enabled.iterrows():
            disc_mode = str(mod.get("discovery_mode", "")).strip().lower()
            if disc_mode in ("full", "extract_only"):
                targets.append(str(mod["module_name"]).strip())

    if not targets:
        logger.info(
            "No enabled modules have discovery_mode='full' or 'extract_only' "
            "in the Excel definition."
        )
        logger.info(
            "Set discovery_mode to 'full' on the modules sheet, re-run "
            "'rca build --input %s', then retry discover.",
            args.input,
        )
        return

    logger.info("Discovery targets: %s", targets)
    logger.info("Loading data from %s", data_path)

    import pandas as pd
    if data_path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(data_path, engine="openpyxl")
    else:
        df = pd.read_csv(data_path)

    id_col   = getattr(args, "id_col", "uid")
    text_col = getattr(args, "text_col", "transcript")
    if id_col not in df.columns:
        df.insert(0, id_col, range(1, len(df) + 1))

    sample_n = min(args.sample_n, len(df))
    sample   = df.sample(n=sample_n, random_state=42)
    records  = [
        {"uid": str(row[id_col]), "text": str(row[text_col])}
        for _, row in sample.iterrows()
    ]
    logger.info("Sampled %d records for discovery", len(records))

    cfg = RunConfig(
        model       = getattr(args, "model", "azure/dsaic-llm-general"),
        batch_size  = getattr(args, "batch_size", 10),
        concurrency = getattr(args, "concurrency", 4),
        retries     = getattr(args, "retries", 3),
        discovery_sample_n = sample_n,
        discovery_top_n    = getattr(args, "top_n", 80),
    )

    logger.info("═" * 50)
    logger.info("DISCOVERY PHASE — running Pass 1 + Pass 2 for %d domains", len(targets))
    logger.info("═" * 50)

    results = await discovery.run_all_discoveries(
        records, targets, cfg, output_dir=draft_dir
    )

    written = []
    for domain, tax in results.items():
        if not tax:
            logger.warning("Discovery returned empty taxonomy for %s", domain)
            continue
        draft_path = draft_dir / f"{domain}_draft.json"
        with open(draft_path, "w", encoding="utf-8") as f:
            json.dump(tax, f, indent=2, ensure_ascii=False)
        n_l1   = len(tax)
        n_leaf = sum(len(v.get("children", {})) for v in tax.values())
        logger.info("  Draft written: %s  (%d L1, %d leaf codes)", draft_path.name, n_l1, n_leaf)
        written.append(domain)

    logger.info("")
    logger.info("═" * 50)
    logger.info("DISCOVERY COMPLETE — %d draft(s) written to %s", len(written), draft_dir)
    logger.info("═" * 50)
    logger.info("")
    logger.info("NEXT STEPS:")
    logger.info("  1. Review and edit the draft taxonomy files in:  %s", draft_dir)
    logger.info("     Rename labels, merge duplicates, add descriptions.")
    logger.info("")
    logger.info("  2. When satisfied, promote drafts to live:")
    logger.info("     rca promote-drafts \\")
    logger.info("         --input %s", input_path)
    logger.info("")
    logger.info("  3. Then run the classification notebook.")


def run_discovery(args: argparse.Namespace) -> None:
    asyncio.run(_run_discovery_async(args))


# ═══════════════════════════════════════════════════════════════════════════
# 8 · Promote drafts
# ═══════════════════════════════════════════════════════════════════════════

def run_promote_drafts(args: argparse.Namespace) -> None:
    draft_dir = Path(args.taxonomy_dir) / "drafts"
    tax_dir   = Path(args.taxonomy_dir)
    manifest_path = Path(args.manifest_file)

    if not draft_dir.exists():
        logger.error("No drafts directory found at %s", draft_dir)
        sys.exit(1)

    drafts = sorted(draft_dir.glob("*_draft.json"))
    if not drafts:
        logger.error("No draft files found in %s", draft_dir)
        sys.exit(1)

    # Load definition to map module→taxonomy_file
    sheets     = load_definition(Path(args.input))
    modules_df = sheets["modules"]
    mod_to_file = {
        str(row["module_name"]).strip(): str(row.get("taxonomy_file", "")).strip()
        for _, row in modules_df.iterrows()
        if str(row.get("taxonomy_file", "")).strip() not in ("", "nan")
    }

    manifest = load_manifest(manifest_path)
    promoted = []

    for draft_path in drafts:
        # draft filename: <module>_draft.json  → module name
        mod_name  = draft_path.stem.replace("_draft", "")
        tax_file  = mod_to_file.get(mod_name, f"{mod_name}.json")
        live_path = tax_dir / tax_file

        with open(draft_path, encoding="utf-8") as f:
            tax = json.load(f)

        n_l1   = len(tax)
        n_leaf = sum(len(v.get("children", {})) for v in tax.values())

        if not args.dry_run:
            live_path.parent.mkdir(parents=True, exist_ok=True)
            with open(live_path, "w", encoding="utf-8") as f:
                json.dump(tax, f, indent=2, ensure_ascii=False)
            manifest.setdefault("modules", {}).setdefault(mod_name, {})[
                "taxonomy_written_at"] = datetime.now(timezone.utc).isoformat()
            manifest["modules"][mod_name]["taxonomy_source"] = "promoted_from_draft"
            logger.info("  Promoted: %s → %s  (%d L1, %d leaf)", draft_path.name,
                        live_path.name, n_l1, n_leaf)
        else:
            logger.info("  [dry-run] would promote: %s → %s", draft_path.name, live_path.name)

        promoted.append(mod_name)

    if not args.dry_run:
        save_manifest(manifest, manifest_path)

    logger.info("")
    logger.info("Promoted %d draft(s): %s", len(promoted), promoted)
    logger.info("Run the classification notebook to classify your data.")


# ═══════════════════════════════════════════════════════════════════════════
# 9 · CLI
# ═══════════════════════════════════════════════════════════════════════════

def _default_definition() -> str | None:
    """The workspace's definition Excel, when definitions/ holds exactly one."""
    files = sorted(p for p in Path("definitions").glob("*.xlsx") if not p.name.startswith("~$"))
    return str(files[0]) if len(files) == 1 else None


def _common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--input",         "-i", default=_default_definition(),
                   help="Definition Excel (default: the only .xlsx in definitions/)")
    p.add_argument("--taxonomy-dir",  "-t", default="generated/taxonomies")
    p.add_argument("--module-dir",    "-m", default="generated/modules")
    p.add_argument("--config-file",         default="generated/pipeline_config.json")
    p.add_argument("--manifest-file",       default="generated/build_manifest.json")
    p.add_argument("--dry-run",             action="store_true")


def main() -> None:
    root = argparse.ArgumentParser(
        description="RCA Pipeline — build, discover, promote",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        Examples:
          rca build --input pipeline_definition.xlsx
          rca build --input pipeline_definition.xlsx --force contact_reason
          rca build --input pipeline_definition.xlsx --force-all
          rca build --input pipeline_definition.xlsx --dry-run
          rca discover --data data/transcripts.csv --sample-n 100
          rca promote-drafts --input pipeline_definition.xlsx
        """),
    )

    sub = root.add_subparsers(dest="command")

    # ── build (default) ───────────────────────────────────────────────────
    build_p = sub.add_parser("build", help="Build taxonomy JSONs and module .py files")
    _common_args(build_p)
    build_p.add_argument("--force",     nargs="+", metavar="MODULE",
                         help="Force-regenerate specific module .py files")
    build_p.add_argument("--force-all", action="store_true",
                         help="Force-regenerate ALL module .py files")

    # ── discover ─────────────────────────────────────────────────────────
    disc_p = sub.add_parser("discover", help="Run discovery to create starter taxonomies")
    _common_args(disc_p)
    disc_p.add_argument("--data",       required=True, help="Path to transcripts CSV/XLSX")
    disc_p.add_argument("--sample-n",   type=int, default=100, dest="sample_n")
    disc_p.add_argument("--top-n",      type=int, default=80,  dest="top_n")
    disc_p.add_argument("--modules",    nargs="+", default=None,
                        help="Specific modules to discover (default: all missing)")
    disc_p.add_argument("--id-col",     default="uid")
    disc_p.add_argument("--text-col",   default="transcript")
    disc_p.add_argument("--model",      default="azure/dsaic-llm-general")
    disc_p.add_argument("--batch-size", type=int, default=10, dest="batch_size")
    disc_p.add_argument("--concurrency",type=int, default=4)
    disc_p.add_argument("--retries",    type=int, default=3)

    # ── promote-drafts ────────────────────────────────────────────────────
    prom_p = sub.add_parser("promote-drafts", help="Promote draft taxonomies to live")
    _common_args(prom_p)

    # If called without a subcommand (old-style: build_pipeline.py --input ...)
    # inject 'build' so it still works.
    import sys as _sys
    _first = _sys.argv[1] if len(_sys.argv) > 1 else ""
    if _first not in ("build", "discover", "promote-drafts", "-h", "--help", ""):
        _sys.argv.insert(1, "build")

    args = root.parse_args()

    if getattr(args, "input", "") is None:
        found = sorted(p.name for p in Path("definitions").glob("*.xlsx") if not p.name.startswith("~$"))
        root.error("which definition? pass --input definitions/<file>.xlsx"
                   + (f" (found: {', '.join(found)})" if found else " (no .xlsx found in definitions/)"))

    if args.command == "build":
        run_build(args)
    elif args.command == "discover":
        run_discovery(args)
    elif args.command == "promote-drafts":
        run_promote_drafts(args)
    else:
        root.print_help()


if __name__ == "__main__":
    main()
