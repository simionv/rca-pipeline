"""
rca run — Generalised production classification runner
================================================================
A product-agnostic replacement for scopus_run.py.  Works with ANY
pipeline_definition.xlsx — all product-specific knowledge is loaded
from pipeline_config.json at startup.

USAGE
-----
  # Minimal — auto-detects everything from pipeline_config.json
  rca run --input data/transcripts.csv

  # Full control
  rca run \
      --input  data/transcripts.csv \
      --output output/enriched.xlsx \
      --id-col uid \
      --text-col conversation \
      --taxonomy-dir taxonomies \
      --batch-size 12 \
      --concurrency 4 \
      --retries 5 \
      --max-tokens 8192 \
      --modules contact_reason root_cause resolution

  # Use a run profile (JSON file with all settings)
  rca run --profile profiles/scopus.json

  # Resume after crash (automatic — just re-run the same command)
  rca run --input data/transcripts.csv

  # Watch live progress
  tail -f run_pipeline.log

  # Background (survives terminal close)
  nohup rca run --input data/transcripts.csv \
      > console.log 2>&1 &

RUN PROFILES
------------
A profile is a JSON file containing any CLI argument.  Create one
per product so you never need to remember flags:

  profiles/scopus.json:
  {
    "input":        "data/Scopus_processed_cases.csv",
    "output":       "output/Scopus_enriched.xlsx",
    "text_col":     "conversation",
    "batch_size":   12,
    "concurrency":  4,
    "retries":      5,
    "max_tokens":   8192,
    "taxonomy_dir": "taxonomies"
  }

  profiles/jira.json:
  {
    "input":        "data/jira_tickets.csv",
    "output":       "output/jira_enriched.xlsx",
    "text_col":     "description",
    "batch_size":   8,
    "modules":      ["contact_reason", "root_cause"]
  }

Then run:  rca run --profile profiles/scopus.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════
# Sentinel auto-detection
# ═══════════════════════════════════════════════════════════════════════════

# Anchor all default paths to the workspace (use-case folder): RCA_WORKSPACE
# if set, otherwise the current directory.  See rca_pipeline/workspace.py.
_PROJECT_DIR           = Path(os.environ.get("RCA_WORKSPACE", ".")).resolve()
_DEFAULT_CONFIG_PATH   = str(_PROJECT_DIR / "generated" / "pipeline_config.json")
_DEFAULT_MANIFEST_PATH = str(_PROJECT_DIR / "generated" / "build_manifest.json")
_DEFAULT_DEFINITION_DIR = str(_PROJECT_DIR / "definitions")
_DEFAULT_TAXONOMY_DIR  = str(_PROJECT_DIR / "generated" / "taxonomies")
_DEFAULT_CHECKPOINT_DIR = str(_PROJECT_DIR / "runs" / "checkpoints")


def _load_pipeline_config(config_path: str = _DEFAULT_CONFIG_PATH) -> dict:
    """Load pipeline_config.json — the generated config from build_pipeline.py."""
    p = Path(config_path)
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _check_build_staleness() -> None:
    """Warn if generated files may be stale relative to the definition Excel."""
    manifest_path = Path(_DEFAULT_MANIFEST_PATH)
    if not manifest_path.exists():
        return
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    generated_at = manifest.get("generated_at", "")
    if not generated_at:
        return

    import datetime as _dt
    try:
        gen_time = _dt.datetime.fromisoformat(generated_at)
    except ValueError:
        return

    defn_dir = Path(_DEFAULT_DEFINITION_DIR)
    if not defn_dir.exists():
        return
    for xlsx in defn_dir.glob("*.xlsx"):
        mtime = _dt.datetime.fromtimestamp(xlsx.stat().st_mtime, tz=_dt.timezone.utc)
        if mtime > gen_time:
            logger.warning(
                "BUILD STALENESS: '%s' was modified after the last build "
                "(Excel: %s > build: %s). Re-run: rca build "
                "--input definitions/<file>.xlsx",
                xlsx.name,
                mtime.strftime("%Y-%m-%d %H:%M"),
                gen_time.strftime("%Y-%m-%d %H:%M"),
            )


def _build_sentinel_map(pipeline_config: dict) -> dict[str, str]:
    """
    Auto-derive the sentinel field for each module from pipeline_config.json.

    Strategy (in priority order):
      1. First field with field_type 'code'  (e.g. contact_reason_primary_code)
      2. First field with field_type 'bool'  (e.g. escalated)
      3. First field listed for the module   (fallback)

    This eliminates the hardcoded _MODULE_SENTINEL dict from scopus_run.py.
    """
    # We need field-level info.  pipeline_config.json stores code_fields and
    # enum_validators, but not the full field list per module.  So we also
    # check the module .py files for field names, or fall back to heuristics.
    #
    # Best approach: read the Excel-derived config.  build_pipeline_config()
    # stores field info in several places — we reconstruct from what's available.

    sentinels: dict[str, str] = {}

    # Try to load the definition Excel for full field info
    definition_path = _find_definition_excel(pipeline_config)
    if definition_path:
        try:
            import pandas as pd
            fields_df = pd.read_excel(definition_path, sheet_name="fields", engine="openpyxl")
            # Clean header rows
            fields_df = fields_df[fields_df["module_name"].notna()]
            fields_df = fields_df[~fields_df["module_name"].astype(str).str.startswith(
                ("prompt_", "Green", "Edit", "L1", "level", "module_name")
            )]

            for mod_name in pipeline_config.get("modules", {}):
                mod_fields = fields_df[fields_df["module_name"] == mod_name]
                if mod_fields.empty:
                    continue

                # Priority 1: first 'code' type field
                code_fields = mod_fields[
                    mod_fields["field_type"].astype(str).str.strip().str.lower() == "code"
                ]
                if not code_fields.empty:
                    sentinels[mod_name] = str(code_fields.iloc[0]["field_name"]).strip()
                    continue

                # Priority 2: first 'bool' type field
                bool_fields = mod_fields[
                    mod_fields["field_type"].astype(str).str.strip().str.lower() == "bool"
                ]
                if not bool_fields.empty:
                    sentinels[mod_name] = str(bool_fields.iloc[0]["field_name"]).strip()
                    continue

                # Priority 3: first 'str' type field (prefer scalar over list)
                str_fields = mod_fields[
                    mod_fields["field_type"].astype(str).str.strip().str.lower() == "str"
                ]
                if not str_fields.empty:
                    sentinels[mod_name] = str(str_fields.iloc[0]["field_name"]).strip()
                    continue

                # Priority 4: first field (any type)
                sentinels[mod_name] = str(mod_fields.iloc[0]["field_name"]).strip()

            return sentinels
        except Exception as e:
            logger.warning("Could not read definition Excel for sentinel detection: %s", e)

    # Fallback: derive from pipeline_config.json heuristics
    for mod_name, mod_cfg in pipeline_config.get("modules", {}).items():
        # Check code_fields list
        code_fields = pipeline_config.get("code_fields", [])
        found = False
        for cf in code_fields:
            if cf.startswith(mod_name) or cf.startswith(mod_name.replace("_", "")):
                sentinels[mod_name] = cf
                found = True
                break
        if not found:
            # Last resort: use <module_name>_primary_code or first known field pattern
            prefix = mod_cfg.get("taxonomy_prefix", "")
            if prefix:
                sentinels[mod_name] = f"{mod_name}_primary_code"
            else:
                # No taxonomy — use the module's classify_fn name to guess
                sentinels[mod_name] = ""  # will need manual override

    return sentinels


def _find_definition_excel(pipeline_config: dict | None = None) -> Path | None:
    """
    Find the pipeline definition Excel that matches the current pipeline config.

    When pipeline_config is supplied, scans all definition files and returns
    the one whose 'modules' sheet contains every module in the config — so the
    right Excel is selected even when multiple definitions exist.  Falls back
    to alphabetical order if no match is found.
    """
    defn_dir = Path(_DEFAULT_DEFINITION_DIR)
    candidates: list[Path] = []
    if defn_dir.exists():
        candidates = sorted(p for p in defn_dir.glob("*.xlsx") if "~$" not in p.name)

    if pipeline_config and candidates:
        target = set(pipeline_config.get("modules", {}).keys())
        if target:
            for excel_path in candidates:
                try:
                    import pandas as _pd
                    mdf = _pd.read_excel(excel_path, sheet_name="modules", engine="openpyxl")
                    excel_mods = set(mdf["module_name"].dropna().astype(str).str.strip())
                    if target.issubset(excel_mods):
                        return excel_path
                except Exception:
                    pass

    if candidates:
        return candidates[0]

    for p in Path(".").glob("*pipeline_definition*.xlsx"):
        if "~$" not in p.name:
            return p
    return None


# ═══════════════════════════════════════════════════════════════════════════
# Logging setup (deferred until we know the run name)
# ═══════════════════════════════════════════════════════════════════════════

logger = logging.getLogger("run_pipeline")


def _setup_logging(log_file: str, console_level: int = logging.INFO) -> None:
    """Configure logging to both file and stdout.

    Uses force=True to override any basicConfig() already called by
    imported modules (pipeline.py, llm_client.py both call basicConfig
    at import time, which would otherwise cause this setup to be silently
    ignored).

    console_level controls what appears on stdout. In non-TTY mode (e.g.
    notebook subprocess) this is set to WARNING so only the clean progress
    lines and evaluation table are visible \u2014 INFO detail stays in the file.
    """
    _fmt = "%(asctime)s \u2502 %(levelname)-7s \u2502 %(name)-20s \u2502 %(message)s"
    _console = logging.StreamHandler(sys.stdout)
    _console.setLevel(console_level)
    _console.setFormatter(logging.Formatter(_fmt, datefmt="%H:%M:%S"))
    logging.basicConfig(
        level=logging.INFO,
        format=_fmt,
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            _console,
        ],
        force=True,
    )
    # Suppress noisy loggers
    for name in ("LiteLLM", "litellm", "httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)


# ═══════════════════════════════════════════════════════════════════════════
# Sentinel check
# ═══════════════════════════════════════════════════════════════════════════

def _is_done(mod: str, record: dict, sentinel_map: dict[str, str]) -> bool:
    """Return True if this record was classified by this module."""
    sentinel = sentinel_map.get(mod, "")
    if not sentinel or sentinel not in record:
        return False
    val = record[sentinel]
    if isinstance(val, (list, bool)):
        return True
    return val not in (None, "", [])


# ═══════════════════════════════════════════════════════════════════════════
# Progress display
# ═══════════════════════════════════════════════════════════════════════════

_IS_TTY = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _clear_lines(n: int) -> None:
    if _IS_TTY and n > 0:
        sys.stdout.write(f"\033[{n}A\033[J")
        sys.stdout.flush()


def _progress_table(
    modules: list, done: dict, module_todo: dict, recs: dict, errs: dict,
    t_start: dict, previously_done: dict, total_records: int,
    elapsed_total: float, checkpoint_file: str, first: bool = False,
    n_modules: int = 1,
) -> int:
    now = time.time()
    lines = []

    lines.append(
        f"{'Module':<22}  {'Prev':>6}  {'Done':>6}/{'Todo':<6}  "
        f"{'Total':>7}  {'Recs':>7}  {'Err':>4}  Status"
    )
    lines.append("─" * 78)

    for m in modules:
        prev = previously_done.get(m, 0)
        todo = module_todo.get(m, 0)
        d = done.get(m, 0)
        total_done = prev + d
        pct = total_done / total_records * 100 if total_records else 0

        if t_start.get(m) is None:
            status = "\u2713 nothing to do" if todo == 0 else "waiting"
        elif d >= todo:
            status = f"\u2713 done ({now - t_start[m]:.0f}s)"
        else:
            elapsed = now - t_start[m]
            pct_run = d / todo * 100 if todo else 100
            if d > 0:
                rate = d / elapsed
                eta_s = (todo - d) / rate
                eta = f"ETA {eta_s/60:.0f}m" if eta_s > 90 else f"ETA {eta_s:.0f}s"
            else:
                eta = "..."
            status = f"{pct_run:5.1f}%  {eta}"

        err_str = f"\u26a0{errs.get(m, 0)}" if errs.get(m, 0) else ""
        lines.append(
            f"  {m:<20}  {prev:6,}  {d:6}/{todo:<6}  "
            f"{total_done:6,}  {recs.get(m, 0):7,}  {err_str:>4}  {status}"
        )

    lines.append("─" * 78)
    total_prev = sum(previously_done.values())
    total_new_rec = sum(recs.values())
    total_all = total_prev + sum(done.values())
    overall_pct = total_all / (total_records * len(modules)) * 100 if total_records else 0

    if elapsed_total > 0 and sum(done.values()) > 0:
        batch_rate = sum(done.values()) / elapsed_total
        remaining = sum(max(0, module_todo.get(m, 0) - done.get(m, 0)) for m in modules)
        eta_total = remaining / batch_rate if batch_rate > 0 else 0
        eta_str = f"  |  ETA ~{eta_total/60:.0f} min" if eta_total > 60 else f"  |  ETA ~{eta_total:.0f}s"
    else:
        eta_str = ""

    lines.append(
        f"  {'TOTAL':20}  {total_prev:6,}  "
        f"{sum(done.values()):6}/{sum(module_todo.values()):<6}  "
        f"{total_all:6,}  {total_new_rec:7,}  "
        f"     {overall_pct:5.1f}%  elapsed {elapsed_total/60:.1f}m{eta_str}"
    )
    # ── Throughput + cost row ─────────────────────────────────────────────
    rec_done   = sum(recs.values())
    prev_recs  = sum(previously_done.values())
    rec_total  = total_records * n_modules
    lines.append("─" * 78)
    if elapsed_total > 0 and rec_done > 0:
        rec_rate    = rec_done / elapsed_total
        sec_per_rec = 1.0 / rec_rate
        remaining_r = max(0, rec_total - rec_done - prev_recs)
        eta_r       = remaining_r / rec_rate
        eta_r_str   = (f"~{eta_r/60:.0f} min" if eta_r > 90 else f"~{eta_r:.0f}s")
        elapsed_str = (f"{elapsed_total/60:.1f} min" if elapsed_total >= 60 else f"{elapsed_total:.0f}s")
        lines.append(
            f"  {rec_done:,}/{rec_total:,} rec done"
            f"  │  {rec_rate:.1f} rec/s"
            f"  │  {sec_per_rec:.2f} s/ticket"
            f"  │  ETA: {eta_r_str}"
            f"  │  Elapsed: {elapsed_str}"
        )
    else:
        lines.append("  Waiting for first results...")

    try:
        from rca_pipeline.llm_client import get_cost_tracker
        _ct = get_cost_tracker()
        if _ct is not None and _ct._calls:
            _calls = list(_ct._calls)
            _total_cost  = sum(c["total_cost_usd"] for c in _calls)
            _total_n     = sum(c["n_records"]       for c in _calls)
            _total_in    = sum(c["prompt_tokens"]   for c in _calls)
            _total_out   = sum(c["completion_tokens"] for c in _calls)
            if _total_n > 0:
                lines.append(
                    f"  Cost: ${_total_cost / _total_n:.5f}/ticket"
                    f"  │  {(_total_in + _total_out) / _total_n:.0f} tok/ticket"
                    f"  ({_total_in / _total_n:.0f} in + {_total_out / _total_n:.0f} out)"
                    f"  │  Total so far: ${_total_cost:.4f}"
                )
    except Exception:
        pass

    lines.append(f"  Checkpoint: {checkpoint_file}")
    lines.append("")

    if not first:
        _clear_lines(len(lines))
    print("\n".join(lines), end="", flush=True)
    return len(lines)


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def _dry_run_report(
    modules, input_file, output_file, df, batches, taxonomies,
    sentinel_map, checkpoint_file, bad_uids_file, cfg_kwargs,
) -> None:
    """Print a summary of what a real run would do and exit."""
    import pandas as _pd
    sep = "=" * 78
    print(f"\n{sep}")
    print("  DRY RUN — no LLM calls will be made, no output will be written")
    print(sep)
    print(f"\n  Input:       {input_file}  ({len(df):,} records)")
    print(f"  Output:      {output_file}  (would be written)")
    print(f"  Checkpoint:  {checkpoint_file}")
    print(f"  Bad-UIDs:    {bad_uids_file}")
    print(f"  Taxonomy:    {cfg_kwargs.get('taxonomy_dir', '—')}")
    print(f"\n  Modules ({len(modules)}):")
    for m in modules:
        sentinel = sentinel_map.get(m, "(none)")
        tax_loaded = "yes" if any(m in k or k in m for k in taxonomies if taxonomies[k]) else "no"
        print(f"    {m:<26}  sentinel={sentinel:<35}  taxonomy={tax_loaded}")
    print(f"\n  Batching:")
    sizes = [len(b) for b in batches]
    print(f"    {len(batches):,} batches  |  records: min={min(sizes) if sizes else 0} "
          f"max={max(sizes) if sizes else 0} mean={sum(sizes)/len(sizes):.1f}" if sizes else
          f"    0 batches")
    print(f"    Total batch-calls to dispatch: {len(batches) * len(modules):,}")
    print(f"\n  Taxonomy files loaded:  {[k for k, v in taxonomies.items() if v]}")
    print(f"  Taxonomy files empty:   {[k for k, v in taxonomies.items() if not v]}")
    print(f"\n  Enhancements enabled:")
    enh_fields = {
        "enable_confidence": "Confidence scoring",
        "incremental":       "Incremental processing",
        "track_costs":       "Cost tracking",
        "detect_language":   "Language detection",
        "run_quality_check": "Quality dashboard",
    }
    for field, label in enh_fields.items():
        val = cfg_kwargs.get(field, False)
        if val:
            print(f"    + {label}")
    print(f"\n{sep}\n")


def _resolve_output(args: argparse.Namespace) -> str:
    """The output file: --output, or <input>_enriched.xlsx next to the input."""
    if args.output:
        return args.output
    return str(Path(args.input).parent / f"{Path(args.input).stem}_enriched.xlsx")


async def run(args: argparse.Namespace) -> None:
    """Main classification loop — fully parameterised, no hardcoded paths."""

    # ── Resolve logging FIRST — before any pipeline imports ───────────────
    # Pipeline modules (pipeline.py, llm_client.py) call logging.basicConfig()
    # at import time.  We must set up our file handler before those imports
    # so all messages (including import-time ones) go to the log file.
    input_file      = args.input
    log_file        = args.log_file or "run_pipeline.log"
    run_name        = args.run_name or Path(input_file).stem

    # In non-TTY mode (notebook subprocess, CI, pipe) suppress INFO on stdout
    # so only the clean progress lines and evaluation table are visible.
    # Full detail still goes to the log file.
    _console_level = logging.INFO if _IS_TTY else logging.WARNING
    _setup_logging(log_file, console_level=_console_level)

    # ── Set LLM backend BEFORE importing pipeline modules ─────────────────
    # llm_client.py reads os.environ["LLM_BACKEND"] at import time, so we
    # must inject the value before the import triggers.
    if args.backend:
        os.environ["LLM_BACKEND"] = args.backend
        logger.info("LLM backend set via --backend: %s", args.backend)
    if args.model:
        os.environ["RCA_MODEL"] = args.model
        logger.info("LLM model set via --model: %s", args.model)

    # ── Now import pipeline modules (their basicConfig calls are overridden) ─
    from rca_pipeline.config import RunConfig, get_credentials
    from rca_pipeline.taxonomy import load_taxonomies
    from rca_pipeline.utils import (
        read_input_file, drop_enrichment_cols, post_process, write_output_file,
    )
    from rca_pipeline.pipeline import (
        MODULE_REGISTRY, prepare_batched_records, run_classification_module,
        build_feedback, confidence_instruction_for, module_suffix,
    )
    from rca_pipeline.llm_client import set_system_prompt_suffix, set_cost_tracker_module

    get_credentials()

    # ── Resolve remaining settings ────────────────────────────────────────
    output_file     = _resolve_output(args)
    taxonomy_dir    = args.taxonomy_dir
    id_col          = args.id_col
    text_col        = args.text_col
    batch_size      = args.batch_size
    max_chars       = args.max_chars
    concurrency     = args.concurrency
    retries         = args.retries
    max_tokens      = args.max_tokens
    _ckpt_dir = Path(_DEFAULT_CHECKPOINT_DIR)
    _ckpt_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_file = args.checkpoint or str(
        _ckpt_dir / f"{Path(input_file).stem}_checkpoint.jsonl"
    )
    bad_uids_file   = args.bad_uids or str(
        _ckpt_dir / f"{Path(input_file).stem}_bad_uids.txt"
    )

    modules_requested = args.modules or list(MODULE_REGISTRY.keys())

    # ── Build staleness check ─────────────────────────────────────────────
    _check_build_staleness()

    # ── Pipeline config + sentinels ───────────────────────────────────────
    pipeline_config = _load_pipeline_config()
    sentinel_map = _build_sentinel_map(pipeline_config)

    # Allow user overrides for sentinels via --sentinel mod:field
    for override in (args.sentinel or []):
        if ":" in override:
            mod, field = override.split(":", 1)
            sentinel_map[mod] = field

    logger.info("Sentinel map: %s", sentinel_map)

    # Warn about modules with no sentinel
    for mod in modules_requested:
        if not sentinel_map.get(mod):
            logger.warning(
                "Module '%s' has no sentinel field — checkpoint resume cannot "
                "detect prior completion for this module. Use --sentinel %s:<field> "
                "to specify one.", mod, mod
            )

    # ── Build RunConfig ───────────────────────────────────────────────────
    cfg_kwargs = dict(
        input_file=input_file,
        output_file=output_file,
        taxonomy_dir=taxonomy_dir,
        id_col=id_col,
        text_col=text_col,
        modules=modules_requested,
        batch_size=batch_size,
        max_chars_per_batch=max_chars,
        concurrency=concurrency,
        retries=retries,
        max_tokens=max_tokens,
        mode="classify",
    )
    if args.model:
        cfg_kwargs["model"] = args.model
    # Left out of cfg_kwargs when unset so RunConfig's own default (RCA_TEMPERATURE,
    # or 0.0) still applies. 0.0 is a legitimate value, so test for None, not falsiness.
    if args.temperature is not None:
        cfg_kwargs["temperature"] = args.temperature
        logger.info("LLM temperature set via --temperature/profile: %s", args.temperature)

    # I1 fix: forward enhancement settings from profile/CLI into RunConfig.
    # These attributes may have been set by the profile JSON loader or CLI args.
    _enhancement_fields = [
        "enable_confidence", "confidence_threshold", "export_review_queue",
        "feedback_dir", "feedback_max_examples", "feedback_strategy",
        "hierarchical_modules",
        "incremental", "incremental_state_file",
        "track_costs", "cost_report_dir",
        "detect_language", "language_strategy",
        "run_quality_check", "quality_report_dir", "previous_quality_report",
    ]
    for field in _enhancement_fields:
        val = getattr(args, field, None)
        if val is not None:
            cfg_kwargs[field] = val

    cfg = RunConfig(**cfg_kwargs)

    modules = cfg.modules

    # ── Load data ─────────────────────────────────────────────────────────
    logger.info("Loading taxonomies from %s", taxonomy_dir)
    taxonomies = load_taxonomies(cfg.taxonomy_dir)
    loaded = [k for k, v in taxonomies.items() if v]
    missing = [k for k, v in taxonomies.items() if not v]
    logger.info("Taxonomies loaded: %s", loaded)
    if missing:
        logger.warning("Empty taxonomies: %s", missing)

    logger.info("Loading input: %s", input_file)
    df = read_input_file(cfg.input_file)
    df = drop_enrichment_cols(df)

    # ── Bad-UID skip list ─────────────────────────────────────────────────
    bad_uids_path = Path(bad_uids_file)
    bad_uids: set = set()
    if bad_uids_path.exists():
        bad_uids = {
            line.strip()
            for line in bad_uids_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        }
        if bad_uids:
            logger.warning("Skipping %d bad UIDs from %s", len(bad_uids), bad_uids_file)
            df = df[~df[id_col].astype(str).isin(bad_uids)].reset_index(drop=True)
            logger.info("Dataset after exclusions: %d records", len(df))

    batches = prepare_batched_records(df, cfg)

    # ── Dry-run: show what would run and exit ────────────────────────────
    if getattr(args, "dry_run", False):
        _dry_run_report(
            modules=modules_requested,
            input_file=input_file,
            output_file=output_file,
            df=df,
            batches=batches,
            taxonomies=taxonomies,
            sentinel_map=sentinel_map,
            checkpoint_file=checkpoint_file,
            bad_uids_file=bad_uids_file,
            cfg_kwargs=cfg_kwargs,
        )
        return

    if not batches:
        logger.error(
            "No batches created — 0 records to process. "
            "Check that: (1) --input file is not empty, "
            "(2) --id-col '%s' exists in the data, "
            "(3) --text-col '%s' exists in the data, "
            "(4) bad-UIDs list hasn't excluded everything.",
            id_col, text_col,
        )
        # Show available columns to help diagnose
        logger.error("Available columns: %s", list(df.columns))
        logger.error("DataFrame has %d rows after pre-processing", len(df))
        return

    # ── Enhancement: language detection / translation ────────────────────
    if getattr(cfg, "detect_language", False):
        from rca_pipeline.enhancements.language import detect_language, preprocess_multilingual
        if getattr(cfg, "language_strategy", "detect") == "translate":
            df = await preprocess_multilingual(df, cfg, text_col=cfg.text_col, strategy="translate")
        else:
            df = detect_language(df, text_col=cfg.text_col,
                                 en_min_score=getattr(cfg, "lang_en_min_score", 0.15),
                                 en_margin=getattr(cfg, "lang_en_margin", 0.05))
        batches = prepare_batched_records(df, cfg)

    # ── Enhancement: incremental — classify only new/changed records ─────
    incremental_runner = None
    cached_results: list = []
    df_to_classify = df
    if getattr(cfg, "incremental", False) and getattr(cfg, "incremental_state_file", None):
        from rca_pipeline.enhancements.incremental import IncrementalRunner
        import pandas as pd
        incremental_runner = IncrementalRunner(cfg.incremental_state_file, cfg)
        new_df, changed_df, unchanged_df = incremental_runner.diff(df, id_col=id_col, text_col=text_col)
        cached_results = incremental_runner.get_cached_results(unchanged_df, id_col=id_col)
        df_to_classify = pd.concat([new_df, changed_df], ignore_index=True)
        batches = prepare_batched_records(df_to_classify, cfg) if len(df_to_classify) else []
        logger.info("Incremental: %d new/changed records to classify, %d reused from %s",
                    len(df_to_classify), len(cached_results), cfg.incremental_state_file)

    # ── Enhancements applied per batch: feedback, confidence, hierarchical ─
    feedback_dir = getattr(args, "feedback_dir", None)  # opt-in: only when set by flag or profile
    fb = build_feedback(cfg, modules, feedback_dir)
    confidence_instruction = confidence_instruction_for(cfg)
    hierarchical_mods = set(getattr(cfg, "hierarchical_modules", None) or [])
    if hierarchical_mods:
        from rca_pipeline.enhancements.hierarchical import run_hierarchical_module
    confidence_on = bool(getattr(cfg, "enable_confidence", False))
    confidence_threshold = getattr(cfg, "confidence_threshold", 0.70)
    if confidence_on:
        from rca_pipeline.enhancements.confidence import (
            enrich_with_confidence, export_review_queue, flag_low_confidence,
        )

    sizes = [len(b) for b in batches] or [0]
    logger.info(
        "Dataset: %d records | %d batches | sizes min=%d max=%d mean=%.1f",
        len(df), len(batches), min(sizes), max(sizes), sum(sizes) / len(sizes),
    )

    # ── Load checkpoint ───────────────────────────────────────────────────
    ckpt_path = Path(checkpoint_file)
    ckpt_results: list = []
    completed: dict[str, set] = {m: set() for m in modules}

    if ckpt_path.exists():
        file_size_mb = ckpt_path.stat().st_size / 1_048_576
        logger.info("Loading checkpoint: %s (%.1f MB)", checkpoint_file, file_size_mb)
        with open(ckpt_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    ckpt_results.append(r)
                    uid = str(r.get("uid", ""))
                    for mod in modules:
                        if _is_done(mod, r, sentinel_map):
                            completed[mod].add(uid)
        logger.info(
            "Checkpoint: %d raw records, %d unique UIDs",
            len(ckpt_results), len({r.get("uid") for r in ckpt_results}),
        )
    else:
        logger.info("No checkpoint found — fresh start")

    # ── Resume summary ────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print(f"  RCA PIPELINE — {run_name}")
    print(f"  Started:  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Input:    {input_file}  ({len(df):,} records)")
    print(f"  Modules:  {modules}")
    print("=" * 78)
    print()

    previously_done = {m: len(completed[m]) for m in modules}

    def _batches_for(mod: str) -> list:
        done_set = completed[mod]
        if not done_set:
            return batches
        return [b for b in batches
                if any(str(r.get("uid", "")) not in done_set for r in b)]

    total_remaining = 0
    print(f"  {'Module':<22}  {'Previously done':>18}  {'Batches todo':>14}")
    print("  " + "─" * 60)

    for mod in modules:
        prev = previously_done[mod]
        pct = prev / len(df) * 100 if len(df) else 0
        todo = len(_batches_for(mod))
        total_remaining += todo
        bar = "\u2588" * int(pct / 2.5)
        print(f"  {mod:<22}  {prev:6,}/{len(df):,}  ({pct:5.1f}%)  {bar}")
        print(f"  {'':22}  skip={len(batches) - todo:4d}  todo={todo:4d}")

    print()
    print(f"  Total batch-calls remaining: {total_remaining:,}")
    print(f"  Checkpoint: {checkpoint_file}")
    print()

    if total_remaining == 0:
        print("  All modules complete — running post-processing only.")
    else:
        print(f"  Starting classification in 3 seconds... (Ctrl+C to abort)")
        time.sleep(3)
    print()

    # ── Cost tracker setup ───────────────────────────────────────────────
    cost_tracker = None
    if cfg.track_costs:
        from rca_pipeline.enhancements.cost_tracker import CostTracker
        from rca_pipeline.llm_client import register_cost_tracker, unregister_cost_tracker
        _model_str = getattr(cfg, "model", None) or os.environ.get("RCA_MODEL", "unknown")
        cost_tracker = CostTracker(_model_str)
        register_cost_tracker(cost_tracker)
        logger.info("Cost tracking enabled (model: %s)", _model_str)

    # ── Dispatch ──────────────────────────────────────────────────────────
    semaphore = asyncio.Semaphore(concurrency)
    done_count = {m: 0 for m in modules}
    rec_count = {m: 0 for m in modules}
    err_count = {m: 0 for m in modules}
    t_start_mod = {m: None for m in modules}
    module_todo = {m: len(_batches_for(m)) for m in modules}
    all_new: list[dict] = []
    t_run_start = time.time()
    last_print = [0.0]
    n_lines = [0]
    REFRESH_SECS = 5

    async def _one(batch, mod):
        if t_start_mod[mod] is None:
            t_start_mod[mod] = time.time()
        async with semaphore:
            try:
                # Each batch runs in its own asyncio task, so these per-task
                # settings cannot leak into another module's concurrent calls.
                set_system_prompt_suffix(module_suffix(mod, batch, fb, cfg, confidence_instruction))
                set_cost_tracker_module(mod)
                if mod in hierarchical_mods:
                    result = await run_hierarchical_module(mod, [batch], taxonomies, cfg)
                else:
                    result = await run_classification_module(mod, [batch], taxonomies, cfg)
                if confidence_on:
                    result = enrich_with_confidence(result, threshold=confidence_threshold)
                return mod, result, None
            except Exception as e:
                return mod, [], e

    coros = [_one(b, m) for m in modules for b in _batches_for(m)]

    if not coros:
        logger.info("Nothing to classify — all modules complete")
    else:
        logger.info("Dispatching %d batch-calls (concurrency=%d)", len(coros), concurrency)

        if _IS_TTY:
            n_lines[0] = _progress_table(
                modules, done_count, module_todo, rec_count, err_count,
                t_start_mod, previously_done, len(df), 0, checkpoint_file, first=True,
                n_modules=len(modules),
            )
        else:
            logger.info(
                "Progress table disabled (not a terminal). "
                "Snapshots logged every 30s."
            )

        ckpt_path.parent.mkdir(parents=True, exist_ok=True)
        cp = open(ckpt_path, "a", encoding="utf-8")
        try:
            for coro in asyncio.as_completed(coros):
                mod, result, err = await coro
                done_count[mod] += 1

                if err is not None:
                    err_count[mod] += 1
                    logger.error("Batch error [%s]: %s", mod, err)
                else:
                    rec_count[mod] += len(result)
                    all_new.extend(result)
                    for rec in result:
                        cp.write(json.dumps(rec) + "\n")
                    cp.flush()

                now = time.time()
                if now - last_print[0] >= REFRESH_SECS:
                    if _IS_TTY:
                        n_lines[0] = _progress_table(
                            modules, done_count, module_todo, rec_count, err_count,
                            t_start_mod, previously_done, len(df),
                            now - t_run_start, checkpoint_file, first=False,
                            n_modules=len(modules),
                        )
                    else:
                        # Non-TTY: print a compact progress line to stdout every
                        # 5 s so notebooks/pipes get live updates.
                        elapsed = now - t_run_start
                        total_done_recs = sum(rec_count.values())
                        total_todo_recs = len(df) * len(modules)
                        rec_rate = (total_done_recs / elapsed
                                    if elapsed > 0 and total_done_recs > 0 else 0)
                        pct = (total_done_recs / total_todo_recs * 100
                               if total_todo_recs else 0)
                        eta_s = ((total_todo_recs - total_done_recs) / rec_rate
                                 if rec_rate > 0 else 0)
                        eta_str = (f"~{eta_s/60:.0f}m" if eta_s > 90
                                   else f"~{eta_s:.0f}s")
                        _cost_str = ""
                        try:
                            from rca_pipeline.llm_client import get_cost_tracker as _gct
                            _ct = _gct()
                            if _ct and _ct._calls:
                                _calls = list(_ct._calls)
                                _tc = sum(c["total_cost_usd"] for c in _calls)
                                _tn = sum(c["n_records"]       for c in _calls)
                                if _tn > 0:
                                    _cost_str = (
                                        f"  |  ${_tc/_tn:.5f}/ticket"
                                        f"  |  Total ${_tc:.4f}"
                                    )
                        except Exception:
                            pass
                        print(
                            f"[{time.strftime('%H:%M:%S')}]  "
                            f"{total_done_recs:,}/{total_todo_recs:,} rec"
                            f"  ({pct:.1f}%)"
                            f"  |  {rec_rate:.1f} rec/s"
                            f"  |  ETA {eta_str}"
                            f"{_cost_str}",
                            flush=True,
                        )
                        # Also log a summary to the log file every 30 s
                        if now - last_print[0] >= 30:
                            logger.info(
                                "Progress: %d/%d rec (%.1f%%)  %.1f rec/s  "
                                "elapsed %.1f min",
                                total_done_recs, total_todo_recs, pct,
                                rec_rate, elapsed / 60,
                            )
                    last_print[0] = now

        except KeyboardInterrupt:
            logger.info("Interrupted — checkpoint saved, re-run to resume")
            cp.close()
            sys.exit(0)
        finally:
            cp.close()

        _progress_table(
            modules, done_count, module_todo, rec_count, err_count,
            t_start_mod, previously_done, len(df),
            time.time() - t_run_start, checkpoint_file, first=False,
        )

    elapsed = time.time() - t_run_start
    logger.info("Classification complete in %.1f min", elapsed / 60)

    # ── Post-processing ───────────────────────────────────────────────────
    logger.info(
        "Post-processing %d checkpoint + %d new records",
        len(ckpt_results), len(all_new),
    )

    all_results = cached_results + ckpt_results + all_new
    grouped: dict[str, dict] = {}
    for r in all_results:
        uid = str(r.get("uid", ""))
        grouped.setdefault(uid, {"uid": uid}).update(r)

    errors = [r for r in grouped.values() if "_error" in r]
    if errors:
        logger.warning("%d records with errors:", len(errors))
        for e in errors[:5]:
            logger.warning("  uid=%s  %s", e.get("uid"), str(e.get("_error", ""))[:100])

        new_bad = {str(e["uid"]) for e in errors if "uid" in e} - bad_uids
        if new_bad:
            bad_uids_path.parent.mkdir(parents=True, exist_ok=True)
            with open(bad_uids_path, "a", encoding="utf-8") as _f:
                for uid in sorted(new_bad):
                    _f.write(f"{uid}\n")
            logger.warning(
                "Added %d UIDs to skip list: %s  (edit %s to remove)",
                len(new_bad), sorted(new_bad)[:10], bad_uids_file,
            )

    df_out = post_process(df, list(grouped.values()), taxonomies, cfg)
    logger.info("Enriched: %d rows x %d columns", len(df_out), len(df_out.columns))

    if confidence_on:
        df_out = flag_low_confidence(df_out, threshold=confidence_threshold)
        if getattr(cfg, "export_review_queue", False):
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            export_review_queue(df_out, str(Path(output_file).parent / "review_queue.xlsx"))

    write_output_file(df_out, output_file)

    if incremental_runner is not None and len(df_to_classify) > 0:
        cached_uids = {str(r.get("uid", "")) for r in cached_results}
        incremental_runner.update_state(
            [r for r in ckpt_results + all_new if str(r.get("uid", "")) not in cached_uids],
            df_to_classify, id_col=id_col, text_col=text_col,
        )

    # ── Compact checkpoint ────────────────────────────────────────────────
    try:
        compact = list(grouped.values())
        with open(ckpt_path, "w", encoding="utf-8") as _f:
            for rec in compact:
                _f.write(json.dumps(rec) + "\n")
        logger.info(
            "Checkpoint compacted: %d unique records (was %d raw lines)",
            len(compact), len(all_results),
        )
    except Exception as e:
        logger.warning("Checkpoint compaction failed (non-fatal): %s", e)

    # ── Cost report ──────────────────────────────────────────────────────
    if cost_tracker is not None:
        cost_tracker.print_summary()
        cost_dir = getattr(cfg, "cost_report_dir", None)
        if cost_dir:
            from pathlib import Path as _Path
            _rdir = _Path(cost_dir)
            _rdir.mkdir(parents=True, exist_ok=True)
            cost_tracker.save(_rdir / f"costs_{cost_tracker._run_id}.json")
        unregister_cost_tracker()

    # ── Enhancement: quality dashboard ──────────────────────────────────
    if getattr(cfg, "run_quality_check", False):
        from rca_pipeline.enhancements.quality_dashboard import run_quality_check
        run_quality_check(df_out, taxonomies, cfg,
                          getattr(cfg, "quality_report_dir", None) or str(Path(output_file).parent),
                          getattr(cfg, "previous_quality_report", None))

    # ── Summary ───────────────────────────────────────────────────────────
    print()
    print("=" * 78)
    print(f"  COMPLETE — {run_name}")
    print(f"  Output:   {output_file}")
    print(f"  Rows:     {len(df_out):,}  |  Columns: {len(df_out.columns)}")
    print(f"  Errors:   {len(errors)} stubbed records")
    print(f"  Elapsed:  {elapsed / 60:.1f} min")
    print("=" * 78)

    # ── Clean up aiohttp sessions left open by litellm ────────────────────
    # litellm creates aiohttp.ClientSession objects internally but doesn't
    # always close them, causing "Unclosed client session" warnings at
    # shutdown.  We close them explicitly here.
    await _cleanup_aiohttp_sessions()


async def _cleanup_aiohttp_sessions() -> None:
    """Close any aiohttp client sessions left open by litellm/openai."""
    try:
        import aiohttp
        import gc
        # Find all unclosed aiohttp sessions in memory and close them
        for obj in gc.get_objects():
            if isinstance(obj, aiohttp.ClientSession) and not obj.closed:
                await obj.close()
    except ImportError:
        pass  # aiohttp not installed — nothing to clean up
    except Exception:
        pass  # non-fatal — suppress any cleanup errors

    # Give the event loop a moment to process the close
    await asyncio.sleep(0.1)


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generalised RCA Pipeline runner — works with any pipeline definition.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  rca run --input data/transcripts.csv
  rca run --input data/transcripts.csv --text-col conversation
  rca run --profile profiles/scopus.json
  rca run --profile profiles/jira.json --concurrency 2
        """,
    )

    # ── Profile ───────────────────────────────────────────────────────────
    p.add_argument(
        "--profile", "-p",
        help="Path to a JSON run profile. CLI args override profile values.",
    )

    # ── Required ──────────────────────────────────────────────────────────
    p.add_argument("--input", "-i", help="Input CSV or XLSX file")

    # ── Output paths ──────────────────────────────────────────────────────
    p.add_argument("--output", "-o", help="Output file (default: <input>_enriched.xlsx)")
    p.add_argument("--checkpoint", help="Checkpoint JSONL file (default: <input>_checkpoint.jsonl)")
    p.add_argument("--bad-uids", help="Bad-UID skip list (default: <input>_bad_uids.txt)")
    p.add_argument("--log-file", help="Log file (default: run_pipeline.log)")
    p.add_argument("--taxonomy-dir", default=_DEFAULT_TAXONOMY_DIR, help="Taxonomy directory")

    # ── Column names ──────────────────────────────────────────────────────
    p.add_argument("--id-col", default="uid", help="UID column name")
    p.add_argument("--text-col", default="transcript", help="Text/transcript column name")

    # ── Tuning ────────────────────────────────────────────────────────────
    p.add_argument("--batch-size", type=int, default=10)
    p.add_argument("--max-chars", type=int, default=60_000)
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--retries", type=int, default=3)
    p.add_argument("--max-tokens", type=int, default=4096)

    # ── LLM backend ──────────────────────────────────────────────────────
    p.add_argument(
        "--backend", default=None, choices=["litellm", "openai"],
        help="LLM backend: 'litellm' (default) or 'openai'. "
             "Overrides LLM_BACKEND env var.",
    )
    p.add_argument(
        "--model", default=None,
        help="LLM model string (e.g. 'azure/dsaic-llm-general' for litellm, "
             "or deployment name for openai). Overrides RCA_MODEL env var.",
    )
    p.add_argument(
        "--temperature", type=float, default=None,
        help="Sampling temperature. Overrides RCA_TEMPERATURE env var "
             "(RunConfig default: 0.0). Settable per profile.",
    )

    # ── Modules ───────────────────────────────────────────────────────────
    p.add_argument(
        "--modules", nargs="+", default=None,
        help="Modules to run (default: all registered)",
    )
    p.add_argument(
        "--sentinel", nargs="*", default=None,
        help="Sentinel overrides as module:field pairs (e.g. metadata:short_summary)",
    )

    # ── Misc ──────────────────────────────────────────────────────────────
    p.add_argument("--run-name", help="Display name for this run (default: input filename)")
    p.add_argument(
        "--dry-run", action="store_true", default=False,
        help="Preview what would run (loads data + config, no LLM calls, no output written)",
    )

    # ── Enhancements ─────────────────────────────────────────────────────
    p.add_argument("--enable-confidence", action="store_true", default=None,
                   dest="enable_confidence",
                   help="Add confidence scores and flag low-confidence records")
    p.add_argument("--confidence-threshold", type=float, default=None,
                   dest="confidence_threshold",
                   help="Records below this are flagged for review (default: 0.70)")
    p.add_argument("--export-review-queue", action="store_true", default=None,
                   dest="export_review_queue",
                   help="Export low-confidence records to a separate file")
    p.add_argument("--feedback-dir", default=None, dest="feedback_dir",
                   help="Directory for human correction JSONL files")
    p.add_argument("--feedback-max-examples", type=int, default=None,
                   dest="feedback_max_examples",
                   help="Max few-shot examples injected per module (default: 5)")
    p.add_argument("--feedback-strategy", default=None, dest="feedback_strategy",
                   choices=["recent", "diverse", "frequent", "smart"],
                   help="Strategy for selecting few-shot examples")
    p.add_argument("--hierarchical-modules", nargs="+", default=None,
                   dest="hierarchical_modules",
                   help="Modules to use two-step L1→L2 classification")
    p.add_argument("--incremental", action="store_true", default=None,
                   help="Only classify new/changed records")
    p.add_argument("--incremental-state-file", default=None,
                   dest="incremental_state_file",
                   help="Path to incremental state JSONL file")
    p.add_argument("--track-costs", action="store_true", default=None,
                   dest="track_costs",
                   help="Track token usage and estimated cost per module")
    p.add_argument("--cost-report-dir", default=None, dest="cost_report_dir",
                   help="Directory for cost report JSON files")
    p.add_argument("--detect-language", action="store_true", default=None,
                   dest="detect_language",
                   help="Detect language of each transcript")
    p.add_argument("--language-strategy", default=None, dest="language_strategy",
                   choices=["translate", "prompt", "detect"],
                   help="How to handle non-English transcripts")
    p.add_argument("--run-quality-check", action="store_true", default=None,
                   dest="run_quality_check",
                   help="Generate a quality report after classification")
    p.add_argument("--quality-report-dir", default=None, dest="quality_report_dir",
                   help="Directory for quality report files")
    p.add_argument("--previous-quality-report", default=None,
                   dest="previous_quality_report",
                   help="Path to previous quality_report.json for run comparison")

    # ── Gold set evaluation ───────────────────────────────────────────────
    p.add_argument(
        "--eval-gold-test", default=None, dest="eval_gold_test",
        help="Path to held-out gold test CSV. After the run, prints F1 / accuracy "
             "for each module, comparing train-set vs test-set performance.",
    )

    args = p.parse_args()

    # ── Merge profile ─────────────────────────────────────────────────────
    if args.profile:
        profile_path = Path(args.profile)
        if not profile_path.exists():
            p.error(f"Profile not found: {profile_path}")
        with open(profile_path, encoding="utf-8") as f:
            profile = json.load(f)

        # Profile values are defaults — CLI args override
        for key, val in profile.items():
            key_attr = key.replace("-", "_")
            # Only apply profile value if CLI didn't set it (is still default)
            if hasattr(args, key_attr):
                current = getattr(args, key_attr)
                default = p.get_default(key_attr)
                if current == default or current is None:
                    setattr(args, key_attr, val)

    if not args.input:
        p.error("--input is required (or set 'input' in the profile JSON)")

    return args


def _mini_eval_pipeline(args, uid_conv_df: "pd.DataFrame") -> "pd.DataFrame | None":
    """
    Run the pipeline on a small set of tickets (uid + conversation) and return
    the predictions DataFrame.  Used when gold-test tickets are not in the main
    input dataset.
    """
    import subprocess
    import pandas as pd

    tmp_dir = Path(_resolve_output(args)).parent
    tmp_in  = tmp_dir / "_gold_eval_in.csv"
    tmp_out = tmp_dir / "_gold_eval_out.xlsx"

    uid_conv_df.to_csv(tmp_in, index=False)

    cmd = [
        sys.executable, "-m", "rca_pipeline.runner",
        "--input",     str(tmp_in),
        "--output",    str(tmp_out),
        "--text-col",  "conversation",
        "--id-col",    "uid",
    ]
    # Forward the key settings so the mini pass uses the same model / feedback
    for flag, attr in [
        ("--modules",              "modules"),
        ("--taxonomy-dir",         "taxonomy_dir"),
        ("--feedback-dir",         "feedback_dir"),
        ("--feedback-strategy",    "feedback_strategy"),
        ("--feedback-max-examples","feedback_max_examples"),
        ("--batch-size",           "batch_size"),
        ("--concurrency",          "concurrency"),
        ("--retries",              "retries"),
        ("--model",                "model"),
    ]:
        val = getattr(args, attr, None)
        if val is not None:
            if isinstance(val, list):
                cmd += [flag] + [str(v) for v in val]
            else:
                cmd += [flag, str(val)]

    print(f"  Running mini eval pass on {len(uid_conv_df)} tickets...", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0 or not tmp_out.exists():
        print("  Mini eval failed — check run_pipeline.log for details.")
        return None
    return pd.read_excel(tmp_out)


def _run_gold_eval(args) -> None:
    """
    Print a train-vs-test accuracy table after the main run.

    When gold-test tickets are not in the main input dataset, automatically
    runs a mini pipeline pass on just those tickets to obtain predictions.
    """
    import pandas as pd
    from sklearn.metrics import accuracy_score, f1_score

    output_path = Path(_resolve_output(args))
    if not output_path.exists():
        logger.warning("eval-gold-test: output file not found (%s) — skipping evaluation", output_path)
        return

    test_path = Path(args.eval_gold_test)
    if not test_path.exists():
        logger.warning("eval-gold-test: test CSV not found (%s) — skipping evaluation", test_path)
        return

    # ── Load pipeline output ──────────────────────────────────────────────
    output_df = pd.read_excel(output_path)

    # ── Build code → label maps from taxonomy JSONs ───────────────────────
    # code_to_label : L2 code → L2 label  (Root Cause in hierarchical taxonomy)
    # code_to_l1    : L2 code → L1 label  (Contact Reason in hierarchical taxonomy)
    code_to_label: dict[str, str] = {}
    code_to_l1:    dict[str, str] = {}
    tax_dir = Path(getattr(args, "taxonomy_dir", _DEFAULT_TAXONOMY_DIR))
    for jf in tax_dir.glob("*.json"):
        try:
            with open(jf, encoding="utf-8") as f:
                tax = json.load(f)
            for l1_code, l1 in tax.items():
                l1_label = l1.get("label", "")
                for code, leaf in l1.get("children", {}).items():
                    code_upper = code.upper()
                    code_to_label[code_upper] = leaf["label"]
                    code_to_l1[code_upper]    = l1_label
        except Exception:
            pass

    def _pred_for_row(row: "pd.Series", gold_col: str) -> str:
        """
        Extract the predicted label for a given gold label column.

        Handles both the old two-module layout (contact_reason + root_cause as
        separate flat modules) and the new hierarchical layout (single
        contact_reason module, L1=Contact Reason, L2=Root Cause).
        """
        norm = gold_col.lower().replace(" ", "_")
        is_cr = "contact" in norm and "reason" in norm
        is_rc = "root" in norm and "cause" in norm

        if is_cr:
            # Hierarchical: Contact Reason is the L1 group label
            for col in ("contact_reason_class_l1_label",
                        "contact_reason_class_l1",
                        "contact_reason_primary_label"):
                if col in row.index:
                    val = str(row[col]).strip()
                    if val and val.lower() not in ("nan", "none", ""):
                        return val
        elif is_rc:
            # Hierarchical: Root Cause is the L2 leaf label
            # Fall back to old flat root_cause module if present
            for col in ("contact_reason_primary_label",
                        "root_cause_primary_label",
                        "root_cause_primary_code"):
                if col in row.index:
                    val = str(row[col]).strip()
                    if val and val.lower() not in ("nan", "none", ""):
                        if col.endswith("_code"):
                            val = code_to_label.get(val.upper(), val)
                        return val
        else:
            # Generic fallback
            for prefix in ("contact_reason", "root_cause"):
                for suffix in ("primary_label", "primary_code"):
                    col = f"{prefix}_{suffix}"
                    if col in row.index:
                        val = str(row[col]).strip()
                        if val and val.lower() not in ("nan", "none", ""):
                            if suffix == "primary_code":
                                val = code_to_label.get(val.upper(), val)
                            return val
        return ""

    # ── Build lookup dicts from output: uid → row, and text-fp → row ─────
    # Gold set UIDs (Ticket Numbers) often differ from the pipeline's id_col
    # (Reference #), so we fall back to matching on the first 200 chars of
    # the Conversation text, which is present in both the output and the
    # gold CSVs.
    def _fp(text: str) -> str:
        return str(text).strip()[:200].lower()

    uid_col_out = "uid" if "uid" in output_df.columns else output_df.columns[0]
    text_col_out = next((c for c in output_df.columns if c.lower() == "conversation"), None)

    uid_to_row: dict[str, "pd.Series"] = {}
    fp_to_row:  dict[str, "pd.Series"] = {}
    for _, row in output_df.iterrows():
        uid_to_row[str(row[uid_col_out]).strip()] = row
        if text_col_out:
            key = _fp(str(row.get(text_col_out, "")))
            if key:
                fp_to_row[key] = row

    def _lookup_pred(uid: str, text: str, gold_col: str) -> str:
        """Return predicted label for a ticket, matching by UID then by text."""
        row = uid_to_row.get(uid.strip())
        if row is None and text and fp_to_row:
            row = fp_to_row.get(_fp(text))
        if row is None:
            return ""
        return _pred_for_row(row, gold_col)

    # ── Load gold test CSV ────────────────────────────────────────────────
    test_df = pd.read_csv(test_path)
    if "uid" not in test_df.columns:
        test_df = test_df.rename(columns={test_df.columns[0]: "uid"})
    test_df["uid"] = test_df["uid"].astype(str).str.strip()
    test_text_col = next((c for c in test_df.columns if c.lower() == "conversation"), None)

    # Detect module columns: "Contact Reason" → contact_reason, etc.
    col_to_module = {}
    for col in test_df.columns:
        norm = col.lower().replace(" ", "_")
        if norm in ("contact_reason", "root_cause"):
            col_to_module[col] = norm
        elif "contact" in norm and "reason" in norm:
            col_to_module[col] = "contact_reason"
        elif "root" in norm and "cause" in norm:
            col_to_module[col] = "root_cause"

    # ── Load gold train labels from JSONL ─────────────────────────────────
    # Each entry: {uid, text (truncated conv), corrected: {field: code}}
    train_gold: dict[str, dict[str, dict]] = {}  # module → {uid: {label, text}}
    feedback_dir = getattr(args, "feedback_dir", None)
    if feedback_dir:
        for jf in Path(feedback_dir).glob("*_corrections.jsonl"):
            module = jf.stem.replace("_corrections", "")
            train_gold[module] = {}
            try:
                with open(jf, encoding="utf-8") as f:
                    for line in f:
                        entry = json.loads(line.strip())
                        uid  = str(entry.get("uid", "")).strip()
                        text = entry.get("text", "")
                        for _, val in entry.get("corrected", {}).items():
                            code     = str(val).upper()
                            l2_label = code_to_label.get(code, str(val))  # Root Cause
                            l1_label = code_to_l1.get(code, "")           # Contact Reason
                            train_gold[module][uid] = {
                                "label":    l2_label,   # backward compat
                                "cr_label": l1_label,   # Contact Reason (L1)
                                "rc_label": l2_label,   # Root Cause     (L2)
                                "text":     text,
                            }
                            break
            except Exception:
                pass

    # ── Print evaluation table ────────────────────────────────────────────
    SEP  = "=" * 70
    SEP2 = "-" * 70
    run_name = getattr(args, "run_name", None) or Path(args.input).stem
    n_fp = len(fp_to_row)
    print(f"\n{SEP}")
    print(f"  GOLD SET EVALUATION   (run: {run_name})")
    if n_fp == 0:
        print("  WARNING: no Conversation column in output — UID-only matching.")
    print(SEP)

    _mini_pass_done = False  # run the test mini-pipeline pass at most once

    # ── Train mini-pass (once, before the per-module loop) ────────────────
    # The feedback JSONL stores uid + truncated text (≤1500 chars).  If those
    # tickets are not in the main output (different dataset), run the pipeline
    # on them now so we can compute in-sample train accuracy.
    if train_gold:
        all_train_uids: set[str] = set().union(*(tg.keys() for tg in train_gold.values()))
        if all_train_uids and not any(u in uid_to_row for u in all_train_uids):
            train_uid_text: dict[str, str] = {}
            for tg in train_gold.values():
                for uid, info in tg.items():
                    if uid not in train_uid_text and info.get("text", "").strip():
                        train_uid_text[uid] = info["text"]
            if train_uid_text:
                _train_df = pd.DataFrame(
                    [{"uid": u, "conversation": t} for u, t in train_uid_text.items()]
                )
                _mini_tr = _mini_eval_pipeline(args, _train_df)
                if _mini_tr is not None:
                    for _, mrow in _mini_tr.iterrows():
                        uid_to_row[str(mrow.get("uid", "")).strip()] = mrow

    for gold_col, module in col_to_module.items():
        # ── Test set ─────────────────────────────────────────────────────
        test_sub = test_df.dropna(subset=[gold_col])
        test_sub = test_sub[test_sub[gold_col].astype(str).str.strip() != ""]

        def _collect_preds() -> tuple[list, list]:
            yt, yp = [], []
            for _, row in test_sub.iterrows():
                uid  = str(row["uid"])
                text = str(row.get(test_text_col, "")) if test_text_col else ""
                pred = _lookup_pred(uid, text, gold_col)
                if pred:
                    yt.append(str(row[gold_col]).strip())
                    yp.append(pred)
            return yt, yp

        y_true_t, y_pred_t = _collect_preds()

        # If no matches and gold tickets are from a different dataset, run a
        # mini pipeline pass on those tickets to get predictions.
        if not y_pred_t and test_text_col and not _mini_pass_done:
            _mini_pass_done = True
            _mini_df = _mini_eval_pipeline(
                args,
                test_df[["uid", test_text_col]]
                    .rename(columns={test_text_col: "conversation"})
                    .copy(),
            )
            if _mini_df is not None:
                for _, mrow in _mini_df.iterrows():
                    uid_to_row[str(mrow.get("uid", "")).strip()] = mrow
                y_true_t, y_pred_t = _collect_preds()

        n_test = len(test_sub)
        if y_pred_t:
            acc_t = accuracy_score(y_true_t, y_pred_t) * 100
            mf1_t = f1_score(y_true_t, y_pred_t, average="macro",    zero_division=0)
            wf1_t = f1_score(y_true_t, y_pred_t, average="weighted", zero_division=0)
        else:
            acc_t = mf1_t = wf1_t = float("nan")

        # ── Train set ─────────────────────────────────────────────────────
        train_n = train_matched = 0
        acc_tr = mf1_tr = wf1_tr = float("nan")
        y_true_tr: list[str] = []
        y_pred_tr: list[str] = []
        # Train gold may be keyed by module name OR the unified "contact_reason" key
        _tg_key = module if module in train_gold else "contact_reason"
        if _tg_key in train_gold and train_gold[_tg_key]:
            tg = train_gold[_tg_key]
            train_n = len(tg)
            _norm_gc = gold_col.lower().replace(" ", "_")
            _is_cr   = "contact" in _norm_gc and "reason" in _norm_gc
            for uid, info in tg.items():
                # Pick the right gold label: CR (L1) or RC (L2)
                if _is_cr:
                    gold_label = info.get("cr_label") or info.get("label", "")
                else:
                    gold_label = info.get("rc_label") or info.get("label", "")
                pred = _lookup_pred(uid, info.get("text", ""), gold_col)
                if pred and gold_label:
                    y_true_tr.append(gold_label)
                    y_pred_tr.append(pred)
            train_matched = len(y_pred_tr)
            if train_matched >= 2:
                acc_tr = accuracy_score(y_true_tr, y_pred_tr) * 100
                mf1_tr = f1_score(y_true_tr, y_pred_tr, average="macro",    zero_division=0)
                wf1_tr = f1_score(y_true_tr, y_pred_tr, average="weighted", zero_division=0)

        def _delta(a, b, pct: bool = False):
            if a != a or b != b:
                return "  n/a"
            d = a - b
            return f"{d:+.1f}" if pct else f"{d:+.2f}"

        has_train = not (acc_tr != acc_tr) and train_matched > 0
        train_label = f"Train (n={train_n})" if has_train else "Train"
        test_label  = f"Test  (n={len(y_pred_t)})"

        print(f"\n  {module:<22}  {train_label:>14}  {test_label:>13}    d")
        print(f"  {SEP2[:66]}")
        if has_train:
            print(f"  {'Accuracy':<22}  {acc_tr:>13.1f}%  {acc_t:>12.1f}%  {_delta(acc_tr, acc_t, pct=True):>6}")
            print(f"  {'Macro F1':<22}  {mf1_tr:>14.2f}  {mf1_t:>13.2f}  {_delta(mf1_tr, mf1_t):>6}")
            print(f"  {'Weighted F1':<22}  {wf1_tr:>14.2f}  {wf1_t:>13.2f}  {_delta(wf1_tr, wf1_t):>6}")
            print(f"  {'Matched records':<22}  {train_matched:>10}/{train_n:<3}  {len(y_pred_t):>9}/{n_test:<3}")
        else:
            print(f"  {'Accuracy':<22}  {'n/a':>14}  {acc_t:>12.1f}%")
            print(f"  {'Macro F1':<22}  {'n/a':>14}  {mf1_t:>13.2f}")
            print(f"  {'Weighted F1':<22}  {'n/a':>14}  {wf1_t:>13.2f}")
            print(f"  {'Matched records':<22}  {'n/a':>14}  {len(y_pred_t):>9}/{n_test:<3}")
    print(f"\n{SEP}\n")


def main() -> None:
    args = _parse_args()
    asyncio.run(run(args))
    # --dry-run promises no LLM calls; the gold evaluation can start a paid mini-run.
    if getattr(args, "eval_gold_test", None) and not getattr(args, "dry_run", False):
        _run_gold_eval(args)


if __name__ == "__main__":
    main()
