"""
feedback.py – Human-in-the-Loop Feedback Store
================================================
Stores human corrections to misclassified records and injects them into
future prompts as few-shot examples.  Over time the prompt accumulates
a curated set of 'hard cases' that anchor the LLM on ambiguous inputs.

Storage format:
  feedback/<module_name>_corrections.jsonl

Each line is a JSON object:
  {
    "uid": "...",
    "text": "... (truncated transcript) ...",
    "original": {"contact_reason_primary_code": "CR1.2", ...},
    "corrected": {"contact_reason_primary_code": "CR3.1", ...},
    "reason": "Free-text note from reviewer explaining the correction",
    "timestamp": "2026-03-30T12:00:00Z",
    "module": "contact_reason"
  }

Usage:
  from feedback import FeedbackStore

  store = FeedbackStore("feedback/")
  store.add_correction("contact_reason", uid="42", text="...",
                       original={"code": "CR1.2"}, corrected={"code": "CR3.1"},
                       reason="This is a password issue, not login blocked")

  # Inject into prompts
  few_shot_block = store.build_few_shot_prompt("contact_reason", max_examples=5)
  system_prompt = base_prompt + few_shot_block
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _tokenise(s: str) -> set[str]:
    return set(re.sub(r"[^a-z0-9\s]", "", s.lower()).split())


class FeedbackStore:
    """
    Persistent store for human corrections, with prompt injection support.

    Each module has its own JSONL file.  Corrections are append-only;
    deduplication happens at read time (latest correction per uid wins).
    """

    def __init__(self, feedback_dir: str | Path = "feedback"):
        self.feedback_dir = Path(feedback_dir)
        self.feedback_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, list[dict]] = {}

    def _path(self, module: str) -> Path:
        return self.feedback_dir / f"{module}_corrections.jsonl"

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------
    def add_correction(
        self,
        module: str,
        uid: str,
        text: str,
        original: dict[str, Any],
        corrected: dict[str, Any],
        reason: str = "",
        max_text_chars: int = 1500,
    ) -> None:
        """
        Append a human correction for a specific record and module.

        Parameters
        ----------
        module : module name (e.g. "contact_reason")
        uid : unique record identifier
        text : the transcript text (will be truncated for storage)
        original : dict of the original LLM-assigned fields
        corrected : dict of the human-corrected fields
        reason : optional reviewer note explaining why
        max_text_chars : truncate transcript to this length for storage
        """
        entry = {
            "uid": str(uid),
            "text": text[:max_text_chars],
            "original": original,
            "corrected": corrected,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "module": module,
        }

        path = self._path(module)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # Invalidate cache
        self._cache.pop(module, None)

        logger.info(
            "Feedback recorded: module=%s uid=%s original=%s → corrected=%s",
            module, uid,
            json.dumps(original, ensure_ascii=False)[:80],
            json.dumps(corrected, ensure_ascii=False)[:80],
        )

    def add_corrections_batch(
        self,
        module: str,
        corrections: list[dict[str, Any]],
    ) -> int:
        """
        Batch-add corrections.  Each dict must have: uid, text, original, corrected.
        Optional: reason.

        Returns the number of corrections added.
        """
        count = 0
        for c in corrections:
            try:
                self.add_correction(
                    module=module,
                    uid=c["uid"],
                    text=c["text"],
                    original=c["original"],
                    corrected=c["corrected"],
                    reason=c.get("reason", ""),
                )
                count += 1
            except KeyError as e:
                logger.warning("Skipping correction missing field: %s", e)
        return count

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    def load_corrections(self, module: str) -> list[dict]:
        """
        Load all corrections for a module, deduplicated by uid
        (latest correction per uid wins).
        """
        if module in self._cache:
            return self._cache[module]

        path = self._path(module)
        if not path.exists():
            return []

        by_uid: dict[str, dict] = {}
        with open(path, encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    by_uid[entry["uid"]] = entry
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(
                        "Feedback parse error %s line %d: %s",
                        path.name, line_no, e,
                    )

        corrections = list(by_uid.values())
        self._cache[module] = corrections
        logger.info(
            "Loaded %d corrections for module '%s'",
            len(corrections), module,
        )
        return corrections

    def get_stats(self) -> dict[str, int]:
        """Return correction counts per module."""
        stats: dict[str, int] = {}
        for path in self.feedback_dir.glob("*_corrections.jsonl"):
            module = path.stem.replace("_corrections", "")
            stats[module] = len(self.load_corrections(module))
        return stats

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------
    def build_few_shot_prompt(
        self,
        module: str,
        max_examples: int = 5,
        max_text_chars: int = 800,
        max_total_chars: int = 4000,
        selection_strategy: str = "recent",
    ) -> str:
        """
        Build a few-shot examples block from stored corrections.

        Parameters
        ----------
        module : module name
        max_examples : maximum number of examples to include
        max_text_chars : truncate each transcript in the prompt
        max_total_chars : P5 fix — hard cap on total prompt block size
        selection_strategy :
            "recent"    — most recent corrections first
            "diverse"   — one per distinct corrected code (maximise coverage)
            "frequent"  — most frequently corrected original→corrected pairs
            "smart"     — two-stage: use build_smart_pool + rerank_pool_for_batch

        Returns
        -------
        A prompt block string ready to append to the system prompt.
        Returns empty string if no corrections exist.
        """
        corrections = self.load_corrections(module)
        if not corrections:
            return ""

        selected = self._select_examples(corrections, max_examples, selection_strategy)
        if not selected:
            return ""

        return self.build_few_shot_prompt_for_batch(selected, max_text_chars, max_total_chars)

    def build_few_shot_prompt_for_batch(
        self,
        pool_subset: list[dict],
        max_text_chars: int = 800,
        max_total_chars: int = 4000,
    ) -> str:
        """
        Format a pre-selected list of corrections as a few-shot prompt block.

        Used by both the static strategies (via build_few_shot_prompt) and the
        smart per-batch path (via build_smart_pool + rerank_pool_for_batch).
        """
        if not pool_subset:
            return ""

        lines = [
            "\n\n## Known Hard Cases (Human-Corrected Examples)",
            "The following examples were previously misclassified and corrected by human reviewers.",
            "Use these as reference for ambiguous cases:\n",
        ]

        running_chars = sum(len(l) for l in lines)

        for i, ex in enumerate(pool_subset, 1):
            text_trunc = ex["text"][:max_text_chars]
            if len(ex["text"]) > max_text_chars:
                text_trunc += "..."

            example_lines = [f"### Example {i}"]
            example_lines.append(f"Transcript: {text_trunc}")
            example_lines.append(f"WRONG classification: {json.dumps(ex['original'], ensure_ascii=False)}")
            example_lines.append(f"CORRECT classification: {json.dumps(ex['corrected'], ensure_ascii=False)}")
            if ex.get("reason"):
                example_lines.append(f"Reason: {ex['reason']}")
            example_lines.append("")

            # P5 fix: check total size before adding this example
            example_text = "\n".join(example_lines)
            if running_chars + len(example_text) > max_total_chars and i > 1:
                logger.debug(
                    "build_few_shot_prompt_for_batch: stopping at %d examples (total %d chars, limit %d)",
                    i - 1, running_chars, max_total_chars,
                )
                break

            lines.extend(example_lines)
            running_chars += len(example_text)

        return "\n".join(lines)

    def _select_examples(
        self,
        corrections: list[dict],
        max_n: int,
        strategy: str,
    ) -> list[dict]:
        """Select the best subset of corrections for few-shot injection."""
        if strategy == "diverse":
            return self._select_diverse(corrections, max_n)
        elif strategy == "frequent":
            return self._select_frequent(corrections, max_n)
        elif strategy == "smart":
            logger.warning(
                "_select_examples called with strategy='smart' — "
                "use build_smart_pool() + rerank_pool_for_batch() instead. "
                "Falling back to 'recent'."
            )
            return self._select_examples(corrections, max_n, "recent")
        else:  # "recent"
            sorted_c = sorted(
                corrections,
                key=lambda x: x.get("timestamp", ""),
                reverse=True,
            )
            return sorted_c[:max_n]

    def _select_diverse(self, corrections: list[dict], max_n: int) -> list[dict]:
        """One example per distinct corrected code — maximise taxonomy coverage.
        Within each code group, the most recent correction is preferred."""
        # Sort by timestamp descending so the most recent correction per code is picked
        sorted_c = sorted(
            corrections,
            key=lambda x: x.get("timestamp", ""),
            reverse=True,
        )
        seen_codes: set[str] = set()
        selected: list[dict] = []

        for c in sorted_c:
            code_values = tuple(
                str(v) for v in c.get("corrected", {}).values()
            )
            key = "|".join(code_values)
            if key not in seen_codes:
                seen_codes.add(key)
                selected.append(c)
                if len(selected) >= max_n:
                    break
        return selected

    def _select_frequent(self, corrections: list[dict], max_n: int) -> list[dict]:
        """Most frequently corrected original→corrected pairs."""
        pair_counts: defaultdict[str, list[dict]] = defaultdict(list)
        for c in corrections:
            orig_key = json.dumps(c.get("original", {}), sort_keys=True)
            corr_key = json.dumps(c.get("corrected", {}), sort_keys=True)
            pair_key = f"{orig_key}→{corr_key}"
            pair_counts[pair_key].append(c)

        # Sort by frequency (most frequent first)
        sorted_pairs = sorted(
            pair_counts.values(),
            key=lambda group: len(group),
            reverse=True,
        )

        selected: list[dict] = []
        for group in sorted_pairs:
            selected.append(group[-1])  # latest from each group
            if len(selected) >= max_n:
                break
        return selected

    # ------------------------------------------------------------------
    # Smart two-stage selection
    # ------------------------------------------------------------------
    def build_smart_pool(
        self,
        module: str,
        max_text_chars: int = 800,
    ) -> list[dict]:
        """
        Stage 1 of the smart strategy: build a candidate pool with the best
        representative correction per distinct corrected code.

        Each candidate is scored by:
            0.4 * has_reason + 0.3 * content_score + 0.3 * recency

        where content_score = diversity_ratio * capped_unique_count, which
        rewards transcripts that are both varied and substantive while
        penalising boilerplate (low diversity) and trivially short texts
        (low unique token count).

        Returns a list of dicts — one per distinct corrected code — each with
        a '_stage1_score' field attached for use as a tie-breaker in Stage 2.
        """
        corrections = self.load_corrections(module)
        if not corrections:
            return []

        # Recency normalization
        timestamps: list[datetime] = []
        for c in corrections:
            try:
                timestamps.append(datetime.fromisoformat(c.get("timestamp", "")))
            except (ValueError, TypeError):
                timestamps.append(datetime.min)

        min_ts = min(timestamps)
        max_ts = max(timestamps)
        ts_range = (max_ts - min_ts).total_seconds()

        def _recency(ts: datetime) -> float:
            if ts_range == 0:
                return 1.0
            return (ts - min_ts).total_seconds() / ts_range

        def _content_score(text: str) -> float:
            tokens_all = re.sub(r"[^a-z0-9\s]", "", text.lower()).split()
            unique = len(set(tokens_all))
            total = max(len(tokens_all), 1)
            return (unique / total) * (min(unique, 80) / 80)

        # Group by corrected code (first value in the corrected dict)
        groups: dict[str, list[tuple[dict, float]]] = defaultdict(list)
        for c, ts in zip(corrections, timestamps):
            code = next(iter(c.get("corrected", {}).values()), "_unknown")
            has_reason = 1.0 if c.get("reason", "").strip() else 0.0
            content = _content_score(c.get("text", ""))
            recency = _recency(ts)
            score = 0.4 * has_reason + 0.3 * content + 0.3 * recency
            groups[str(code)].append((c, score))

        pool: list[dict] = []
        for group_entries in groups.values():
            best_c, best_score = max(group_entries, key=lambda x: x[1])
            entry = dict(best_c)
            entry["text"] = entry.get("text", "")[:max_text_chars]
            entry["_stage1_score"] = best_score
            pool.append(entry)

        logger.debug("build_smart_pool: %d code groups → %d pool entries for '%s'",
                     len(groups), len(pool), module)
        return pool

    def rerank_pool_for_batch(
        self,
        pool: list[dict],
        batch: list[dict],
        max_examples: int,
    ) -> list[dict]:
        """
        Stage 2 of the smart strategy: rerank the candidate pool by Jaccard
        token-overlap with the records in the current batch.

        Each correction is scored by its maximum overlap with any record in the
        batch (not mean — a single strong match is enough to surface the example).
        Ties are broken by _stage1_score from build_smart_pool.
        """
        if not pool:
            return []

        batch_token_sets = [
            _tokenise(r.get("text", ""))
            for r in batch
            if r.get("text", "").strip()
        ]

        result: list[dict] = []
        for c in pool:
            c_tokens = _tokenise(c.get("text", ""))
            if not c_tokens or not batch_token_sets:
                max_overlap = 0.0
            else:
                max_overlap = max(
                    len(c_tokens & r_tokens) / max(len(c_tokens), len(r_tokens))
                    for r_tokens in batch_token_sets
                    if r_tokens
                ) if batch_token_sets else 0.0
            entry = dict(c)
            entry["_stage2_score"] = max_overlap
            result.append(entry)

        result.sort(key=lambda x: (x["_stage2_score"], x.get("_stage1_score", 0.0)), reverse=True)
        return result[:max_examples]

    # ------------------------------------------------------------------
    # Import from review spreadsheet
    # ------------------------------------------------------------------
    def import_from_review_file(
        self,
        filepath: str | Path,
        module: str,
        text_col: str = "transcript",
        uid_col: str = "uid",
        code_fields: list[str] | None = None,
        corrected_suffix: str = "_corrected",
    ) -> int:
        """
        Import corrections from a reviewed spreadsheet.

        Expected format: the review file has original columns plus
        <field>_corrected columns (e.g. contact_reason_primary_code_corrected)
        for rows where the human reviewer changed the value.

        Returns the number of corrections imported.
        """
        import pandas as pd

        filepath = Path(filepath)
        if filepath.suffix.lower() in (".xlsx", ".xls"):
            df = pd.read_excel(filepath, engine="openpyxl")
        else:
            df = pd.read_csv(filepath)

        if code_fields is None:
            # Auto-detect: any column ending with corrected_suffix
            code_fields = [
                c.replace(corrected_suffix, "")
                for c in df.columns
                if c.endswith(corrected_suffix)
            ]

        if not code_fields:
            logger.warning("No corrected fields found in %s", filepath.name)
            return 0

        count = 0
        for _, row in df.iterrows():
            original = {}
            corrected = {}
            has_correction = False

            for cf in code_fields:
                corr_col = cf + corrected_suffix
                if corr_col in df.columns:
                    orig_val = str(row.get(cf, "")).strip()
                    corr_val = str(row.get(corr_col, "")).strip()
                    if corr_val and corr_val != "nan" and corr_val != orig_val:
                        original[cf] = orig_val
                        corrected[cf] = corr_val
                        has_correction = True

            if has_correction:
                reason_col = "correction_reason"
                reason = str(row.get(reason_col, "")).strip()
                if reason == "nan":
                    reason = ""

                self.add_correction(
                    module=module,
                    uid=str(row.get(uid_col, "")),
                    text=str(row.get(text_col, "")),
                    original=original,
                    corrected=corrected,
                    reason=reason,
                )
                count += 1

        logger.info("Imported %d corrections from %s for module '%s'",
                     count, filepath.name, module)
        return count

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def compact(self, module: str) -> int:
        """
        Compact the corrections file by deduplicating (latest per uid).
        Returns the number of unique corrections after compaction.
        """
        corrections = self.load_corrections(module)
        if not corrections:
            return 0

        path = self._path(module)
        with open(path, "w", encoding="utf-8") as f:
            for entry in corrections:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        self._cache.pop(module, None)
        logger.info("Compacted %s: %d unique corrections", path.name, len(corrections))
        return len(corrections)
