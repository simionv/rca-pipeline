"""
config.py – RunConfig & Credential Management
================================================
Central configuration dataclass for the pipeline.  Every tuneable setting
lives here so callers never need to touch individual module files.

Environment variables (all optional — sensible defaults are provided):
  RCA_MODEL            LiteLLM model string  (default: azure/dsaic-llm-general)
  RCA_TEMPERATURE      Sampling temperature  (default: 0.0)
  RCA_MAX_TOKENS       Max tokens per call   (default: 4096)
  RCA_TIMEOUT          HTTP timeout seconds  (default: 120)
  RCA_BATCH_SIZE       Records per LLM batch (default: 10)
  RCA_MAX_CHARS        Max chars per batch   (default: 60000)
  RCA_CONCURRENCY      Parallel batch limit  (default: 4)
  RCA_RETRIES          Retry attempts        (default: 3)
  MAX_WORKERS          Thread pool workers   (default: 4)
  MAX_IN_FLIGHT        Max concurrent LLM calls in flight (default: 8)
  CHECKPOINT_EVERY     Flush checkpoint every N batches   (default: 5)
  LOG_LEVEL            Logging level (default: INFO)

  AZURE_API_KEY        Azure OpenAI key
  AZURE_API_BASE       Azure endpoint URL
  AZURE_API_VERSION    Azure API version
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from dotenv import find_dotenv, load_dotenv

# ---------------------------------------------------------------------------
# Workspace root — the use-case folder (see workspace.py)
# ---------------------------------------------------------------------------
from .workspace import root as _workspace_root

_PROJECT_ROOT = _workspace_root()
load_dotenv(_PROJECT_ROOT / ".env")
load_dotenv(find_dotenv(usecwd=True))  # fall back to a shared .env higher up (e.g. the repo root)

# ---------------------------------------------------------------------------
# Apply LOG_LEVEL from environment (must happen before any logger is created)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s │ %(levelname)-7s | %(name)-22s | %(message)s",
    datefmt="%H:%M:%S",
)


# ---------------------------------------------------------------------------
# RunConfig
# ---------------------------------------------------------------------------
@dataclass
class RunConfig:
    """
    Central configuration object passed through every pipeline stage.

    Make a copy before mutating:
        from dataclasses import replace
        safe_cfg = replace(cfg, mode="classify")
    """

    # --- LLM provider -------------------------------------------------------
    model: str = os.getenv("RCA_MODEL", "azure/dsaic-llm-general")
    temperature: float = float(os.getenv("RCA_TEMPERATURE", "0.0"))
    max_tokens: int = int(os.getenv("RCA_MAX_TOKENS", "4096"))
    timeout: int = int(os.getenv("RCA_TIMEOUT", "120"))

    # --- Batching -----------------------------------------------------------
    batch_size: int = int(os.getenv("RCA_BATCH_SIZE", "10"))
    max_chars_per_batch: int = int(os.getenv("RCA_MAX_CHARS", "60000"))
    concurrency: int = int(os.getenv("RCA_CONCURRENCY", "2"))

    # --- Resilience ---------------------------------------------------------
    retries: int = int(os.getenv("RCA_RETRIES", "5"))

    # --- Async worker tuning ------------------------------------------------
    max_workers: int = int(os.getenv("MAX_WORKERS", "4"))
    max_in_flight: int = int(os.getenv("MAX_IN_FLIGHT", "8"))
    checkpoint_every: int = int(os.getenv("CHECKPOINT_EVERY", "5"))

    # --- Paths --------------------------------------------------------------
    taxonomy_dir: str = str(_PROJECT_ROOT / "generated" / "taxonomies")
    input_file: Optional[str] = None
    output_file: Optional[str] = None

    # --- Column names -------------------------------------------------------
    id_col: str = "uid"
    text_col: str = "transcript"

    # --- Module selection ---------------------------------------------------
    modules: List[str] = field(default_factory=lambda: [
        "contact_reason",
        "root_cause",
        "resolution",
        "escalation",
        "troubleshooting",
        "metadata",
    ])

    # --- Pipeline mode ------------------------------------------------------
    mode: str = "classify"

    # --- Discovery settings -------------------------------------------------
    discovery_sample_n: int = 100
    discovery_top_n: int = 80

    # --- Confidence scoring (Enhancement 1) ---------------------------------
    enable_confidence: bool = False
    confidence_threshold: float = 0.70
    export_review_queue: bool = False

    # --- Feedback / few-shot (Enhancement 2) --------------------------------
    feedback_dir: str = str(_PROJECT_ROOT / "runs" / "feedback")
    feedback_max_examples: int = 5
    feedback_strategy: str = "recent"

    # --- Hierarchical classification (Enhancement 3) ------------------------
    hierarchical_modules: List[str] = field(default_factory=list)

    # --- Incremental processing (Enhancement 4) -----------------------------
    incremental: bool = False
    incremental_state_file: Optional[str] = None

    # --- Cost tracking (Enhancement 5) --------------------------------------
    track_costs: bool = False
    cost_report_dir: str = str(_PROJECT_ROOT / "runs" / "cost_reports")

    # --- Language support (Enhancement 6) -----------------------------------
    detect_language: bool = False
    language_strategy: str = "translate"
    lang_en_min_score: float = 0.15
    lang_en_margin: float = 0.05

    # --- Quality dashboard (Enhancement 7) ----------------------------------
    run_quality_check: bool = False
    quality_report_dir: str = str(_PROJECT_ROOT / "runs" / "output")
    previous_quality_report: Optional[str] = None


# ---------------------------------------------------------------------------
# Shared pipeline config loader
# ---------------------------------------------------------------------------
def load_pipeline_config(config_path: Path | None = None) -> dict:
    """Load generated/pipeline_config.json. Returns {} if not found."""
    import json
    if config_path is None:
        config_path = _PROJECT_ROOT / "generated" / "pipeline_config.json"
    if not config_path.exists():
        return {}
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Credential helper
# ---------------------------------------------------------------------------
def get_credentials() -> dict:
    """Return Azure / provider credentials loaded from environment."""
    return {
        "AZURE_API_KEY":     os.getenv("AZURE_API_KEY", ""),
        "AZURE_API_BASE":    os.getenv("AZURE_API_BASE", ""),
        "AZURE_API_VERSION": os.getenv("AZURE_API_VERSION", ""),
    }
