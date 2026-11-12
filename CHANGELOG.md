# Changelog

## 0.1.1 — 2026-11-12

Fixes three problems found while reviewing the consolidated code.

- **`rca run` now applies the enhancement settings.** Before, it accepted the flags and profile keys
  for confidence scoring, feedback examples, hierarchical classification, incremental runs, language
  detection and the quality report, but only cost tracking took effect. They now work the same way
  as in the library path (`run_pipeline(cfg)`), through shared helpers in `pipeline.py`. Feedback
  examples are used only when `--feedback-dir` / `feedback_dir` is set explicitly.
  - Profiles that already set these keys will behave differently on their next run:
    `leapspace_legacy` (feedback), `mendeley` and `scopus_content` (confidence, review queue,
    quality report, and feedback when its folder has corrections).
  - Results produced with feedback settings before this release were zero-shot
    (see the `leapspace_legacy` and `evolve` use-case pages).
- **Concurrent modules no longer share prompt text or cost labels.** The prompt suffix and the
  cost-attribution label in `llm_client.py` are now per-task (`contextvars`), so `rca run`'s
  concurrent batches each keep their own module's examples, and per-module costs are attributed correctly.
- **Hierarchical classification** loads the generated module from the workspace file; before, the
  import always failed and the L2 step fell back to a minimal prompt.
- **`aggregate_costs` totals the real reports.** It read `cost_*.json` and top-level keys, while the
  tracker writes `costs_*.json` with totals under `summary`, so it reported $0. On the archived
  reports it now totals $2,514.49 over 563 runs.
- **`--eval-gold-test`** no longer crashes without `--output` (it uses the default output file), and is
  skipped with `--dry-run`, so a dry run can never start the paid mini pass.
- `rca run` creates the checkpoint folder if a custom `--checkpoint` path points into a new folder.

## 0.1.0 — 2026-11-12

First consolidated release: the `rca` CLI, 17 use cases with README cards and `CATALOG.md`,
formatted definition workbooks with `rca validate`, consolidated manual and methodology, and
guard-rails against committing customer data.
