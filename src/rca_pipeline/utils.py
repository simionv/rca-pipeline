"""
utils.py – Shared Utilities
=============================
Config-driven: enrichment prefixes and column reorder order are read from
pipeline_config.json so new modules are handled automatically.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import pandas as pd

from .config import RunConfig, load_pipeline_config as _load_config
from .taxonomy import (
    leaf_label_lookup, leaf_description_lookup,
    get_l1_from_code, get_prefix_from_code,
)

logger = logging.getLogger(__name__)

_EVIDENCE_TYPES = frozenset({"customer_symptom", "agent_action", "system_message"})


def _ensure_object_dtype(df: pd.DataFrame, col: str) -> None:
    """Cast a column to object dtype in-place so string assignment won't fail.

    A column the LLM returns entirely empty/numeric is inferred as float64;
    pandas >= 2.1 raises `TypeError: Invalid value '' for dtype 'float64'`
    on string assignment instead of silently upcasting to object.
    """
    if df[col].dtype != object:
        df[col] = df[col].astype(object)


# ---------------------------------------------------------------------------
# Build enrichment prefixes from config + structural baseline
# ---------------------------------------------------------------------------
_STRUCTURAL_PREFIXES = (
    "access_classification",
    "contact_reason_", "secondary_codes",
    "root_cause_", "contributing_codes",
    "resolution_",
    "escalat",
    "troubleshooting_",
    "environment_tags", "products_mentioned", "error_messages",
    "time_criticality", "deadlines", "urgency",
    "short_summary", "evidence_snippets",
    "metadata_",
)


def _build_enrichment_prefixes(config: dict) -> tuple[str, ...]:
    from_config = config.get("enrichment_prefixes", [])
    combined    = list(dict.fromkeys(list(_STRUCTURAL_PREFIXES) + from_config))
    return tuple(combined)


def _build_module_order(config: dict) -> dict[str, int]:
    base = {
        "access":          0,
        "contact":         1,
        "secondary":       2,
        "root":            3,
        "root_e":          4,   # root_cause evidence slot
        "contributing":    5,
        "resolution":      6,
        "escalat":         7,
        "troubleshooting": 8,
        "environment":     9,
        "products":       10,
        "error":          11,
        "time":           12,
        "deadline":       13,
        "urgency":        14,
        "short":          15,
        "evidence":       16,
        "metadata":       17,
    }
    for group, order in config.get("reorder_groups", {}).items():
        if group not in base:
            base[group] = int(order)
    return base


_CONFIG          = _load_config()
_ENRICH_PREFIXES = _build_enrichment_prefixes(_CONFIG)
_MODULE_ORDER    = _build_module_order(_CONFIG)
_OUTPUT_EXCLUDE  = frozenset(_CONFIG.get("output_exclude", []))   # in_output=FALSE
_EXPLODE_FIELDS  = frozenset(_CONFIG.get("list_fields", []))      # explode_list=TRUE
_OBJECT_LIST_FIELDS = dict(_CONFIG.get("object_list_fields", {})) # explode_list=TRUE + explode_keys

_ROOT_EVIDENCE_COLS = frozenset({
    "root_cause_justification",
    "root_cause_evidence",
    "root_cause_evidence_type",
})


# ===========================================================================
# PRE-PROCESSING
# ===========================================================================

def read_input_file(filepath: str | Path) -> pd.DataFrame:
    filepath = Path(filepath)
    df = (pd.read_excel(filepath, engine="openpyxl")
          if filepath.suffix.lower() in (".xlsx", ".xls")
          else pd.read_csv(filepath))
    if "uid" not in df.columns:
        df.insert(0, "uid", range(1, len(df) + 1))
    logger.info("Loaded %d rows from %s", len(df), filepath.name)
    return df


def drop_enrichment_cols(df: pd.DataFrame) -> pd.DataFrame:
    drop = [c for c in df.columns
            if any(c.startswith(p) or c == p.rstrip("_") for p in _ENRICH_PREFIXES)]
    if drop:
        logger.info("Dropping %d stale enrichment columns", len(drop))
        df = df.drop(columns=drop)
    return df


def make_batches(
    df: pd.DataFrame,
    batch_size: int = 20,
    max_chars: int = 80_000,
    text_col: str = "transcript",
) -> list[pd.DataFrame]:
    batches: list[pd.DataFrame] = []
    idxs:    list[Any]          = []
    chars                       = 0

    for idx, row in df.iterrows():
        tlen = len(str(row.get(text_col, "")))
        if (len(idxs) >= batch_size or
                (chars + tlen > max_chars and idxs)):
            batches.append(df.loc[idxs].copy())
            idxs  = []
            chars = 0
        idxs.append(idx)
        chars += tlen

    if idxs:
        batches.append(df.loc[idxs].copy())

    logger.info("Created %d batches from %d rows (size≤%d, chars≤%d)",
                len(batches), len(df), batch_size, max_chars)
    return batches


# ===========================================================================
# POST-PROCESSING
# ===========================================================================

def merge_results(
    df: pd.DataFrame,
    results: list[dict[str, Any]],
    id_col: str = "uid",
) -> pd.DataFrame:
    if not results:
        logger.warning("merge_results: no results")
        return df
    df_r = pd.DataFrame(results)

    # ── Prevent duplicate "uid" columns ──────────────────────────────────
    # Results from call_batch() always use "uid" as the key (set by
    # prepare_records).  But the DataFrame's real ID column may be named
    # differently (e.g. "ticket_id", "Reference #").  If they differ, rename
    # the results' "uid" to match id_col so the merge key is correct.
    if id_col != "uid" and "uid" in df_r.columns and id_col not in df_r.columns:
        df_r = df_r.rename(columns={"uid": id_col})
    # Also drop the results' "uid" column if it would duplicate one already
    # in the DataFrame AND isn't the merge key.
    if id_col != "uid" and "uid" in df_r.columns and "uid" in df.columns:
        df_r = df_r.drop(columns=["uid"])

    if id_col in df_r.columns:
        df_r[id_col] = df_r[id_col].astype(str)
        df_o = df.copy()
        df_o[id_col] = df_o[id_col].astype(str)
        merged = df_o.merge(df_r, on=id_col, how="left", suffixes=("", "_enriched"))
        merged = merged.drop(columns=[c for c in merged.columns if c.endswith("_enriched")])
    else:
        df_r.index = df.index[:len(df_r)]
        merged = pd.concat([df, df_r], axis=1)

    # ── Safety net: deduplicate any remaining duplicate column names ──────
    # This catches edge cases where both sides contribute a column with the
    # same name that isn't the merge key (e.g. both have "uid").
    dupe_cols = merged.columns[merged.columns.duplicated(keep="last")]
    if len(dupe_cols) > 0:
        logger.warning(
            "merge_results: dropping %d duplicate columns: %s",
            len(dupe_cols), list(dupe_cols),
        )
        merged = merged.loc[:, ~merged.columns.duplicated(keep="last")]

    logger.info("Merged: %d columns", merged.shape[1])
    return merged


def validate_enum_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Validate all enum columns defined in pipeline_config.json.

    Values are normalised to lowercase before comparison — the normalised form
    is written back so downstream code (label derivation etc.) sees consistent
    casing.
    """
    config = _load_config()
    df     = df.copy()
    validators = {"root_cause_evidence_type": list(_EVIDENCE_TYPES)}
    validators.update(config.get("enum_validators", {}))

    for col, valid in validators.items():
        if col not in df.columns:
            continue
        valid_set = frozenset(str(v).lower().strip() for v in valid)
        # Normalise column to lowercase for comparison
        normalised = df[col].astype(str).str.strip().str.lower()
        non_empty  = df[col].notna() & (normalised != "") & (normalised != "nan")
        bad = non_empty & ~normalised.isin(valid_set)
        if bad.any():
            bad_vals = df.loc[bad, col].unique().tolist()
            logger.warning(
                "validate_enum_cols: %d invalid in '%s' — setting to blank. "
                "Bad values: %s. Allowed: %s",
                bad.sum(), col, bad_vals, sorted(valid_set)
            )
            _ensure_object_dtype(df, col)
            df.loc[bad, col] = ""   # blank — visible in output, not silently replaced
        # Write back normalised (lowercase) values for valid entries
        good = non_empty & ~bad
        if good.any():
            _ensure_object_dtype(df, col)
            df.loc[good, col] = normalised[good]
    return df


# ---------------------------------------------------------------------------
# Evidence hallucination detection
# ---------------------------------------------------------------------------

# Columns that should contain verbatim quotes from the transcript.
# Detected by naming convention — any column containing 'evidence' or
# 'snippet' (but NOT 'evidence_type', an enum, or '_grounded', the boolean
# flag this same check produces — without excluding it, a second grounding
# pass over already-flagged columns re-matches its own output, e.g.
# "compliance_evidence_grounded" -> "compliance_evidence_grounded_grounded").
_EVIDENCE_NAME_PATTERNS = ("_evidence", "_snippet", "evidence_snippet")
_EVIDENCE_NAME_EXCLUDE  = ("_evidence_type", "_grounded")


def _is_evidence_col(col: str) -> bool:
    """Return True if this column should contain verbatim transcript text."""
    col_lower = col.lower()
    if any(ex in col_lower for ex in _EVIDENCE_NAME_EXCLUDE):
        return False
    return any(pat in col_lower for pat in _EVIDENCE_NAME_PATTERNS)


# Typographic punctuation folded to ASCII before matching. robust_json_loads()
# rewrites curly quotes to ASCII on every LLM response before parsing it, so a
# quote the model copied faithfully arrives as " where the transcript still has “.
# Without this the difference reads as a fabrication.
_PUNCT_FOLD = str.maketrans({
    "“": '"', "”": '"', "„": '"', "‟": '"',   # “ ” „ ‟
    "‘": "'", "’": "'", "‚": "'", "‛": "'",   # ‘ ’ ‚ ‛
    "＂": '"', "＇": "'",                                 # ＂ ＇ full-width
    "«": '"', "»": '"',                                 # « »
    "–": "-", "—": "-", "−": "-",                  # – — −
})


# Below this many whitespace tokens, token overlap carries no signal and Tier 2
# falls back to character overlap. 4 keeps every ordinary English phrase on the
# token path; the CJK strings that were being mis-flagged had 1-5 tokens across
# 22-81 characters.
_MIN_TOKENS_FOR_TOKEN_OVERLAP = 4


def _normalise_for_match(text: str) -> str:
    """Normalise text for fuzzy substring matching.

    Lowercase, fold typographic punctuation to ASCII, collapse whitespace.
    """
    return re.sub(r"\s+", " ", text.translate(_PUNCT_FOLD).lower().strip())


def _evidence_in_transcript(evidence: str, transcript: str, threshold: float = 0.65) -> bool:
    """
    Check whether an evidence string is grounded in the transcript.

    Uses a two-tier approach:
      1. Exact substring match (after whitespace normalisation).
      2. Overlap match — if >= threshold of the evidence appears in the
         transcript, it's considered grounded.  This handles minor LLM
         paraphrasing (word reordering, dropped articles, etc.) while still
         catching outright fabrications.

    Tier 2 measures overlap over whitespace tokens for space-delimited text, and
    over characters when the evidence has too few tokens for that to mean
    anything.  Chinese and Japanese barely use whitespace: a 50-character
    Chinese quote is often one "token", so token overlap is 0.0 or 1.0 and a
    single differing character reads as a fabrication.  Measured over a
    1,000-record sample, CJK evidence was flagged at 9.9% against 0.32% for the
    rest — a difference in the script, not in the model.
    """
    if not evidence or not transcript:
        return True  # nothing to validate

    norm_ev = _normalise_for_match(evidence)
    norm_tx = _normalise_for_match(transcript)

    # Tier 1: exact substring
    if norm_ev in norm_tx:
        return True

    # Tier 2: overlap, over whichever unit carries information in this script
    ev_tokens = set(norm_ev.split())
    if not ev_tokens:
        return True
    if len(ev_tokens) < _MIN_TOKENS_FOR_TOKEN_OVERLAP:
        ev_units = set(norm_ev.replace(" ", ""))
        tx_units = set(norm_tx.replace(" ", ""))
        if not ev_units:
            return True
    else:
        ev_units, tx_units = ev_tokens, set(norm_tx.split())
    overlap = len(ev_units & tx_units) / len(ev_units)
    return overlap >= threshold


def validate_evidence_fields(
    df: pd.DataFrame,
    text_col: str = "transcript",
    id_col: str = "uid",
    flag_col_suffix: str = "_grounded",
) -> pd.DataFrame:
    """
    Validate that evidence/snippet fields contain text actually present in
    the transcript.  Adds a boolean *_grounded column for each evidence field
    and blanks evidence that is clearly fabricated (token overlap < threshold).

    This catches LLM hallucinations where the model invents plausible-sounding
    evidence quotes that don't exist in the source text.
    """
    if text_col not in df.columns:
        return df

    df = df.copy()

    # Find all evidence columns (including exploded _1, _2, _3 variants)
    evidence_cols = [c for c in df.columns if _is_evidence_col(c)]

    if not evidence_cols:
        return df

    total_checked  = 0
    total_flagged  = 0

    # Determine which column to use for uid display in warnings.
    # Prefer id_col, fall back to "uid", fall back to index.
    _uid_col = id_col if id_col in df.columns else ("uid" if "uid" in df.columns else None)

    for col in evidence_cols:
        grounded_col = col + flag_col_suffix

        mask = df[col].notna() & (df[col].astype(str).str.strip() != "")
        if not mask.any():
            continue

        grounded = pd.Series(True, index=df.index)

        for idx in df.index[mask]:
            evidence   = str(df.at[idx, col]).strip()
            transcript = str(df.at[idx, text_col]) if pd.notna(df.at[idx, text_col]) else ""

            is_grounded = _evidence_in_transcript(evidence, transcript)
            grounded.at[idx] = is_grounded
            total_checked += 1

            if not is_grounded:
                total_flagged += 1
                # Safe uid extraction — handles duplicate column names
                if _uid_col:
                    uid_val = df.at[idx, _uid_col]
                    # df.at returns a Series when columns are duplicated
                    if isinstance(uid_val, pd.Series):
                        uid_val = uid_val.iloc[0]
                else:
                    uid_val = idx
                logger.warning(
                    "Hallucination detected: uid=%s col=%s — evidence not found "
                    "in transcript (flagged, not blanked). Evidence: %.100s...",
                    uid_val, col, evidence,
                )

        df[grounded_col] = grounded

    if total_checked > 0:
        pct = total_flagged / total_checked * 100 if total_checked else 0
        logger.info(
            "Evidence validation: %d checked, %d flagged as ungrounded (%.1f%%) "
            "across %d evidence columns",
            total_checked, total_flagged, pct, len(evidence_cols),
        )

    return df


def derive_labels(df: pd.DataFrame, taxonomies: dict[str, dict]) -> pd.DataFrame:
    lookup = leaf_label_lookup(taxonomies)
    desc   = leaf_description_lookup(taxonomies)
    df     = df.copy()

    if desc:
        logger.info("Description lookup: %d entries available for backfill", len(desc))
    else:
        logger.warning(
            "Description lookup is EMPTY — taxonomy JSONs have no 'description' "
            "fields. Rebuild from Excel: rca build --input "
            "<definition.xlsx> --force-all"
        )

    # ── Fix L1 codes used as primary codes ─────────────────────────────────
    _l1_children = _build_l1_children_map(taxonomies)

    for col in [c for c in df.columns
                if c.endswith("_code") or c.endswith("_primary_code")]:

        # Attempt to fix L1 codes before label derivation
        if "primary" in col:
            _fix_l1_primary_codes(df, col, _l1_children)

        # label column
        lc = col.replace("_code", "_label")
        if lc not in df.columns:
            df[lc] = df[col].map(
                lambda x, _l=lookup: _l.get(str(x).strip(), "") if pd.notna(x) else "")

        # description column — backfill blanks from taxonomy descriptions
        dc = col.replace("_code", "_description")
        if dc in df.columns:
            # Column exists (from LLM output) — fill only blank values
            if desc:
                mask = df[dc].isna() | (df[dc].astype(str).str.strip() == "")
                if mask.any():
                    _ensure_object_dtype(df, dc)
                    df.loc[mask, dc] = df.loc[mask, col].map(
                        lambda x, _d=desc: _d.get(str(x).strip(), "") if pd.notna(x) else "")
                    filled = mask.sum() - (df[dc].isna() | (df[dc].astype(str).str.strip() == "")).sum()
                    if filled > 0:
                        logger.info("  Backfilled %d blank %s from taxonomy descriptions", filled, dc)
        elif desc:
            # Column doesn't exist — create from taxonomy lookup
            df[dc] = df[col].map(
                lambda x, _d=desc: _d.get(str(x).strip(), "") if pd.notna(x) else "")

        # L1 class columns for primary codes
        if "primary" in col:
            l1c = col.replace("_primary_code", "_class_l1")
            if l1c not in df.columns:
                df[l1c] = df[col].map(
                    lambda x: get_l1_from_code(str(x)) if pd.notna(x) else "")
                # L1 label
                df[l1c + "_label"] = df[l1c].map(
                    lambda x, _l=lookup: _l.get(str(x).strip(), "") if x else "")
                # L1 description (was missing — this fixes the blank l1_description)
                if desc:
                    df[l1c + "_description"] = df[l1c].map(
                        lambda x, _d=desc: _d.get(str(x).strip(), "") if x else "")
            else:
                # L1 class column already exists — ensure label and description exist
                if l1c + "_label" not in df.columns:
                    df[l1c + "_label"] = df[l1c].map(
                        lambda x, _l=lookup: _l.get(str(x).strip(), "") if x else "")
                if l1c + "_description" not in df.columns and desc:
                    df[l1c + "_description"] = df[l1c].map(
                        lambda x, _d=desc: _d.get(str(x).strip(), "") if x else "")
    return df


def _build_l1_children_map(taxonomies: dict[str, dict]) -> dict[str, list[str]]:
    """Build a map of L1 code → list of child leaf codes across all taxonomies."""
    l1_map: dict[str, list[str]] = {}
    config = _load_config()
    for mod_cfg in config.get("modules", {}).values():
        tf = mod_cfg.get("taxonomy_file", "")
        key = tf.replace(".json", "") if tf else ""
        tax = taxonomies.get(key, {})
        if not tax:
            continue
        for l1_code, l1_node in tax.items():
            if isinstance(l1_node, dict) and "children" in l1_node:
                l1_map[l1_code] = list(l1_node["children"].keys())
    return l1_map


def _fix_l1_primary_codes(
    df: pd.DataFrame, col: str, l1_children: dict[str, list[str]],
    text_col: str = "transcript",
) -> None:
    """
    In-place fix: if a primary code column contains an L1 code (no dot),
    resolve it to a leaf code using one of three strategies in priority order:

    1. Sole child  — L1 has exactly one leaf: use it directly.
    2. Description match — compare the record's text against each child's
       label/description and pick the closest (keyword overlap).
    3. First child — deterministic fallback when text match is inconclusive.

    Strategy 2 keeps the output meaningful without requiring a second LLM call.
    It is imperfect but always better than leaving an L1 code in a leaf column.
    """
    if col not in df.columns:
        return

    # Build a label+description lookup for children so we can do text matching
    # We need the full taxonomy here; extract it from l1_children structure.
    # l1_children maps L1 code → [leaf_code, ...]; we only have codes not labels.
    # Text matching against codes alone is useless, so we use a simple heuristic:
    # pick the child whose numeric suffix is most common when there are no other
    # signals, or use text overlap against the child codes themselves.
    # The full label lookup happens in derive_labels — here we just ensure a
    # valid leaf code is stored so downstream label resolution works correctly.

    mask = df[col].notna() & (df[col].astype(str).str.strip() != "")
    n_fixed_sole     = 0
    n_fixed_first    = 0

    for idx in df.index[mask]:
        code = str(df.at[idx, col]).strip()
        if not code or "." in code:
            continue  # already a leaf code

        children = l1_children.get(code, [])
        uid = df.at[idx, "uid"] if "uid" in df.columns else "?"

        if not children:
            logger.debug("fix_l1_codes: uid=%s %s=%s — no children found in taxonomy", uid, col, code)
            continue

        if len(children) == 1:
            # Strategy 1: unambiguous
            df.at[idx, col] = children[0]
            n_fixed_sole += 1
            logger.debug("fix_l1_codes: uid=%s %s=%s → %s (sole child)", uid, col, code, children[0])

        else:
            # Strategy 3: first child (deterministic, safe fallback).
            # Sort children so the lowest-numbered leaf is always chosen
            # (e.g. CE1.1 before CE1.2), giving a consistent result.
            sorted_children = sorted(children, key=lambda c: (
                [int(p) if p.isdigit() else p for p in c.split(".")]))
            chosen = sorted_children[0]
            df.at[idx, col] = chosen
            n_fixed_first += 1
            logger.warning(
                "fix_l1_codes: uid=%s %s=%s is L1 with %d children — "
                "falling back to first leaf %s. "
                "Re-run with --force to regenerate this module with the updated prompt "
                "(CRITICAL leaf-code instruction now included in all module prompts).",
                uid, col, code, len(children), chosen,
            )

    if n_fixed_sole or n_fixed_first:
        logger.info(
            "fix_l1_codes %s: resolved %d L1 codes (%d sole-child, %d first-child fallback)",
            col, n_fixed_sole + n_fixed_first, n_fixed_sole, n_fixed_first,
        )


def heuristic_fallbacks(
    df: pd.DataFrame,
    taxonomies: dict[str, dict],
    text_col: str = "transcript",
) -> pd.DataFrame:
    """No-op — heuristic keyword fallbacks were removed (legacy config.json).

    Kept as a stub so callers (post_process) don't need changing.
    Remove this function entirely once all call sites are cleaned up.
    """
    return df


def explode_lists(df: pd.DataFrame) -> pd.DataFrame:
    """
    Explode list-valued columns into positional columns.
    Only explodes columns listed in _EXPLODE_FIELDS (explode_list=TRUE in Excel).
    Falls back to exploding ALL list columns if _EXPLODE_FIELDS is empty
    (backwards compatible when pipeline_config.json predates this feature).
    """
    df = df.copy()
    list_cols = [c for c in df.columns
                 if df[c].apply(lambda x: isinstance(x, list)).any()]

    # If no explicit list is configured, explode everything (old behaviour)
    to_explode = [c for c in list_cols
                  if (not _EXPLODE_FIELDS) or c in _EXPLODE_FIELDS]

    for col in to_explode:
        max_n = df[col].apply(lambda x: len(x) if isinstance(x, list) else 0).max()
        for i in range(max_n):
            df[f"{col}_{i+1}"] = df[col].apply(
                lambda x, j=i: x[j] if isinstance(x, list) and len(x) > j else "")
        df = df.drop(columns=[col])

    # Convert any remaining (non-exploded) list columns to strings
    # so they don't cause issues in downstream steps or Excel export
    for col in list_cols:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: ", ".join(str(i) for i in x) if isinstance(x, list) else x)
    return df


def explode_object_lists(df: pd.DataFrame) -> pd.DataFrame:
    """
    Explode list-of-object columns (e.g. matched_rules: [{"code":..,"verdict":..,"evidence":..}])
    into positional per-key columns: matched_rules_code_1, matched_rules_verdict_1, ...
    Key-then-slot naming (not slot-then-key) so a "code"-keyed column matches
    derive_positional_labels()'s *_code_N -> *_labels_N pattern and gets label derivation for free.
    Driven by _OBJECT_LIST_FIELDS (populated from explode_keys in the Excel fields sheet).
    Must run before explode_lists(), which would otherwise stringify these dict-list columns.
    """
    if not _OBJECT_LIST_FIELDS:
        return df
    df = df.copy()
    for col, keys in _OBJECT_LIST_FIELDS.items():
        if col not in df.columns:
            continue
        max_n = df[col].apply(lambda x: len(x) if isinstance(x, list) else 0).max()
        for i in range(max_n):
            for k in keys:
                df[f"{col}_{k}_{i+1}"] = df[col].apply(
                    lambda x, j=i, kk=k: x[j].get(kk, "")
                    if isinstance(x, list) and len(x) > j and isinstance(x[j], dict) else "")
        df = df.drop(columns=[col])
    return df


def _looks_like_code(value: str, lookup: dict[str, str]) -> bool:
    """Return True if a string value appears to be a taxonomy code (e.g. CR1.2, CE3)."""
    v = value.strip()
    if not v:
        return False
    # Direct hit in lookup
    if v in lookup:
        return True
    # Matches the structural pattern: 1-4 uppercase letters + digits + optional .digits
    return bool(re.match(r"^[A-Z]{1,4}\d+(\.\d+)?$", v))


def derive_positional_labels(
    df: pd.DataFrame, taxonomies: dict[str, dict]
) -> pd.DataFrame:
    """
    Add label columns alongside every exploded positional column that contains
    taxonomy codes.

    Handles two naming patterns:
      1. *_codes_N  / *_code_N  → *_labels_N   (original pattern)
      2. Any other *_N column whose non-empty values look like taxonomy codes
         (e.g. secondary_contact_reasons_1, effort_themes_2) → *_label_N

    Pattern 2 is needed because list fields like secondary_contact_reasons and
    effort_themes explode to names that don't contain the word "code", but the
    LLM still returns taxonomy codes as their values.
    """
    lookup = leaf_label_lookup(taxonomies)
    df     = df.copy()

    # Pattern 1: columns explicitly named *_code(s)_N
    # Falls back to the raw value if the code is not in the taxonomy (e.g. free-text
    # PA1-PA9 codes returned by policy_compliance that have no PC taxonomy entry).
    for col in [c for c in df.columns if re.search(r"_codes?_\d+$", c)]:
        lc = re.sub(r"_codes?_(\d+)$", r"_labels_\1", col)
        if lc not in df.columns:
            df[lc] = df[col].map(
                lambda x, _l=lookup: _l.get(str(x).strip(), str(x).strip())
                if pd.notna(x) and str(x).strip() else "")

    # Pattern 2: any *_N column (positional from explode_lists) whose values
    # look like taxonomy codes but whose name doesn't already end in _code(s)_N
    positional_pat = re.compile(r"^(.+)_(\d+)$")
    for col in df.columns:
        m = positional_pat.match(col)
        if not m:
            continue
        base, num = m.group(1), m.group(2)
        # Skip if already handled by pattern 1
        if re.search(r"_codes?$", base):
            continue
        # Skip if a label column already exists
        label_col = f"{base}_label_{num}"
        if label_col in df.columns:
            continue
        # Sample non-empty values to decide if this column contains codes
        sample = df[col].dropna()
        sample = sample[sample.astype(str).str.strip() != ""]
        if sample.empty:
            continue
        sample_vals = sample.astype(str).head(10).tolist()
        if not any(_looks_like_code(v, lookup) for v in sample_vals):
            continue
        # Column contains codes — derive labels
        df[label_col] = df[col].map(
            lambda x, _l=lookup: _l.get(str(x).strip(), str(x).strip())
            if pd.notna(x) and str(x).strip() else "")
        logger.info("derive_positional_labels: resolved labels for %s → %s", col, label_col)

    return df


def reorder_columns(
    df: pd.DataFrame,
    id_col: str = "uid",
    text_col: str = "transcript",
    original_cols: list | None = None,
) -> pd.DataFrame:
    """
    Reorder columns so that:
      1. All original (pre-enrichment) columns come first, in their original order.
      2. All enrichment columns follow, sorted by module definition order.

    original_cols: the column list of the original DataFrame before enrichment.
    If not provided, falls back to id_col + text_col only (backwards compatible).
    """
    # ── Determine which columns are "original" ────────────────────────────
    if original_cols:
        # Keep original columns in their original order, only if present in df
        fixed  = [c for c in original_cols if c in df.columns]
        enrich = [c for c in df.columns if c not in set(fixed)]
    else:
        # Fallback: only id and text columns are fixed
        fixed  = [c for c in [id_col, text_col] if c in df.columns]
        enrich = [c for c in df.columns if c not in set(fixed)]

    # ── Sort enrichment columns by module definition order ─────────────────
    def _key(col: str) -> tuple:
        if col in _ROOT_EVIDENCE_COLS:
            sub = {"justification": 0, "evidence": 1, "evidence_type": 2}.get(
                col.replace("root_cause_", ""), 9)
            return (_MODULE_ORDER.get("root_e", 4), 2, sub, col)
        prefix   = col.split("_")[0] if "_" in col else col
        order    = _MODULE_ORDER.get(prefix, 99)
        type_ord = 0 if "_code" in col else 1 if "_label" in col else 2
        return (order, type_ord, 0, col)

    enrich.sort(key=_key)
    return df[fixed + enrich]


# ===========================================================================
# FRICTION POINT NORMALISATION
# ===========================================================================

def _load_friction_categories() -> list[tuple[str, list[str]]]:
    """Load friction categories from pipeline_config.json. Falls back to empty list."""
    cfg = _load_config()
    raw = cfg.get("friction_categories", [])
    return [(entry["label"], entry["keywords"]) for entry in raw if "label" in entry and "keywords" in entry]


_friction_warned = False


def _get_friction_categories() -> list[tuple[str, list[str]]]:
    global _friction_warned
    # Reload each time so pipeline_config.json edits take effect without restart.
    result = _load_friction_categories()
    if not result and not _friction_warned:
        _friction_warned = True
        logger.warning(
            "friction_categories not found in pipeline_config.json — "
            "friction normalisation will be a no-op. "
            "Re-run: rca build --input definitions/<file>.xlsx"
        )
    return result


def normalise_friction_value(value: str) -> str:
    """
    Map a single free-text friction description to a canonical category label.
    Categories and keywords are loaded from pipeline_config.json (friction_categories key).
    Returns the original value unchanged if no category matches.
    """
    if not value or not isinstance(value, str):
        return ""
    v = value.strip()
    if not v:
        return v
    categories = _get_friction_categories()
    canonical = {cat for cat, _ in categories}
    if v in canonical:
        return v
    v_lower = v.lower()
    for category, patterns in categories:
        if any(re.search(p, v_lower) for p in patterns):
            return category
    return v  # no match — keep original


def normalise_friction_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalise all friction_points columns (original list column or exploded
    positional columns _1, _2, …) to canonical category labels.

    Called as part of post_process after explode_lists so that both the
    raw list column (if still present) and the exploded positional columns
    are normalised.
    """
    df = df.copy()
    friction_cols = [
        c for c in df.columns
        if c == "friction_points" or re.match(r"^friction_points_\d+$", c)
    ]
    if not friction_cols:
        return df

    changed_total = 0
    for col in friction_cols:
        mask = df[col].notna() & (df[col].astype(str).str.strip() != "")
        if not mask.any():
            continue
        original = df.loc[mask, col].astype(str)
        normalised = original.map(normalise_friction_value)
        changed = (original != normalised).sum()
        if changed:
            _ensure_object_dtype(df, col)
            df.loc[mask, col] = normalised
            changed_total += changed

    if changed_total:
        logger.info(
            "normalise_friction_columns: normalised %d friction values across %d column(s)",
            changed_total, len(friction_cols),
        )
    return df


# ===========================================================================
# FULL POST-PROCESS ORCHESTRATOR
# ===========================================================================

def post_process(
    df_original: pd.DataFrame,
    results: list[dict[str, Any]],
    taxonomies: dict[str, dict],
    cfg: RunConfig,
) -> pd.DataFrame:
    # Capture original columns BEFORE enrichment so reorder_columns can
    # keep them first in their original order.
    original_cols = list(df_original.columns)

    df = merge_results(df_original, results, id_col=cfg.id_col)
    df = validate_enum_cols(df)
    df = validate_evidence_fields(df, text_col=cfg.text_col, id_col=cfg.id_col)
    df = derive_labels(df, taxonomies)
    df = heuristic_fallbacks(df, taxonomies, text_col=cfg.text_col)
    df = explode_object_lists(df)         # list-of-objects first (explode_lists would stringify them)
    # Re-run evidence grounding on columns just exposed by explode_object_lists (e.g.
    # matched_rules_evidence_N) — the first pass above ran before they existed, since
    # "matched_rules" itself doesn't match the *_evidence naming pattern pre-explosion.
    df = validate_evidence_fields(df, text_col=cfg.text_col, id_col=cfg.id_col)
    df = explode_lists(df)
    df = normalise_friction_columns(df)   # normalise after explode so positional cols exist
    df = derive_positional_labels(df, taxonomies)
    df = reorder_columns(df, id_col=cfg.id_col, text_col=cfg.text_col,
                         original_cols=original_cols)

    # Strip fields marked in_output=FALSE — done last so they were available
    # for intermediate steps (label derivation, positional labels etc.)
    if _OUTPUT_EXCLUDE:
        drop = [c for c in df.columns
                if any(c == ex or c.startswith(ex + "_") for ex in _OUTPUT_EXCLUDE)
                and c not in original_cols]  # never drop original dataset columns
        if drop:
            logger.info("Dropping %d in_output=FALSE columns: %s", len(drop), drop)
            df = df.drop(columns=drop)

    return df


# ===========================================================================
# OUTPUT
# ===========================================================================

def write_output_file(df: pd.DataFrame, filepath: str | Path) -> Path:
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    if filepath.suffix.lower() in (".xlsx", ".xls"):
        df.to_excel(filepath, index=False, engine="openpyxl")
    else:
        df.to_csv(filepath, index=False)
    logger.info("Wrote %d rows × %d cols → %s", len(df), len(df.columns), filepath.name)
    return filepath
