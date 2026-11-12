# RCA Pipeline

**Classify support tickets with an LLM, driven by an Excel workbook you can edit without writing code.**

You describe the questions (contact reason, root cause, effort, …) and the categories in one Excel
definition. The pipeline turns it into classifiers, runs them over your transcripts in batches with
retries and checkpoints, and writes the original data plus one column per answer.

Every past analysis is kept as a ready-to-copy example: see **[CATALOG.md](CATALOG.md)**.

---

## Install

```bash
git clone <this repo> && cd rca-pipeline
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[notebooks]"                          # or: pip install -e .   (no Jupyter)
cp .env.example .env                                   # then add your Azure OpenAI / OpenAI key
```

To use it from another project: `pip install git+<repo-url>@v0.1.0`. This gives you the `rca` command.

## Try it (no data or API key needed)

```bash
cd use_cases/_template
rca validate                                           # checks the Excel definition
rca build                                              # turns it into classifiers
rca run --profile profiles/example.json --dry-run      # shows what would run on 20 made-up tickets
```

Remove `--dry-run` (with a key in `.env`) to classify for real. Results go to `runs/output/`.

## Start a new analysis

1. **Copy** `use_cases/_template` to `use_cases/<your_name>/`.
2. **Describe it** in that folder's `README.md`: the business question, data, and approach.
3. **Edit the definition** in `definitions/`. Open the *Start here* sheet first. Green columns are safe to
   edit; hover over any header for help. See the [definition guide](docs/definition-guide.md).
4. **Put your data** in `data/`. Customer data is never committed (see below).
5. `rca validate` → `rca build` → `rca run --profile profiles/<profile>.json`
6. When finished, record the results in the README and run `rca catalog` to update [CATALOG.md](CATALOG.md).

Not sure where to start? Find the closest past analysis in the catalog, copy its folder, and adapt it.

## How it is organised

```
rca-pipeline/
├── CATALOG.md            every analysis, one row each: question, technique, status
├── src/rca_pipeline/     the engine (the `rca` command)
├── use_cases/<name>/     one folder per analysis — a self-contained, re-runnable example
│   ├── README.md         what was asked, data, approach, results, lessons
│   ├── definitions/      the Excel workbook (the source of truth)
│   ├── profiles/         run settings, one JSON per step
│   ├── generated/        built classifiers and taxonomies (rebuilt by `rca build`)
│   ├── notebooks/        the analysis notebooks (outputs cleared)
│   ├── docs/ scripts/    findings, decks and the scripts that made them
│   └── data/ runs/ feedback/   links to the local data archive (never committed)
├── notebooks/            general walkthroughs of the pipeline
├── docs/                 manual, methodology, definition guide, architecture
├── tools/                link_archive.py, check_repo.py, OSvC export client
└── portfolio/ history/   cross-analysis review deck; older build snapshots
```

## Customer data stays local

Transcripts, outputs and human corrections contain customer data, so they are **never** committed.
They live in a separate local folder (the *data archive*), with one sub-folder per use case. Link it
into the use-case folders once:

```bash
python tools/link_archive.py /path/to/rca-data-archive
```

The archive's `ARCHIVE_INDEX.md` lists every original file and where it went during consolidation.
A pre-commit hook (with the virtual environment activated: `pip install pre-commit && pre-commit install`) and CI block commits that contain
notebook outputs, e-mail addresses, passwords or large files.

## Commands

| command | what it does |
|---|---|
| `rca validate` | checks the definition workbook and the profiles; explains problems in plain words |
| `rca build` | validates, then builds classifiers + taxonomies into `generated/` |
| `rca discover --data <file>` | drafts a taxonomy from a sample of your data (for a new domain) |
| `rca promote-drafts` | accepts the reviewed draft taxonomies |
| `rca run --profile <file>` | classifies transcripts (`--dry-run` to preview; resumes after a crash) |
| `rca catalog` | rebuilds CATALOG.md from the use-case READMEs |

Run them inside a use-case folder, or from anywhere with `rca --workspace use_cases/<name> <command>`.
Every flag is listed in the [manual](docs/manual.md).

## Documentation

- [Manual](docs/manual.md): install, definition workbook, every command, flag and profile key, enhancements, troubleshooting
- [Methodology](docs/methodology.md): how and why it classifies the way it does, with links to the use cases that show each technique
- [Definition guide](docs/definition-guide.md): editing the Excel workbook, for non-technical colleagues
- [Architecture](docs/ARCHITECTURE.md): code structure and data flow
- `docs/history/`: earlier manuals, kept for reference

## Development

```bash
pip install -e . pytest
pytest                      # unit tests + an end-to-end smoke test on use_cases/_template
python tools/check_repo.py  # the same data/secret checks CI runs
```
