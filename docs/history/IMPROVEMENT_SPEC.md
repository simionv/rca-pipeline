# RCA Pipeline Improvement and Error-Fixing Specification

## Purpose

This document converts the codebase assessment into an implementation-ready
backlog. It covers confirmed runtime issues, likely correctness risks,
test-coverage gaps, operational improvements, and a staged path for using DSPy
to streamline module and prompt creation.

No changes in this document should be treated as already implemented. Each item
below includes intent, proposed design, acceptance criteria, and risk notes so
work can be planned and verified independently.

## Assumptions

- The Excel pipeline definitions remain the source of truth for modules, fields,
  taxonomy structure, and prompt instructions.
- The current production entry point remains `run_pipeline.py`.
- The current generated-module contract remains stable in the near term:
  `generated/modules/<module>.py` exposes `classify_<module>()`.
- Existing batching, checkpointing, cost tracking, taxonomy loading, and
  post-processing should be preserved unless a task explicitly replaces them.
- DSPy adoption should begin as an opt-in module authoring/runtime layer, not as
  an immediate rewrite of the whole pipeline.

## Current Validation Snapshot

- `uv run pytest -q -p no:cacheprovider` passed with 44 tests.
- `uv run python -m compileall -q build_pipeline.py run_pipeline.py rca_pipeline tests`
  passed.
- `uv run python build_pipeline.py build --input definitions/scopus_content_pipeline_definition_v2.xlsx --dry-run`
  reported stale generated modules for `contact_reason` and `customer_effort`.
- `uv run python run_pipeline.py --profile profiles/scopus_content_profile.json --dry-run`
  failed because `data/scopus_conversations.csv` does not exist.
- `uv run python run_pipeline.py --profile profiles/leapspace_profile.json --dry-run`
  returned the dry-run report, but the top-level CLI then continued into gold
  evaluation because the profile sets `eval_gold_test`.
- Running the ambient `python` instead of `uv run python` exposed NumPy/Pandas
  compiled-extension incompatibilities, so project commands should use the
  managed uv environment.

## Priority Model

- P0: A confirmed issue that can cause failed runs, wrong module execution, or
  invalid evaluation.
- P1: A correctness, reproducibility, or operational risk that can mislead users
  or silently degrade output quality.
- P2: A maintainability, observability, or developer-experience improvement.
- P3: Strategic enhancements that improve long-term quality or extensibility.

## P0: Fix Profile, Config, and Generated Artifact Drift

### Problem

The runtime currently relies on one global `generated/pipeline_config.json`.
Profiles can request modules or taxonomies from another product definition, but
`rca_pipeline.pipeline.MODULE_REGISTRY` and `rca_pipeline.taxonomy.load_taxonomies()`
are built from the active global config. This can produce mismatches where files
exist but are not registered or loaded.

Confirmed example:

- `profiles/mendeley_profile.json` requests `root_cause`.
- `generated/modules/root_cause.py` and `generated/taxonomies/root_cause.json`
  exist.
- Dry-run showed `root_cause` with no sentinel/taxonomy because the current
  `pipeline_config.json` is Scopus-oriented and does not include `root_cause`.

### Proposed Design

Introduce explicit profile-to-build-artifact binding.

Add profile fields:

```json
{
  "definition_file": "definitions/mendeley_pipeline_definition.xlsx",
  "pipeline_config": "generated/configs/mendeley_pipeline_config.json",
  "module_dir": "generated/modules/mendeley",
  "taxonomy_dir": "generated/taxonomies/mendeley"
}
```

Minimum viable version:

- Add `pipeline_config` support first.
- Load registry and taxonomy file lists from the profile-selected config.
- Keep generated modules in the existing `generated/modules` directory until the
  config binding is stable.

Longer-term version:

- Build per-profile or per-definition artifact directories.
- Keep `generated/pipeline_config.json` only as a default/symlink-style fallback.

### Acceptance Criteria

- `run_pipeline.py --profile profiles/mendeley_profile.json --dry-run` resolves
  `root_cause` using the intended config and taxonomy.
- If a requested module is not present in the selected config, the runner fails
  before reading input data.
- If a requested module exists in config but its generated `.py` file is missing,
  the runner fails with a build command that includes the relevant definition.
- A profile can be validated without LLM calls.

### Tests

- Unit test: profile with `pipeline_config` loads the correct module set.
- CLI test: dry-run fails clearly when profile requests a module absent from its
  config.
- CLI test: dry-run succeeds for a fixture profile whose config includes all
  requested modules.

## P0: Make `--dry-run` Truly Dry

### Problem

`run_pipeline.py` returns from `run(args)` after the dry-run report, but `main()`
still calls `_run_gold_eval(args)` if `eval_gold_test` is set. This means a dry
run can still launch evaluation work and import heavier dependencies.

### Proposed Design

Guard gold evaluation in `main()`:

```python
if getattr(args, "eval_gold_test", None) and not getattr(args, "dry_run", False):
    _run_gold_eval(args)
```

Also include the gold-eval plan in the dry-run report:

- Whether `eval_gold_test` is set.
- Whether evaluation would run after a real classification run.
- Which test file would be used.

### Acceptance Criteria

- `run_pipeline.py --profile profiles/leapspace_profile.json --dry-run` exits
  after the dry-run report.
- No output file, checkpoint compaction, mini-eval, sklearn import, or gold-eval
  computation occurs during dry-run.

### Tests

- CLI-level test with a profile containing `eval_gold_test` verifies that
  `_run_gold_eval` is not called in dry-run mode.

## P0: Correct or Retire Invalid Profiles

### Problem

`profiles/scopus_content_profile.json` points to
`data/scopus_conversations.csv`, which does not exist in the workspace.

### Proposed Design

Add a profile validation step and update invalid profiles after confirming the
intended dataset.

Likely candidates in the current workspace:

- `data/Scopus_Content_Collapsed.xlsx`
- `data/Scopus_Content_Collapsed.csv`
- `data/Scopus_Content.csv`

### Acceptance Criteria

- Every profile in `profiles/*.json` either points to an existing input file or
  is explicitly marked disabled/example.
- `run_pipeline.py --profile <profile> --dry-run` fails before importing LLM
  modules if the input file is missing.
- Documentation distinguishes example profiles from executable profiles.

### Tests

- Add `scripts/validate_profiles.py` or a pytest that checks profile paths.
- Run it in CI.

## P0: Handle Stale Generated Modules as a Blocking Error in Strict Mode

### Problem

The builder detects stale generated module files, but the runner can still use
them. For Scopus, `contact_reason.py` and `customer_effort.py` were stale when
checked against `definitions/scopus_content_pipeline_definition_v2.xlsx`.

### Proposed Design

Add a strict build-validation mode:

- `run_pipeline.py --strict-build` or profile field `"strict_build": true`.
- Compare selected definition/config/module hashes before running.
- Fail if generated `.py` files are stale.

Default behavior can remain warning-only initially, but production profiles
should enable strict mode.

### Acceptance Criteria

- Strict mode blocks execution when a selected module's definition hash differs
  from the manifest hash.
- The error message includes:
  - module name,
  - definition file,
  - current command to regenerate,
  - whether `--force <module>` or `--force-all` is needed.

### Tests

- Fixture manifest with mismatched hash causes strict dry-run failure.
- Non-strict dry-run logs a warning but continues.

## P1: Fail Fast on Unknown Requested Modules

### Problem

`run_classification_module()` logs an error and returns `[]` if a module is not
registered. This can produce output that looks successful but silently lacks a
requested classification module.

### Proposed Design

Validate requested modules once before data processing:

- Unknown module -> raise `ValueError`.
- Known in config but import failed -> raise `RuntimeError`.
- Known and imported -> continue.

Allow a `--allow-missing-modules` flag only for exploratory notebooks.

### Acceptance Criteria

- A run cannot complete successfully while omitting a requested module due to
  registry failure.
- Error records are reserved for per-record LLM failures, not module import
  failures.

## P1: Make Taxonomy Loading Module-Scoped

### Problem

`load_taxonomies()` loads every taxonomy listed in the global config, not only
the modules requested by the selected profile. This causes noisy missing-file
warnings and can obscure the actual module requirements.

### Proposed Design

Extend `load_taxonomies()`:

```python
def load_taxonomies(taxonomy_dir, config=None, modules=None) -> dict[str, dict]:
    ...
```

Only load taxonomy files for requested modules unless `modules=None`.

### Acceptance Criteria

- LeapSpace dry-run with only `contact_reason` does not warn about missing
  `customer_effort`, `policy_compliance`, or `policy_rules` taxonomies.
- The dry-run report shows taxonomy status only for requested modules by default.

## P1: Repair Windows Console Encoding Failures

### Problem

Logging uses Unicode box-drawing characters. On cp1252 Windows terminals, this
can raise `UnicodeEncodeError` during otherwise valid commands.

### Proposed Design

Use ASCII-safe console logging and keep Unicode only in UTF-8 file logs.

Options:

1. Set console handler errors to replacement where supported.
2. Use an ASCII console format:

```python
"%(asctime)s | %(levelname)-7s | %(name)-20s | %(message)s"
```

3. Keep UTF-8 file handler with richer formatting if desired.

### Acceptance Criteria

- `uv run python run_pipeline.py --profile profiles/mendeley_profile.json --dry-run`
  emits no logging encoding tracebacks on Windows.
- Log files remain UTF-8 encoded.

## P1: Make uv the Supported Execution Path

### Problem

Ambient `python` imported user-site packages and produced NumPy/Pandas/pyarrow
ABI errors. The uv-managed environment passed tests and dry-run checks.

### Proposed Design

Update docs and scripts to consistently use:

```bash
uv run python run_pipeline.py ...
uv run pytest
```

Optionally add a startup warning when `sys.prefix` is not the project `.venv`
and `UV`/virtual environment markers are absent.

### Acceptance Criteria

- README quick-start commands use `uv run`.
- Troubleshooting docs explain the NumPy ABI symptom and remediation.
- CI uses `uv sync` and `uv run`.

## P1: Add Profile Validation Command

### Problem

Profiles are a central operational interface, but there is no single command
that validates them end to end without touching the LLM.

### Proposed Design

Add:

```bash
uv run python run_pipeline.py --profile profiles/x.json --validate-only
```

Validation should check:

- input exists,
- output parent exists or can be created,
- selected config exists,
- requested modules are registered,
- generated module files exist and are current if strict mode is enabled,
- taxonomy files exist for requested taxonomy-backed modules,
- `id_col` and `text_col` exist in input,
- checkpoint/bad UID paths are writable,
- optional gold test file exists,
- model/backend settings are coherent.

### Acceptance Criteria

- `--validate-only` makes zero LLM calls and writes no output/checkpoint data.
- It returns non-zero on any blocking issue.
- It produces a compact, actionable report.

## P1: Strengthen Test Coverage Around the CLI Contract

### Problem

Current tests cover pure helpers but not the failure modes that matter most for
running the pipeline.

### Proposed Design

Add tests for:

- profile merge behavior,
- dry-run behavior,
- eval-gold suppression during dry-run,
- missing input file,
- unknown requested module,
- missing taxonomy,
- stale build manifest strict mode,
- registry import failure,
- profile-selected config.

### Acceptance Criteria

- At least one test fails against each confirmed P0 issue before the fix.
- Tests use small fixture CSVs and JSON configs, not production data.
- No tests make LLM calls.

## P1: Separate Example Profiles from Executable Profiles

### Problem

Profiles mix real production-like runs, older product runs, and potentially stale
examples. This makes validation noisy and can mislead users.

### Proposed Design

Introduce:

```text
profiles/
  active/
  examples/
  archived/
```

Or add a profile field:

```json
{ "status": "active" | "example" | "archived" }
```

Validation can default to active profiles only.

### Acceptance Criteria

- `validate_profiles` can check active profiles only.
- Example profiles are clearly documented and excluded from production checks.

## P1: Improve Gold Evaluation Control Flow

### Problem

Gold evaluation is embedded at the end of `main()` and can trigger a secondary
classification pass. This makes control flow harder to reason about.

### Proposed Design

Make gold evaluation an explicit mode:

```bash
uv run python run_pipeline.py --profile x.json --eval-gold-test data/test.csv
uv run python run_pipeline.py eval --profile x.json --gold-test data/test.csv
```

Minimum viable version:

- Keep the current flag but ensure it never runs during dry-run or validate-only.
- Log whether it will reuse output or run mini-eval.

### Acceptance Criteria

- Dry-run reports evaluation plan but does not execute it.
- Evaluation can be run independently against an existing output file.
- Evaluation errors do not obscure the success/failure of the main
  classification run.

## P2: Reduce Generated Python Surface Area

### Problem

Generated modules are large prompt-heavy Python files. Stale detection exists,
but the generated code still couples prompt wording, schema formatting, taxonomy
loading, parsing, and runtime execution.

### Proposed Design

Move common generated-module behavior into runtime helpers:

- module metadata dataclass,
- schema renderer,
- field instruction renderer,
- taxonomy prompt resolver,
- enum validator builder,
- classify module runner.

Generated files should contain mostly data:

```python
MODULE_SPEC = {
    "name": "contact_reason",
    "taxonomy_key": "contact_reason",
    "fields": [...],
    "description": "...",
}

async def classify_contact_reason(batches, taxonomies, cfg):
    return await run_generated_module(MODULE_SPEC, batches, taxonomies, cfg)
```

### Acceptance Criteria

- Generated modules are short and easy to diff.
- A generator change rarely requires regenerating every module.
- Unit tests can cover most generated behavior without generating files.

## P2: Add Manifest and Artifact Governance

### Problem

`generated/build_manifest.json` records hashes, but there is no clear workflow
for per-definition artifacts, stale warnings, or promotion of generated outputs.

### Proposed Design

Create an artifact contract:

```text
generated/
  builds/
    <profile_or_definition_id>/
      pipeline_config.json
      build_manifest.json
      modules/
      taxonomies/
```

Add manifest fields:

- source definition path,
- definition content hash,
- generator version,
- module hash,
- taxonomy hash,
- generated timestamp,
- build command,
- Python/package version.

### Acceptance Criteria

- A profile can identify exactly which definition produced its runtime artifacts.
- Stale checks compare against the correct definition only.
- Temporary Excel lock files like `~$*.xlsx` are ignored by staleness checks.

## P2: Normalize Documentation Encoding

### Problem

Several Markdown files display mojibake in terminal output. This may be caused
by historical encoding conversion or console rendering, but the docs should be
verified and normalized.

### Proposed Design

Audit Markdown files for mojibake sequences such as `â€”`, `â†’`, and box-drawing
artifacts. Normalize to UTF-8, or convert decorative characters to ASCII.

### Acceptance Criteria

- README and docs render cleanly in UTF-8.
- Console snippets avoid characters likely to break cp1252 terminals.

## P2: Add Structured Run Reports

### Problem

Operational data is spread across logs, outputs, checkpoint files, and cost
reports. There is no single manifest for a run.

### Proposed Design

After each run, write:

```text
runs/reports/<run_id>.json
```

Fields:

- profile path,
- config path/hash,
- definition path/hash,
- modules run,
- input path/hash/row count,
- output path,
- model/backend,
- batch count,
- retry/error counts,
- cost summary,
- quality/eval summary,
- code version/git status if available.

### Acceptance Criteria

- Every full run emits one machine-readable report.
- Reports are safe to share without credentials or raw transcript text.

## P2: Make Error Handling More Explicit

### Problem

There are many broad `except Exception` blocks. Some are appropriate for LLM
resilience, but others can hide misconfiguration or data-contract failures.

### Proposed Design

Classify errors:

- configuration errors: fail fast,
- artifact errors: fail fast,
- data-contract errors: fail fast with row/column context,
- LLM/transient errors: retry/degrade,
- per-record parse errors: emit `_error`.

### Acceptance Criteria

- Missing module/config/taxonomy is never converted into empty successful output.
- Per-record LLM failures remain recoverable.
- Logs distinguish warnings from blocking errors.

## P2: Tighten Data Input Validation

### Problem

`read_input_file()` adds `uid` if missing, but validation of `id_col`,
`text_col`, duplicates, null text, and empty datasets happens later or
implicitly.

### Proposed Design

Add `validate_input_df(df, cfg)` before batching:

- required columns exist,
- ID column has no nulls,
- duplicate IDs are either rejected or reported,
- text column has non-empty values,
- row count is non-zero,
- text length distribution is reported.

### Acceptance Criteria

- Invalid input fails before loading LLM modules or taxonomies when possible.
- Dry-run includes column and row validation summary.

## P2: Revisit Checkpoint Semantics

### Problem

Checkpoint resume depends on sentinel fields. Missing or incorrect sentinels can
lead to repeated work or false completion.

### Proposed Design

Store module completion explicitly in checkpoint records:

```json
{
  "uid": "...",
  "_module": "contact_reason",
  "_completed": true,
  "contact_reason_primary_code": "..."
}
```

Or store one checkpoint file per module.

### Acceptance Criteria

- Resume logic does not need heuristic sentinel detection for generated modules.
- Dry-run can accurately report checkpoint coverage by module.

## P2: Improve Cost Tracking Accuracy and Freshness

### Problem

Static pricing in `cost_tracker.py` can drift as provider prices change.

### Proposed Design

Use configurable pricing:

- `pricing.json` in config,
- profile-level overrides,
- model alias normalization.

### Acceptance Criteria

- Unknown model uses a visible fallback warning.
- Cost report records the pricing source and timestamp.

## P2: Add Linting and Formatting Tooling

### Problem

The repo has tests but no visible lint/format contract.

### Proposed Design

Add a minimal, low-churn toolchain:

- `ruff check`
- `ruff format` or keep formatting manual if churn is a concern
- optional `mypy` later for core package only

### Acceptance Criteria

- Lint runs in CI.
- Generated files are either excluded or linted separately.
- First pass avoids broad style rewrites.

## P3: DSPy Runtime for Module and Prompt Creation

### Problem

The builder manually creates module-specific prompt strings, output schema text,
and generated Python wrappers. This is exactly the kind of repeated LLM program
shape DSPy is meant to simplify.

### Proposed Design

Add DSPy as an opt-in runtime abstraction for generated modules.

New component:

```text
rca_pipeline/dspy_runtime.py
```

Responsibilities:

- build a DSPy `Signature` from module fields,
- map Excel `field_type` values to Python/DSPy output types,
- construct a `dspy.Predict` or `dspy.ChainOfThought` module,
- pass taxonomy prompt and conversation text as inputs,
- return a dict matching the existing pipeline output schema.

Generated module shape:

```python
from rca_pipeline.dspy_runtime import classify_with_dspy

MODULE_SPEC = {...}

async def classify_contact_reason(batches, taxonomies, cfg):
    return await classify_with_dspy(MODULE_SPEC, batches, taxonomies, cfg)
```

Profile/config flag:

```json
{
  "module_runtime": "legacy",
  "dspy_runtime_modules": ["contact_reason"]
}
```

Valid values:

- `legacy`: current generated prompt code.
- `dspy`: DSPy signatures for selected modules.
- `mixed`: legacy by default, DSPy for listed modules.

### Design Constraints

- Keep current batch/checkpoint/post-processing flow.
- Preserve output field names exactly.
- Do not require GEPA for basic DSPy runtime.
- Do not remove `process_batches_async` until DSPy output handling is proven.
- Start with single-record DSPy calls if batch structured output is awkward,
  then optimize batching later.

### Acceptance Criteria

- A DSPy-backed `contact_reason` module produces the same output columns as the
  legacy module.
- Legacy and DSPy modules can run side by side in the same pipeline.
- Dry-run reports which runtime each module uses.
- Gold-set evaluation can compare legacy vs DSPy.

### Pilot

Use LeapSpace `contact_reason` first:

- gold set: `data/leapspace_gold_set.xlsx`,
- held-out test: `data/leapspace_gold_test.csv`,
- taxonomy: `data/leapspace_taxonomies/contact_reason.json`,
- metric: contact reason exact-match plus optional L1 partial credit.

## P3: DSPy Prompt Authoring Without Runtime Replacement

### Problem

A full DSPy runtime may be more change than needed initially.

### Proposed Design

Use DSPy-style signatures only as a prompt-authoring layer:

- Generate concise structured prompt specs from Excel.
- Render them into the current legacy prompt format.
- Keep all LLM calls through `llm_client.py`.

This is a lower-risk stepping stone to full DSPy runtime.

### Acceptance Criteria

- Generated prompts are shorter and more consistent.
- No production runtime behavior changes.
- Existing tests and dry-runs remain green.

## P3: GEPA Offline Prompt Optimization

### Problem

Manual prompt and taxonomy instruction tuning is slow, and the repo already has
gold sets and feedback artifacts that can support metric-driven prompt
optimization.

### Proposed Design

After DSPy module specs exist, add an offline optimizer command:

```bash
uv run python scripts/optimize_prompts.py \
  --profile profiles/leapspace_profile.json \
  --module contact_reason \
  --train data/leapspace_gold_set.xlsx \
  --test data/leapspace_gold_test.csv \
  --optimizer gepa \
  --budget light
```

Outputs:

```text
generated/optimized_prompts/<profile>/<module>/
  optimized_program.json
  prompt_diff.md
  eval_report.json
  run_manifest.json
  gepa_logs/
```

### Metrics

Return both score and feedback:

- exact code match,
- L1 match partial credit,
- invalid schema penalty,
- invalid enum penalty,
- evidence not grounded penalty,
- explanation optional bonus/penalty where gold explanations exist.

### Acceptance Criteria

- Optimized prompt is never promoted automatically.
- Promotion requires held-out metric improvement and no schema/evidence
  regression.
- Runtime can load an optimized prompt artifact only when the profile opts in.

## P3: Taxonomy Quality Tooling

### Problem

Accuracy depends heavily on taxonomy descriptions and label clarity. The repo
already notes this, but taxonomy quality checks are not a formal gate.

### Proposed Design

Add taxonomy lint:

- missing L2 descriptions,
- duplicate labels,
- overly broad labels like `Other`,
- unbalanced branches,
- leaf codes unused in gold set,
- gold labels missing from taxonomy,
- near-duplicate descriptions.

### Acceptance Criteria

- `uv run python scripts/taxonomy_lint.py --taxonomy <file> --gold <file>`
  produces actionable warnings.
- Build can optionally fail on severe taxonomy defects.

## P3: Better Feedback and Few-Shot Governance

### Problem

Feedback examples are powerful but can become stale, redundant, or product-mixed.

### Proposed Design

Add feedback validation:

- feedback examples must match current taxonomy codes,
- examples are scoped by profile/product,
- duplicates are removed or weighted,
- examples record source: SME correction, gold set, model error analysis.

### Acceptance Criteria

- FeedbackStore reports invalid/outdated examples before a run.
- Dry-run includes feedback count by module and source.

## P3: Observability for LLM Quality Failures

### Problem

The pipeline logs parse, hallucination, and validation issues, but quality
failures are not aggregated into one actionable report.

### Proposed Design

Create a per-run quality summary:

- parse failures,
- UID repairs,
- L1-only code repairs,
- invalid enum counts,
- evidence grounding failures,
- empty outputs by module,
- low confidence rows,
- most common predicted labels,
- drift from prior run distribution.

### Acceptance Criteria

- Quality report is generated without requiring notebooks.
- Report includes thresholds that can fail CI or production runs.

## Suggested Implementation Order

1. Fix dry-run gold-eval leakage.
2. Add fail-fast validation for requested modules.
3. Add profile validation and correct/disable missing-input profiles.
4. Add profile-selected pipeline config support.
5. Make taxonomy loading module-scoped.
6. Add strict build staleness mode.
7. Repair Windows console logging.
8. Add CLI/profile tests for the above.
9. Reduce generated Python surface area.
10. Pilot DSPy as an opt-in module runtime for LeapSpace `contact_reason`.
11. Add offline GEPA optimization once DSPy specs and metrics are stable.

## Definition of Done for the Remediation Phase

- All active profiles pass `--validate-only`.
- All active profiles pass `--dry-run`.
- Dry-run makes zero LLM calls and triggers no evaluation.
- Requested modules must be registered or the run fails.
- Missing taxonomy files for requested modules fail or are explicitly allowed by
  module config.
- Strict profiles cannot run stale generated modules.
- Test suite includes CLI coverage for the confirmed P0 issues.
- README documents `uv run` as the supported execution path.

## Definition of Done for the DSPy Phase

- DSPy is optional and disabled by default.
- At least one module can run through DSPy and produce the existing output schema.
- Legacy vs DSPy evaluation is automated on a gold set.
- DSPy prompt/module artifacts are versioned and reproducible.
- GEPA optimization is offline-only and gated by held-out evaluation.

