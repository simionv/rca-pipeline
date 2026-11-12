"""
incremental.py – Incremental Processing Engine
=================================================
Formalises incremental (append-only) processing as a first-class feature.
Instead of re-classifying the entire dataset, only new/changed records
are dispatched to the LLM.

Key features:
  - Maintains a state database (JSONL) of previously classified records
  - Detects new, changed, and deleted records via UID comparison
  - Supports daily/periodic batch runs with merge-back into the master output
  - Provides a CLI and programmatic API

Usage:
  # CLI
  python incremental.py --input data/today_batch.csv --state data/state.jsonl \
      --output output/enriched.xlsx

  # Programmatic
  from incremental import IncrementalRunner
  runner = IncrementalRunner("data/state.jsonl")
  new_records, changed_records = runner.diff(today_df)
  results = await runner.process_new(new_records, cfg)
  runner.merge_and_save(results, today_df, "output/enriched.xlsx")
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from ..config import RunConfig

logger = logging.getLogger(__name__)


class IncrementalState:
    """
    Tracks the classification state of all previously processed records.

    Storage: JSONL file where each line is:
      {"uid": "...", "text_hash": "...", "classified_at": "...", "results": {...}}

    The text_hash allows detecting changed records (same uid, different text).
    """

    def __init__(self, state_path: str | Path):
        self.state_path = Path(state_path)
        self._records: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        """Load state from disk."""
        if not self.state_path.exists():
            logger.info("No existing state at %s — starting fresh", self.state_path)
            return

        count = 0
        with open(self.state_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    uid = str(entry.get("uid", ""))
                    if uid:
                        self._records[uid] = entry
                        count += 1
                except json.JSONDecodeError:
                    continue

        logger.info("Loaded incremental state: %d records from %s",
                     count, self.state_path.name)

    def save(self) -> None:
        """Persist current state to disk (full rewrite for compaction)."""
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_path, "w", encoding="utf-8") as f:
            for entry in self._records.values():
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logger.info("Saved incremental state: %d records → %s",
                     len(self._records), self.state_path.name)

    @staticmethod
    def _hash_text(text: str) -> str:
        """SHA-256 hash of normalised text for change detection."""
        normalised = " ".join(str(text).split()).strip().lower()
        return hashlib.sha256(normalised.encode("utf-8")).hexdigest()[:16]

    def get(self, uid: str) -> Optional[dict]:
        return self._records.get(uid)

    def has(self, uid: str) -> bool:
        return uid in self._records

    def is_changed(self, uid: str, text: str) -> bool:
        """Check if a record's text has changed since last classification."""
        existing = self._records.get(uid)
        if not existing:
            return False  # Not "changed" — it's new
        return existing.get("text_hash", "") != self._hash_text(text)

    def update(self, uid: str, text: str, results: dict[str, Any]) -> None:
        """Update or add a record's state."""
        self._records[uid] = {
            "uid": uid,
            "text_hash": self._hash_text(text),
            "classified_at": datetime.now(timezone.utc).isoformat(),
            "results": results,
        }

    def update_batch(self, records: list[dict[str, Any]], text_map: dict[str, str]) -> None:
        """Update state for a batch of classified records."""
        for r in records:
            uid = str(r.get("uid", ""))
            text = text_map.get(uid, "")
            self.update(uid, text, r)

    def get_results(self, uid: str) -> dict:
        """Get the cached classification results for a uid."""
        entry = self._records.get(uid)
        if entry:
            return entry.get("results", {})
        return {}

    def remove(self, uid: str) -> None:
        self._records.pop(uid, None)

    @property
    def count(self) -> int:
        return len(self._records)

    @property
    def all_uids(self) -> set[str]:
        return set(self._records.keys())


class IncrementalRunner:
    """
    High-level incremental processing engine.

    Workflow:
      1. diff()            → identify new, changed, and unchanged records
      2. process_new()     → classify only new + changed records
      3. merge_and_save()  → combine cached + new results, write output
    """

    def __init__(
        self,
        state_path: str | Path,
        cfg: Optional[RunConfig] = None,
    ):
        self.state = IncrementalState(state_path)
        self.cfg = cfg or RunConfig()

    def diff(
        self,
        df: pd.DataFrame,
        id_col: str = "uid",
        text_col: str = "transcript",
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Compare incoming data against the state to find what needs processing.

        Returns
        -------
        (new_df, changed_df, unchanged_df)
            new_df: records not in state (need full classification)
            changed_df: records in state but text changed (need reclassification)
            unchanged_df: records in state with same text (use cached results)
        """
        new_idx = []
        changed_idx = []
        unchanged_idx = []

        for idx, row in df.iterrows():
            uid = str(row[id_col])
            text = str(row[text_col])

            if not self.state.has(uid):
                new_idx.append(idx)
            elif self.state.is_changed(uid, text):
                changed_idx.append(idx)
            else:
                unchanged_idx.append(idx)

        new_df = df.loc[new_idx].copy() if new_idx else pd.DataFrame(columns=df.columns)
        changed_df = df.loc[changed_idx].copy() if changed_idx else pd.DataFrame(columns=df.columns)
        unchanged_df = df.loc[unchanged_idx].copy() if unchanged_idx else pd.DataFrame(columns=df.columns)

        total = len(df)
        logger.info(
            "Incremental diff: %d total → %d new + %d changed + %d unchanged",
            total, len(new_df), len(changed_df), len(unchanged_df),
        )

        return new_df, changed_df, unchanged_df

    def get_cached_results(
        self,
        df: pd.DataFrame,
        id_col: str = "uid",
    ) -> list[dict[str, Any]]:
        """Retrieve cached classification results for unchanged records."""
        results = []
        for _, row in df.iterrows():
            uid = str(row[id_col])
            cached = self.state.get_results(uid)
            if cached:
                results.append(cached)
        return results

    def update_state(
        self,
        results: list[dict[str, Any]],
        df: pd.DataFrame,
        id_col: str = "uid",
        text_col: str = "transcript",
    ) -> None:
        """Update state with newly classified results."""
        text_map = {
            str(row[id_col]): str(row[text_col])
            for _, row in df.iterrows()
        }
        self.state.update_batch(results, text_map)
        self.state.save()

    def prune_deleted(
        self,
        current_uids: set[str],
    ) -> int:
        """
        Remove state entries for records no longer in the current dataset.
        Returns the number of pruned entries.
        """
        stale_uids = self.state.all_uids - current_uids
        for uid in stale_uids:
            self.state.remove(uid)
        if stale_uids:
            self.state.save()
            logger.info("Pruned %d stale records from state", len(stale_uids))
        return len(stale_uids)

    def summary(self) -> dict[str, Any]:
        """Return a summary of the current incremental state."""
        return {
            "total_cached": self.state.count,
            "state_file": str(self.state.state_path),
        }


# ---------------------------------------------------------------------------
# Convenience function for pipeline integration
# ---------------------------------------------------------------------------
async def run_incremental_pipeline(
    df: pd.DataFrame,
    state_path: str | Path,
    classify_fn,
    taxonomies: dict[str, dict],
    cfg: RunConfig,
    id_col: str = "uid",
    text_col: str = "transcript",
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """
    Run the pipeline incrementally: only classify new/changed records.

    NOTE: The primary incremental path is implemented directly in pipeline.py
    using IncrementalRunner.  This convenience function is provided for callers
    that manage their own classification loop (e.g. tests, notebooks).  It uses
    the same IncrementalRunner internally so behaviour is identical.

    Parameters
    ----------
    df           : full input DataFrame (all records, new and old)
    state_path   : path to incremental state JSONL
    classify_fn  : async callable with signature
                   ``async (batches: list[list[dict]], taxonomies, cfg) -> list[dict]``
                   where each batch is a list of {uid, text} dicts.
    taxonomies   : loaded taxonomies
    cfg          : RunConfig
    id_col       : name of the unique ID column in df
    text_col     : name of the transcript/text column in df

    Returns
    -------
    (all_results, stats)
        all_results : combined cached + newly classified results
        stats       : dict with keys new, changed, unchanged, total,
                      classified_now, from_cache
    """
    from ..utils import make_batches

    runner = IncrementalRunner(state_path, cfg)

    # Step 1: Diff — identify what needs classifying
    new_df, changed_df, unchanged_df = runner.diff(df, id_col=id_col, text_col=text_col)

    # Step 2: Retrieve cached results for unchanged records
    cached_results = runner.get_cached_results(unchanged_df, id_col=id_col)

    # Step 3: Classify new + changed records
    to_classify = pd.concat([new_df, changed_df], ignore_index=True)
    new_results: list[dict] = []

    if len(to_classify) > 0:
        logger.info("Incremental: classifying %d new/changed records", len(to_classify))
        batch_dfs = make_batches(
            to_classify, cfg.batch_size, cfg.max_chars_per_batch, text_col,
        )
        # Build batches in the format classify_fn expects: list[list[{uid, text}]]
        batches = [
            [
                {id_col: str(row[id_col]), "uid": str(row[id_col]), "text": str(row[text_col])}
                for _, row in b.iterrows()
            ]
            for b in batch_dfs
        ]
        new_results = await classify_fn(batches, taxonomies, cfg)

        # Update state — use uid-set to guard against accidental double-writes
        runner.update_state(new_results, to_classify, id_col=id_col, text_col=text_col)
    else:
        logger.info("Incremental: all %d records cached — nothing to classify", len(df))

    # Step 4: Prune deleted records from state
    current_uids = {str(row[id_col]) for _, row in df.iterrows()}
    runner.prune_deleted(current_uids)

    # Combine: cached first, then newly classified
    all_results = cached_results + new_results

    stats = {
        "new":            len(new_df),
        "changed":        len(changed_df),
        "unchanged":      len(unchanged_df),
        "total":          len(df),
        "classified_now": len(new_results),
        "from_cache":     len(cached_results),
    }

    logger.info(
        "Incremental complete: %d from cache + %d newly classified = %d total",
        stats["from_cache"], stats["classified_now"], len(all_results),
    )

    return all_results, stats
