"""Patch notebook cells 5, 7, 13, 21 for the hierarchical CR->RC taxonomy."""
import json
from pathlib import Path

NB = Path("notebooks/04_leapspace_classify_with_gold_set.ipynb")
with open(NB, encoding="utf-8") as f:
    nb = json.load(f)

# ── Cell 5: load hierarchy code map + EVAL_MODE logic ────────────────────────
nb["cells"][5]["source"] = """\
# ── Load hierarchy code map and apply EVAL_MODE ──────────────────────────────
import json

CODE_MAP_PATH = BASE / "data/leapspace_code_map.json"
assert CODE_MAP_PATH.exists(), (
    "Code map not found. Run: python scripts/build_leapspace_definition.py"
)
with open(CODE_MAP_PATH, encoding="utf-8") as _f:
    _code_map = json.load(_f)
# hierarchy[cr_label][rc_label] -> leaf code  (e.g. "CR4.2")
hierarchy = _code_map["hierarchy"]
print(f"Code map: {sum(len(v) for v in hierarchy.values())} CR->RC leaf codes")
print()

if EVAL_MODE == "all":
    gold_train = gold.copy()
    print(f"Mode ALL: {len(gold_train)} tickets used as few-shot examples")
    print("  Post-run eval (cell 13) will be in-sample.")
    print("  For an honest estimate run k-fold (cell 23).")

elif EVAL_MODE == "split":
    from sklearn.model_selection import train_test_split
    _cr_counts = gold["Contact Reason"].value_counts()
    _stratify  = gold["Contact Reason"].where(
        gold["Contact Reason"].map(_cr_counts) >= 2, "other"
    )
    gold_train, gold_test = train_test_split(
        gold, test_size=20, random_state=42, stratify=_stratify
    )
    gold_test.to_csv(EVAL_GOLD_TEST, index=False)
    print(f"Mode SPLIT: {len(gold_train)} few-shot | {len(gold_test)} held-out")
    print(f"  Test set: {EVAL_GOLD_TEST.relative_to(BASE)}")

else:
    raise ValueError(f"Unknown EVAL_MODE: {EVAL_MODE!r}. Use 'all' or 'split'.")
"""

# ── Cell 7: single-module hierarchical JSONL write ────────────────────────────
nb["cells"][7]["source"] = """\
import json
from datetime import datetime, timezone

FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)

def write_feedback_jsonl(df, out_path):
    \"\"\"Write gold-set rows as FeedbackStore JSONL using hierarchical CR->RC codes.\"\"\"
    entries, skipped = [], 0
    for _, row in df.iterrows():
        cr   = str(row["Contact Reason"]).strip()
        rc   = str(row["Root Cause"]).strip()
        code = hierarchy.get(cr, {}).get(rc)
        if not code:
            skipped += 1
            continue
        entries.append({
            "uid":       str(row["Ticket Number"]),
            "text":      str(row["Conversation"])[:1500],
            "original":  {"contact_reason_primary_code": code},
            "corrected": {"contact_reason_primary_code": code},
            "reason":    str(row.get("Explanations", "")).strip(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "module":    "contact_reason",
        })
    with open(out_path, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\\n")
    print(f"  {out_path.name}: {len(entries)} entries ({skipped} skipped)")
    return entries

cr_entries = write_feedback_jsonl(
    gold_train,
    FEEDBACK_DIR / "contact_reason_corrections.jsonl",
)

# Remove stale root_cause JSONL if it exists from the old two-module setup
_old_rc = FEEDBACK_DIR / "root_cause_corrections.jsonl"
if _old_rc.exists():
    _old_rc.unlink()
    print(f"  Removed stale: {_old_rc.name}")

print("\\nFeedback JSONL ready.")
"""

# ── Cell 13: single module, conditional eval ──────────────────────────────────
nb["cells"][13]["source"] = """\
import subprocess, sys, threading

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

cmd = [
    sys.executable, str(PROJECT_DIR / "run_pipeline.py"),
    "--input",                str(INPUT_CSV),
    "--output",               str(OUTPUT_PATH),
    "--text-col",             TEXT_COL,
    "--modules",              "contact_reason",
    "--feedback-dir",         str(FEEDBACK_DIR),
    "--feedback-strategy",    FEEDBACK_STRATEGY,
    "--feedback-max-examples", str(FEEDBACK_MAX),
    "--batch-size",           str(BATCH_SIZE),
    "--concurrency",          str(CONCURRENCY),
    "--track-costs",
]

if EVAL_MODE == "split" and EVAL_GOLD_TEST.exists():
    cmd += ["--eval-gold-test", str(EVAL_GOLD_TEST)]
elif EVAL_MODE == "all":
    print("Mode ALL: skipping post-run eval. Run k-fold (cell 23) for honest numbers.")
    print()

print("Running:", " ".join(str(c) for c in cmd))
print()

_err_lines: list[str] = []

def _capture_err(proc):
    for line in iter(proc.stderr.readline, ""):
        _err_lines.append(line)

proc = subprocess.Popen(
    cmd, text=True, encoding="utf-8", errors="replace",
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1,
)
_t = threading.Thread(target=_capture_err, args=(proc,), daemon=True)
_t.start()
for _line in iter(proc.stdout.readline, ""):
    print(_line, end="", flush=True)
proc.wait()
_t.join(timeout=5)

if proc.returncode == 0:
    print(f"\\n-> Pipeline complete. Output: {OUTPUT_PATH}")
else:
    print(f"\\n-> Pipeline exited with code {proc.returncode}")
    if _err_lines:
        print("\\n--- Errors (last 60 lines) ---")
        print("".join(_err_lines[-60:]))
"""

# ── Cell 21: updated column names for hierarchical output ────────────────────
nb["cells"][21]["source"] = """\
from sklearn.metrics import classification_report

pred    = pd.read_excel(gold_output)
eval_df = gold_eval.merge(pred, on="uid", how="inner")
print(f"Matched {len(eval_df)} / {len(gold_eval)} held-out tickets\\n")

# Hierarchical module: CR = L1 group label, RC = L2 leaf label
cr_pred_col = "contact_reason_class_l1_label"  # Contact Reason
rc_pred_col = "contact_reason_primary_label"    # Root Cause

if cr_pred_col in eval_df.columns:
    print("-- Contact Reason accuracy --")
    print(classification_report(
        eval_df["gold_contact_reason"], eval_df[cr_pred_col], zero_division=0
    ))

if rc_pred_col in eval_df.columns:
    print("-- Root Cause accuracy --")
    print(classification_report(
        eval_df["gold_root_cause"], eval_df[rc_pred_col], zero_division=0
    ))
"""

for idx in [5, 7, 13, 21]:
    nb["cells"][idx]["outputs"] = []
    nb["cells"][idx]["execution_count"] = None

with open(NB, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
print("Patched cells 5, 7, 13, 21")
