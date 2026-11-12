# Notebook Guide

Six Jupyter notebooks covering every phase of the pipeline lifecycle.
Run them in order (10 → 15) for a complete first-time walkthrough;
individual notebooks can also be used standalone once notebook 10 has
produced a baseline output file.

---

## How every notebook starts

All six notebooks share an identical **project-root detection cell**:

```python
_root = Path().absolute()
while not (_root / "rca_pipeline").exists() and _root.parent != _root:
    _root = _root.parent
os.chdir(_root)
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
```

**Why:** Jupyter's working directory is wherever it was launched from,
which may not be the project root.  This loop walks up the directory tree
until it finds the `rca_pipeline/` package folder and then `chdir`s to it,
so every relative path used in subsequent cells (`data/`, `runs/`,
`generated/`, etc.) resolves correctly regardless of launch location.
`sys.path.insert(0, str(_root))` makes `import rca_pipeline` work without
installing the package.

---

## 10 · Pipeline Tour (`notebooks/10_pipeline_tour.ipynb`)

**Purpose:** A guided, end-to-end first run on a 100-row sample.
No background knowledge is required beyond a configured `.env` file.
This is the canonical "does it work?" notebook.

### Settings cell

```python
DEFINITION_FILE = "definitions/scopus_content_pipeline_definition_v2.xlsx"
DATA_FILE       = "data/Scopus_Content_Collapsed.xlsx"
OUTPUT_FILE     = "runs/output/tour_sample_enriched.xlsx"
TAXONOMY_DIR    = "generated/taxonomies"

ID_COL          = "Reference #"
TEXT_COL        = "Conversation"
SAMPLE_N        = 100
SAMPLE_SEED     = 42

MODEL           = "azure/dsaic-llm-general"
BATCH_SIZE      = 10
CONCURRENCY     = 2
RETRIES         = 3
MAX_TOKENS      = 4096

MODULES         = ["contact_reason", "customer_effort"]
```

All tuneable parameters are consolidated here so the rest of the notebook
never contains magic strings.  `SAMPLE_SEED = 42` makes the 100-row
sample reproducible across runs.

---

### Step 1 · Build

```python
result = subprocess.run(
    [sys.executable, "build_pipeline.py", "build", "--input", DEFINITION_FILE],
    capture_output=True, text=True
)
```

**What it does:**  
Invokes `build_pipeline.py build` as a subprocess.  The build script reads
the Excel definition file and generates two artefacts per module:

- `generated/modules/<module>.py` — the classifier Python file with the
  structured prompt and schema.
- `generated/taxonomies/<module>.json` — the taxonomy JSON with L1/L2
  codes, labels, and descriptions.

It also writes `generated/pipeline_config.json` (mapping module names to
their generated files) and `generated/build_manifest.json` (timestamp and
version info).

**Why a subprocess and not a direct import?**  
`build_pipeline.py` is a CLI script that writes files to disk.  Calling it
as a subprocess keeps the build step isolated — the notebook does not need
to import build internals, and stdout/stderr from the build are cleanly
captured and printed.

**Second cell — manifest inspection:**  
After the build the notebook reads `build_manifest.json` and
`pipeline_config.json` to show what was generated:

```python
manifest = json.loads(manifest_path.read_text())
print(f"Generator version : {manifest.get('generator_version', '?')}")
...
for mod, cfg in config["modules"].items():
    tax = load_taxonomy_file(Path(TAXONOMY_DIR) / cfg["taxonomy_file"])
    l1  = len(tax)
    l2  = sum(len(n.get("children", {})) for n in tax.values() if isinstance(n, dict))
    print(f"  {mod}  L1={l1}  L2 (leaf)={l2}")
```

This verifies that the build actually produced valid taxonomy trees before
any LLM calls are made.  It is a fast, cheap sanity check.

---

### Step 2 · Load data

```python
df_full = pd.read_excel(DATA_FILE)
df = df_full.sample(n=min(SAMPLE_N, len(df_full)), random_state=SAMPLE_SEED).reset_index(drop=True)
```

**What it does:**  
Reads the full 8,307-row Scopus dataset, samples 100 rows, and resets
the index so row numbers start at 0.  `min(SAMPLE_N, len(df_full))`
prevents a crash when `SAMPLE_N` exceeds the dataset size (useful when
experimenting with smaller files).

**Second cell — ground-truth distribution:**  
Prints value counts for `Contact_Reason_Level_1` and
`Csat Effort Answer Desc` in the sample.  This establishes a baseline
before classification so you can judge how representative the sample is
(e.g., are all contact reason categories present, or is it skewed?).

---

### Step 3 · Classify

**First cell — configure RunConfig and prepare batches:**

```python
cfg = RunConfig(
    input_file=_tmp, output_file=OUTPUT_FILE,
    taxonomy_dir=TAXONOMY_DIR, id_col=ID_COL, text_col=TEXT_COL,
    modules=MODULES, model=MODEL, batch_size=BATCH_SIZE,
    concurrency=CONCURRENCY, retries=RETRIES, max_tokens=MAX_TOKENS,
)
taxonomies = load_taxonomies(TAXONOMY_DIR)
df_work    = drop_enrichment_cols(df.copy())
batches    = prepare_batched_records(df_work, cfg)
```

- `RunConfig` is the central configuration object consumed by every
  pipeline component.  Setting it up once here avoids scattering
  parameters across the notebook.
- `drop_enrichment_cols` strips any columns from a previous run
  (e.g., `contact_reason_primary_code`) so they do not pollute the new
  classification input.
- `prepare_batched_records` groups rows into batches of `BATCH_SIZE`,
  respecting a per-batch character limit.  Each batch becomes one LLM
  call.
- The sample is written to a temp file (`_tour_sample_tmp.xlsx`) because
  `RunConfig.input_file` expects a file path.

**Second cell — async classification loop:**

```python
async def _classify():
    for mod in MODULES:
        t0 = time.time()
        results = await run_classification_module(mod, batches, taxonomies, cfg)
        all_results.extend(results)
        print(f"  {mod}  {len(results)} records  {time.time()-t0:.1f}s")

asyncio.run(_classify())
```

`nest_asyncio.apply()` (called at the top of the notebook) allows
`asyncio.run()` inside Jupyter, which already runs its own event loop.
`run_classification_module` dispatches all batches for a single module
concurrently up to `CONCURRENCY` in-flight requests, with `RETRIES`
retries on transient failures.  Running modules sequentially (the `for`
loop) is simpler to reason about in a notebook; notebook 12 shows how to
enable full concurrency.

---

### Step 4 · Inspect results

**First cell — post-process and write output:**

```python
grouped = {}
for r in all_results:
    uid = str(r.get("uid", ""))
    grouped.setdefault(uid, {"uid": uid}).update(r)

df_out = post_process(df_work, list(grouped.values()), taxonomies, cfg)
write_output_file(df_out, OUTPUT_FILE)
```

- Results from both modules arrive in a flat list; the `grouped` dict
  merges them by `uid` so each row gets columns from both `contact_reason`
  and `customer_effort`.
- `post_process` performs validation, label derivation (code → label),
  heuristic fallbacks for unrecognised codes, and column reordering.
- `write_output_file` saves to Excel (`.xlsx`).

**Second cell — accuracy comparison:**  
Prints value-count distributions for `contact_reason_primary_label` vs
`Contact_Reason_Level_1` (ground truth), and `effort_primary_label` vs
`Csat Effort Answer Desc`.  These distributions give a quick sense of
classification quality without computing a formal accuracy metric.

**Third cell — side-by-side preview:**  
A 10-row table showing ID, ground-truth L1, predicted label, effort score
— a human-readable sanity check.

**Why this notebook is the entry point:**  
The `tour_sample_enriched.xlsx` it writes is used by notebooks 13, 14, and
15 as their "prior run" input, so they need this to have run at least once.

---

## 11 · Build & Manage (`notebooks/11_build_and_manage.ipynb`)

**Purpose:** Operational tooling for managing the generated layer.
Use this whenever you update the Excel definition and need to verify the
build, or when you want to browse the taxonomy structure before classifying.

### Settings cell

```python
DEFINITION_FILE = "definitions/scopus_content_pipeline_definition_v2.xlsx"
TAXONOMY_DIR    = "generated/taxonomies"
MANIFEST_PATH   = "generated/build_manifest.json"
CONFIG_PATH     = "generated/pipeline_config.json"
```

---

### Step 1 · Staleness check

```python
defn_mtime = datetime.fromtimestamp(defn_path.stat().st_mtime, tz=timezone.utc)
gen_at = datetime.fromisoformat(gen_at_str.replace("Z", "+00:00"))
rebuild_needed = defn_mtime > gen_at
```

**What it does:**  
Compares the filesystem modification time of the Excel definition against
the `generated_at` timestamp in the manifest.  If the definition is newer,
a rebuild is flagged as necessary.

**Why:** The generated files in `generated/` are derived artefacts — they
must stay in sync with the definition.  This check prevents classifying
with a stale taxonomy (e.g., after adding a new L2 code to the Excel).
It runs in milliseconds and requires no LLM calls.

---

### Step 2 · Force rebuild

```python
result = subprocess.run(
    [sys.executable, "build_pipeline.py", "build",
     "--input", DEFINITION_FILE, "--force-all"],
    capture_output=True, text=True
)
```

**What it does:**  
Passes `--force-all` to regenerate every module even when the build
system considers them current.  Without `--force-all`, the build only
regenerates modules whose Excel rows have changed (incremental build).

**When to use `--force-all`:**
- After changing prompt templates or classifier logic in `build_pipeline.py`
  itself (the content changes but the Excel checksum does not).
- After upgrading the generator version.
- When debugging stale behaviour and wanting a clean slate.

---

### Step 3 · Inspect the manifest

**First cell — manifest fields:**  
Reads `build_manifest.json` and displays generator version, generation
timestamp, and input file.  Then reads `pipeline_config.json` and builds a
table: module name, taxonomy file path, classifier file path, taxonomy
prefix.  This confirms what was built and where the outputs live.

**Second cell — generated files on disk:**  
Lists all files under `generated/taxonomies/` and `generated/modules/`
with sizes.  Size is a useful proxy: a suspiciously small taxonomy JSON
(e.g., 200 bytes) usually means the build wrote an empty structure.

---

### Step 4 · Browse taxonomies

**First cell — tree walk:**

```python
for l1_code, l1_node in sorted(tax.items()):
    children = l1_node.get("children", {})
    print(f"  [{l1_code}] {l1_label}")
    for l2_code, l2_node in sorted(children.items()):
        print(f"      [{l2_code}] {l2_label}: {l2_desc[:70]}...")
```

Prints the complete taxonomy as an indented tree: L1 category → L2
children with truncated descriptions.  Change `BROWSE_MODULE` at the top
of the cell to explore different modules.

**Why inspect descriptions here?**  
Descriptions are what the LLM uses to decide which code to assign.  A
missing or generic description is the most common cause of misclassification.
This visual walk lets you spot weak descriptions before running an
expensive classification job.

**Second cell — summary table:**  
A compact DataFrame showing L1 node count, L2 leaf count, and description
count per module.  Description count < (L1 + L2 count) means some nodes
are missing descriptions — an immediate signal to rebuild with corrected
Excel input.

---

## 12 · Classify with Enhancements (`notebooks/12_classify_with_enhancements.ipynb`)

**Purpose:** Demonstrate all seven pipeline enhancements active in a single
run.  This is the production-equivalent configuration; notebook 10 is the
minimal configuration.

### Settings cell

All seven enhancement blocks are configured here with boolean toggles:

| Setting | Default | Effect |
|---------|---------|--------|
| `ENABLE_CONFIDENCE` | `True` | Adds `_confidence_score` per label; routes low-confidence rows to a review queue |
| `CONFIDENCE_THRESHOLD` | `0.70` | Below this score a row is flagged for human review |
| `EXPORT_REVIEW_QUEUE` | `True` | Writes low-confidence rows to a separate `review_queue.xlsx` |
| `ENABLE_FEEDBACK` | `True` | Injects stored human corrections into every prompt |
| `FEEDBACK_STRATEGY` | `"diverse"` | Which examples to select: `recent`, `diverse`, `frequent`, or `smart` |
| `ENABLE_HIERARCHICAL` | `True` | Validates L2 codes against their declared L1 parent |
| `ENABLE_INCREMENTAL` | `False` | When `True`, skips rows already in the checkpoint |
| `TRACK_COSTS` | `True` | Writes a cost JSON after each run |
| `DETECT_LANGUAGE` | `False` | When `True`, detects non-English and translates before classification |
| `RUN_QUALITY_CHECK` | `True` | Generates a per-run quality report |

---

### Step 1 · Load and sample

Identical to notebook 10 — samples 100 rows with `SAMPLE_SEED = 42`.

---

### Step 2 · Configure RunConfig with all enhancements

```python
cfg = RunConfig(
    ...
    enable_confidence    = ENABLE_CONFIDENCE,
    confidence_threshold = CONFIDENCE_THRESHOLD,
    export_review_queue  = EXPORT_REVIEW_QUEUE,

    feedback_dir          = FEEDBACK_DIR,
    feedback_max_examples = FEEDBACK_MAX,
    feedback_strategy     = FEEDBACK_STRATEGY,

    hierarchical_modules = MODULES if ENABLE_HIERARCHICAL else [],

    incremental            = ENABLE_INCREMENTAL,
    incremental_state_file = CHECKPOINT_FILE,

    track_costs     = TRACK_COSTS,
    cost_report_dir = COST_REPORT_DIR,

    detect_language   = DETECT_LANGUAGE,
    language_strategy = LANGUAGE_STRATEGY,

    run_quality_check  = RUN_QUALITY_CHECK,
    quality_report_dir = QUALITY_REPORT_DIR,
)
```

`RunConfig` is the single object that carries all configuration to every
pipeline component; enabling an enhancement is a matter of setting the
corresponding field.  The pipeline reads these flags internally — no
call-site changes required.

---

### Step 3 · Run classification

Identical async pattern to notebook 10.  With all enhancements active the
LLM prompt is augmented with:
- Feedback examples (if any are stored) injected by `FeedbackStore.select()`
- A confidence instruction appended by `inject_confidence_instruction()`

The pipeline handles these transparently inside `run_classification_module`.

---

### Step 4 · Post-process and inspect enhancements

**Confidence scores cell:**  
Prints descriptive statistics (min, mean, max, std) for the confidence
column and counts how many rows fall below `CONFIDENCE_THRESHOLD`.  These
are the rows that should be human-reviewed before acting on the output.

**Review queue cell:**  
Reads `review_queue.xlsx` if written, or reconstructs it in memory by
filtering on the confidence threshold.  Displays the first five rows —
typically the most ambiguous tickets.

**Cost report cell:**  
Reads the latest `cost_*.json` from `runs/cost_reports/` and prints all
fields (model, tokens in, tokens out, estimated cost, timestamp).  Use
this to project costs before a full-dataset run.

**Quality report cell:**  
Reads the latest `quality_*.json` and prints each section with its top
five entries.  The quality report tracks metrics like label entropy (are
too many tickets getting the same code?), null rate, and inter-run drift
(if a `previous_quality_report` is supplied).

---

## 13 · Feedback & Corrections (`notebooks/13_feedback_corrections.ipynb`)

**Purpose:** Demonstrate the human-in-the-loop feedback workflow: add
corrections to the `FeedbackStore`, verify the selection strategies, and
measure whether injecting those corrections improves accuracy.

### Settings cell

`SAMPLE_N = 30` — a smaller sample (30 rows) keeps re-classification fast
for the demo.  `PRIOR_RUN` points to notebook 10's output so real
mismatches can be extracted.

---

### Step 1 · Load a prior run

```python
mismatches = df_prior[df_prior[label_col] != df_prior[gt_col]][
    [ID_COL, TEXT_COL, gt_col, label_col]
]
```

**What it does:**  
Reads the output from notebook 10 and finds every row where the LLM label
differs from the ground-truth `Contact_Reason_Level_1`.  These are the
candidates for correction.

**Why this matters:**  
The feedback loop is closed here — rather than discarding errors, they
become training examples that are injected into future prompts.  Over
multiple iterations this can substantially reduce systematic errors (e.g.,
a category the LLM consistently confuses with another).

---

### Step 2 · Add corrections to FeedbackStore

```python
store = FeedbackStore(FEEDBACK_DIR, module=MODULE)
store.add(
    uid=uid,
    text=text,
    wrong_label=wrong,
    correct_label=right,
    notes="auto-derived from ground-truth mismatch",
)
```

**What it does:**  
`FeedbackStore` is a persistent JSON-Lines store keyed by module name.
Each `add()` call appends one correction record containing:
- `uid` — the ticket ID so the same row is not corrected twice
- `text` — a (truncated) excerpt of the conversation
- `wrong_label` / `correct_label` — the before-and-after labels
- `notes` — optional human annotation for context

When a prior run is not available (e.g., first time), two synthetic
examples are added instead so the notebook still demonstrates the
FeedbackStore API.

---

### Step 3 · Inspect examples and selection strategies

```python
for strategy in ["recent", "diverse", "frequent", "smart"]:
    examples = store.select(n=3, strategy=strategy)
```

**What it does:**  
Calls `FeedbackStore.select()` four times, each with a different strategy,
and prints which examples were chosen.

**Why the strategies matter:**

| Strategy | Logic | Best for |
|----------|-------|----------|
| `recent` | Most recently added corrections | Fast-moving datasets where categories change |
| `diverse` | Maximise label coverage across selected examples | Balanced coverage; default recommendation |
| `frequent` | Errors that appear most often | Fixing systematic misclassification |
| `smart` | Combines recency + diversity + frequency | General production use |

The strategy is set in `RunConfig.feedback_strategy`; changing it
requires no code changes.

**Full dump cell:**  
Loads all stored examples into a DataFrame for audit — confirms what is
in the store before it gets injected into prompts.

---

### Step 4 · Re-classify with feedback injected

Constructs a new `RunConfig` with `feedback_dir` set, then runs
classification on the 30-row sample.  The `FeedbackStore` is loaded
internally by the pipeline; selected examples are formatted into the system
prompt alongside the taxonomy description.

---

### Step 5 · Before-vs-after comparison

```python
comparison = pd.concat([prior_labels, after_labels], axis=1, join="inner")
changed = comparison[comparison["before_feedback"] != comparison["after_feedback"]]
```

**What it does:**  
Aligns the pre-feedback labels (from notebook 10) with the post-feedback
labels (just computed) on the shared ID column, then isolates rows where
the label changed.  If ground truth is available a before-vs-after accuracy
delta is also computed.

**Interpreting the output:**
- Changed rows are not all improvements; the notebook shows the three
  columns (`before`, `after`, `ground_truth`) side by side so you can
  verify the direction.
- A positive accuracy delta confirms the feedback helped; a negative delta
  indicates the examples may be introducing noise and should be reviewed.

---

## 14 · Taxonomy Analysis (`notebooks/14_taxonomy_analysis.ipynb`)

**Purpose:** Structural analysis of taxonomy files — visualise what codes
exist, compare versions, identify coverage gaps, and flag quality issues.
This notebook makes no LLM calls.

### Settings cell

```python
TAXONOMY_DIR = "generated/taxonomies"
PRIOR_RUN    = "runs/output/tour_sample_enriched.xlsx"
MODULE       = "contact_reason"
```

---

### Step 1 · Visualise the current taxonomy

**Tree cell:**  
Loads the taxonomy for `MODULE` and prints every L1 node with its child
count.  Fast way to confirm structure after a rebuild.

**Bar chart cell:**  
```python
ax.bar(l1_labels, l2_counts, color="steelblue")
```
Plots the number of L2 codes per L1 group.  A highly uneven distribution
(e.g., one L1 with 20 children and another with 2) may indicate the
taxonomy needs rebalancing — either the Excel definition has inconsistent
granularity, or some categories are genuinely rarer and need fewer sub-codes.

---

### Step 2 · Diff two taxonomy versions

```python
result = subprocess.run(
    [sys.executable, "scripts/taxonomy_diff.py", tmp_path, str(new_tax_path)],
    ...
)
```

**What it does:**  
Creates a synthetic "old" version by stripping descriptions from the
current taxonomy, writes it to a temp file, then runs `taxonomy_diff.py`
to compare the two.  The diff script reports:
- Added codes (in new, not in old)
- Removed codes (in old, not in new)
- Relabelled codes (same code, different label)
- Re-described codes (same code, different description)
- Reparented codes (same code, different L1 parent)
- Unchanged codes

**Why this matters:**  
When a new Excel definition arrives, the diff shows exactly what changed
before re-running classification.  This matters operationally because
changing a code label or description will affect future classifications
but not historical ones — a diff makes the impact visible.

**Replacing the synthetic old version:**  
In practice, replace `tmp_path` with the path to a saved copy of the
previous taxonomy JSON.  The `.gitignore` is configured to exclude
`generated/taxonomies/*.json` but include
`generated/taxonomies/product_specific/` — curated taxonomies can be saved
there and versioned.

---

### Step 3 · Code distribution from a classification run

```python
dist = df_run[label_col].value_counts()
```

Reads notebook 10's output and counts how often each label was assigned.
The horizontal bar chart (top 15) makes it easy to see dominant categories.

**Why this is useful:**  
A skewed distribution (one category getting 80% of tickets) can indicate:
- A legitimate data characteristic (most tickets really are that type)
- An overly broad category definition (the LLM defaults to it when unsure)
- Missing or weak descriptions for competing categories

---

### Step 4 · Coverage gaps — codes never assigned

```python
all_codes  = {every code defined in the taxonomy}
used_codes = {every code that appeared in df_run}
unused     = sorted(all_codes - used_codes)
```

Lists every code that exists in the taxonomy but was never assigned in the
sample.  For a 100-row sample this is expected; for a full run over
thousands of tickets it indicates either:
- The category genuinely does not appear in the data
- The description is too narrow or ambiguous for the LLM to match

Both cases are actionable: remove dead codes or rewrite their descriptions.

---

### Step 5 · Quality checks on taxonomy files

```python
if not l1_node.get("label"):
    issues.append({"module": mod_name, "code": l1_code, "issue": "missing L1 label"})
if not l1_node.get("description"):
    issues.append({"module": mod_name, "code": l1_code, "issue": "missing L1 description"})
```

Iterates every node in every loaded taxonomy and flags:
- Missing L1 or L2 labels
- Missing L1 or L2 descriptions

Outputs a grouped count table and a detailed DataFrame.  Zero issues is
the goal; any issue here will silently degrade classification quality
because the LLM receives incomplete context.

---

## 15 · Quality & Accuracy Metrics (`notebooks/15_quality_and_accuracy.ipynb`)

**Purpose:** Rigorous evaluation of classification quality against the
ground-truth columns in `Scopus_Content_Collapsed.xlsx`.  This is the
primary evaluation notebook — run it after any significant change
(new model, new taxonomy, feedback iterations) to measure impact.

### Settings cell

```python
ID_COL      = "Reference #"
PRED_L1     = "contact_reason_primary_label"
PRED_L2     = "contact_reason_primary_code"
GT_L1       = "Contact_Reason_Level_1"
GT_L2       = "Contact_Reason_Level_2"
PRED_EFFORT = "effort_primary_label"
GT_EFFORT   = "Csat Effort Answer Desc"
CONF_COL    = "contact_reason_confidence_score"
```

All column name mappings are declared here.  If the pipeline renames an
output column (e.g., `effort_primary_label` → `effort_label`) only this
cell needs updating.

---

### Step 1 · Load and align

Reads the run file and checks which ground-truth and prediction columns
are actually present.  Prints a clear inventory before computing any
metrics so you know immediately if a column is missing (rather than
getting a silent `NaN` result later).

---

### Step 2 · Contact reason accuracy

```python
def accuracy_report(df, pred_col, gt_col, name=""):
    valid = df[[pred_col, gt_col]].dropna()
    n_correct = (valid[pred_col] == valid[gt_col]).sum()
    acc = n_correct / len(valid)
    print(f"  {name}  {n_correct}/{len(valid)}  ({acc:.1%})")
```

Reports exact-match accuracy for:
1. L1 label (`contact_reason_primary_label` vs `Contact_Reason_Level_1`)
2. L2 code (`contact_reason_primary_code` vs `Contact_Reason_Level_2`)

Exact-match on L1 label is the primary metric.  L2 code accuracy is a
secondary, stricter metric — the LLM must get both the broad category and
the specific sub-type right.

**`dropna()` before comparison:**  
Rows where either the prediction or the ground truth is null are excluded
from the denominator.  This prevents artificially low accuracy when the
LLM correctly abstained (e.g., for tickets with no contact reason) and
when the dataset has legitimately unlabelled rows.

---

### Step 3 · Effort accuracy

```python
effort_norm = {
    "low effort": "Low effort", "low": "Low effort",
    "high effort": "High effort", ...
}
df_eff["pred_norm"] = df_eff[PRED_EFFORT].str.lower().map(
    lambda x: effort_norm.get(str(x).lower(), str(x)))
```

**Why normalisation:**  
The LLM output may use lower-case (`"low effort"`) or abbreviated forms
(`"low"`) while the ground truth uses title case (`"Low effort"`).
The `effort_norm` dict canonicalises both sides before comparison,
avoiding false mismatches.

Prints both predicted and ground-truth distributions after normalisation
so you can spot systematic over- or under-prediction of effort levels.

---

### Step 4 · Confusion matrix

```python
confusion = pd.crosstab(
    valid_l1[GT_L1].rename("Ground Truth"),
    valid_l1[PRED_L1].rename("Predicted"),
)
```

`pd.crosstab` creates a category × category matrix where `confusion[i][j]`
is the number of times the ground truth was category `i` and the prediction
was category `j`.  The diagonal is correct classifications; off-diagonal
elements are errors.

**Heatmap:**  
For up to 20 categories a colour heatmap is drawn with `imshow`.  The
intensity of each cell is proportional to the count, making the most
common errors immediately visible.  For larger taxonomies the table alone
is shown (the heatmap becomes unreadable at 30+ categories).

**Reading the matrix:**  
A strong off-diagonal cell at (row=A, col=B) means the LLM frequently
predicts B when the ground truth is A.  This is the primary diagnostic for
category confusion — the next step is to inspect those tickets and often
to tighten the descriptions that distinguish A from B.

---

### Step 5 · Precision, Recall, F1 per category

```python
from sklearn.metrics import classification_report
report = classification_report(valid_l1[GT_L1], valid_l1[PRED_L1],
                                output_dict=True, zero_division=0)
df_report = pd.DataFrame(report).T.sort_values("f1-score", ascending=False)
```

**What the metrics mean:**

| Metric | Definition | Interpretation |
|--------|-----------|----------------|
| Precision | TP / (TP + FP) | Of all tickets the LLM labelled as X, what fraction were actually X? |
| Recall | TP / (TP + FN) | Of all tickets that are actually X, what fraction did the LLM find? |
| F1 | harmonic mean of P and R | Single score balancing both; 1.0 is perfect |
| Support | count of GT=X | How many examples the metric is based on |

Sorted by F1 descending — categories at the top are well-classified;
categories at the bottom need attention.

**Fallback without sklearn:**  
If `sklearn` is not installed, the notebook computes the same metrics
manually using basic DataFrame operations so the output is identical.

---

### Step 6 · Confidence calibration

```python
df_cal["conf_bin"] = pd.cut(df_cal[CONF_COL], bins=10, labels=False)
calibration = df_cal.groupby("conf_bin").agg(
    mean_confidence=(CONF_COL, "mean"),
    accuracy=("correct", "mean"),
    count=("correct", "count"),
)
```

**What it does:**  
Divides confidence scores into 10 equal-width bins and computes the
actual accuracy within each bin.  A well-calibrated model has a monotone
relationship: higher confidence → higher accuracy.

**Calibration plot:**  
Plots `mean_confidence` on the x-axis and `accuracy` on the y-axis.
The dashed diagonal is perfect calibration.  If the curve sits:
- Below the diagonal: the model is overconfident (claims 0.9 but only
  achieves 0.7 accuracy)
- Above the diagonal: the model is underconfident (useful as a filter
  signal — even "low confidence" predictions are often correct)

Bubble size encodes the count of rows per bin, so sparse bins are visually
de-emphasised.

---

### Step 7 · Error analysis — worst-performing categories

**Error pair cell:**

```python
error_pairs = (
    errors.groupby([GT_L1, PRED_L1])
          .size()
          .reset_index(name="count")
          .sort_values("count", ascending=False)
)
```

Lists the most common confusion pairs (e.g., "Add Missing Document" is
predicted as "General Inquiry" 7 times).  This is the most actionable
output: each row identifies a specific pair of categories whose descriptions
need to be sharpened.

**Category error-rate cell:**

```python
cat_stats = (
    stats.groupby(GT_L1)
         .agg(total=("correct", "count"), correct=("correct", "sum"))
         .assign(error_rate=lambda d: 1 - d["correct"] / d["total"])
         .query("total >= 3")
         .sort_values("error_rate", ascending=False)
)
```

Computes per-category error rate, filtering to categories with at least 3
examples (to avoid noise from singleton categories).  Sorted descending so
the worst-performing categories appear first.  A horizontal bar chart shows
the top 8.

**Example errors cell:**  
Drills into the worst category and prints the conversation text for a few
error cases.  Reading the actual text is essential: it reveals whether the
error is a bad description, an ambiguous ticket, or a genuine edge case
that the taxonomy cannot handle cleanly.

---

## Running order and dependencies

```
10_pipeline_tour          ← required first; generates tour_sample_enriched.xlsx
├── 11_build_and_manage   ← independent; requires only the definition file
├── 12_classify_with_enhancements  ← independent; generates enhanced_sample_enriched.xlsx
├── 13_feedback_corrections        ← reads tour_sample_enriched.xlsx (optional)
├── 14_taxonomy_analysis           ← reads tour_sample_enriched.xlsx (optional)
└── 15_quality_and_accuracy        ← reads tour_sample_enriched.xlsx (required)
```

Notebooks 11–14 can be run in any order after notebook 10.
Notebook 15 specifically requires notebook 10's output to compute accuracy
metrics — without it, it will raise `FileNotFoundError` with an
explanatory message.
