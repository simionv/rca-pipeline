"""
confidence.py – Classification Confidence Scoring
====================================================
Extracts confidence scores from LLM responses using token log-probabilities.
Low-confidence classifications are flagged for human review.

Two modes:
  1. Logprob mode: requests logprobs from the API and computes a confidence
     score from the token probabilities of the classification code tokens.
  2. Self-report mode (fallback): asks the LLM to self-report confidence on
     a 0-1 scale as an additional JSON field — less reliable but universally
     supported.

Usage:
  from confidence import (
      enrich_with_confidence, flag_low_confidence,
      CONFIDENCE_THRESHOLD,
  )
"""

from __future__ import annotations

import json
import logging
import math
import re
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Default threshold — classifications below this are flagged for human review.
CONFIDENCE_THRESHOLD = 0.70


# ---------------------------------------------------------------------------
# Logprob extraction from API responses
# ---------------------------------------------------------------------------
def extract_logprob_confidence(response: Any, target_tokens: list[str] | None = None) -> float:
    """
    Extract a confidence score from the logprobs in an LLM API response.

    The score is computed as the geometric mean of the token probabilities
    for the tokens composing the classification code (e.g. "CR", "4", ".", "1").

    Parameters
    ----------
    response : raw API response object (litellm or openai format)
    target_tokens : optional list of tokens to look for — if None, scans all.

    Returns
    -------
    float in [0, 1] — confidence score.  Returns -1 if logprobs unavailable.
    """
    try:
        choice = response.choices[0]
        logprobs = getattr(choice, "logprobs", None)
        if logprobs is None:
            return -1.0

        content_logprobs = getattr(logprobs, "content", None)
        if not content_logprobs:
            return -1.0

        # Collect log-probabilities for all tokens
        all_logprobs: list[float] = []
        for token_info in content_logprobs:
            lp = getattr(token_info, "logprob", None)
            if lp is not None:
                all_logprobs.append(lp)

        if not all_logprobs:
            return -1.0

        # Geometric mean of probabilities = exp(mean of log-probs)
        mean_logprob = sum(all_logprobs) / len(all_logprobs)
        confidence = math.exp(mean_logprob)

        return min(max(confidence, 0.0), 1.0)

    except Exception as e:
        logger.debug("extract_logprob_confidence: %s", e)
        return -1.0


def extract_code_token_confidence(
    response: Any,
    code: str,
    occurrence: int = 0,
) -> float:
    """
    Extract confidence specifically for the tokens that form a classification
    code (e.g. "CR4.1") by scanning the logprob stream for matching tokens.

    This is more targeted than the full-response geometric mean.

    Parameters
    ----------
    response   : raw API response object
    code       : the classification code string to locate (e.g. "CR4.1")
    occurrence : which occurrence of the code to score (0 = first, 1 = second …).
                 Use this when the same code appears multiple times in the response
                 (e.g. batches with several records sharing the same code).
    """
    try:
        choice = response.choices[0]
        logprobs = getattr(choice, "logprobs", None)
        if logprobs is None or not getattr(logprobs, "content", None):
            return -1.0

        content_tokens = logprobs.content
        token_texts = [getattr(t, "token", "") for t in content_tokens]
        joined = "".join(token_texts)

        # Find the requested occurrence of the code in the concatenated stream
        search_from = 0
        pos = -1
        for _ in range(occurrence + 1):
            found = joined.find(code, search_from)
            if found == -1:
                return -1.0
            pos = found
            search_from = found + len(code)

        # Collect log-probabilities for tokens that overlap the code span
        code_logprobs: list[float] = []
        running = 0
        for i, t in enumerate(content_tokens):
            tok_text = getattr(t, "token", "")
            tok_start = running
            tok_end   = running + len(tok_text)
            # Token overlaps the code span [pos, pos+len(code))
            if tok_end > pos and tok_start < pos + len(code):
                lp = getattr(t, "logprob", None)
                if lp is not None:
                    code_logprobs.append(lp)
            running = tok_end
            if running >= pos + len(code):
                break

        if not code_logprobs:
            return -1.0

        mean_lp = sum(code_logprobs) / len(code_logprobs)
        return min(max(math.exp(mean_lp), 0.0), 1.0)

    except Exception as e:
        logger.debug("extract_code_token_confidence: %s", e)
        return -1.0


def _tokenise_code(code: str) -> list[str]:
    """Split a code like 'CR4.1' into likely token fragments."""
    parts = []
    current = ""
    for ch in code:
        if ch == ".":
            if current:
                parts.append(current)
            parts.append(".")
            current = ""
        elif ch.isalpha() != (current[-1:].isalpha() if current else True):
            if current:
                parts.append(current)
            current = ch
        else:
            current += ch
    if current:
        parts.append(current)
    return parts


# ---------------------------------------------------------------------------
# Self-reported confidence (fallback when logprobs unavailable)
# ---------------------------------------------------------------------------
def inject_confidence_instruction(system_prompt: str) -> str:
    """
    Append a confidence self-report instruction to the system prompt.
    The LLM is asked to include a 'confidence' float (0-1) in each result object.
    """
    instruction = (
        "\n\n## Confidence (additional field — keep ALL other fields above)\n"
        "Add a `confidence` field (float 0.0–1.0) to each JSON object indicating "
        "how confident you are in your classification. This is IN ADDITION to all "
        "other fields — do NOT omit any field from the schema above.\n"
        "  - 0.9–1.0: Very confident — clear match to taxonomy\n"
        "  - 0.7–0.9: Confident — good match with minor ambiguity\n"
        "  - 0.5–0.7: Moderate — could fit multiple codes\n"
        "  - 0.0–0.5: Low — guessing or transcript is ambiguous/sparse\n"
        "\n"
        "IMPORTANT: Every field listed in the Output Format above MUST still appear "
        "in every record. Do not skip description, evidence, or justification fields.\n"
    )
    return system_prompt + instruction


def extract_self_reported_confidence(record: dict) -> float:
    """Extract the self-reported confidence from a parsed record."""
    raw = record.get("confidence", record.get("conf", -1.0))
    try:
        val = float(raw)
        return min(max(val, 0.0), 1.0) if val >= 0 else -1.0
    except (ValueError, TypeError):
        return -1.0


# ---------------------------------------------------------------------------
# Batch-level confidence enrichment
# ---------------------------------------------------------------------------
def enrich_with_confidence(
    results: list[dict[str, Any]],
    code_fields: list[str] | None = None,
    threshold: float = CONFIDENCE_THRESHOLD,
) -> list[dict[str, Any]]:
    """
    Add confidence metadata to each result record.

    For each record:
      - Extracts or uses self-reported confidence.
      - Adds `_confidence` (float) and `_needs_review` (bool) fields.

    Parameters
    ----------
    results : list of enrichment dicts from the LLM.
    code_fields : list of field names containing classification codes.
                  If provided, per-field confidence is computed.
    threshold : records below this threshold are flagged.

    Returns
    -------
    The same list, each dict enriched with confidence fields.
    """
    for record in results:
        conf = extract_self_reported_confidence(record)

        record["_confidence"] = round(conf, 4) if conf >= 0 else None
        record["_needs_review"] = (
            conf < threshold if conf >= 0 else True
        )

        # Per-code confidence if code_fields provided
        if code_fields:
            for cf in code_fields:
                field_conf = record.get(f"{cf}_confidence", None)
                if field_conf is not None:
                    try:
                        record[f"_{cf}_confidence"] = round(float(field_conf), 4)
                    except (ValueError, TypeError):
                        pass

    flagged = sum(1 for r in results if r.get("_needs_review", False))
    if flagged:
        logger.info(
            "Confidence: %d/%d records flagged for review (threshold=%.2f)",
            flagged, len(results), threshold,
        )

    return results


# ---------------------------------------------------------------------------
# DataFrame-level flagging
# ---------------------------------------------------------------------------
def flag_low_confidence(
    df: pd.DataFrame,
    threshold: float = CONFIDENCE_THRESHOLD,
    confidence_col: str = "_confidence",
    review_col: str = "_needs_review",
) -> pd.DataFrame:
    """
    Flag low-confidence rows in the enriched DataFrame.

    Adds or updates the review column.  Rows with confidence below threshold
    or with missing confidence are flagged.
    """
    df = df.copy()

    if confidence_col not in df.columns:
        logger.warning("flag_low_confidence: column '%s' not found", confidence_col)
        return df

    # B5 fix: coerce to numeric first — handles strings like "None", "", NaN
    numeric_conf = pd.to_numeric(df[confidence_col], errors="coerce")
    df[review_col] = numeric_conf.isna() | (numeric_conf < threshold)

    n_flagged = df[review_col].sum()
    logger.info(
        "Low-confidence flagging: %d/%d rows need review (%.1f%%)",
        n_flagged, len(df), n_flagged / len(df) * 100 if len(df) else 0,
    )

    return df


def export_review_queue(
    df: pd.DataFrame,
    output_path: str,
    review_col: str = "_needs_review",
    sort_by: str = "_confidence",
) -> None:
    """Export low-confidence records to a separate file for human review."""
    if review_col not in df.columns:
        logger.warning("export_review_queue: column '%s' not found — exporting nothing", review_col)
        return

    review_df = df[df[review_col].astype(bool)].copy()

    if sort_by in review_df.columns:
        review_df = review_df.sort_values(sort_by, ascending=True)

    if output_path.endswith(".xlsx"):
        review_df.to_excel(output_path, index=False, engine="openpyxl")
    else:
        review_df.to_csv(output_path, index=False)

    logger.info("Exported %d records for review → %s", len(review_df), output_path)
