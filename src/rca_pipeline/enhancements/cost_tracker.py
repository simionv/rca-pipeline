"""
cost_tracker.py – Token Usage & Cost Tracker
===============================================
Tracks token usage and estimated cost per record, per module, per run.
Enables cost-aware decisions like:
  - Batching cheap modules more aggressively
  - Routing ambiguous cases to larger models
  - Estimating cost before a full run

Storage: cost_reports/<run_name>_costs.json

Usage:
  from cost_tracker import CostTracker

  tracker = CostTracker()
  tracker.record_call("contact_reason", prompt_tokens=1200, completion_tokens=800, n_records=10)
  tracker.print_summary()
  tracker.save("cost_reports/run_001.json")
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pricing table (USD per 1K tokens) — update as prices change
# ---------------------------------------------------------------------------
# Source: Azure OpenAI / OpenAI pricing pages (approximate, March 2026)
_PRICING: dict[str, dict[str, float]] = {
    # Azure models
    "azure/dsaic-llm-general": {"prompt": 0.005, "completion": 0.015},
    "azure/gpt-4o":            {"prompt": 0.005, "completion": 0.015},
    "azure/gpt-4o-mini":       {"prompt": 0.00015, "completion": 0.0006},
    "azure/gpt-4":             {"prompt": 0.03,  "completion": 0.06},
    "azure/gpt-35-turbo":      {"prompt": 0.0005, "completion": 0.0015},
    # OpenAI direct
    "gpt-4o":                  {"prompt": 0.005, "completion": 0.015},
    "gpt-4o-mini":             {"prompt": 0.00015, "completion": 0.0006},
    "gpt-4":                   {"prompt": 0.03,  "completion": 0.06},
    "gpt-3.5-turbo":           {"prompt": 0.0005, "completion": 0.0015},
    # Anthropic via litellm
    "anthropic/claude-sonnet-4-20250514": {"prompt": 0.003, "completion": 0.015},
    "anthropic/claude-3-haiku-20240307":  {"prompt": 0.00025, "completion": 0.00125},
}

# Fallback pricing when model not in table
_DEFAULT_PRICING = {"prompt": 0.005, "completion": 0.015}


def get_pricing(model: str) -> dict[str, float]:
    """Look up pricing for a model, falling back to defaults."""
    if model in _PRICING:
        return _PRICING[model]
    # Try partial match (strip version suffixes)
    for key, pricing in _PRICING.items():
        if model.startswith(key) or key.startswith(model):
            return pricing
    logger.debug("No pricing found for '%s' — using defaults", model)
    return _DEFAULT_PRICING


# ---------------------------------------------------------------------------
# CostTracker
# ---------------------------------------------------------------------------
class CostTracker:
    """
    Accumulates token usage and cost across modules and batches.

    Thread-safe for concurrent module classification (uses append-only lists).
    """

    def __init__(self, model: str = "azure/dsaic-llm-general"):
        self.model = model
        self.pricing = get_pricing(model)
        self._calls: list[dict[str, Any]] = []
        self._start_time = time.time()
        self._run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    def record_call(
        self,
        module: str,
        prompt_tokens: int,
        completion_tokens: int,
        n_records: int = 1,
        duration_s: float = 0.0,
        batch_index: int = -1,
        was_retry: bool = False,
        tier: int = 1,
    ) -> dict[str, Any]:
        """
        Record a single LLM API call.

        Returns the computed cost entry.
        """
        total_tokens = prompt_tokens + completion_tokens
        prompt_cost = (prompt_tokens / 1000) * self.pricing["prompt"]
        completion_cost = (completion_tokens / 1000) * self.pricing["completion"]
        total_cost = prompt_cost + completion_cost
        cost_per_record = total_cost / max(n_records, 1)

        entry = {
            "module": module,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "n_records": n_records,
            "prompt_cost_usd": round(prompt_cost, 6),
            "completion_cost_usd": round(completion_cost, 6),
            "total_cost_usd": round(total_cost, 6),
            "cost_per_record_usd": round(cost_per_record, 6),
            "duration_s": round(duration_s, 2),
            "tokens_per_second": round(total_tokens / max(duration_s, 0.001), 1),
            "batch_index": batch_index,
            "was_retry": was_retry,
            "tier": tier,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._calls.append(entry)
        return entry

    def record_from_response(
        self,
        module: str,
        response: Any,
        n_records: int = 1,
        duration_s: float = 0.0,
    ) -> dict[str, Any]:
        """
        Record usage from a raw LLM response object (litellm/openai format).
        Extracts token counts from the usage field.
        """
        usage = getattr(response, "usage", None)
        if usage is None:
            usage = getattr(response, "_usage", None)

        if usage is not None:
            prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
            completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        else:
            prompt_tokens = 0
            completion_tokens = 0

        return self.record_call(
            module=module,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            n_records=n_records,
            duration_s=duration_s,
        )

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------
    def summary_by_module(self) -> dict[str, dict[str, Any]]:
        """Aggregate costs per module."""
        modules: dict[str, dict[str, Any]] = defaultdict(lambda: {
            "total_calls": 0,
            "total_records": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "retry_calls": 0,
            "total_duration_s": 0.0,
        })

        for call in self._calls:
            mod = call["module"]
            m = modules[mod]
            m["total_calls"] += 1
            m["total_records"] += call["n_records"]
            m["total_prompt_tokens"] += call["prompt_tokens"]
            m["total_completion_tokens"] += call["completion_tokens"]
            m["total_tokens"] += call["total_tokens"]
            m["total_cost_usd"] += call["total_cost_usd"]
            m["total_duration_s"] += call["duration_s"]
            if call.get("was_retry"):
                m["retry_calls"] += 1

        # Compute derived metrics
        for mod, m in modules.items():
            m["avg_cost_per_record"] = round(
                m["total_cost_usd"] / max(m["total_records"], 1), 6
            )
            m["avg_tokens_per_record"] = round(
                m["total_tokens"] / max(m["total_records"], 1), 1
            )
            m["total_cost_usd"] = round(m["total_cost_usd"], 6)
            m["total_duration_s"] = round(m["total_duration_s"], 2)

        return dict(modules)

    def total_summary(self) -> dict[str, Any]:
        """Compute overall totals across all modules."""
        elapsed = time.time() - self._start_time
        total_prompt = sum(c["prompt_tokens"] for c in self._calls)
        total_completion = sum(c["completion_tokens"] for c in self._calls)
        total_cost = sum(c["total_cost_usd"] for c in self._calls)
        total_records = sum(c["n_records"] for c in self._calls)

        return {
            "run_id": self._run_id,
            "model": self.model,
            "total_calls": len(self._calls),
            "total_records": total_records,
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_tokens": total_prompt + total_completion,
            "total_cost_usd": round(total_cost, 4),
            "avg_cost_per_record": round(total_cost / max(total_records, 1), 6),
            "elapsed_s": round(elapsed, 2),
            "records_per_second": round(total_records / max(elapsed, 0.001), 2),
        }

    # ------------------------------------------------------------------
    # Cost estimation
    # ------------------------------------------------------------------
    def estimate_run_cost(
        self,
        n_records: int,
        modules: list[str] | None = None,
        avg_text_tokens: int = 500,
    ) -> dict[str, Any]:
        """
        Estimate the cost of a full run based on historical averages or defaults.

        Uses recorded call data if available, otherwise falls back to estimates.
        """
        by_module = self.summary_by_module()

        module_estimates: dict[str, float] = {}
        total_estimated = 0.0

        target_modules = modules or list(by_module.keys()) or ["classification"]

        for mod in target_modules:
            if mod in by_module and by_module[mod]["total_records"] > 0:
                # Use historical average
                cost_per_rec = by_module[mod]["avg_cost_per_record"]
            else:
                # Estimate: assume ~prompt_tokens + ~completion_tokens per record
                est_prompt = avg_text_tokens + 500  # text + system prompt amortised
                est_completion = 200  # per-record response
                cost_per_rec = (
                    (est_prompt / 1000) * self.pricing["prompt"]
                    + (est_completion / 1000) * self.pricing["completion"]
                )

            module_cost = cost_per_rec * n_records
            module_estimates[mod] = round(module_cost, 4)
            total_estimated += module_cost

        return {
            "n_records": n_records,
            "model": self.model,
            "estimated_total_usd": round(total_estimated, 4),
            "by_module": module_estimates,
            "note": "Estimates based on historical averages where available",
        }

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------
    def print_summary(self) -> None:
        """Print a formatted cost summary to the log."""
        total = self.total_summary()
        by_mod = self.summary_by_module()

        logger.info("=" * 70)
        logger.info("COST SUMMARY — Run %s", total["run_id"])
        logger.info("=" * 70)
        logger.info("Model:         %s", total["model"])
        logger.info("Total calls:   %d", total["total_calls"])
        logger.info("Total records: %d", total["total_records"])
        logger.info("Total tokens:  %s (prompt: %s + completion: %s)",
                     f'{total["total_tokens"]:,}',
                     f'{total["total_prompt_tokens"]:,}',
                     f'{total["total_completion_tokens"]:,}')
        logger.info("Total cost:    $%.4f", total["total_cost_usd"])
        logger.info("Avg/record:    $%.6f", total["avg_cost_per_record"])
        logger.info("Throughput:    %.1f records/sec", total["records_per_second"])
        logger.info("-" * 70)

        for mod, m in sorted(by_mod.items()):
            logger.info(
                "  %-20s │ %4d records │ %7s tokens │ $%.4f │ $%.6f/rec",
                mod, m["total_records"],
                f'{m["total_tokens"]:,}',
                m["total_cost_usd"],
                m["avg_cost_per_record"],
            )
        logger.info("=" * 70)

    def save(self, filepath: str | Path) -> None:
        """Save the full cost report to a JSON file."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        report = {
            "summary": self.total_summary(),
            "by_module": self.summary_by_module(),
            "calls": self._calls,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info("Cost report saved → %s", filepath)

    def to_dataframe(self) -> "pd.DataFrame":
        """Convert call log to a DataFrame for analysis."""
        import pandas as pd
        return pd.DataFrame(self._calls)


# ---------------------------------------------------------------------------
# Module-level cost-aware batch sizing
# ---------------------------------------------------------------------------
def recommend_batch_size(
    tracker: CostTracker,
    module: str,
    budget_per_call_usd: float = 0.05,
    max_batch: int = 20,
    min_batch: int = 3,
) -> int:
    """
    Recommend an optimal batch size for a module based on cost data.

    Cheap modules (e.g. escalation) → larger batches.
    Expensive modules (e.g. root_cause) → smaller batches.
    """
    by_module = tracker.summary_by_module()
    mod_stats = by_module.get(module)

    if not mod_stats or mod_stats["total_records"] == 0:
        return 10  # default

    avg_cost = mod_stats["avg_cost_per_record"]
    if avg_cost <= 0:
        return max_batch

    # How many records fit in the budget?
    recommended = int(budget_per_call_usd / avg_cost)
    recommended = max(min_batch, min(recommended, max_batch))

    logger.info(
        "Recommended batch size for %s: %d (avg $%.6f/record, budget $%.4f/call)",
        module, recommended, avg_cost, budget_per_call_usd,
    )
    return recommended
