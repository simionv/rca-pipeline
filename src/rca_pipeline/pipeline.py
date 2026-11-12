"""
pipeline.py – Main Orchestrator
=================================
Config-driven: MODULE_REGISTRY is built from pipeline_config.json at startup.
All import errors are caught gracefully so a broken module never crashes the import.
"""
from __future__ import annotations

import asyncio
import importlib
import json
import logging
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import importlib.util

import pandas as pd

from .config import RunConfig, get_credentials, load_pipeline_config
from .taxonomy import load_taxonomies
from .utils import (
    read_input_file, drop_enrichment_cols, make_batches,
    post_process, write_output_file,
)
from . import discovery as _disc

# Enhancement module imports (graceful — missing modules don't crash the pipeline)
try:
    from .enhancements.confidence import enrich_with_confidence, flag_low_confidence, inject_confidence_instruction, export_review_queue
except ImportError:
    enrich_with_confidence = flag_low_confidence = inject_confidence_instruction = export_review_queue = None

try:
    from .enhancements.feedback import FeedbackStore
except ImportError:
    FeedbackStore = None

try:
    from .enhancements.hierarchical import run_hierarchical_module
except ImportError:
    run_hierarchical_module = None

try:
    from .enhancements.incremental import IncrementalRunner
except ImportError:
    IncrementalRunner = None

try:
    from .enhancements.cost_tracker import CostTracker
except ImportError:
    CostTracker = None

try:
    from .enhancements.language import detect_language, preprocess_multilingual
except ImportError:
    detect_language = preprocess_multilingual = None

try:
    from .enhancements.quality_dashboard import run_quality_check
except ImportError:
    run_quality_check = None

from . import workspace
from .llm_client import (
    set_system_prompt_suffix, clear_system_prompt_suffix,
    register_cost_tracker, set_cost_tracker_module, unregister_cost_tracker,
    set_per_batch_suffixes, clear_per_batch_suffixes,
)

logger = logging.getLogger("pipeline")

_CONFIG_PATH = workspace.generated_dir() / "pipeline_config.json"
_GENERATED_MODULES_DIR = workspace.generated_dir() / "modules"

def _discoverable_domains() -> list[str]:
    """Return modules configured for discovery (mode='full' or 'extract_only') in pipeline_config.json."""
    return [
        name for name, mod_cfg in PIPELINE_CONFIG.get("modules", {}).items()
        if mod_cfg.get("discovery_mode") in ("full", "extract_only")
    ]


# ---------------------------------------------------------------------------
# Config + registry
# ---------------------------------------------------------------------------
def _load_pipeline_config() -> dict:
    cfg = load_pipeline_config(_CONFIG_PATH)
    if not cfg:
        logger.warning(
            "pipeline_config.json not found — run: "
            "rca build --input pipeline_definition.xlsx"
        )
        return {"modules": {}}
    return cfg


def _build_registry(config: dict) -> dict[str, Any]:
    registry: dict[str, Any] = {}
    for mod_name, mod_cfg in config.get("modules", {}).items():
        fn_name = mod_cfg.get("classify_fn", f"classify_{mod_name}")
        mod_path = _GENERATED_MODULES_DIR / f"{mod_name}.py"
        try:
            if not mod_path.exists():
                logger.warning(
                    "'%s' not found at %s — run `rca build` first.",
                    mod_name, mod_path,
                )
                continue
            spec = importlib.util.spec_from_file_location(mod_name, mod_path)
            mod  = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            fn   = getattr(mod, fn_name, None)
            if fn:
                registry[mod_name] = fn
            else:
                logger.warning("Module '%s' has no function '%s'", mod_name, fn_name)
        except (SyntaxError, IndentationError) as e:
            logger.error(
                "Syntax error in '%s' (line %s): %s — skipping.\n"
                "Fix or re-run: rca build --force %s",
                mod_path, getattr(e, "lineno", "?"), e.msg, mod_name,
            )
        except Exception as e:
            logger.error("Cannot import '%s': %s — skipping.", mod_path, e)
    return registry


PIPELINE_CONFIG  = _load_pipeline_config()
MODULE_REGISTRY  = _build_registry(PIPELINE_CONFIG)


# ---------------------------------------------------------------------------
# Record helpers
# ---------------------------------------------------------------------------
def prepare_records(df: pd.DataFrame, cfg: RunConfig) -> list[dict[str, str]]:
    return [
        {"uid": str(row[cfg.id_col]), "text": str(row[cfg.text_col])}
        for _, row in df.iterrows()
    ]


def prepare_batched_records(df: pd.DataFrame, cfg: RunConfig) -> list[list[dict[str, str]]]:
    return [
        prepare_records(b, cfg)
        for b in make_batches(df, cfg.batch_size, cfg.max_chars_per_batch, cfg.text_col)
    ]


# ---------------------------------------------------------------------------
# Single module runner
# ---------------------------------------------------------------------------
async def run_classification_module(
    module_name: str,
    batches: list[list[dict[str, str]]],
    taxonomies: dict[str, dict],
    cfg: RunConfig,
) -> list[dict[str, Any]]:
    if module_name not in MODULE_REGISTRY:
        logger.error(
            "Module '%s' not registered. Available: %s",
            module_name, list(MODULE_REGISTRY.keys()),
        )
        return []
    fn    = MODULE_REGISTRY[module_name]
    start = time.time()
    logger.info("Starting: %s", module_name)

    # B2 fix: attribute cost to this module
    set_cost_tracker_module(module_name)

    results = await fn(batches, taxonomies, cfg)
    logger.info("Done: %s — %d records in %.1fs",
                module_name, len(results), time.time() - start)
    return results


# ---------------------------------------------------------------------------
# Prompt suffix helpers (shared with `rca run`)
# ---------------------------------------------------------------------------
@dataclass
class Feedback:
    """Few-shot material loaded from the feedback store, per module."""
    store: Any = None
    prompts: dict[str, str] = field(default_factory=dict)     # static strategies
    smart_pools: dict[str, list[dict]] = field(default_factory=dict)  # 'smart' strategy


def build_feedback(cfg: RunConfig, modules: list[str], feedback_dir: str | None) -> Feedback:
    """Load corrections from feedback_dir and prepare few-shot text per module."""
    fb = Feedback()
    if FeedbackStore is None or not feedback_dir:
        return fb
    max_ex   = getattr(cfg, "feedback_max_examples", 5)
    strategy = getattr(cfg, "feedback_strategy", "recent")
    fb.store = FeedbackStore(feedback_dir)
    stats = fb.store.get_stats()
    if stats:
        logger.info("Feedback store: %s", stats)
    for mod_name in modules:
        if strategy == "smart":
            pool = fb.store.build_smart_pool(mod_name)
            if pool:
                fb.smart_pools[mod_name] = pool
                logger.info("Feedback smart pool: %d candidates for %s", len(pool), mod_name)
        else:
            prompt = fb.store.build_few_shot_prompt(
                mod_name, max_examples=max_ex, selection_strategy=strategy,
            )
            if prompt:
                fb.prompts[mod_name] = prompt
                logger.info("Feedback: %d-char few-shot prompt for %s", len(prompt), mod_name)
    return fb


def confidence_instruction_for(cfg: RunConfig) -> str:
    """The confidence self-report instruction, or '' when confidence is off."""
    if getattr(cfg, "enable_confidence", False) and inject_confidence_instruction is not None:
        return inject_confidence_instruction("")
    return ""


def module_suffix(name: str, batch: list[dict] | None, fb: Feedback, cfg: RunConfig,
                  confidence_instruction: str) -> str:
    """System-prompt suffix for one module (and, with the 'smart' strategy, one batch)."""
    parts = [confidence_instruction] if confidence_instruction else []
    if name in fb.smart_pools and batch is not None:
        reranked = fb.store.rerank_pool_for_batch(
            fb.smart_pools[name], batch, getattr(cfg, "feedback_max_examples", 5))
        batch_fb = fb.store.build_few_shot_prompt_for_batch(
            reranked,
            max_text_chars=getattr(cfg, "feedback_max_text_chars", 800),
            max_total_chars=getattr(cfg, "feedback_max_total_chars", 4000),
        )
        if batch_fb:
            parts.append(batch_fb)
    elif name in fb.prompts:
        parts.append(fb.prompts[name])
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Main async pipeline
# ---------------------------------------------------------------------------
async def run_pipeline_async(cfg: RunConfig) -> pd.DataFrame:
    cfg = replace(cfg)
    t0  = time.time()

    _section("STEP 1 · Loading inputs")
    get_credentials()
    logger.info("Model: %s | Mode: %s | Modules: %s", cfg.model, cfg.mode, cfg.modules)
    logger.info("Registry: %s", list(MODULE_REGISTRY.keys()) or "(empty — run `rca build`)")

    # ── B2 fix: register cost tracker ────────────────────────────────────
    cost_tracker = None
    if getattr(cfg, "track_costs", False) and CostTracker is not None:
        cost_tracker = CostTracker(model=cfg.model)
        register_cost_tracker(cost_tracker)
        logger.info("Cost tracking enabled")

    # ── B3 fix: load feedback store and build few-shot examples ──────────
    strategy = getattr(cfg, "feedback_strategy", "recent")
    fb = build_feedback(cfg, cfg.modules, getattr(cfg, "feedback_dir", "feedback"))
    feedback_store = fb.store

    # ── B1 fix: build confidence instruction ─────────────────────────────
    confidence_instruction = confidence_instruction_for(cfg)

    _section("STEP 2 · Pre-processing")
    taxonomies = load_taxonomies(cfg.taxonomy_dir)
    df         = read_input_file(cfg.input_file)
    df_original = df.copy()          # cache before any incremental slicing
    df         = drop_enrichment_cols(df)

    # Enhancement 6: Language detection
    if getattr(cfg, "detect_language", False) and detect_language is not None:
        _section("LANGUAGE DETECTION")
        lang_strategy = getattr(cfg, "language_strategy", "detect")
        en_min  = getattr(cfg, "lang_en_min_score", 0.15)
        en_marg = getattr(cfg, "lang_en_margin", 0.05)
        if lang_strategy == "translate" and preprocess_multilingual is not None:
            df = await preprocess_multilingual(df, cfg, text_col=cfg.text_col, strategy="translate")
        else:
            df = detect_language(df, text_col=cfg.text_col,
                                 en_min_score=en_min, en_margin=en_marg)

    # ── B6 fix: incremental processing ───────────────────────────────────
    incremental_runner = None
    cached_results: list[dict] = []
    if getattr(cfg, "incremental", False) and IncrementalRunner is not None:
        state_file = getattr(cfg, "incremental_state_file", None)
        if state_file:
            _section("INCREMENTAL MODE")
            incremental_runner = IncrementalRunner(state_file, cfg)
            new_df, changed_df, unchanged_df = incremental_runner.diff(
                df, id_col=cfg.id_col, text_col=cfg.text_col,
            )
            cached_results = incremental_runner.get_cached_results(
                unchanged_df, id_col=cfg.id_col,
            )
            df = pd.concat([new_df, changed_df], ignore_index=True)
            if len(df) == 0:
                logger.info("Incremental: all records cached — nothing to classify")
            else:
                logger.info("Incremental: classifying %d new/changed records", len(df))

    batches    = prepare_batched_records(df, cfg)
    logger.info("Input: %d rows | %d batches", len(df), len(batches))

    if cfg.mode == "discover":
        _section("DISCOVERY MODE")
        sample_df = df.sample(n=min(cfg.discovery_sample_n, len(df)), random_state=42)
        records   = prepare_records(sample_df, cfg)
        domains   = [m for m in cfg.modules if m in _discoverable_domains()]
        if domains:
            found = await _disc.run_all_discoveries(
                records, domains, cfg,
                output_dir=Path(cfg.taxonomy_dir) / "discovered",
            )
            for domain, tax in found.items():
                if tax:
                    key = domain if domain != "troubleshooting" else "troubleshooting_steps"
                    taxonomies[key] = tax
        else:
            logger.warning(
                "DISCOVERY MODE: no modules have discovery_mode='full' or 'extract_only' "
                "in pipeline_config.json. Nothing was discovered.\n"
                "  → Either run  'rca build --input <definition.xlsx>'  first,\n"
                "  → or set discovery_mode on the relevant modules in the Excel definition."
            )
        cfg = replace(cfg, mode="classify")

    _section("STEPS 3-4 · Classification")

    # Enhancement 3: Hierarchical classification for designated modules
    hierarchical_mods = set(getattr(cfg, "hierarchical_modules", []))

    # NOTE: Modules run sequentially here; each sets its prompt suffix
    # (confidence instruction + feedback examples) before its call.  The suffix
    # is a per-task ContextVar, so concurrent callers (`rca run`) set it inside
    # each task instead.
    all_results: list[dict[str, Any]] = []
    for name in cfg.modules:
        if strategy == "smart" and feedback_store is not None and name in fb.smart_pools:
            # Smart strategy: build per-batch suffixes (confidence + batch-specific
            # feedback) so each batch gets few-shot examples matched to its records.
            set_per_batch_suffixes([module_suffix(name, batch, fb, cfg, confidence_instruction)
                                    for batch in batches])
            set_system_prompt_suffix("")  # feedback handled per-batch
        else:
            # Static strategies: one suffix shared across all batches for this module
            set_system_prompt_suffix(module_suffix(name, None, fb, cfg, confidence_instruction))
            clear_per_batch_suffixes()

        set_cost_tracker_module(name)

        try:
            if name in hierarchical_mods and run_hierarchical_module is not None:
                logger.info("Using hierarchical (L1→L2) classification for: %s", name)
                res = await run_hierarchical_module(name, batches, taxonomies, cfg)
            else:
                res = await run_classification_module(name, batches, taxonomies, cfg)
        except Exception as exc:
            logger.error("Module %s raised: %s", name, exc)
            res = []
        finally:
            clear_per_batch_suffixes()

        # Enhancement 1: Confidence scoring
        if getattr(cfg, "enable_confidence", False) and enrich_with_confidence is not None:
            threshold = getattr(cfg, "confidence_threshold", 0.70)
            res = enrich_with_confidence(res, threshold=threshold)

        all_results.extend(res)

    # Clean up prompt suffix
    clear_system_prompt_suffix()

    # Merge cached results from incremental mode
    all_results = cached_results + all_results

    # Merge by uid
    grouped: dict[str, dict] = {}
    for r in all_results:
        uid = str(r.get("uid", ""))
        grouped.setdefault(uid, {"uid": uid}).update(r)

    # B6 fix: update incremental state with new results.
    # Use uid-set membership (not dict identity / value equality) to distinguish
    # newly classified records from those that came from the cache.
    if incremental_runner is not None and len(df) > 0:
        cached_uids = {str(r.get("uid", "")) for r in cached_results}
        new_results_only = [r for r in all_results
                            if str(r.get("uid", "")) not in cached_uids]
        incremental_runner.update_state(
            new_results_only, df,
            id_col=cfg.id_col, text_col=cfg.text_col,
        )

    _section("STEP 5 · Post-processing")
    # For post-processing, use the full original df (before incremental slicing).
    # df_original was captured before the incremental diff, so no second disk read needed.
    df_for_post = drop_enrichment_cols(df_original) if incremental_runner is not None else df

    df_out = post_process(df_for_post, list(grouped.values()), taxonomies, cfg)
    logger.info("Enriched: %d rows × %d columns", *df_out.shape)

    # Enhancement 1: Flag low-confidence rows
    if getattr(cfg, "enable_confidence", False) and flag_low_confidence is not None:
        threshold = getattr(cfg, "confidence_threshold", 0.70)
        df_out = flag_low_confidence(df_out, threshold=threshold)

        # Export review queue if requested
        if getattr(cfg, "export_review_queue", False) and export_review_queue is not None:
            review_path = str(Path(cfg.output_file or "output/review_queue.xlsx").parent / "review_queue.xlsx")
            export_review_queue(df_out, review_path)

    _section("STEP 6 · Output")
    if cfg.output_file:
        write_output_file(df_out, cfg.output_file)

    # Enhancement 5: Cost summary
    if cost_tracker is not None:
        cost_tracker.print_summary()
        cost_dir = getattr(cfg, "cost_report_dir", "cost_reports")
        cost_tracker.save(Path(cost_dir) / f"costs_{cost_tracker._run_id}.json")
        unregister_cost_tracker()

    # Enhancement 7: Quality dashboard
    if getattr(cfg, "run_quality_check", False) and run_quality_check is not None:
        _section("QUALITY DASHBOARD")
        quality_dir = getattr(cfg, "quality_report_dir", "output")
        prev_report = getattr(cfg, "previous_quality_report", None)
        run_quality_check(df_out, taxonomies, cfg, quality_dir, prev_report)

    logger.info("Pipeline done in %.1fs", time.time() - t0)
    return df_out


def run_pipeline(cfg: RunConfig) -> pd.DataFrame:
    return asyncio.run(run_pipeline_async(cfg))


def _section(title: str) -> None:
    logger.info("=" * 60)
    logger.info(title)
    logger.info("=" * 60)
