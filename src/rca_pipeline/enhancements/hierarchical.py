"""
hierarchical.py – Two-Step Hierarchical Classification
========================================================
Instead of asking the LLM to jump directly to a leaf code, this module
uses a two-step approach:

  Step 1: Classify the L1 group (small decision space)
  Step 2: Classify the L2 leaf within that group (narrowed decision space)

This narrows the search space for each step and may improve leaf-level
accuracy, at the cost of doubling LLM calls.

Usage:
  from hierarchical import classify_hierarchical

  results = await classify_hierarchical(
      batches, taxonomies, cfg,
      module_name="contact_reason",
      taxonomy_key="contact_reason",
      prefix="CR",
  )

Or integrate into the pipeline by setting:
  cfg.hierarchical_modules = ["contact_reason", "root_cause"]
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Optional

from ..config import RunConfig
from ..llm_client import process_batches_async
from ..taxonomy import taxonomy_to_rich_prompt

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Step 1 – L1 classification prompt
# ---------------------------------------------------------------------------
def _build_l1_system_prompt(
    taxonomy: dict,
    prefix: str,
    module_description: str = "",
) -> str:
    """Build a system prompt for L1-only classification."""
    l1_entries: list[str] = []
    for code, node in sorted(taxonomy.items()):
        if not isinstance(node, dict):
            continue
        label = node.get("label", code)
        desc = node.get("description", "")
        entry = f"  {code}: {label}"
        if desc:
            entry += f"\n    Description: {desc}"
        n_children = len(node.get("children", {}))
        entry += f"\n    ({n_children} leaf codes)"
        l1_entries.append(entry)

    taxonomy_block = "\n".join(l1_entries)

    return f"""You are an expert classifier for support tickets.
Your task: {module_description or 'Classify the support interaction.'}

## Step 1 — Group Classification
Classify each transcript into ONE of these top-level groups:

{taxonomy_block}

## Output Format
Return a JSON array — one object per record:
[
  {{
    "uid": "<record uid>",
    "l1_code": "<{prefix}N>",
    "l1_confidence": <0.0-1.0>
  }}
]

IMPORTANT: Return ONLY valid JSON. Every input uid MUST appear in output.
Choose the single best-fitting group. If uncertain, choose the closest match."""


# ---------------------------------------------------------------------------
# Step 2 – L2 classification prompt (narrowed to one L1 group)
# ---------------------------------------------------------------------------
def _build_l2_system_prompt(
    taxonomy: dict,
    l1_code: str,
    prefix: str,
    module_description: str = "",
) -> str:
    """Build a system prompt for L2 leaf classification within one L1 group."""
    l1_node = taxonomy.get(l1_code, {})
    group_label = l1_node.get("label", l1_code)
    children = l1_node.get("children", {})

    leaf_entries: list[str] = []
    for code, node in sorted(children.items()):
        if not isinstance(node, dict):
            continue
        label = node.get("label", code)
        desc = node.get("description", "")
        entry = f"  {code}: {label}"
        if desc:
            entry += f"\n    Description: {desc}"
        leaf_entries.append(entry)

    taxonomy_block = "\n".join(leaf_entries)

    return f"""You are an expert classifier for support tickets.
Your task: {module_description or 'Classify the support interaction.'}

## Step 2 — Leaf Classification
The transcript has been classified into group: {l1_code} ({group_label}).
Now assign the most specific LEAF code from this group:

{taxonomy_block}

## Output Format
Return a JSON array — one object per record:
[
  {{
    "uid": "<record uid>",
    "l2_code": "<{prefix}N.M>",
    "l2_confidence": <0.0-1.0>,
    "justification": "<1-2 sentence reasoning>"
  }}
]

IMPORTANT: Return ONLY valid JSON. Every input uid MUST appear in output.
Match on MEANING not just keywords. Use the descriptions to decide."""


_USER_TEMPLATE = """Classify the following support transcripts.

{records_json}

Return a JSON array with one object per record."""


# ---------------------------------------------------------------------------
# Core two-step classifier
# ---------------------------------------------------------------------------
async def classify_hierarchical(
    batches: list[list[dict[str, str]]],
    taxonomies: dict[str, dict],
    cfg: RunConfig,
    module_name: str = "contact_reason",
    taxonomy_key: str = "contact_reason",
    prefix: str = "CR",
    module_description: str = "",
    code_field: str | None = None,
    l2_prompt_builder: Optional[Callable[[str], str]] = None,
    l2_user_template: Optional[str] = None,
    l2_parse_fn: Optional[Callable] = None,
) -> list[dict[str, Any]]:
    """
    Two-step hierarchical classification.

    Parameters
    ----------
    batches : pre-batched records
    taxonomies : loaded taxonomy dict
    cfg : pipeline config
    module_name : name of the module
    taxonomy_key : key into the taxonomies dict
    prefix : taxonomy code prefix (CR, RC, etc.)
    module_description : task description for the LLM
    code_field : output field name for the code (default: {module_name}_primary_code)
    l2_prompt_builder : if provided, called as builder(taxonomy_prompt_str) to produce
        the L2 system prompt. The builder should be the generated module's
        _build_system_prompt function so the L2 step returns all pipeline-defined fields.
    l2_user_template : user prompt template to use in L2 step when builder is provided.
    l2_parse_fn : per-record validation/normalisation function for the L2 step.

    Returns
    -------
    List of enrichment dicts with uid, code, and all pipeline-defined fields.
    """
    if code_field is None:
        code_field = f"{module_name}_primary_code"

    taxonomy = taxonomies.get(taxonomy_key, {})
    if not taxonomy:
        logger.error("Taxonomy '%s' not found for hierarchical classification", taxonomy_key)
        return []

    # ----- Step 1: L1 classification -----
    logger.info("Hierarchical Step 1 — L1 classification for %s", module_name)
    l1_prompt = _build_l1_system_prompt(taxonomy, prefix, module_description)

    l1_results = await process_batches_async(
        batches, l1_prompt, _USER_TEMPLATE, cfg,
    )

    # Group records by their L1 assignment
    l1_by_uid: dict[str, str] = {}
    for r in l1_results:
        uid = str(r.get("uid", ""))
        l1_code = str(r.get("l1_code", "")).strip()
        if l1_code:
            l1_by_uid[uid] = l1_code

    # Build a map of uid → record text for Step 2
    uid_to_record: dict[str, dict] = {}
    for batch in batches:
        for rec in batch:
            uid_to_record[str(rec.get("uid", ""))] = rec

    # Group records by L1 code for batched Step 2 calls
    l1_groups: dict[str, list[dict]] = {}
    for uid, l1_code in l1_by_uid.items():
        l1_groups.setdefault(l1_code, []).append(uid_to_record.get(uid, {"uid": uid}))

    # ----- Step 2: L2 classification per L1 group -----
    logger.info(
        "Hierarchical Step 2 — L2 classification across %d groups",
        len(l1_groups),
    )

    all_l2_results: list[dict[str, Any]] = []

    async def _classify_l2_group(l1_code: str, records: list[dict]) -> list[dict]:
        """Classify all records in one L1 group at L2 level."""
        if l2_prompt_builder is not None:
            # Build a narrowed taxonomy containing only this L1 group, then
            # use the generated module's system prompt so all pipeline-defined
            # output fields are requested in one shot.
            narrowed_tax = {l1_code: taxonomy.get(l1_code, {})}
            narrowed_prompt = taxonomy_to_rich_prompt(narrowed_tax, prefix)
            l2_sys = l2_prompt_builder(narrowed_prompt)
            user_tmpl = l2_user_template or _USER_TEMPLATE
            parse_fn = l2_parse_fn
        else:
            l2_sys = _build_l2_system_prompt(taxonomy, l1_code, prefix, module_description)
            user_tmpl = _USER_TEMPLATE
            parse_fn = None

        # Re-batch the group records
        sub_batches = []
        for i in range(0, len(records), cfg.batch_size):
            sub_batches.append(records[i:i + cfg.batch_size])

        return await process_batches_async(
            sub_batches, l2_sys, user_tmpl, cfg, parse_fn=parse_fn,
        )

    # Run all L1 groups concurrently
    tasks = [
        _classify_l2_group(l1_code, records)
        for l1_code, records in l1_groups.items()
    ]
    group_results = await asyncio.gather(*tasks, return_exceptions=True)

    for i, (l1_code, _) in enumerate(l1_groups.items()):
        result = group_results[i]
        if isinstance(result, Exception):
            logger.error("Step 2 failed for L1=%s: %s", l1_code, result)
        else:
            all_l2_results.extend(result)

    # ----- Merge into final output format -----
    final: list[dict[str, Any]] = []
    l2_by_uid = {str(r.get("uid", "")): r for r in all_l2_results}

    # P9 fix: build O(1) lookup for L1 confidence instead of O(n) scan per uid
    l1_conf_by_uid: dict[str, float] = {
        str(r.get("uid", "")): r.get("l1_confidence", -1)
        for r in l1_results
    }

    for uid, l1_code in l1_by_uid.items():
        l2_result = l2_by_uid.get(uid, {})

        if l2_prompt_builder is not None:
            # Builder path: L2 result uses the native code field name and
            # carries all pipeline-defined fields.
            l2_code = str(l2_result.get(code_field, "")).strip()
        else:
            l2_code = str(l2_result.get("l2_code", "")).strip()

        # Fall back to L1 code if L2 classification failed
        final_code = l2_code if l2_code and "." in l2_code else l1_code

        entry: dict[str, Any] = {
            "uid": uid,
            code_field: final_code,
            f"{module_name}_l1_code": l1_code,
            f"{module_name}_hierarchical": True,
        }

        if l2_prompt_builder is not None:
            # Carry through all fields the module returned (skip uid and the
            # code field which we've already set above).
            for k, v in l2_result.items():
                if k not in ("uid", code_field):
                    entry[k] = v
        else:
            # Original path: carry through L2 justification only
            if l2_result.get("justification"):
                entry[f"{module_name}_justification"] = l2_result["justification"]

        # Confidence: combine L1 and L2 when both are available
        l1_conf = l1_conf_by_uid.get(uid, -1)
        l2_conf = l2_result.get("l2_confidence", -1)
        try:
            l1_c = float(l1_conf)
            l2_c = float(l2_conf)
            if l1_c >= 0 and l2_c >= 0:
                entry["_confidence"] = round(l1_c * l2_c, 4)  # joint probability
            elif l2_c >= 0:
                entry["_confidence"] = round(l2_c, 4)
            elif l1_c >= 0:
                entry["_confidence"] = round(l1_c, 4)
        except (ValueError, TypeError):
            pass

        final.append(entry)

    # Handle records that didn't get an L1 assignment
    all_uids = {str(rec.get("uid", "")) for batch in batches for rec in batch}
    missing = all_uids - set(l1_by_uid.keys())
    if missing:
        logger.warning(
            "Hierarchical: %d records missing L1 assignment — stubbing",
            len(missing),
        )
        for uid in missing:
            final.append({
                "uid": uid,
                code_field: "",
                f"{module_name}_hierarchical": True,
                "_error": "no_l1_assignment",
            })

    logger.info(
        "Hierarchical classification complete: %s — %d records, %d L1 groups",
        module_name, len(final), len(l1_groups),
    )
    return final


# ---------------------------------------------------------------------------
# Wrapper that auto-detects taxonomy from pipeline config
# ---------------------------------------------------------------------------
def _load_generated_module(module_name: str):
    """Load <workspace>/generated/modules/<module_name>.py by path.

    Generated modules are not on sys.path (pipeline.py loads them by file
    location too), so importlib.import_module(module_name) cannot find them.
    """
    import importlib.util

    from rca_pipeline import workspace
    path = workspace.generated_dir() / "modules" / f"{module_name}.py"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found — run `rca build`")
    spec = importlib.util.spec_from_file_location(f"_generated_{module_name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def run_hierarchical_module(
    module_name: str,
    batches: list[list[dict[str, str]]],
    taxonomies: dict[str, dict],
    cfg: RunConfig,
) -> list[dict[str, Any]]:
    """
    Auto-configured hierarchical classification.
    Reads prefix, taxonomy_key, etc. from pipeline_config.json.
    Pulls _build_system_prompt / _USER_PROMPT_TEMPLATE / _validate_record from
    the generated module so the L2 step returns all pipeline-defined fields.
    """
    import json as _json
    from pathlib import Path

    from rca_pipeline import workspace
    config_path = workspace.generated_dir() / "pipeline_config.json"
    mod_cfg: dict = {}
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            pipeline_cfg = _json.load(f)
        mod_cfg = pipeline_cfg.get("modules", {}).get(module_name, {})

    prefix = mod_cfg.get("taxonomy_prefix", module_name[:2].upper())
    taxonomy_key = mod_cfg.get("taxonomy_key", module_name)
    description = mod_cfg.get("description", "")

    # Read the primary code field name from config; fall back to pattern default.
    # This matters for modules like customer_effort whose code field is
    # "effort_primary_code", not "customer_effort_primary_code".
    code_field = mod_cfg.get("code_field") or f"{module_name}_primary_code"

    # Extract prompt builder from the generated module so the L2 step uses
    # the full pipeline-defined output fields instead of the minimal default.
    l2_prompt_builder = None
    l2_user_template = None
    l2_parse_fn = None
    try:
        # Loaded fresh from the workspace file, so it always reflects the last build.
        mod = _load_generated_module(module_name)
        l2_prompt_builder = getattr(mod, "_build_system_prompt", None)

        # Fallback for modules generated before _build_system_prompt existed:
        # use the static _SYSTEM_PROMPT so the L2 step still requests all
        # pipeline-defined fields rather than falling back to the minimal
        # default that only asks for code + justification.
        if l2_prompt_builder is None:
            _static = getattr(mod, "_SYSTEM_PROMPT", None)
            if _static:
                logger.info(
                    "Hierarchical: '%s' using _SYSTEM_PROMPT fallback for L2 step",
                    module_name,
                )
                l2_prompt_builder = lambda _tax, _p=_static: _p

        l2_user_template  = getattr(mod, "_USER_PROMPT_TEMPLATE", None)
        l2_parse_fn       = getattr(mod, "_validate_record", None)

        if l2_prompt_builder:
            logger.info(
                "Hierarchical: '%s' L2 step will use full pipeline-defined prompt", module_name,
            )
        else:
            logger.warning(
                "Hierarchical: '%s' has no _build_system_prompt — L2 step uses minimal "
                "default (only code + justification). Regenerate with: "
                "rca build --force %s",
                module_name, module_name,
            )
    except Exception as e:
        logger.warning(
            "Could not import '%s' for L2 prompt builder — falling back to default L2 prompt: %s",
            module_name, e,
        )

    return await classify_hierarchical(
        batches=batches,
        taxonomies=taxonomies,
        cfg=cfg,
        module_name=module_name,
        taxonomy_key=taxonomy_key,
        prefix=prefix,
        module_description=description,
        code_field=code_field,
        l2_prompt_builder=l2_prompt_builder,
        l2_user_template=l2_user_template,
        l2_parse_fn=l2_parse_fn,
    )
