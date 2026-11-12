"""
taxonomy.py – Taxonomy Loader & Helpers
=========================================
load_taxonomies() reads its file list from pipeline_config.json so new modules
are picked up automatically. Falls back to hardcoded defaults if config missing.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from .config import load_pipeline_config as _load_config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Code helpers
# ---------------------------------------------------------------------------
def get_l1_from_code(code: str) -> str:
    if not code or not isinstance(code, str):
        return ""
    return code.split(".")[0]


def get_prefix_from_code(code: str) -> str:
    if not code or not isinstance(code, str):
        return ""
    m = re.match(r"^([A-Z]+)", code)
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------
def load_taxonomy_file(path: Path) -> dict:
    if not path.exists():
        logger.warning("Taxonomy file not found: %s", path)
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    logger.info("Loaded: %s", path.name)
    return data


def load_taxonomies(taxonomy_dir: str | Path) -> dict[str, dict]:
    """
    Load all taxonomy files. File list from pipeline_config.json.
    Falls back to hardcoded defaults if config not present.
    """
    taxonomy_dir = Path(taxonomy_dir)
    config = _load_config()

    if config.get("modules"):
        files: dict[str, str] = {}
        for mod_cfg in config["modules"].values():
            tf = mod_cfg.get("taxonomy_file", "")
            if tf:
                files[tf.replace(".json", "")] = tf
    else:
        logger.warning("pipeline_config.json missing — using default taxonomy list")
        files = {
            "contact_reason":         "contact_reason.json",
            "root_cause":             "root_cause.json",
            "resolution_codes":       "resolution_codes.json",
            "troubleshooting_steps":  "troubleshooting_steps.json",
        }

    taxonomies = {key: load_taxonomy_file(taxonomy_dir / fname)
                  for key, fname in files.items()}
    loaded = [k for k, v in taxonomies.items() if v]
    logger.info("Loaded %d/%d taxonomy files: %s", len(loaded), len(files), loaded)
    return taxonomies


# ---------------------------------------------------------------------------
# Flatten
# ---------------------------------------------------------------------------
def flatten_taxonomy(tax: dict, prefix: str = "") -> dict[str, str]:
    root = tax
    if prefix:
        top = tax.get(prefix)
        if isinstance(top, dict) and "label" not in top:
            root = top
    flat: dict[str, str] = {}
    for code, node in root.items():
        if isinstance(node, dict):
            flat[code] = node.get("label", code)
            for cc, cn in node.get("children", {}).items():
                flat[cc] = cn.get("label", cc) if isinstance(cn, dict) else str(cn)
        else:
            flat[code] = str(node)
    return flat


# ---------------------------------------------------------------------------
# Sort key for codes
# ---------------------------------------------------------------------------
def _sort_key(code: str) -> tuple:
    prefix = get_prefix_from_code(code)
    nums   = []
    for part in code[len(prefix):].split("."):
        try:
            nums.append(int(part))
        except ValueError:
            nums.append(999)
    while len(nums) < 2:
        nums.append(0)
    return (prefix, nums[0], nums[1])


# ---------------------------------------------------------------------------
# Prompt formatters
# ---------------------------------------------------------------------------
def taxonomy_to_prompt_list(flat: dict[str, str]) -> str:
    return "\n".join(
        f"  - {c}: {l}"
        for c, l in sorted(flat.items(), key=lambda x: _sort_key(x[0]))
    )


def taxonomy_to_rich_prompt(tax: dict, prefix: str = "") -> str:
    root = tax
    if prefix:
        top = tax.get(prefix)
        if isinstance(top, dict) and "label" not in top:
            root = top
    lines: list[str] = []
    for l1 in sorted(root, key=_sort_key):
        node = root[l1]
        if not isinstance(node, dict):
            continue
        lines.append(f"\n  {l1}: {node.get('label', l1)}")
        if node.get("description"):
            lines.append(f"    Description: {node['description']}")
        for lc in sorted(node.get("children", {}), key=_sort_key):
            leaf = node["children"][lc]
            if not isinstance(leaf, dict):
                continue
            lines.append(f"    {lc}: {leaf.get('label', lc)}")
            if leaf.get("description"):
                lines.append(f"      Description: {leaf['description']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Global lookups (used in post-processing)
# ---------------------------------------------------------------------------
def _prefix_map(taxonomies: dict) -> dict[str, str]:
    config = _load_config()
    pm: dict[str, str] = {}
    for mod_cfg in config.get("modules", {}).values():
        tf = mod_cfg.get("taxonomy_file", "")
        px = mod_cfg.get("taxonomy_prefix", "")
        if tf and px:
            pm[tf.replace(".json", "")] = px
    return pm


def leaf_label_lookup(taxonomies: dict[str, dict]) -> dict[str, str]:
    pm     = _prefix_map(taxonomies)
    lookup: dict[str, str] = {}
    for key, tax in taxonomies.items():
        if not tax:
            continue
        lookup.update(flatten_taxonomy(tax, pm.get(key, "")))
    return lookup


def leaf_description_lookup(taxonomies: dict[str, dict]) -> dict[str, str]:
    pm     = _prefix_map(taxonomies)
    lookup: dict[str, str] = {}
    for key, tax in taxonomies.items():
        if not tax:
            continue
        prefix = pm.get(key, "")
        # Resolve the root of the taxonomy tree.
        # When a prefix is set (e.g. "CR"), the taxonomy may be wrapped under
        # that top-level key OR it may be a flat dict keyed directly by L1 codes.
        # We try the prefix first; if the result has a "label" key it IS a node
        # (not a namespace wrapper), so fall back to using the whole dict as root.
        root = tax
        if prefix and prefix in tax:
            top = tax[prefix]
            if isinstance(top, dict) and "label" not in top:
                # top is a namespace wrapper whose values are L1 nodes
                root = top
            # else: top is itself an L1 node — root stays as the full tax dict
        for l1c, l1n in root.items():
            if not isinstance(l1n, dict):
                continue
            if "description" in l1n:
                lookup[l1c] = l1n["description"]
            for lc, ln in l1n.get("children", {}).items():
                if isinstance(ln, dict) and "description" in ln:
                    lookup[lc] = ln["description"]
    return lookup
