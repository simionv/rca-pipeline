"""
Patch notebooks/04_leapspace_classify_with_gold_set.ipynb for Option B:
  - Inserts a train/test split cell after the gold-set load cell
  - Rewrites the JSONL-write cell to use gold_train + code-based field names
  - Fixes cell 12 (run pipeline): adds --modules flag
  - Fixes eval cells 18-20 to use the held-out test set

Run from project root:
    python scripts/patch_leapspace_notebook.py
"""
from __future__ import annotations

import json
from pathlib import Path

NB_PATH = Path("notebooks/04_leapspace_classify_with_gold_set.ipynb")

# ── New cell sources ──────────────────────────────────────────────────────────

SPLIT_CELL = """\
# ── Train / test split ────────────────────────────────────────────────────────
# Load the code map produced by scripts/build_leapspace_definition.py.
# Codes are assigned by label order in the taxonomy sheet (CR1.1, CR1.2, …).
CODE_MAP_PATH = BASE / "data/leapspace_code_map.json"
assert CODE_MAP_PATH.exists(), (
    "Code map not found. Run first:\\n"
    "  python scripts/build_leapspace_definition.py"
)
with open(CODE_MAP_PATH, encoding="utf-8") as _f:
    _code_map = json.load(_f)
cr_code_map = _code_map["contact_reason"]   # label → CR1.x
rc_code_map = _code_map["root_cause"]       # label → RC1.x
print(f"Code map: {len(cr_code_map)} CR codes, {len(rc_code_map)} RC codes")

# Stratified 49 / 20 split — protect single-instance classes by collapsing
# them into an "other" stratum so sklearn doesn't error.
from sklearn.model_selection import train_test_split

_cr_counts = gold["Contact Reason"].value_counts()
_stratify  = gold["Contact Reason"].where(
    gold["Contact Reason"].map(_cr_counts) >= 2, "other"
)
gold_train, gold_test = train_test_split(
    gold, test_size=20, random_state=42, stratify=_stratify
)
gold_test.to_csv(BASE / "data/leapspace_gold_test.csv", index=False)
print(f"Train: {len(gold_train)}, Test: {len(gold_test)}")
"""

JSONL_CELL = """\
import json
from datetime import datetime, timezone

FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)

def write_feedback_jsonl(df, module, label_col, field_name, label_to_code, out_path):
    \"\"\"Write gold-set rows as FeedbackStore JSONL entries (code-based).\"\"\"
    entries, skipped = [], 0
    for _, row in df.iterrows():
        label = str(row[label_col]).strip()
        code  = label_to_code.get(label)
        if not code:
            skipped += 1
            continue
        entry = {
            "uid":       str(row["Ticket Number"]),
            "text":      str(row["Conversation"])[:1500],
            "original":  {field_name: code},
            "corrected": {field_name: code},
            "reason":    str(row["Explanations"]).strip(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "module":    module,
        }
        entries.append(entry)

    with open(out_path, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\\n")

    print(f"  {out_path.name}: {len(entries)} entries written ({skipped} skipped)")
    return entries

cr_entries = write_feedback_jsonl(
    gold_train, "contact_reason", "Contact Reason",
    "contact_reason_primary_code", cr_code_map,
    FEEDBACK_DIR / "contact_reason_corrections.jsonl",
)
rc_entries = write_feedback_jsonl(
    gold_train, "root_cause", "Root Cause",
    "root_cause_primary_code", rc_code_map,
    FEEDBACK_DIR / "root_cause_corrections.jsonl",
)
print("\\nFeedback JSONL files ready.")
"""

RUN_PIPELINE_CELL = """\
import subprocess, sys

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

cmd = [
    sys.executable, str(PROJECT_DIR / "run_pipeline.py"),
    "--input",                str(INPUT_CSV),
    "--output",               str(OUTPUT_PATH),
    "--text-col",             TEXT_COL,
    "--modules",              *MODULES,
    "--feedback-dir",         str(FEEDBACK_DIR),
    "--feedback-strategy",    FEEDBACK_STRATEGY,
    "--feedback-max-examples", str(FEEDBACK_MAX),
    "--batch-size",           str(BATCH_SIZE),
    "--concurrency",          str(CONCURRENCY),
]

print("Running command:")
print(" ".join(cmd))
print()

result = subprocess.run(cmd, text=True, capture_output=True)
print(result.stdout[-3000:] if result.stdout else "")
print(result.stderr[-2000:] if result.stderr else "")
if result.returncode == 0:
    print(f"\\n✓ Pipeline complete. Output: {OUTPUT_PATH}")
else:
    print(f"\\n✗ Pipeline exited with code {result.returncode}")
"""

SAVE_EVAL_CELL = """\
# Use the held-out 20-ticket test set for unbiased evaluation
gold_eval = pd.read_csv(BASE / "data/leapspace_gold_test.csv")
gold_eval = gold_eval[["Ticket Number", "Conversation", "Contact Reason", "Root Cause"]].copy()
gold_eval.columns = ["uid", "conversation", "gold_contact_reason", "gold_root_cause"]

gold_tmp = Path("data/leapspace_gold_eval_tmp.csv")
gold_eval[["uid", "conversation"]].to_csv(gold_tmp, index=False)
print(f"Saved {len(gold_eval)} held-out test tickets to {gold_tmp}")
"""

RUN_EVAL_CELL = """\
# Run pipeline on the held-out 20 tickets
gold_output = Path("runs/output/leapspace_gold_eval.xlsx")
gold_output.parent.mkdir(parents=True, exist_ok=True)

cmd_eval = [
    sys.executable, str(PROJECT_DIR / "run_pipeline.py"),
    "--input",                str(gold_tmp),
    "--output",               str(gold_output),
    "--text-col",             "conversation",
    "--modules",              *MODULES,
    "--feedback-dir",         str(FEEDBACK_DIR),
    "--feedback-strategy",    FEEDBACK_STRATEGY,
    "--feedback-max-examples", str(FEEDBACK_MAX),
    "--batch-size",           "10",
    "--concurrency",          "4",
]

print("Running evaluation on held-out test set...")
result = subprocess.run(cmd_eval, capture_output=True, text=True)
print(result.stdout[-2000:] if result.stdout else "")
print(result.stderr[-1000:] if result.stderr else "")
print(f"Done. Exit code: {result.returncode}")
"""

METRICS_CELL = """\
from sklearn.metrics import classification_report

pred    = pd.read_excel(gold_output)
eval_df = gold_eval.merge(pred, on="uid", how="inner")
print(f"Matched {len(eval_df)} / {len(gold_eval)} held-out test tickets\\n")

# Build inverse maps: code → label (for readable report when label col absent)
cr_inv = {v: k for k, v in cr_code_map.items()}
rc_inv = {v: k for k, v in rc_code_map.items()}

def _resolve_col(pred_df, module):
    \"\"\"Find the best prediction column: prefer *_label, fall back to *_code.\"\"\"
    for suffix in ("label", "code"):
        cols = [c for c in pred_df.columns if module in c.lower() and suffix in c.lower()]
        if cols:
            return cols[0], suffix
    return None, None

cr_col, cr_kind = _resolve_col(pred, "contact_reason")
rc_col, rc_kind = _resolve_col(pred, "root_cause")

if cr_col:
    preds_cr = eval_df[cr_col]
    if cr_kind == "code":
        preds_cr = preds_cr.map(lambda x: cr_inv.get(str(x), x))
    print("── Contact Reason accuracy ──")
    print(classification_report(eval_df["gold_contact_reason"], preds_cr, zero_division=0))

if rc_col:
    preds_rc = eval_df[rc_col]
    if rc_kind == "code":
        preds_rc = preds_rc.map(lambda x: rc_inv.get(str(x), x))
    print("── Root Cause accuracy ──")
    print(classification_report(eval_df["gold_root_cause"], preds_rc, zero_division=0))
"""

# ── Patch logic ───────────────────────────────────────────────────────────────

def make_code_cell(source: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": source}


def main() -> None:
    with open(NB_PATH, encoding="utf-8") as f:
        nb = json.load(f)

    cells = nb["cells"]

    def src(i: int) -> str:
        s = cells[i]["source"]
        return s if isinstance(s, str) else "".join(s)

    # Locate target cells by content signatures
    SIGS = {
        "gold_load":     "gold = pd.read_excel(GOLD_SET_PATH)",
        "jsonl_write":   "def write_feedback_jsonl(",
        "run_pipeline":  "OUTPUT_PATH.parent.mkdir",
        "save_eval":     "gold_eval = gold[",
        "run_eval":      "gold_output = Path(\"runs/output/leapspace_gold_eval.xlsx\")",
        "metrics":       "from sklearn.metrics import classification_report",
    }

    idx: dict[str, int] = {}
    for i, cell in enumerate(cells):
        s = src(i)
        for name, sig in SIGS.items():
            if name not in idx and sig in s:
                idx[name] = i

    missing = [k for k in SIGS if k not in idx]
    if missing:
        print(f"WARNING: could not locate cells: {missing}")
        print("Patch may be incomplete — check the notebook manually.")

    # 1. Insert train/test split cell after gold_load
    if "gold_load" in idx:
        insert_pos = idx["gold_load"] + 1
        cells.insert(insert_pos, make_code_cell(SPLIT_CELL))
        print(f"  Inserted train/test split cell at position {insert_pos}")
        # Shift all subsequent indices
        for k in list(idx.keys()):
            if idx[k] >= insert_pos:
                idx[k] += 1

    # 2. Replace JSONL write cell
    if "jsonl_write" in idx:
        cells[idx["jsonl_write"]]["source"] = JSONL_CELL
        cells[idx["jsonl_write"]]["outputs"] = []
        cells[idx["jsonl_write"]]["execution_count"] = None
        print(f"  Replaced JSONL write cell at position {idx['jsonl_write']}")

    # 3. Replace run pipeline cell
    if "run_pipeline" in idx:
        cells[idx["run_pipeline"]]["source"] = RUN_PIPELINE_CELL
        cells[idx["run_pipeline"]]["outputs"] = []
        cells[idx["run_pipeline"]]["execution_count"] = None
        print(f"  Replaced run-pipeline cell at position {idx['run_pipeline']}")

    # 4. Replace save-eval cell
    if "save_eval" in idx:
        cells[idx["save_eval"]]["source"] = SAVE_EVAL_CELL
        cells[idx["save_eval"]]["outputs"] = []
        cells[idx["save_eval"]]["execution_count"] = None
        print(f"  Replaced save-eval cell at position {idx['save_eval']}")

    # 5. Replace run-eval cell
    if "run_eval" in idx:
        cells[idx["run_eval"]]["source"] = RUN_EVAL_CELL
        cells[idx["run_eval"]]["outputs"] = []
        cells[idx["run_eval"]]["execution_count"] = None
        print(f"  Replaced run-eval cell at position {idx['run_eval']}")

    # 6. Replace metrics cell
    if "metrics" in idx:
        cells[idx["metrics"]]["source"] = METRICS_CELL
        cells[idx["metrics"]]["outputs"] = []
        cells[idx["metrics"]]["execution_count"] = None
        print(f"  Replaced metrics cell at position {idx['metrics']}")

    with open(NB_PATH, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
    print(f"\nNotebook patched: {NB_PATH}")


if __name__ == "__main__":
    main()
