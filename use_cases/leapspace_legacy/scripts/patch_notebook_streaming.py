"""Patch notebook cells 2, 13, 20 to use live streaming subprocess calls."""
from __future__ import annotations
import json
from pathlib import Path

NB_PATH = Path("notebooks/04_leapspace_classify_with_gold_set.ipynb")

# ── Cell 2: add EVAL_GOLD_TEST path ──────────────────────────────────────────
CELL2 = (
    "import os\n"
    r'os.chdir(r"c:\Users\simionv\custom_taxonomy_v1")' "\n"
    "\n"
    "from pathlib import Path\n"
    "BASE = Path().resolve()\n"
    "\n"
    "\n"
    "# ── Paths ────────────────────────────────────────────────────────────────────────────────\n"
    "PROJECT_DIR    = BASE\n"
    "GOLD_SET_PATH  = BASE / \"data/leapspace_gold_set.xlsx\"\n"
    "INPUT_CSV      = BASE / \"data/leapspace_collapsed.csv\"\n"
    "OUTPUT_PATH    = BASE / \"runs/output/leapspace_enriched.xlsx\"\n"
    "FEEDBACK_DIR   = BASE / \"feedback/leapspace\"\n"
    "EVAL_GOLD_TEST = BASE / \"data/leapspace_gold_test.csv\"  "
    "# held-out 20 tickets; shown in evaluation table after main run\n"
    "\n"
    "# ── Classification settings ──────────────────────────────────────────────────────\n"
    "TEXT_COL          = \"Conversation\"\n"
    "MODULES           = [\"contact_reason\", \"root_cause\"]\n"
    "FEEDBACK_STRATEGY = \"smart\"\n"
    "FEEDBACK_MAX      = 5\n"
    "BATCH_SIZE        = 10\n"
    "CONCURRENCY       = 4\n"
    "\n"
    "# ── Sanity check ───────────────────────────────────────────────────────────────────────\n"
    "assert GOLD_SET_PATH.exists(), f\"Gold set not found: {GOLD_SET_PATH}\"\n"
    "assert INPUT_CSV.exists(), f\"Input CSV not found: {INPUT_CSV}\"\n"
    "print(\"Paths OK\")\n"
)

# ── Cell 13: streaming main run + auto eval ───────────────────────────────────
CELL13 = (
    "import subprocess, sys, threading\n"
    "\n"
    "OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)\n"
    "\n"
    "cmd = [\n"
    "    sys.executable, str(PROJECT_DIR / \"run_pipeline.py\"),\n"
    "    \"--input\",                str(INPUT_CSV),\n"
    "    \"--output\",               str(OUTPUT_PATH),\n"
    "    \"--text-col\",             TEXT_COL,\n"
    "    \"--modules\",              *MODULES,\n"
    "    \"--feedback-dir\",         str(FEEDBACK_DIR),\n"
    "    \"--feedback-strategy\",    FEEDBACK_STRATEGY,\n"
    "    \"--feedback-max-examples\", str(FEEDBACK_MAX),\n"
    "    \"--batch-size\",           str(BATCH_SIZE),\n"
    "    \"--concurrency\",          str(CONCURRENCY),\n"
    "    \"--track-costs\",\n"
    "    \"--eval-gold-test\",       str(EVAL_GOLD_TEST),\n"
    "]\n"
    "\n"
    "print(\"Running:\", \" \".join(str(c) for c in cmd))\n"
    "print()\n"
    "\n"
    "# Stream stdout (progress + evaluation table) live in the cell.\n"
    "# Stderr (verbose log) is captured silently; shown only on failure.\n"
    "_err_lines: list[str] = []\n"
    "\n"
    "def _capture_err(proc):\n"
    "    for line in iter(proc.stderr.readline, \"\"):\n"
    "        _err_lines.append(line)\n"
    "\n"
    "proc = subprocess.Popen(\n"
    "    cmd, text=True, encoding=\"utf-8\", errors=\"replace\",\n"
    "    stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1,\n"
    ")\n"
    "_t = threading.Thread(target=_capture_err, args=(proc,), daemon=True)\n"
    "_t.start()\n"
    "for _line in iter(proc.stdout.readline, \"\"):\n"
    "    print(_line, end=\"\", flush=True)\n"
    "proc.wait()\n"
    "_t.join(timeout=5)\n"
    "\n"
    "if proc.returncode == 0:\n"
    "    print(f\"\\n✓ Pipeline complete. Output: {OUTPUT_PATH}\")\n"
    "else:\n"
    "    print(f\"\\n✗ Pipeline exited with code {proc.returncode}\")\n"
    "    if _err_lines:\n"
    "        print(\"\\n--- Pipeline errors (last 60 lines) ---\")\n"
    "        print(\"\".join(_err_lines[-60:]))\n"
)

# ── Cell 20: streaming eval run ───────────────────────────────────────────────
CELL20 = (
    "# Run pipeline on the held-out 20 tickets (standalone re-evaluation)\n"
    "gold_output = Path(\"runs/output/leapspace_gold_eval.xlsx\")\n"
    "gold_output.parent.mkdir(parents=True, exist_ok=True)\n"
    "\n"
    "cmd_eval = [\n"
    "    sys.executable, str(PROJECT_DIR / \"run_pipeline.py\"),\n"
    "    \"--input\",                str(gold_tmp),\n"
    "    \"--output\",               str(gold_output),\n"
    "    \"--text-col\",             \"conversation\",\n"
    "    \"--modules\",              *MODULES,\n"
    "    \"--feedback-dir\",         str(FEEDBACK_DIR),\n"
    "    \"--feedback-strategy\",    FEEDBACK_STRATEGY,\n"
    "    \"--feedback-max-examples\", str(FEEDBACK_MAX),\n"
    "    \"--batch-size\",           \"10\",\n"
    "    \"--concurrency\",          \"4\",\n"
    "]\n"
    "\n"
    "print(\"Running evaluation on held-out test set...\")\n"
    "_eval_err: list[str] = []\n"
    "\n"
    "def _cap_err(proc):\n"
    "    for line in iter(proc.stderr.readline, \"\"):\n"
    "        _eval_err.append(line)\n"
    "\n"
    "proc_eval = subprocess.Popen(\n"
    "    cmd_eval, text=True, encoding=\"utf-8\", errors=\"replace\",\n"
    "    stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1,\n"
    ")\n"
    "_et = threading.Thread(target=_cap_err, args=(proc_eval,), daemon=True)\n"
    "_et.start()\n"
    "for _line in iter(proc_eval.stdout.readline, \"\"):\n"
    "    print(_line, end=\"\", flush=True)\n"
    "proc_eval.wait()\n"
    "_et.join(timeout=5)\n"
    "print(f\"Done. Exit code: {proc_eval.returncode}\")\n"
    "if proc_eval.returncode != 0 and _eval_err:\n"
    "    print(\"\\n--- Errors ---\")\n"
    "    print(\"\".join(_eval_err[-30:]))\n"
)


def main() -> None:
    with open(NB_PATH, encoding="utf-8") as f:
        nb = json.load(f)

    cells = nb["cells"]
    cells[2]["source"]  = CELL2;  cells[2]["outputs"]  = []; cells[2]["execution_count"]  = None
    cells[13]["source"] = CELL13; cells[13]["outputs"] = []; cells[13]["execution_count"] = None
    cells[20]["source"] = CELL20; cells[20]["outputs"] = []; cells[20]["execution_count"] = None

    with open(NB_PATH, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
    print("Notebook patched: cells 2, 13, 20")


if __name__ == "__main__":
    main()
