"""
5-fold cross-validation evaluation for the LeapSpace gold set.

Uses the HIERARCHICAL taxonomy (L1=Contact Reason, L2=Root Cause).
For each fold k (k=1..5):
  - Use ~55 tickets as few-shot examples (written to a temporary feedback JSONL)
  - Run the pipeline on the held-out ~14 tickets
  - Collect predictions

Aggregating over 5 folds gives an unbiased accuracy estimate for both
Contact Reason (L1) and Root Cause (L2) as if all 69 tickets were used
as few-shot examples in production.

Usage (from project root):
    python scripts/run_kfold_eval.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import os
import sys
import time
import threading
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import StratifiedKFold

BASE = Path(os.environ.get("RCA_WORKSPACE", ".")).resolve()  # the use-case folder (run from use_cases/leapspace_legacy)

# ── Config ────────────────────────────────────────────────────────────────────
GOLD_SET_PATH   = BASE / "data/leapspace_gold_set.xlsx"
CODE_MAP_PATH   = BASE / "data/leapspace_code_map.json"
TAXONOMY_DIR    = BASE / "generated/taxonomies"
TMP_DIR         = BASE / "runs/tmp_kfold"
RESULTS_PATH    = BASE / "runs/output/kfold_eval_results.xlsx"

N_FOLDS           = 5
RANDOM_STATE      = 42
BATCH_SIZE        = 10
CONCURRENCY       = 4
FEEDBACK_STRATEGY = "smart"
FEEDBACK_MAX      = 5


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write_feedback_jsonl(fold_train: pd.DataFrame,
                          hierarchy: dict[str, dict[str, str]],
                          out_path: Path) -> None:
    """Write hierarchical feedback JSONL for a fold's training set."""
    entries = []
    for _, row in fold_train.iterrows():
        cr   = str(row["Contact Reason"]).strip()
        rc   = str(row["Root Cause"]).strip()
        code = hierarchy.get(cr, {}).get(rc)
        if not code:
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
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def _run_fold(fold_idx: int, test_df: pd.DataFrame,
              feedback_dir: Path) -> pd.DataFrame | None:
    """Run the pipeline on test_df and stream progress. Returns predictions."""
    fold_dir  = TMP_DIR / f"fold_{fold_idx}"
    fold_dir.mkdir(parents=True, exist_ok=True)
    in_csv    = fold_dir / "fold_in.csv"
    out_xlsx  = fold_dir / "fold_out.xlsx"

    test_df[["uid", "conversation"]].to_csv(in_csv, index=False)

    cmd = [
        sys.executable, "-m", "rca_pipeline.cli", "run",
        "--input",                str(in_csv),
        "--output",               str(out_xlsx),
        "--text-col",             "conversation",
        "--id-col",               "uid",
        "--modules",              "contact_reason",
        "--taxonomy-dir",         str(BASE / "data" / "leapspace_taxonomies"),
        "--feedback-dir",         str(feedback_dir),
        "--feedback-strategy",    FEEDBACK_STRATEGY,
        "--feedback-max-examples", str(FEEDBACK_MAX),
        "--batch-size",           str(BATCH_SIZE),
        "--concurrency",          str(CONCURRENCY),
    ]

    err_lines: list[str] = []

    proc = subprocess.Popen(
        cmd, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1,
    )

    def _cap_err(p):
        for line in iter(p.stderr.readline, ""):
            err_lines.append(line)

    t = threading.Thread(target=_cap_err, args=(proc,), daemon=True)
    t.start()
    for line in iter(proc.stdout.readline, ""):
        print(f"    {line}", end="", flush=True)
    proc.wait()
    t.join(timeout=5)

    if proc.returncode != 0 or not out_xlsx.exists():
        print(f"    [fold {fold_idx + 1}] pipeline failed (exit {proc.returncode})")
        if err_lines:
            print("".join(err_lines[-10:]))
        return None

    return pd.read_excel(out_xlsx)


def _extract_preds(pred_df: pd.DataFrame,
                   test_gold: pd.DataFrame) -> list[dict]:
    """Extract CR and RC predictions for each test ticket."""
    pred_df = pred_df.copy()
    pred_df["uid"] = pred_df["uid"].astype(str).str.strip()
    indexed = pred_df.set_index("uid")

    records = []
    for _, row in test_gold.iterrows():
        uid = str(row["Ticket Number"])
        if uid not in indexed.index:
            continue
        pred_row = indexed.loc[uid]

        # Contact Reason = L1 group label (auto-derived by pipeline)
        cr_pred = str(pred_row.get("contact_reason_class_l1_label", "")).strip()
        # Root Cause = L2 leaf label (auto-derived by pipeline)
        rc_pred = str(pred_row.get("contact_reason_primary_label", "")).strip()

        # Fallback: if label not derived, map from code
        if not cr_pred or cr_pred.lower() in ("nan", "none"):
            code = str(pred_row.get("contact_reason_primary_code", "")).strip()
            cr_pred = str(pred_row.get("contact_reason_class_l1", "")).strip()
        if not rc_pred or rc_pred.lower() in ("nan", "none"):
            rc_pred = ""

        records.append({
            "uid":     uid,
            "gold_cr": str(row["Contact Reason"]).strip(),
            "gold_rc": str(row["Root Cause"]).strip(),
            "pred_cr": cr_pred,
            "pred_rc": rc_pred,
        })
    return records


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    t0 = time.time()

    gold = pd.read_excel(GOLD_SET_PATH)
    with open(CODE_MAP_PATH, encoding="utf-8") as f:
        code_map = json.load(f)
    hierarchy: dict[str, dict[str, str]] = code_map["hierarchy"]

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Stratified split — collapse rare CR classes (< N_FOLDS instances)
    cr_counts = gold["Contact Reason"].value_counts()
    stratify  = gold["Contact Reason"].where(
        gold["Contact Reason"].map(cr_counts) >= N_FOLDS, "rare"
    )

    skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    all_records: list[dict] = []
    fold_cr_accs: list[float] = []
    fold_rc_accs: list[float] = []

    SEP = "=" * 68
    print(f"\n{SEP}")
    print(f"  5-FOLD CROSS-VALIDATION  ({len(gold)} gold tickets)")
    print(f"  Each fold: ~{len(gold) - len(gold)//N_FOLDS} few-shot  |  ~{len(gold)//N_FOLDS} held-out")
    print(f"  Columns: Contact Reason (L1) + Root Cause (L2) from single hierarchical module")
    print(SEP)

    for fold_idx, (train_idx, test_idx) in enumerate(skf.split(gold, stratify)):
        fold_train = gold.iloc[train_idx].copy()
        fold_test  = gold.iloc[test_idx].copy()

        print(f"\n  Fold {fold_idx + 1}/{N_FOLDS}  "
              f"({len(fold_train)} few-shot | {len(fold_test)} test)")
        print(f"  {'-' * 50}")

        # Write per-fold feedback JSONL
        fb_dir = TMP_DIR / f"feedback_{fold_idx}"
        fb_dir.mkdir(parents=True, exist_ok=True)
        _write_feedback_jsonl(fold_train, hierarchy,
                              fb_dir / "contact_reason_corrections.jsonl")

        # Prepare test CSV
        test_input = fold_test.rename(
            columns={"Ticket Number": "uid", "Conversation": "conversation"}
        )[["uid", "conversation"]].copy()
        test_input["uid"] = test_input["uid"].astype(str)

        t_fold  = time.time()
        pred_df = _run_fold(fold_idx, test_input, fb_dir)
        fold_s  = time.time() - t_fold

        if pred_df is None:
            print(f"  Fold {fold_idx + 1} failed — skipping")
            continue

        fold_rows = _extract_preds(pred_df, fold_test)
        all_records.extend(fold_rows)

        # Quick fold summary
        valid_cr = [r for r in fold_rows if r["pred_cr"]]
        valid_rc = [r for r in fold_rows if r["pred_rc"]]
        cr_acc = rc_acc = float("nan")
        if valid_cr:
            cr_acc = accuracy_score([r["gold_cr"] for r in valid_cr],
                                    [r["pred_cr"] for r in valid_cr]) * 100
            fold_cr_accs.append(cr_acc)
        if valid_rc:
            rc_acc = accuracy_score([r["gold_rc"] for r in valid_rc],
                                    [r["pred_rc"] for r in valid_rc]) * 100
            fold_rc_accs.append(rc_acc)
        cr_str = f"{cr_acc:.1f}%" if cr_acc == cr_acc else "n/a"
        rc_str = f"{rc_acc:.1f}%" if rc_acc == rc_acc else "n/a"
        print(f"  Fold {fold_idx + 1} done in {fold_s:.0f}s  |  "
              f"CR: {cr_str}  RC: {rc_str}  ({len(fold_rows)}/{len(fold_test)} matched)")

    # ── Aggregate results ─────────────────────────────────────────────────────
    df = pd.DataFrame(all_records)

    print(f"\n\n{SEP}")
    print(f"  AGGREGATE RESULTS  (n={len(df)} predictions across {N_FOLDS} folds)")
    print(SEP)

    for label, gold_col, pred_col in [
        ("Contact Reason (L1)", "gold_cr", "pred_cr"),
        ("Root Cause (L2)",     "gold_rc", "pred_rc"),
    ]:
        valid = df[df[pred_col].str.strip() != ""].copy()
        if valid.empty:
            print(f"\n  {label}: no predictions found")
            continue

        y_true = valid[gold_col]
        y_pred = valid[pred_col]
        acc    = accuracy_score(y_true, y_pred) * 100
        mf1    = f1_score(y_true, y_pred, average="macro",    zero_division=0)
        wf1    = f1_score(y_true, y_pred, average="weighted", zero_division=0)

        print(f"\n  {label}  ({len(y_true)} predictions)")
        print(f"  {'-' * 50}")
        print(f"  Accuracy:     {acc:.1f}%")
        print(f"  Macro F1:      {mf1:.2f}")
        print(f"  Weighted F1:   {wf1:.2f}")

        fold_accs = fold_cr_accs if label.startswith("Contact") else fold_rc_accs
        if fold_accs:
            fold_strs = "  ".join(f"F{i+1}:{a:.0f}%" for i, a in enumerate(fold_accs))
            print(f"  Per-fold:     {fold_strs}")

        print(f"\n  Per-class:")
        print(classification_report(y_true, y_pred, zero_division=0))

    elapsed = time.time() - t0
    print(f"{SEP}")
    print(f"  Total time: {elapsed/60:.1f} min")
    print(SEP)

    # ── Save ──────────────────────────────────────────────────────────────────
    df.to_excel(RESULTS_PATH, index=False)
    print(f"\n  Results saved to: {RESULTS_PATH.relative_to(BASE)}")

    # ── Cleanup ───────────────────────────────────────────────────────────────
    if TMP_DIR.exists():
        shutil.rmtree(TMP_DIR)


if __name__ == "__main__":
    main()
