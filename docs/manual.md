# RCA Pipeline — User & Operations Manual

This manual explains **how** to install, configure and run the pipeline as the code works today.
For **why** it works this way (taxonomy design, multi-stage patterns, evaluation), read
[methodology.md](methodology.md). For a non-technical walkthrough of editing a definition workbook,
read [definition-guide.md](definition-guide.md). For the code structure, read
[ARCHITECTURE.md](ARCHITECTURE.md).

The code is the source of truth. Where earlier manuals (in `docs/history/`) say something different,
this manual follows the code; the differences are listed in
[Changes from earlier manuals](#18-changes-from-earlier-manuals).

---

## Contents

1. [Installation](#1-installation)
2. [The use-case / workspace model](#2-the-use-case--workspace-model)
3. [The definition workbook](#3-the-definition-workbook)
4. [Commands](#4-commands)
5. [Run profiles](#5-run-profiles)
6. [RunConfig reference](#6-runconfig-reference)
7. [Enhancement modules](#7-enhancement-modules)
8. [The feedback loop](#8-the-feedback-loop)
9. [Gold-set evaluation](#9-gold-set-evaluation)
10. [Checkpoints and crash recovery](#10-checkpoints-and-crash-recovery)
11. [Post-processing and output columns](#11-post-processing-and-output-columns)
12. [Credentials and environment variables](#12-credentials-and-environment-variables)
13. [Generic tools](#13-generic-tools)
14. [Notebooks](#14-notebooks)
15. [Costs](#15-costs)
16. [Troubleshooting](#16-troubleshooting)
17. [Features in the code not previously documented](#17-features-in-the-code-not-previously-documented)
18. [Changes from earlier manuals](#18-changes-from-earlier-manuals)

---

## 1. Installation

### 1.1 Requirements

- Python **3.11.4 or later** (`requires-python = ">=3.11.4"` in `pyproject.toml`).
- Access to an LLM endpoint: Azure OpenAI (default, through LiteLLM) or OpenAI directly.
- Core dependencies are installed automatically: `litellm`, `pandas` (3.x), `numpy`, `openpyxl`,
  `python-dotenv`, `scikit-learn`, `tenacity`.

### 1.2 Install the package

From a clone of the repository (recommended if you will edit use cases):

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e .                     # the library and the `rca` command
pip install -e ".[notebooks]"        # plus Jupyter support (ipykernel, matplotlib, seaborn, nest-asyncio)
pip install pytest                   # optional: to run the test suite
```

Without a clone (library and command only):

```bash
pip install "git+<repo-url>"
pip install "rca-pipeline[notebooks] @ git+<repo-url>"
```

`uv sync` also works (the repo has a `uv.lock`).

Installation creates one console command, **`rca`**. Check it:

```bash
rca --help
```

Optional extras that the code uses when present: `langdetect` (better language detection, see
[7.7](#77-language-detection)) and `openai` (already pulled in by LiteLLM; used by `--backend openai`).

### 1.3 Credentials

Copy `.env.example` to `.env` and fill in the endpoint and key. See
[section 12](#12-credentials-and-environment-variables). `.env` is gitignored — never commit it.

### 1.4 Link the local data archive

Customer data is never committed. Each use case has four folders — `data/`, `runs/`, `output/`,
`feedback/` — that are **symbolic links** into a separate local folder, the *data archive*, with one
sub-folder per use case. Create the links once per clone:

```bash
python tools/link_archive.py /path/to/rca-data-archive
```

For every `use_cases/<name>/` (except folders starting with `_`), the script creates
`<name>/data → <archive>/<name>/data` (and the same for `runs`, `output`, `feedback`), creating the
archive sub-folders if needed. Existing links are replaced; a real folder already in place is left
alone and reported as `skip`. Profiles refer to `data/...` and `runs/...`, so they work unchanged
once the links exist.

### 1.5 Windows console encoding

Log lines contain box-drawing characters (`│`, `─`, `═`, `→`). On a Windows `cp1252` console or a
piped subprocess these raise `UnicodeEncodeError`. Set UTF-8 before running anything:

```bash
export PYTHONIOENCODING=utf-8 PYTHONUTF8=1          # Git Bash
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONUTF8='1'  # PowerShell
```

Notebooks pass the same two variables to every subprocess they start.

---

## 2. The use-case / workspace model

### 2.1 Repository layout

```
rca-pipeline/
├── src/rca_pipeline/        the library (installed as `rca_pipeline`) and the `rca` command
│   └── tools/               generic tools: python -m rca_pipeline.tools.<name>
├── use_cases/               one folder per analysis ("workspace")
│   └── _template/           starting point for a new use case
├── notebooks/               generic tutorial notebooks (pick a use case with WORKSPACE = "...")
├── tools/                   repo-level tools: link_archive.py, build_repo_manual_methodology.py, osvc_api/
├── docs/                    this manual, methodology, definition guide, architecture; history/ = old manuals
├── history/                 archived snapshots (e.g. old generated/ backups)
├── portfolio/               portfolio review deck and its scripts
├── tests/                   pytest suite (no LLM calls)
├── CATALOG.md               list of all use cases, generated by `rca catalog`
└── pyproject.toml
```

### 2.2 Inside a use case

Each analysis is a folder `use_cases/<name>/`. That folder is the **workspace**: every relative path
(definition, profiles, data, runs, generated files) is resolved from it.

| Path | What it holds | In git? |
|---|---|---|
| `README.md` | The use-case card: question, data, approach, results, how to re-run. Its front-matter block feeds `CATALOG.md`. | yes |
| `definitions/` | The Excel definition workbook (normally exactly one `.xlsx`). | yes |
| `profiles/` | Run profiles (JSON), usually one per stage. | yes |
| `generated/` | Build output: `modules/` (one `.py` per module), `taxonomies/` (one JSON per category list, plus `drafts/` from discovery), `pipeline_config.json`, `build_manifest.json`. | yes |
| `notebooks/` | Notebooks that prepare data, run stages, route, merge and score. | yes (outputs stripped) |
| `scripts/` | Use-case-specific helpers (definition writers, deck builders, models). | yes |
| `docs/` | Use-case deliverables and specifications. | yes |
| `history/` | Superseded definitions, notebooks and snapshots. | yes |
| `data/` → archive | Input exports, gold sets, intermediate inputs. | **no** (link) |
| `runs/` → archive | `checkpoints/`, `output/`, `intermediate/`, `cost_reports/`, logs. | **no** (link) |
| `output/` → archive | Older output location kept for legacy use cases. | **no** (link) |
| `feedback/` → archive | Human corrections (`<module>_corrections.jsonl`). | **no** (link) |

Not every use case has every folder: older ones (for example `login_blocked`) have only `generated/`
and the archive links.

### 2.3 How the workspace is chosen

Run commands from inside the use-case folder:

```bash
cd use_cases/sd_2026
rca validate
rca build
rca run --profile profiles/sd_2026_step1_contact_reason.json
```

or from anywhere with `--workspace` (short form `-w`), which must come **before** the command:

```bash
rca --workspace use_cases/sd_2026 build
rca -w use_cases/sd_2026 run --profile profiles/sd_2026_step1_contact_reason.json --dry-run
```

What happens:

- `--workspace DIR` sets the environment variable `RCA_WORKSPACE` to the absolute path of `DIR` and
  changes into that folder before running the command.
- Without `--workspace`, `RCA_WORKSPACE` defaults to the current directory (only if it is not
  already set).
- The library reads `RCA_WORKSPACE` once, when its modules are first imported, to locate
  `generated/`, `runs/checkpoints/` and `definitions/`. Change folders (or set the variable) **before**
  importing `rca_pipeline` in a notebook.
- `rca build`, `rca discover`, `rca promote-drafts` and `rca validate` resolve their default paths
  (`definitions/`, `generated/...`, `profiles/`) from the **current directory**, not from
  `RCA_WORKSPACE`. In normal use these are the same folder. Do not leave a stale `RCA_WORKSPACE`
  exported in your shell — see [Troubleshooting](#16-troubleshooting).
- `.env` is loaded from the workspace first, then from the nearest `.env` found walking up from the
  current directory (for example a shared one at the repo root). Variables already set in the shell
  win.

### 2.4 Starting a new use case

1. Copy the template: `cp -r use_cases/_template use_cases/<new_name>`. It contains a small,
   formatted definition (`definitions/my_usecase_definition.xlsx`, one `contact_reason` module with
   6 categories), an example profile (`profiles/example.json`) and 20 synthetic transcripts
   (`data/sample_transcripts.csv`).
2. Fill in `README.md`, including the front-matter block at the top (`name`, `title`, `product`,
   `status`, `owner`, `period`, `updated`, `tags`, `question`).
3. Rename and edit the definition (see [section 3](#3-the-definition-workbook) and the
   [definition guide](definition-guide.md)).
4. Check it: `rca validate`.
5. Build it: `rca build`.
6. Preview a run without LLM calls: `rca run --profile profiles/example.json --dry-run`.
7. Re-run `python tools/link_archive.py <archive>` so the new folder gets its archive links (the
   template's own `data/` is a real folder with synthetic data; replace or move it first if you want
   it linked).
8. Update the catalog: `rca catalog` (rewrites `CATALOG.md` at the repo root).

The test `tests/test_smoke_template.py` copies the template and runs steps 4–6, so the template
always works.

---

## 3. The definition workbook

One Excel workbook per use case defines **what** the AI is asked about each ticket. `rca build`
compiles it into the files in `generated/`. Nothing in the workbook is code.

### 3.1 Sheets

| Sheet | Required | Purpose |
|---|---|---|
| `Start here` | no | Plain-language instructions and a summary table of the modules. Added by `format_definition`. Ignored by the build. |
| `modules` | **yes** | One row per classification step ("module"). |
| `fields` | **yes** | One row per output column a module produces, with the instruction the AI follows. |
| `taxonomy` | **yes** | The category list of each module: L1 rows are groups, L2 rows are the categories inside them. |
| `Change log` | no | One row per change: date, who, sheet, what changed, why. Ignored by the build. |
| any other (`README`, `how_to_use`, …) | no | Ignored. |

Columns are matched **by name** in row 1; their order does not matter (except that `module_name`
must stay the first column — see below) and optional columns may be absent.

**Note and header rows.** In each of the three data sheets, the build drops any row whose first cell
is empty or starts with `Green`, `Edit`, `L1`, `L2`, `level` or `module_name`. That lets older
workbooks carry guidance rows under the header. `rca validate` also skips a row whose first cell is a
sentence (contains a space) when the sheet's key column (`enabled` / `field_name` / `level`) is empty.
Keep `module_name` in column A so this rule works.

**Booleans.** `TRUE`, `1` and `1.0` mean true; `FALSE`, `0`, `0.0` mean false. Excel checkbox
values (`True`/`False`) work.

### 3.2 Colour convention

`python -m rca_pipeline.tools.format_definition` colours the header cells and adds a note to each
(hover to read it):

- **green** — edit freely (descriptions, instructions, labels, notes, on/off switches);
- **yellow** — advanced; change only if you know what it does;
- **grey** — linking names that connect the sheets; rename everywhere or not at all.

The tables below show the colour of each column.

### 3.3 `modules` sheet

| Column | Colour | Required | Read by | Meaning |
|---|---|---|---|---|
| `module_name` | grey | yes | build, run | Short name of the step, e.g. `sd_contact_reason`. Letters, digits and `_` only. Becomes `generated/modules/<name>.py`, the function `classify_<name>` and the value you pass to `--modules`. The other sheets refer to it. |
| `taxonomy_prefix` | yellow | with a category list | build, run | Letters used to build codes, e.g. `CR` gives `CR1`, `CR1.1`. Empty = no category list. No prefix may be the start of another prefix used in the same workspace (codes are parsed with the greedy pattern `^[A-Z]+`). |
| `taxonomy_file` | grey | with a category list | build, run | File name of the category list, e.g. `contact_reason.json`. Its stem is the taxonomy key. Fill both prefix and file, or neither. |
| `reorder_group` | yellow | no | build | Groups output columns. Defaults to the module name. Only takes effect when the group name equals the first `_`-separated word of a column name. |
| `reorder_order` | yellow | no | build | Position of the group in the output (lower = earlier). Default 99. |
| `enabled` | green | yes | build, validate | `TRUE` to build and run the module; `FALSE` switches it off without deleting it. Disabled modules are left out of `pipeline_config.json`. |
| `description` | green | yes | build (prompt) | The module's task, in plain words. Baked into the system prompt as `Your task: …`. Long decision rules (precedence between categories) usually go here. |
| `discovery_mode` | yellow | no | discover | `full` or `extract_only` marks the module as a target for `rca discover`. Any other value counts as empty. |
| `extract_prompt` | yellow | no | discover | The Pass-1 system prompt used by `rca discover`. |
| `notes` | green | no | — | Free notes for people. Not sent to the model (but part of the change-detection hash). |

### 3.4 `fields` sheet

| Column | Colour | Required | Read by | Meaning |
|---|---|---|---|---|
| `module_name` | grey | yes | build | Which module this output column belongs to. |
| `field_name` | grey | yes | build (prompt) | Output key and column name, e.g. `sdcr_code`. Letters, digits and `_`. Must be unique across all modules in the workbook (results are merged per record, and the last module to write a name wins). |
| `field_type` | yellow | yes | build (prompt) | See [3.5](#35-field-types). |
| `description` | green | no | — | Explanation for people reading the results. Never sent to the model. |
| `prompt_instruction` | green | yes (validate warns) | build (prompt) | The exact instruction the AI follows for this field. The biggest single lever on accuracy. Empty = no instruction line. |
| `in_output` | yellow | no | build | `FALSE` removes the column from the result file at the very end of post-processing (it is still available to the steps before). Default `TRUE`. |
| `explode_list` | yellow | no | build | For `list` fields: `TRUE` splits the list into columns `<field>_1`, `<field>_2`, … Default `FALSE`. |
| `validate_enum` | yellow | no | build | For `enum:` fields: `FALSE` removes the field from the post-processing enum check. It does **not** switch off the parse-time check inside the generated module (see [3.5](#35-field-types)). Default `TRUE`. |
| `explode_keys` | yellow | no | build (prompt) | For lists of objects: comma-separated keys of each item, e.g. `code, verdict, evidence`. With `explode_list = TRUE` the list is exploded to `<field>_<key>_<n>`. The keys also appear in the JSON example given to the model. |
| `notes` | green | no | — | Free notes. Not sent to the model. |

The **first field of type `code`** in a module becomes the module's `code_field` in
`pipeline_config.json` and its checkpoint *sentinel* (see [10.2](#102-how-done-is-decided-sentinels)).

### 3.5 Field types

| Type | The model returns | Post-processing |
|---|---|---|
| `code` | One leaf code from the module's category list, e.g. `CR2.1`. | Adds `<…>_label` and `<…>_description` columns (for column names ending `_code`). Columns whose name contains `primary` also get L1 repair and `*_class_l1` columns ([11](#11-post-processing-and-output-columns)). Only valid in a module with a category list. |
| `str` | Free text. | Columns whose name contains `_evidence` or `_snippet` get a grounding check ([11](#11-post-processing-and-output-columns)). |
| `bool` | `true` / `false`. | — |
| `int`, `float` | A number. | — |
| `list` | A JSON list (of strings, or of objects when `explode_keys` is set). | Exploded when `explode_list = TRUE`. |
| `enum:a,b,c` | Exactly one of the listed values. | At parse time the generated module lowercases the answer and blanks it (with a warning) if it is not in the list — **write options in lowercase**. Post-processing checks again unless `validate_enum = FALSE`. Needs at least two options. |

Anything else is accepted but treated as free text (`rca validate` warns).

### 3.6 `taxonomy` sheet

| Column | Colour | Required | Meaning |
|---|---|---|---|
| `module_name` | grey | yes | Which module this category belongs to. |
| `level` | green | yes | `L1` = a group heading; `L2` = a category inside the group above it. |
| `label` | green | yes | Category name. Rows with an empty label are skipped. |
| `description` | green | no (validate warns for L2) | When to use the category, and when not to. The best single way to improve accuracy. Rendered into the prompt. |
| `code` | yellow | no | Normally empty. A filled cell is used verbatim instead of the automatic code (for fixed reference codes such as `PA1`). |
| `notes` | green | no | Free notes. Not sent to the model. |

**Code numbering.** Codes are assigned from the row order within each module: the n-th L1 is
`<PREFIX>n`, the m-th L2 under it is `<PREFIX>n.m`. An L2 row attaches to the nearest L1 row above it
in the same module; an L2 before any L1 is skipped with a warning. **Inserting a row renumbers every
later code**, which breaks comparison with earlier runs, gold sets and feedback files. Append new rows
at the end of their group where possible, keep the catch-all ("Other") last, and never type codes by
hand unless you need fixed codes.

**Flat lists.** The generated prompt and post-processing expect leaf codes. A flat list of
categories is modelled as one L1 per category with a single L2 of the same name (for example the
ScienceDirect stage-1 contact reasons).

### 3.7 How the workbook reaches the prompt

`rca build` writes one Python module per enabled module. Its system prompt is assembled in this order:

1. Fixed role line: *"You are an expert classifier for Elsevier support tickets."*
2. `Your task:` + `modules.description` — **baked into the `.py` at build time.**
3. `## Taxonomy` + every code, label and `Description:` line, rendered **at run time** from
   `generated/taxonomies/<file>.json` (modules with a category list only).
4. `## Instructions`: one numbered line per field with a `prompt_instruction`, as
   `n. <instruction> → \`<field_name>\`` — baked.
5. `## Output Format`: a JSON array example built from the field names and types — baked.
6. Closing lines: return only valid JSON, every input uid must appear; always use leaf codes. (The
   leaf-code example is fixed text — `CR4.1`/`CR4` for modules with a category list, `CE1.1`/`CE1`
   for those without — whatever the module's prefix.)

The user message is *"Classify the following support transcripts."* followed by the batch as a JSON
list of `{"uid": …, "text": …}`.

Consequences:

- Edits to **taxonomy labels and descriptions** take effect at the next `rca build` (the JSON is
  rewritten every build).
- Edits to a **module description**, **field instruction**, **field name** or **field type** are
  baked into the `.py`, which `rca build` does **not** overwrite once it exists. Rebuild with
  `rca build --force <module>` (or `--force-all`).
- `fields.description` and all `notes` columns never reach the model.

### 3.8 Naming rules that prevent silent errors

- **Give every module one short field stub** (`sdcr_`, `eer_`, `s2_` …) and name fields
  `<stub>_code`, `<stub>_justification`, `<stub>_evidence`.
- **Avoid structural prefixes.** Before a run, input columns whose names start with any of
  `access_classification`, `contact_reason_`, `secondary_codes`, `root_cause_`, `contributing_codes`,
  `resolution_`, `escalat`, `troubleshooting_`, `environment_tags`, `products_mentioned`,
  `error_messages`, `time_criticality`, `deadlines`, `urgency`, `short_summary`, `evidence_snippets`,
  `metadata_` — or with any field name of the current `pipeline_config.json` — are dropped as "stale
  enrichment". Do not name source columns that way, and do not give new fields such prefixes unless
  you mean to.
- **Field names unique across modules** (last writer wins when results are merged).
- **No prefix may start another prefix** (`SD` and `SDCR` in the same workspace would clash).
- **Lowercase enum options.**
- **L1 repair and `*_class_l1` columns** only apply to columns whose name contains `primary`
  (`contact_reason_primary_code`). A field called `<stub>_code` gets only `_label` and `_description`.

### 3.9 Formatting a workbook for editors

```bash
python -m rca_pipeline.tools.format_definition definitions/*.xlsx
```

Adds a `Start here` sheet (instructions plus a table of the modules: on/off, number of output
columns, number of categories, description), header colours and notes, dropdowns (TRUE/FALSE, L1/L2,
field types, module names that must match the `modules` sheet), shading for L1 rows, amber
highlighting of L2 rows without a description, and a `Change log` sheet if there is none. It never
changes a cell value in `modules`, `fields` or `taxonomy`, so the build output is unchanged. Safe to
run repeatedly; close the workbook in Excel first.

---

## 4. Commands

```
rca [--workspace DIR | -w DIR] <command> [options]

  validate        check the definition workbook and the profiles
  build           build generated/ from the workbook (runs validate first)
  discover        draft a category list from a sample of tickets
  promote-drafts  copy reviewed drafts into the live taxonomy folder
  run             classify transcripts
  catalog         rebuild CATALOG.md from the use-case READMEs
```

`rca <command> --help` lists the options of each command. `rca` with no command, `-h` or `--help`
prints the overview; an unknown command prints it and exits with an error.

### 4.1 `rca validate`

```bash
rca validate [--input definitions/<file>.xlsx]
```

| Flag | Default | Meaning |
|---|---|---|
| `--input`, `-i` | the only `.xlsx` in `definitions/` (Excel lock files `~$…` ignored) | Workbook to check. If there are zero or several workbooks you must pass it. |

Checks the workbook and every `profiles/*.json`, and prints each problem with its sheet and Excel row:

- `ERROR` — the build would fail or produce wrong results. Fix before building.
- `WARNING` — works, but is likely to hurt accuracy or confuse people.

The exit code is 1 when there is at least one error. What it checks:

| Area | Errors | Warnings |
|---|---|---|
| Structure | missing `modules`/`fields`/`taxonomy` sheet; missing required columns (`modules`: `module_name`, `enabled`, `description`; `fields`: `module_name`, `field_name`, `field_type`, `prompt_instruction`; `taxonomy`: `module_name`, `level`, `label`); workbook cannot be opened (often: still open in Excel) | — |
| modules | invalid or duplicate module name; prefix without file or file without prefix | enabled module without description; boolean cell not TRUE/FALSE |
| fields | unknown module; invalid field name; enum with fewer than 2 options; `code` field in a module without a category list | field name used twice; unknown field type; empty `prompt_instruction` |
| taxonomy | unknown module; level not L1/L2; first category of a module is L2; L2 without label | categories for a module without prefix/file (ignored); L1 group without L2 rows; L2 without description; duplicate label in a module |
| cross-checks | — | enabled module with a category list but no taxonomy rows and no existing JSON; module with a category list but no `code` field |
| profiles | profile is not valid JSON | profile lists modules that are not enabled; profile `input` file does not exist (fine if an earlier step creates it) |

It does **not** check that profile keys are known to `rca run` (see [5.4](#54-validating-a-profile)).
The [definition guide](definition-guide.md#7-reading-rca-validate-messages) explains each message in
plain words.

### 4.2 `rca build`

```bash
rca build [--input FILE] [--force MODULE ...] [--force-all] [--dry-run]
          [--taxonomy-dir DIR] [--module-dir DIR] [--config-file FILE] [--manifest-file FILE]
```

`rca build` first runs `rca validate` on the same workbook and stops with
`rca build: stopped — fix the errors above first.` if there are errors (warnings are printed but do
not stop it).

| Flag | Default | Meaning |
|---|---|---|
| `--input`, `-i` | the only `.xlsx` in `definitions/` | Workbook to build. With zero or several workbooks the command stops and lists them. |
| `--force MODULE …` | none | Regenerate the `.py` of the named modules even if it exists. Hand edits are lost. |
| `--force-all` | off | Regenerate the `.py` of every enabled module. Use after a generator version change. |
| `--dry-run` | off | Log what would be written; write nothing. |
| `--taxonomy-dir`, `-t` | `generated/taxonomies` | Where taxonomy JSONs (and `drafts/`) are written. |
| `--module-dir`, `-m` | `generated/modules` | Where module `.py` files are written. |
| `--config-file` | `generated/pipeline_config.json` | Where the runtime config is written. `rca run` always reads `<workspace>/generated/pipeline_config.json`, so changing this only makes sense for inspection. |
| `--manifest-file` | `generated/build_manifest.json` | Where the build manifest is written. |

For each **enabled** module:

| Artefact | When written | Notes |
|---|---|---|
| `generated/taxonomies/<taxonomy_file>` | every build, if the module has prefix and file and at least one category row | The workbook always wins: hand edits and promoted drafts are overwritten. A module with prefix and file but no category rows writes nothing (it reuses another module's list). |
| `generated/modules/<module>.py` | if missing, or named in `--force`, or with `--force-all` | Otherwise: if the module's rows are unchanged since the last generation it is skipped; if they changed, a **STALE** warning is logged and the old file is kept. |
| `generated/pipeline_config.json` | every build | Runtime contract: enabled modules, enum validators, list and object-list fields, code fields, output exclusions, enrichment prefixes, column groups. |
| `generated/build_manifest.json` | every build | Per-module hashes and timestamps, generator version, `generated_at`. |

**Change detection.** The build hashes (SHA-256) all of a module's rows on the three sheets. Any
change — including taxonomy-only or notes-only edits — marks the `.py` as stale even though taxonomy
edits do not need `--force`. A safe habit: build with `--force <your modules>` after editing
descriptions or field instructions.

**Generator version.** The manifest records the generator version (currently 1.7.0). If it differs
from the installed code, the build warns that existing `.py` files may be stale; rebuild with
`--force-all`.

Calling the build without a subcommand (`python -m rca_pipeline.build --input …`) is treated as
`build`.

### 4.3 `rca discover`

Drafts a category list from a sample of tickets when a module has none yet. The output is a draft for
human curation, never used directly.

```bash
rca discover --data runs/intermediate/population.csv [--modules M ...] [--sample-n 100]
             [--top-n 80] [--id-col uid] [--text-col transcript] [--model azure/dsaic-llm-general]
             [--batch-size 10] [--concurrency 4] [--retries 3] [--input FILE]
```

| Flag | Default | Meaning |
|---|---|---|
| `--data` | **required** | CSV or XLSX of tickets to sample from. |
| `--modules M …` | every enabled module with `discovery_mode` = `full` or `extract_only` | Modules to discover. Each must be enabled in the workbook. |
| `--sample-n` | `100` | Rows sampled with `random_state=42`. A pre-stratified file of exactly N rows run with `--sample-n N` keeps your stratification. |
| `--top-n` | `80` | Most frequent Pass-1 items passed to Pass 2. |
| `--id-col` | `uid` | ID column; a synthetic 1..N id is added if it is missing. |
| `--text-col` | `transcript` | Text column. |
| `--model` | `azure/dsaic-llm-general` | Model string. `RCA_MODEL` is **not** used by discover. |
| `--batch-size` | `10` | Pass-1 batch size. |
| `--concurrency` | `4` | Parallel Pass-1 calls. |
| `--retries` | `3` | Total attempts per call. |
| `--input`, `-i` | the only `.xlsx` in `definitions/` | Workbook (used to pick the targets). |
| `--taxonomy-dir`, `-t` | `generated/taxonomies` | Drafts go to `<dir>/drafts/`. |
| `--module-dir`, `-m`, `--config-file`, `--manifest-file` | as for build | Accepted; not used for discovery. |
| `--dry-run` | off | Accepted but **ignored**: LLM calls still happen. |

Max tokens, temperature and timeout come from `RCA_MAX_TOKENS`, `RCA_TEMPERATURE`, `RCA_TIMEOUT` or
their defaults. The prefix, `discovery_mode` and `extract_prompt` are read from the **built**
`generated/pipeline_config.json`, so build the workbook (with a placeholder category and at least one
field) before discovering. A module missing from the built config falls back to a two-letter prefix
from its name and a built-in prompt.

Outputs in `generated/taxonomies/drafts/`:

| File | Written | Content |
|---|---|---|
| `<module>_extracted.json` | whenever Pass 1 yields items | Frequency-ranked Pass-1 items. |
| `<module>_discovered.json` | every `full` run | The Pass-2 taxonomy, or `{}` if Pass 2 failed. |
| `<module>_draft.json` | only when the Pass-2 taxonomy is not empty | The two-level draft to curate. |

When Pass 2 fails, no new draft is written but an older one stays in place and the log still says
`DISCOVERY COMPLETE — 0 draft(s)`. Check the modification time of the draft. On Windows the process
has been seen to crash at interpreter shutdown (exit code 3221225477 / -1073741819) after printing
`DISCOVERY COMPLETE`; treat the run as successful only if that line was printed and the draft is new.

Recommended curation: read the draft beside the counts in `_extracted.json` and a sample of tickets,
then write the final categories into the workbook's `taxonomy` sheet (with descriptions, catch-all
last), remove the placeholder rows, and rebuild with `--force <module>`.

### 4.4 `rca promote-drafts`

```bash
rca promote-drafts [--input FILE] [--dry-run] [--taxonomy-dir DIR] [--manifest-file FILE]
```

| Flag | Default | Meaning |
|---|---|---|
| `--input`, `-i` | the only `.xlsx` in `definitions/` | Workbook used to map module → `taxonomy_file`. |
| `--dry-run` | off | Show what would be promoted. |
| `--taxonomy-dir`, `-t` | `generated/taxonomies` | Live folder; drafts are read from `<dir>/drafts/`. |
| `--manifest-file` | `generated/build_manifest.json` | Marks promoted modules `taxonomy_source = promoted_from_draft`. |
| `--module-dir`, `-m`, `--config-file` | as for build | Accepted; not used. |

It copies **every** `*_draft.json` in `drafts/` to the live folder (not only the drafts of the
workbook's modules), falling back to `<module>.json` when the module is not in the workbook. Because
the next `rca build` rewrites every taxonomy JSON from the workbook, a promoted draft survives only
until the next build. Prefer copying the curated categories into the workbook.

### 4.5 `rca run`

Classifies one input file with the modules of the current workspace, checkpointing as it goes, then
post-processes and writes one enriched file. It does not chain stages: routing between stages,
merging and scoring are done in notebooks.

```bash
rca run --profile profiles/<profile>.json [--dry-run] [overrides ...]
rca run --input data/tickets.csv --text-col Conversation --id-col INCIDENT_REF --modules sd_contact_reason
```

`--input` is required, on the command line or as `input` in the profile.

#### Every flag

| Flag | Default | Meaning |
|---|---|---|
| `--profile`, `-p` | none | JSON run profile ([section 5](#5-run-profiles)). |
| `--input`, `-i` | **required** | Input CSV, or XLSX/XLS. |
| `--output`, `-o` | `<input folder>/<input stem>_enriched.xlsx` | Output file; `.xlsx`/`.xls` is written as Excel, anything else as CSV. |
| `--checkpoint` | `<workspace>/runs/checkpoints/<input stem>_checkpoint.jsonl` | Checkpoint file. (The `--help` text says `<input>_checkpoint.jsonl`; the code uses the path shown here.) |
| `--bad-uids` | `<workspace>/runs/checkpoints/<input stem>_bad_uids.txt` | Skip list of failed ids. |
| `--log-file` | `run_pipeline.log` in the current directory | Log file (appended). |
| `--taxonomy-dir` | `<workspace>/generated/taxonomies` | Folder of taxonomy JSONs. Which files are loaded still comes from `pipeline_config.json`. |
| `--id-col` | `uid` | ID column. Sent to the model and used to merge results back. |
| `--text-col` | `transcript` | Text column sent to the model. |
| `--batch-size` | `10` | Maximum records per LLM call. |
| `--max-chars` | `60000` | Maximum characters per batch (a single longer text is sent alone, whole). |
| `--concurrency` | `4` | Maximum concurrent calls (over all modules and batches). |
| `--retries` | `3` | Total attempts per call for transient errors (Tier 1). |
| `--max-tokens` | `4096` | Completion token limit per call. |
| `--backend` | `LLM_BACKEND`, else `litellm` | `litellm` or `openai`. |
| `--model` | `RCA_MODEL`, else `azure/dsaic-llm-general` | Model string (`azure/<deployment>` for LiteLLM; bare deployment name for the openai backend). |
| `--temperature` | `RCA_TEMPERATURE`, else `0.0` | Sampling temperature. |
| `--modules M …` | all modules registered from `pipeline_config.json` | Modules to run. |
| `--sentinel MOD:FIELD …` | automatic | Override the field used to decide a record is done for a module ([10.2](#102-how-done-is-decided-sentinels)). |
| `--run-name` | input stem | Display name in the console banner and gold-eval table. |
| `--dry-run` | off | Load config, taxonomies and input, apply the bad-UID list, batch, print a summary and stop: no LLM calls, no output, checkpoint not read. |
| `--enable-confidence` | off | See [7.2](#72-confidence-scoring). Through `rca run` this only asks the API for log-probabilities. |
| `--confidence-threshold` | `0.70` | See [7.2](#72-confidence-scoring). Not applied by `rca run`. |
| `--export-review-queue` | off | See [7.2](#72-confidence-scoring). Not applied by `rca run`. |
| `--feedback-dir` | `<workspace>/runs/feedback` | Corrections folder. `rca run` reads it only as training labels for `--eval-gold-test`; it does not inject few-shot examples ([7.3](#73-feedback-few-shot-examples)). |
| `--feedback-max-examples` | `5` | Not applied by `rca run`. |
| `--feedback-strategy` | `recent` | `recent`, `diverse`, `frequent` or `smart`. Not applied by `rca run`. |
| `--hierarchical-modules M …` | none | Not applied by `rca run` ([7.4](#74-hierarchical-classification)). |
| `--incremental` | off | Not applied by `rca run` ([7.5](#75-incremental-processing)). |
| `--incremental-state-file` | none | Not applied by `rca run`. |
| `--track-costs` | off | Record tokens and estimated cost; print a summary and save a report ([7.6](#76-cost-tracking)). **Works in `rca run`.** |
| `--cost-report-dir` | `<workspace>/runs/cost_reports` | Folder for `costs_<YYYYMMDD_HHMMSS>.json`. |
| `--detect-language` | off | Not applied by `rca run` ([7.7](#77-language-detection)). |
| `--language-strategy` | `translate` | `translate`, `prompt` or `detect`. Not applied by `rca run`. |
| `--run-quality-check` | off | Not applied by `rca run` ([7.8](#78-quality-dashboard)). |
| `--quality-report-dir` | `<workspace>/runs/output` | Not applied by `rca run`. |
| `--previous-quality-report` | none | Not applied by `rca run`. |
| `--eval-gold-test` | none | After the run, score contact reason / root cause against a gold CSV ([9.1](#91-built-in---eval-gold-test)). |

The flags marked *not applied* are accepted, forwarded into `RunConfig` and shown by `--dry-run`
under "Enhancements enabled", but `rca run` calls the module classifiers directly and never executes
those enhancements. They work only through the library path ([7.1](#71-where-enhancements-work)).

#### What a run does

1. Parse the command line and merge the profile.
2. Set up logging (file + console; in a non-terminal such as a notebook pipe, the console shows only
   warnings and a one-line progress update every 5 seconds).
3. Put `--backend` and `--model` into the environment, then import the library; the module registry
   is built from `generated/pipeline_config.json` at import.
4. Warn `BUILD STALENESS` for any `definitions/*.xlsx` modified after the last build.
5. Work out the sentinel field of each module.
6. Load taxonomies and input; drop stale enrichment columns; remove ids listed in the bad-UID file.
7. Batch the records. With `--dry-run`: print the summary and stop here.
8. Load the checkpoint, print per module how many records were done before and how many batches are
   still to do, then wait 3 seconds (Ctrl+C to abort).
9. Dispatch every (module, batch) pair concurrently up to `--concurrency`, appending each result to
   the checkpoint. A terminal shows a live progress table with ETA and, with cost tracking, cost per
   ticket.
10. Merge checkpoint + new results per id, add ids with errors to the bad-UID file, post-process
    ([section 11](#11-post-processing-and-output-columns)), write the output, compact the checkpoint
    to one line per id, save the cost report.
11. If `--eval-gold-test` is set, run the gold evaluation.

Ctrl+C during step 9 keeps the checkpoint; re-run the same command to resume.

### 4.6 `rca catalog`

```bash
rca catalog [--repo DIR]
```

| Flag | Default | Meaning |
|---|---|---|
| `--repo` | the first folder at or above the current directory that contains `use_cases/` | Repository root. |

Reads the front-matter block at the top of every `use_cases/*/README.md` (folders starting with `_`
are skipped) and writes `CATALOG.md` at the repo root: one row per use case (title linked to its
README, product, question, tags, status, period), sorted by status (`active`, `complete`,
`superseded`) then product, plus an index by tag. Edit the READMEs, not `CATALOG.md`.

---

## 5. Run profiles

A profile is a JSON file in `profiles/` holding the settings of one run, so a stage can be repeated
exactly. The usual convention is one profile per stage and module, named
`<product>_<year>_<stage>_<module>.json`.

### 5.1 Format and precedence

- Each key is an `rca run` option with `-` replaced by `_` (`--batch-size` → `batch_size`). Keys with
  `-` are also accepted.
- **Unknown keys are ignored silently** — including typos (`max_char`) and `_comment`. Use
  `_comment` for provenance (which notebook writes the input, which stage this is).
- Precedence, highest first:
  1. a command-line value that differs from the parser default;
  2. the profile value;
  3. the parser default (table in [4.5](#every-flag));
  4. for model, backend and temperature only: the environment / `.env`, then the built-in default.
- A command-line value **equal to the parser default** is overwritten by the profile (for example
  `--batch-size 10` does not beat `"batch_size": 5`).
- A switch set to `true` in the profile cannot be turned off from the command line (there are no
  `--no-…` flags).
- Relative paths in a profile resolve from the current directory — run from the use-case folder (or
  use `--workspace`).
- Notebooks typically pass `--input`, `--output` and `--modules` on the command line to point a stage
  profile at a smoke-test or subset file.

### 5.2 Every key

| Key | Default | Applied by `rca run`? | Notes |
|---|---|---|---|
| `_comment` | — | ignored | Free text. |
| `input` | required | yes | Its stem names the checkpoint — give every stage input a unique, product-prefixed name. |
| `output` | `<input>_enriched.xlsx` beside the input | yes | |
| `checkpoint` | `runs/checkpoints/<stem>_checkpoint.jsonl` | yes | |
| `bad_uids` | `runs/checkpoints/<stem>_bad_uids.txt` | yes | |
| `log_file` | `run_pipeline.log` | yes | |
| `taxonomy_dir` | `<workspace>/generated/taxonomies` | yes | |
| `id_col` | `uid` | yes | |
| `text_col` | `transcript` | yes | |
| `batch_size` | `10` | yes | |
| `max_chars` | `60000` | yes | |
| `concurrency` | `4` | yes | |
| `retries` | `3` | yes | |
| `max_tokens` | `4096` | yes | |
| `backend` | `LLM_BACKEND` / `litellm` | yes | |
| `model` | `RCA_MODEL` / `azure/dsaic-llm-general` | yes | |
| `temperature` | `RCA_TEMPERATURE` / `0.0` | yes | |
| `modules` | all registered | yes | JSON list. |
| `sentinel` | automatic | yes | JSON list of `"module:field"`. |
| `run_name` | input stem | yes | |
| `dry_run` | `false` | yes | Prefer `--dry-run` on the command line. |
| `track_costs` | `false` | **yes** | |
| `cost_report_dir` | `<workspace>/runs/cost_reports` | **yes** | |
| `eval_gold_test` | none | **yes** | Remove it before a dry run ([9.1](#91-built-in---eval-gold-test)). |
| `feedback_dir` | `<workspace>/runs/feedback` | partly | Only as training labels for `eval_gold_test`. |
| `enable_confidence` | `false` | partly | Only requests log-probabilities; no confidence columns. |
| `confidence_threshold` | `0.70` | no | Library path only. |
| `export_review_queue` | `false` | no | Library path only. |
| `feedback_max_examples` | `5` | no | Library path only. |
| `feedback_strategy` | `recent` | no | Library path only. |
| `hierarchical_modules` | `[]` | no | Library path only. |
| `incremental` | `false` | no | Library path only. |
| `incremental_state_file` | none | no | Library path only. |
| `detect_language` | `false` | no | Library path only. |
| `language_strategy` | `translate` | no | Library path only. |
| `run_quality_check` | `false` | no | Library path only. |
| `quality_report_dir` | `<workspace>/runs/output` | no | Library path only. |
| `previous_quality_report` | none | no | Library path only. |

Keys that exist only on `RunConfig` (for example `lang_en_min_score`, `timeout`) are **not**
profile keys; `rca run` ignores them.

### 5.3 Example

`use_cases/_template/profiles/example.json`:

```json
{
  "_comment": "Example run profile. Copy and rename per run. Paths are relative to this use-case folder.",
  "input": "data/sample_transcripts.csv",
  "output": "runs/output/sample_enriched.xlsx",
  "text_col": "conversation",
  "id_col": "uid",
  "taxonomy_dir": "generated/taxonomies",
  "modules": ["contact_reason"],
  "batch_size": 10,
  "concurrency": 2,
  "retries": 5,
  "max_tokens": 4096,
  "track_costs": true,
  "cost_report_dir": "runs/cost_reports"
}
```

Typical tuning in the 2026 use cases: `batch_size` 5, `max_chars` 40000, `concurrency` 4, `retries`
5, `max_tokens` 8192, `temperature` 0.0 for single-label stages; `batch_size` 1 for modules that
return several evidence quotes per ticket (batching long transcripts with wide evidence prompts has
mixed up quotes between tickets).

### 5.4 Validating a profile

`rca validate` checks that profile modules are enabled and that the input exists, but not that every
key is known. Check keys against `rca run --help` (the 2026 notebooks do this before writing a
profile):

```bash
python -c "import json,re,subprocess,sys; h=subprocess.run(['rca','run','--help'],capture_output=True,text=True).stdout; d={f.replace('-','_') for f in re.findall(r'--([a-z][a-z0-9-]+)',h)}; p=json.load(open(sys.argv[1],encoding='utf-8')); print([k for k in p if k!='_comment' and k.replace('-','_') not in d])" profiles/<profile>.json
```

Then run `rca run --profile profiles/<profile>.json --dry-run`.

---

## 6. RunConfig reference

`RunConfig` (in `rca_pipeline.config`) is the settings object passed through every pipeline stage.
`rca run` builds it from its flags; the library path ([7.1](#71-where-enhancements-work)) builds it
directly. Defaults marked *env* are read from the environment **once, when `rca_pipeline.config` is
first imported**.

| Field | Default | Env var | Set by `rca run` | Used for |
|---|---|---|---|---|
| `model` | `azure/dsaic-llm-general` | `RCA_MODEL` | `--model` (else env) | Model string. |
| `temperature` | `0.0` | `RCA_TEMPERATURE` | `--temperature` (else env) | Sampling temperature. |
| `max_tokens` | `4096` | `RCA_MAX_TOKENS` | always (`--max-tokens`) | Completion limit. |
| `timeout` | `120` | `RCA_TIMEOUT` | no (env only) | HTTP timeout per call, seconds. |
| `batch_size` | `10` | `RCA_BATCH_SIZE` | always (`--batch-size`) | Records per call. |
| `max_chars_per_batch` | `60000` | `RCA_MAX_CHARS` | always (`--max-chars`) | Characters per batch. |
| `concurrency` | `2` | `RCA_CONCURRENCY` | always (`--concurrency`, default 4) | Parallel calls. |
| `retries` | `5` | `RCA_RETRIES` | always (`--retries`, default 3) | Total attempts per call. |
| `max_workers` | `4` | `MAX_WORKERS` | no | Not used by any code. |
| `max_in_flight` | `8` | `MAX_IN_FLIGHT` | no | Not used by any code. |
| `checkpoint_every` | `5` | `CHECKPOINT_EVERY` | no | Not used by any code (`rca run` flushes after every batch). |
| `taxonomy_dir` | `<workspace>/generated/taxonomies` | — | `--taxonomy-dir` | Taxonomy folder. |
| `input_file` | `None` | — | `--input` | Input file. |
| `output_file` | `None` | — | `--output` | Output file (library path: not written if `None`). |
| `id_col` | `uid` | — | `--id-col` | ID column. |
| `text_col` | `transcript` | — | `--text-col` | Text column. |
| `modules` | `contact_reason, root_cause, resolution, escalation, troubleshooting, metadata` | — | `--modules` (default: all registered) | Modules to run. |
| `mode` | `classify` | — | always `classify` | Library path: `discover` runs discovery inline first ([7.1](#71-where-enhancements-work)). |
| `discovery_sample_n` | `100` | — | — | Library-path discovery sample size (`rca discover` sets it from `--sample-n`). |
| `discovery_top_n` | `80` | — | — | Items passed to discovery Pass 2 (`rca discover` sets it from `--top-n`). |
| `enable_confidence` | `False` | — | `--enable-confidence` | [7.2](#72-confidence-scoring). |
| `confidence_threshold` | `0.70` | — | `--confidence-threshold` | [7.2](#72-confidence-scoring). |
| `export_review_queue` | `False` | — | `--export-review-queue` | [7.2](#72-confidence-scoring). |
| `feedback_dir` | `<workspace>/runs/feedback` | — | `--feedback-dir` | [7.3](#73-feedback-few-shot-examples). |
| `feedback_max_examples` | `5` | — | `--feedback-max-examples` | [7.3](#73-feedback-few-shot-examples). |
| `feedback_strategy` | `recent` | — | `--feedback-strategy` | [7.3](#73-feedback-few-shot-examples). |
| `hierarchical_modules` | `[]` | — | `--hierarchical-modules` | [7.4](#74-hierarchical-classification). |
| `incremental` | `False` | — | `--incremental` | [7.5](#75-incremental-processing). |
| `incremental_state_file` | `None` | — | `--incremental-state-file` | [7.5](#75-incremental-processing). |
| `track_costs` | `False` | — | `--track-costs` | [7.6](#76-cost-tracking). |
| `cost_report_dir` | `<workspace>/runs/cost_reports` | — | `--cost-report-dir` | [7.6](#76-cost-tracking). |
| `detect_language` | `False` | — | `--detect-language` | [7.7](#77-language-detection). |
| `language_strategy` | `translate` | — | `--language-strategy` | [7.7](#77-language-detection). |
| `lang_en_min_score` | `0.15` | — | no | Minimum English common-word score in heuristic detection ([7.7](#77-language-detection)). |
| `lang_en_margin` | `0.05` | — | no | Margin by which English must beat other languages in heuristic detection. |
| `run_quality_check` | `False` | — | `--run-quality-check` | [7.8](#78-quality-dashboard). |
| `quality_report_dir` | `<workspace>/runs/output` | — | `--quality-report-dir` | [7.8](#78-quality-dashboard). |
| `previous_quality_report` | `None` | — | `--previous-quality-report` | [7.8](#78-quality-dashboard). |

Because `rca run` always passes its own defaults for batch size, max chars, concurrency, retries and
max tokens, the env vars `RCA_BATCH_SIZE`, `RCA_MAX_CHARS`, `RCA_CONCURRENCY`, `RCA_RETRIES` and
`RCA_MAX_TOKENS` have **no effect on `rca run`**. Set tuning in the profile.

---

## 7. Enhancement modules

Seven optional modules live in `rca_pipeline/enhancements/`. All are off by default.

### 7.1 Where enhancements work

`rca run` calls each module's classifier directly. Only cost tracking is wired into it. The other
enhancements run only through the **library path**, `rca_pipeline.pipeline.run_pipeline(cfg)` (or
`run_pipeline_async`), which the generic notebooks in `notebooks/` use.

| Enhancement | `rca run` | Library path |
|---|---|---|
| Confidence scoring | requests log-probabilities only; no columns | yes |
| Feedback few-shot | no (feedback dir used only by `--eval-gold-test`) | yes |
| Hierarchical L1→L2 | no | yes |
| Incremental | no | yes |
| Cost tracking | **yes** | yes |
| Language detection / translation | no | yes |
| Quality dashboard | no | yes |

Library path example (from inside a use-case folder, or after `os.chdir` to one, before importing):

```python
import os
os.environ["RCA_WORKSPACE"] = os.path.abspath("use_cases/scopus_content")   # or os.chdir(...)
from rca_pipeline.config import RunConfig
from rca_pipeline.pipeline import run_pipeline       # in Jupyter: nest_asyncio.apply() first, or await run_pipeline_async(cfg)

cfg = RunConfig(
    input_file="data/sample.xlsx", output_file="runs/output/sample_enriched.xlsx",
    id_col="Reference #", text_col="Conversation",
    modules=["contact_reason", "customer_effort"],
    batch_size=10, concurrency=2,
    enable_confidence=True, export_review_queue=True,
    feedback_dir="feedback", feedback_strategy="smart",
    track_costs=True, run_quality_check=True,
)
df = run_pipeline(cfg)
```

Differences from `rca run`: no checkpoint, no bad-UID list, no resume, no progress table; modules run
**one after another** (so each gets its own prompt suffix), batches within a module run concurrently.
With `mode="discover"` the pipeline first runs discovery on `discovery_sample_n` records for modules
with a `discovery_mode` and uses the result in memory (written to `<taxonomy_dir>/discovered/`).

### 7.2 Confidence scoring

**Switch on (library path):** `enable_confidence=True`, `confidence_threshold=0.70`,
`export_review_queue=True`.

**What happens:** an instruction is appended to every system prompt asking for an extra `confidence`
field (0.0–1.0) with calibration bands (0.9–1.0 very confident; 0.7–0.9 confident; 0.5–0.7 could fit
several codes; below 0.5 guessing). Each record gets `_confidence` (self-reported value, or empty) and
`_needs_review` (below the threshold or missing). With `export_review_queue`, flagged rows are written,
lowest confidence first, to `review_queue.xlsx` beside the output file.

**Through `rca run`:** `--enable-confidence` only adds `logprobs` to the API request (dropped
automatically if the deployment rejects it); no confidence columns are produced. The log-probability
helpers in `confidence.py` exist but the pipeline does not use them to compute scores — confidence is
the model's self-report.

**Caveat:** `_confidence` is one column per record; when several modules run, the last module's
value is kept.

### 7.3 Feedback few-shot examples

**Switch on (library path):** `feedback_dir="feedback"` (the use case's corrections folder),
`feedback_strategy="smart"`, `feedback_max_examples=5`.

**What happens:** corrections stored in `<feedback_dir>/<module>_corrections.jsonl` are appended to
that module's system prompt as "Known Hard Cases (Human-Corrected Examples)", each showing the
transcript (cut to 800 characters), the wrong and correct classification and the reviewer's reason.
The block is capped at 4,000 characters. Strategies:

| Strategy | Selects |
|---|---|
| `recent` | The most recent corrections. |
| `diverse` | One example per distinct corrected code (most recent within each). |
| `frequent` | The most common original→corrected pairs. |
| `smart` | One representative per corrected code, then, for each batch, the representatives most similar to that batch's tickets (see [methodology](methodology.md#9-few-shot-feedback-selection)). |

See [section 8](#8-the-feedback-loop) for how to record corrections. **Through `rca run` no examples
are injected**, whatever the profile says.

### 7.4 Hierarchical classification

**Switch on (library path):** `hierarchical_modules=["contact_reason"]`.

**What happens:** for each listed module, step 1 asks the model only for the L1 group (with child
counts and descriptions); step 2 asks, per group, for the leaf within that group, using the module's
own generated prompt so all its fields are returned. Twice the calls, smaller decision space per call.
If step 2 fails for a record, it keeps the L1 result.

**Caveat:** step 2 imports the generated module by name; if `generated/modules` is not importable
(not on `sys.path`) it falls back to a minimal prompt that returns only the code and a justification
(a warning is logged).

No current use case relies on this enhancement. The multi-stage use cases implement L1→L2 as
separate modules and profiles instead ([methodology](methodology.md#5-single-stage-vs-multi-stage-designs)).

### 7.5 Incremental processing

**Switch on (library path):** `incremental=True` **and** `incremental_state_file="runs/state.jsonl"`
(without a state file the flag does nothing).

**What happens:** records are compared with the state file by id and a hash of the text. New and
changed records are classified; unchanged ones reuse the cached result; the state file is updated
afterwards. Delete the state file to start again. The pipeline does not prune ids that have
disappeared from the input.

### 7.6 Cost tracking

**Switch on:** `--track-costs` (or `"track_costs": true`), optionally `--cost-report-dir`.

**What happens:** token usage of every successful call is recorded per module and priced from a
built-in table in `cost_tracker.py` (approximate list prices; an unknown model falls back to
$0.005 / $0.015 per 1K prompt / completion tokens without warning). The live progress shows cost per
ticket. At the end a summary is logged and `costs_<YYYYMMDD_HHMMSS>.json` (UTC) is saved with three
blocks: `summary` (calls, records, tokens, total and per-record cost, elapsed time, throughput),
`by_module` and `calls`. Figures are **estimates**, not billed spend. When modules run concurrently,
per-module attribution is approximate. Discovery calls are not tracked.

### 7.7 Language detection

**Switch on (library path):** `detect_language=True`, `language_strategy="translate" | "prompt" | "detect"`.

**What happens:** each transcript gets `_detected_language` and `_language_confidence`. Detection uses
`langdetect` if installed, otherwise a common-word heuristic for English, Spanish, French, German and
Portuguese (tuned by `lang_en_min_score` and `lang_en_margin`). With `translate`, non-English
transcripts are translated to English by the LLM before classification and `_original_text` /
`_translated_from` keep the original. With `prompt`, a `_prompt_language` column is added but the
prompts are not changed (so it behaves like `detect`). With `detect`, only the columns are added.

### 7.8 Quality dashboard

**Switch on (library path):** `run_quality_check=True`, optionally `quality_report_dir` and
`previous_quality_report="runs/output/quality_report.json"`.

**What happens:** after the output is written, `quality_report.json` and `quality_report.xlsx` are
saved in the report folder, and a summary is logged: coverage per module, code distribution (codes
under 1% or over 50%), unused codes, evidence types, error rate, confidence and language
distributions, anomalies (L1-only codes, one code taking over 60% of records, duplicate ids, many
blanks) and, with a previous report, a run-over-run comparison.

---

## 8. The feedback loop

Corrections from reviewers are stored per module in `feedback/<module>_corrections.jsonl` (the
`feedback/` link points into the data archive). One JSON object per line:

```json
{"uid": "12345", "text": "first 1,500 characters of the transcript ...",
 "original": {"sdcr_code": "SDCR5.1"}, "corrected": {"sdcr_code": "SDCR3.1"},
 "reason": "Reviewer note: why the correct code applies", "timestamp": "2026-08-01T12:00:00+00:00",
 "module": "sd_contact_reason"}
```

The file is append-only; when read, the latest correction per uid wins.

**Add corrections in Python:**

```python
from rca_pipeline.enhancements.feedback import FeedbackStore
store = FeedbackStore("feedback")
store.add_correction("sd_contact_reason", uid="12345", text=transcript,
                     original={"sdcr_code": "SDCR5.1"}, corrected={"sdcr_code": "SDCR3.1"},
                     reason="Customer is asking about ...")
store.compact("sd_contact_reason")    # optional: rewrite the file with one line per uid
```

**Import from a reviewed spreadsheet:** add a `<field>_corrected` column next to each field the
reviewer changed (for example `sdcr_code_corrected`) and optionally a `correction_reason` column, then:

```python
store.import_from_review_file("runs/output/reviewed.xlsx", module="sd_contact_reason",
                              text_col="Conversation", uid_col="INCIDENT_REF")
```

Only rows where the corrected value differs from the original are imported.

**Use them:** through the library path with a `feedback_strategy` ([7.3](#73-feedback-few-shot-examples)).
`rca run` does not inject them.

**Keep corrections valid:** a correction refers to codes of one taxonomy version. If you renumber or
replace a taxonomy, old corrections point at the wrong categories — move them aside (the LeapSpace
2026 profiles deliberately omit `feedback_dir` for this reason). Never use held-out gold tickets as
feedback examples ([methodology](methodology.md#11-measuring-accuracy)).

---

## 9. Gold-set evaluation

### 9.1 Built-in `--eval-gold-test`

```bash
rca run --profile profiles/<p>.json --output runs/output/<out>.xlsx --eval-gold-test data/gold_test.csv
```

After the run, compares the output with a gold CSV and prints accuracy, macro-F1 and weighted F1 for
the test set and, if `feedback_dir` contains corrections, for those "training" tickets.

- The gold CSV needs an id column (`uid`, or its first column is used as the id) and one or more
  label columns whose names contain *contact* + *reason* or *root* + *cause*. A `Conversation`
  column (any case) enables matching by the first 200 characters of text when ids differ.
- Predictions are read from `contact_reason_class_l1_label` / `contact_reason_primary_label` /
  `root_cause_primary_label` style columns, so it suits **contact reason / root cause** modules only,
  not modules with stub field names.
- If no gold ticket is found in the output, it runs a small extra classification ("mini pass") on the
  gold tickets as a subprocess. That pass forwards only modules, taxonomy dir, feedback settings, batch
  size, concurrency, retries and model, and hard-codes the text column `conversation`.
- Always give `--output` explicitly; without it the evaluation fails. Remove `eval_gold_test` from the
  profile before a `--dry-run`, otherwise it scores whatever output file already exists (and may start
  the paid mini pass).

### 9.2 Notebook-based scoring

The 2026 use cases score in their notebooks, which is more flexible: map gold labels onto taxonomy
codes, run every stage blind on the gold tickets, and report stage-1 accuracy, stage-2 accuracy given
correct routing, and end-to-end accuracy, with n, the majority-class baseline, macro-F1 and the top
confusions. See `use_cases/sd_2026/notebooks/07_sd_2026_two_stage.ipynb` and
[methodology](methodology.md#11-measuring-accuracy).

### 9.3 k-fold cross-validation

`use_cases/leapspace_legacy` and `use_cases/evolve` notebooks run stratified 5-fold cross-validation:
each fold writes its training tickets as feedback examples and classifies the held-out fold. Because
`rca run` does not inject feedback, those runs were effectively **zero-shot**, and all folds wrote the
same input name (`fold_in.csv`), so they share one checkpoint. Clear
`runs/checkpoints/fold_in_checkpoint.jsonl` before re-running and give each fold its own input name.
`python -m rca_pipeline.tools.run_kfold_eval` is a LeapSpace-specific script with the same caveat
(see [13.1](#131-library-tools)).

---

## 10. Checkpoints and crash recovery

### 10.1 Checkpoint

`rca run` appends every batch's results to `runs/checkpoints/<input stem>_checkpoint.jsonl` as soon as
it returns. If the process stops (crash, Ctrl+C, closed laptop), re-run **the same command**: the run
loads the checkpoint, skips what is done and sends only the remaining batches. At the end the file is
compacted to one line per id. At most the in-flight batches are lost.

### 10.2 How "done" is decided (sentinels)

A record counts as done for a module when the module's **sentinel field** is present and not empty in
the checkpoint (lists and booleans always count). The sentinel is read from the definition workbook
whose `modules` sheet lists all built modules: the first `code` field, else the first `bool`, else the
first `str`, else the first field. Override with `--sentinel module:field`. A module without a
sentinel is never detected as done (a warning is logged).

### 10.3 What resume does not notice

- **Prompt, taxonomy, model, temperature or tuning changes.** After editing a definition and
  rebuilding, a re-run with the same input prints `skip=N todo=0`, makes no calls and re-emits the old
  answers. Delete the checkpoint (and bad-UID file) after any change that should alter results. The
  2026 notebooks store a prompt fingerprint next to the checkpoint (`<stem>_checkpoint.fingerprint`)
  and delete stale checkpoints automatically; running `rca run` directly bypasses that guard.
- **Per-record resume.** A batch is re-sent whole if any of its records is not done, and batches are
  recomputed from the current input. Changing the input between resumes can re-bill finished records.
  Put a partial remainder in its own input file instead.
- **Shared names.** Checkpoints are keyed only by the input file's stem, so two stages with the same
  input file name share a checkpoint.

### 10.4 Bad-UID skip list

After merging, every id whose result carries `_error` is appended to
`runs/checkpoints/<stem>_bad_uids.txt`. Lines starting with `#` are comments. On the next run these ids
are removed from the input before batching, so they disappear from the output (the first run still
has them as rows with `_error`). To retry an id, delete its line **and** remove its records from the
checkpoint (the `_error` key is otherwise merged back in). A content-filter refusal stubs its whole
batch, so at `batch_size` 5 one refused ticket puts four innocent ones on the list — review the file
after each run and retry those at `batch_size` 1.

### 10.5 Starting fresh

```bash
rm runs/checkpoints/<stem>_checkpoint.jsonl runs/checkpoints/<stem>_bad_uids.txt runs/checkpoints/<stem>_checkpoint.fingerprint
```

---

## 11. Post-processing and output columns

After classification, results are merged per id and passed through these steps, in order:

1. **Merge** all modules' results onto the input rows (by `--id-col`; later values overwrite earlier ones).
2. **Enum validation** — values of `enum:` fields not in the allowed list are blanked (lowercase compare).
3. **Evidence grounding** — every column whose name contains `_evidence`, `_snippet` or
   `evidence_snippet` (but not `_evidence_type` or `_grounded`) is checked against the transcript.
   A boolean `<column>_grounded` is added. Ungrounded quotes are logged ("Hallucination detected") and
   **flagged, not blanked**. Empty evidence counts as grounded.
4. **Labels** — for each column ending `_code`: `<…>_label` and `<…>_description` from the taxonomy
   (blank descriptions returned by the model are back-filled). For columns containing `primary`: an L1
   code returned instead of a leaf is replaced by its only child, or by its lowest-numbered child if
   there are several (logged as a warning); and `*_class_l1`, `*_class_l1_label`,
   `*_class_l1_description` are added.
5. **Object-list explosion** — `explode_list` + `explode_keys` fields become `<field>_<key>_<n>`.
6. **Evidence grounding again** — for evidence columns created by step 5.
7. **List explosion** — `explode_list` fields become `<field>_1 … <field>_N`.
8. **Friction normalisation** — columns named `friction_points` / `friction_points_N` are mapped to
   canonical labels using `friction_categories` in `pipeline_config.json`. The build never writes that
   key, so this is a no-op unless a notebook adds it after building.
9. **Positional labels** — exploded values that look like codes (1–4 capitals + digits) get
   `_label_N` columns.
10. **Column order** — original columns first, then enrichment columns grouped by
    `reorder_group`/`reorder_order` (stub-named fields mostly fall to order 99).
11. **Output exclusion** — fields with `in_output = FALSE` are removed.

Other columns you will see:

- `uid` — if the input has no column literally named `uid`, a synthetic 1..N `uid` is inserted as the
  first column, whatever `--id-col` is. Ignore it and join on your real id.
- `_error` — present on records that could not be classified.

Excel cells hold at most 32,767 characters. The notebooks cut long text with a visible marker in
deliverable workbooks and ship a full-text CSV beside them; never read conversation text back from an
`.xlsx`.

---

## 12. Credentials and environment variables

Set these in `.env` (in the use-case folder or any parent folder, e.g. the repo root) or in the shell.
Shell values win over `.env`.

| Variable | Default | Used by | Notes |
|---|---|---|---|
| `AZURE_API_KEY` | — | LiteLLM `azure/…` models, openai backend (Azure) | Required for Azure. |
| `AZURE_API_BASE` | — | same | Endpoint URL. |
| `AZURE_API_VERSION` | `2024-02-01` (openai backend) | same | |
| `OPENAI_API_KEY` | — | openai backend with `USE_AZURE=false`; LiteLLM non-Azure models | |
| `USE_AZURE` | `true` | openai backend | `false` = OpenAI directly. |
| `LLM_BACKEND` | `litellm` | all LLM calls | `litellm` or `openai`; anything else stops with an error at import. `--backend` overrides. |
| `RCA_MODEL` | `azure/dsaic-llm-general` | `rca run`, library | `--model` overrides. Ignored by `rca discover`. |
| `RCA_TEMPERATURE` | `0.0` | `rca run`, discover, library | `--temperature` overrides. |
| `RCA_MAX_TOKENS` | `4096` | discover, library | Ignored by `rca run` (use `max_tokens`). |
| `RCA_TIMEOUT` | `120` | all | Seconds per call. No flag. |
| `RCA_BATCH_SIZE` | `10` | library | Ignored by `rca run`. |
| `RCA_MAX_CHARS` | `60000` | discover, library | Ignored by `rca run`. |
| `RCA_CONCURRENCY` | `2` | library | Ignored by `rca run`. |
| `RCA_RETRIES` | `5` | library | Ignored by `rca run`. |
| `MAX_WORKERS`, `MAX_IN_FLIGHT`, `CHECKPOINT_EVERY` | `4`, `8`, `5` | — | Read into `RunConfig`; not used. |
| `LOG_LEVEL` | `INFO` | import-time logging | `rca run` sets its own logging (INFO to file). |
| `RCA_WORKSPACE` | current directory | all | Use-case folder; set by `--workspace`. |
| `OSVC_USERNAME`, `OSVC_PASSWORD` | — | `tools/osvc_api/` | Read with `os.environ[...]`; the scripts do not load `.env`, so export them in the shell. |

Backends:

- **LiteLLM (default):** the model string carries the provider prefix, e.g. `azure/dsaic-llm-general`.
- **openai:** `--backend openai`; with Azure (default) set the Azure variables and give the bare
  deployment name as the model; with `USE_AZURE=false` set `OPENAI_API_KEY` and a model name.

Model precedence for `rca run`: `--model` > profile `model` > `RCA_MODEL` in the shell > `.env` >
built-in default. Backend: `--backend` > profile `backend` > `LLM_BACKEND` > `litellm`.

---

## 13. Generic tools

### 13.1 Library tools

Run with `python -m rca_pipeline.tools.<name>` from the use-case folder.

| Tool | Usage | What it does |
|---|---|---|
| `format_definition` | `python -m rca_pipeline.tools.format_definition definitions/*.xlsx` | Adds the `Start here` sheet, colours, header notes, dropdowns and `Change log` ([3.9](#39-formatting-a-workbook-for-editors)). |
| `convert_taxonomy` | `python -m rca_pipeline.tools.convert_taxonomy --input taxonomy.xlsx [--output-dir taxonomies] [--group-col …] [--subcategory-col …] [--rootcause-col …] [--description-col …] [--cr-prefix CR] [--rc-prefix RC] [--cr-filename contact_reason.json] [--rc-filename root_cause.json] [--sheet-name 0]` | Turns a "group / sub-category / root causes / description" spreadsheet into contact-reason and root-cause taxonomy JSONs (columns auto-detected if not given). Note that `rca build` overwrites JSONs from the workbook; use this to seed a workbook or for one-off comparisons. |
| `taxonomy_diff` | `python -m rca_pipeline.tools.taxonomy_diff old.json new.json [--codes-only] [--output diff.xlsx]` | Lists codes added, removed and relabelled between two taxonomy JSONs. |
| `aggregate_costs` | `python -m rca_pipeline.tools.aggregate_costs [--dir runs/cost_reports] [--since YYYY-MM-DD] [--output summary.xlsx]` | Meant to total the cost reports. **Currently matches `cost_*.json` and reads top-level keys, while the reports are `costs_*.json` with totals under `summary`, so it under-counts.** Until fixed, sum `summary.total_cost_usd` yourself (one-liner in [section 15](#15-costs)). |
| `diagnose_and_fix_descriptions` | `python -m rca_pipeline.tools.diagnose_and_fix_descriptions` | Diagnostic script (runs on import): checks that taxonomy descriptions load and that `*_description` columns can be derived. |
| `run_kfold_eval` | `python -m rca_pipeline.tools.run_kfold_eval` | LeapSpace-specific 5-fold evaluation with hard-coded paths. **Not runnable as-is after the restructuring** (it calls a `run_pipeline.py` script relative to the package folder), and it relies on feedback injection that `rca run` does not do. Use the notebook in `use_cases/leapspace_legacy` as the reference. |

### 13.2 Repository tools

| Tool | Usage | What it does |
|---|---|---|
| `tools/link_archive.py` | `python tools/link_archive.py /path/to/rca-data-archive` | Creates the `data/`, `runs/`, `output/`, `feedback/` links in every use case ([1.4](#14-link-the-local-data-archive)). |
| `tools/check_repo.py` | run by CI and the pre-commit hook (`pip install pre-commit && pre-commit install`) | Blocks commits containing notebook outputs, e-mail addresses, passwords or large data files. |
| `tools/build_repo_manual_methodology.py` | see its docstring | Generator of the October 2026 Word manual (`docs/history/RCA_Repo_Manual_and_Methodology_2026.docx`) from a content JSON that is not in the repo. Kept for reference. |
| `tools/osvc_api/` | `python tools/osvc_api/osvc_api.py` | OSvC report export client (exported notebook code: report and product ids are set in the script). Credentials from `OSVC_USERNAME` / `OSVC_PASSWORD`. |

---

## 14. Notebooks

- **Use-case notebooks** (`use_cases/<name>/notebooks/`) prepare the input, write or check the
  definition, build, render and check the prompts, write profiles, run each stage as an `rca run`
  subprocess (`python -m rca_pipeline.cli run …`), route tickets between stages, merge, audit, score
  and write the deliverable. They find their use-case folder by walking up from the notebook. Run them
  with the `[notebooks]` extra installed and the project's virtual environment as kernel (they assert
  pandas 3.x).
- **Generic notebooks** (`notebooks/`, repo root) are tutorials: build and discover, classification
  with enhancements (library path), feedback corrections, taxonomy analysis, quality and accuracy, EDA,
  gold-set evaluation. Set `WORKSPACE = "<use case>"` in the first cell; the notebook changes into
  `use_cases/<WORKSPACE>` before importing the library.

---

## 15. Costs

- Turn on `track_costs` in every profile; reports land in `runs/cost_reports/`.
- Figures are list-price estimates from a static table — write "est." next to them.
- Typical cost has been about $0.005–0.014 per ticket per module pass; wide multi-field modules at
  `batch_size` 1 cost more (about $0.03 per ticket).
- The system prompt dominates input tokens at small batch sizes; shortening it lowers cost.
- Spend in stages: free prompt review → smoke test on 20–40 tickets → gold evaluation or a
  1,000-ticket probe → full run ([methodology](methodology.md#14-cost-and-the-spend-ladder)).

Total all reports in a use case (both name forms, reading the `summary` block):

```bash
python -c "import json,glob; s=[json.load(open(p,encoding='utf-8'))['summary'] for p in sorted(glob.glob('runs/cost_reports/cost*_*.json'))]; print(len(s), 'reports, est. USD', round(sum(x['total_cost_usd'] for x in s), 2))"
```

---

## 16. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `rca build: stopped — fix the errors above first.` | `rca validate` found errors. | Fix the listed rows; see the [definition guide](definition-guide.md#7-reading-rca-validate-messages). |
| `which definition? pass --input definitions/<file>.xlsx` | `definitions/` has zero or several `.xlsx`. | Pass `--input`, or move old workbooks to `history/`. |
| `Cannot open … Is it still open in Excel?` | Workbook locked. | Close Excel and retry. |
| A re-run after editing finishes at once with `skip=N todo=0` | The checkpoint already has answers; resume ignores prompt changes. | Delete `<stem>_checkpoint.jsonl` (and `_bad_uids.txt`, `.fingerprint`). |
| Edits to a description or instruction change nothing | The `.py` is not regenerated once it exists (STALE warning). | `rca build --force <module>` (or `--force-all`). |
| `Module 'X' not registered` / output lacks a module's columns | Module not enabled, not built, or its `.py` failed to import. | Check `enabled`, run `rca build`, read the log for a syntax error; `rca build --force X`. |
| `No batches created — 0 records to process` | Wrong `--id-col`/`--text-col`, empty input, or the bad-UID list excluded everything. | Check the listed available columns; check the bad-UID file. |
| Every value of an enum column is blank | Enum options with capitals; the answer is lowercased before the check. | Write options in lowercase; rebuild with `--force`. |
| Source columns vanish from the output | Their names start with a structural prefix or a field name of the current config. | Rename them before the run ([3.8](#38-naming-rules-that-prevent-silent-errors)). |
| Truncated or invalid JSON, many `Tier 2` lines | Responses too long for `max_tokens`. | Raise `max_tokens` (e.g. 8192), lower `batch_size` or `max_chars`. |
| Rate-limit errors, long pauses | Too many concurrent calls. Any retryable error pauses all batches (Retry-After + 1 s, or 30 s). | Lower `concurrency`. |
| Five consecutive tickets with `_error`, log shows a content-policy error | A refused batch is stubbed whole. | Retry the innocent ids at `batch_size` 1 in their own input. |
| An evidence quote belongs to another ticket | Several long transcripts in one batch with a wide evidence prompt. | `batch_size` 1 for such modules; check ungrounded quotes against neighbouring rows. |
| `BUILD STALENESS` warning on every run | A workbook in `definitions/` is newer than the last build. | Rebuild, or ignore if only notes changed. |
| Feedback / confidence / quality settings have no effect | Not applied by `rca run` ([7.1](#71-where-enhancements-work)). | Use the library path. |
| A profile setting is ignored | Unknown key (typo) or the command line gave the default value. | Validate keys ([5.4](#54-validating-a-profile)). |
| `UnicodeEncodeError` on Windows | Console code page. | Set `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8`. |
| Commands use the wrong use case's files | A stale `RCA_WORKSPACE` exported in the shell: the library uses it, while build/validate use the current folder. | `unset RCA_WORKSPACE`, or always use `rca --workspace …`. |
| `--dry-run` raises `TypeError` or starts a paid pass | `eval_gold_test` is set in the profile. | Remove it before dry runs; always give `--output`. |
| `discover` exit code 3221225477 on Windows | Crash at interpreter shutdown after finishing. | Accept if `DISCOVERY COMPLETE` was printed and the draft is new. |
| Cost summary shows $0 or an odd price | `track_costs` off, or the model is not in the price table (default price used). | Turn it on; add the model to `_PRICING` in `cost_tracker.py`. |

Read-only checks (no LLM calls):

```bash
python -c "import json; print(list(json.load(open('generated/pipeline_config.json', encoding='utf-8'))['modules']))"
rca build --dry-run
rca run --profile profiles/<profile>.json --dry-run
wc -l runs/checkpoints/*_bad_uids.txt
```

---

## 17. Features in the code not previously documented

- **`rca validate`** — plain-language check of the workbook and profiles, with sheet and Excel row
  numbers; `rca build` runs it first.
- **Workspaces** — `rca --workspace DIR` / `RCA_WORKSPACE`; every use case has its own `generated/`,
  so building one use case no longer replaces another's modules.
- **Default definition** — `rca build`/`validate`/`discover`/`promote-drafts` use the only `.xlsx` in
  `definitions/` when `--input` is omitted.
- **`rca catalog`** — builds `CATALOG.md` from use-case README front matter.
- **`format_definition`** — `Start here` sheet, colour convention, header notes, dropdowns, change log.
- **`--temperature`** flag and `temperature` profile key.
- **Optional workbook columns** — `discovery_mode`, `extract_prompt` (modules), `explode_keys`
  (fields), `code` (taxonomy).
- **List-of-object fields** — `explode_list` + `explode_keys`, with grounding re-checked on the
  exploded evidence columns.
- **Script-aware grounding** — typographic quotes and dashes are folded before matching; evidence of
  fewer than 4 words is compared by characters (fixes false alarms on Chinese/Japanese text, but makes
  short quotes lenient).
- **Process-wide rate-limit gate** — a retryable error pauses every in-flight call for the Retry-After
  time (+1 s) or 30 s; Tier 1 honours `Retry-After`, else exponential backoff with jitter (2–90 s).
- **Tier 2 split depth cap** (4 levels) before falling back to single records.
- **Log-probability fallback** — if a deployment rejects `logprobs`, it is dropped for that model for
  the rest of the process.
- **Dry-run summary** and **live progress table** with ETA, records/second and cost per ticket.
- **Build staleness warning** in `rca run`, and the **generator version** check in `rca build`.
- **Template smoke test** (`tests/test_smoke_template.py`) and `tests/test_validate.py`.
- **`tools/link_archive.py`** and the data-archive model.

## 18. Changes from earlier manuals

The earlier manuals are in `docs/history/` (v1/v3 Manual and Methodology, May 2026; Repo Manual and
Methodology, October 2026). Where they differ from the code, this manual follows the code:

| Earlier manual said | Code does now |
|---|---|
| `python build_pipeline.py build …`, `python run_pipeline.py …` | `rca build`, `rca run` (and `rca validate`, `discover`, `promote-drafts`, `catalog`). The root scripts are gone. |
| One shared `generated/` and `profiles/` at the repo root; building product B removes product A's modules; back up and restore `pipeline_config.json` around each build | One workspace per use case under `use_cases/<name>/` with its own `generated/` and `profiles/`; no backup/restore needed. |
| `--input` always required for build; default was the Scopus v2 workbook | Default is the only `.xlsx` in `definitions/`; with zero or several, the command asks. |
| Build writes everything without checks | `rca build` runs `rca validate` first and stops on errors. |
| Python 3.9+; `pip install pandas openpyxl litellm …` | Python ≥ 3.11.4; `pip install -e .` or `pip install git+<repo-url>`; extra `[notebooks]`. |
| Generated module inlines the taxonomy (`TAXONOMY = {...}`) | The taxonomy is rendered at run time from `generated/taxonomies/*.json`; only description, instructions and schema are baked in. |
| Enhancement flags (confidence, feedback, hierarchical, incremental, language, quality) work through the runner and profiles | Only cost tracking works in `rca run`; the others work only through `rca_pipeline.pipeline.run_pipeline`. `--enable-confidence` in `rca run` only requests log-probabilities. |
| A library entry point `rca-run` / `python -m rca_pipeline.pipeline` | No such entry point; call `run_pipeline(cfg)` from Python. |
| Multi-child L1 codes are kept with a warning | Replaced by the lowest-numbered child (warning logged), and only in columns whose name contains `primary`. |
| L1 repair uses description matching | Only sole-child and first-child rules exist (the description strategy in the docstring is not implemented). |
| Evidence grounding: exact match or ≥ 65% word overlap; "blanks fabricated evidence" (code docstring) | Quotes/dashes folded first; under 4 words, character-set overlap; ungrounded evidence is flagged, never blanked; empty evidence counts as grounded. |
| Incremental mode prunes records no longer in the input | The pipeline never calls the prune function. |
| Language strategy `prompt` adapts the prompts | It only adds a `_prompt_language` column; prompts are unchanged. |
| `RCA_CONCURRENCY` default 4, `RCA_RETRIES` default 3; env vars and `.env` set run tuning | `RunConfig` defaults are 2 and 5; `rca run` always passes its own defaults (4, 3, batch 10, max chars 60000, max tokens 4096), so these env vars do not affect it. |
| `--temperature` is an uncommitted flag | It is part of `rca run`. |
| Checkpoints at `<input>_checkpoint.jsonl` (help text) or under the repo root | `<workspace>/runs/checkpoints/<input stem>_checkpoint.jsonl`. |
| `pipeline_config.json` contains `friction_categories` | The build never writes it; friction normalisation is a no-op unless it is added by hand or by a notebook. |
| `promote-drafts` makes a draft live | It copies every draft; the next build overwrites them from the workbook. |
| Discovery `--dry-run` previews | Accepted but ignored; LLM calls happen. |
| Scripts under `scripts/` (convert_taxonomy, taxonomy_diff, aggregate_costs, run_kfold_eval …) | Generic tools are `python -m rca_pipeline.tools.<name>`; use-case scripts live in `use_cases/<name>/scripts/`. |
| OSvC client under `scripts/osvic_api/` with credentials in the code | `tools/osvc_api/`, credentials from `OSVC_USERNAME` / `OSVC_PASSWORD`. |
| Notebooks 00–19 in one `notebooks/` folder | Use-case notebooks moved into their use case; generic tutorials remain in `notebooks/` and select a use case with `WORKSPACE`. |
