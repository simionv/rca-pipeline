"""
build_policy_rules_notebook.py
Builds runs/output/Scopus effort/Scopus_Policy_Rules_Full_Run.ipynb — an executable
runbook for activating PA12-18 and running the new policy_rules module on the full
8,307-ticket Scopus corpus. Mirrors the CLI's live progress reporting by shelling
out to the exact same run_pipeline.py/build_pipeline.py commands via `!`.

Re-run after editing this script to regenerate the notebook:
  uv run python scripts/build_policy_rules_notebook.py
"""
from __future__ import annotations

import json
from pathlib import Path

OUT_PATH = Path(r"runs/output/Scopus effort/Scopus_Policy_Rules_Full_Run.ipynb")

KERNELSPEC = {
    "kernelspec": {
        "display_name": "custom-taxonomy-v1 (3.11.4.final.0)",
        "language": "python",
        "name": "python3",
    },
    "language_info": {
        "codemirror_mode": {"name": "ipython", "version": 3},
        "file_extension": ".py",
        "mimetype": "text/x-python",
        "name": "python",
        "nbconvert_exporter": "python",
        "pygments_lexer": "ipython3",
        "version": "3.11.4",
    },
}


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)}


def code(text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": text.splitlines(keepends=True),
    }


cells = []

# ---------------------------------------------------------------------------
cells.append(md("""\
# Scopus Policy Rules — Full Corpus Run

Executable runbook for:
1. Activating **PA12-PA18** in the existing `policy_compliance` module (currently live data only has PA0-PA11)
2. Running the new **`policy_rules`** module (49 curated atomic rules across all 18 areas) on the full ~8,307-ticket corpus
3. Wiring both into the R analysis layer

Full background/design notes: `C:\\Users\\simionv\\.claude\\plans\\how-can-i-implement-linear-cocke.md`. \
Rule content and citations: `POLICY_RULE_SOURCES.md` (this folder).

**Cost warning:** Steps 2 and 6 spend real money on LLM calls (~$75-95 and ~$135-145 respectively, \
~$210-240 combined). Steps 1 and 5-prep are cheap sanity checks (a few cents). **Do not "Run All" blindly** \
— run cells in order and read each markdown block first, especially before Step 2 and Step 6.

Each `!uv run python -u run_pipeline.py ...` cell streams the *exact same* live progress reporting you'd see \
in a terminal (the `[HH:MM:SS] N/M rec ... rec/s ... ETA ...` lines and the final \
`Module   Prev   Done/Todo   Total   Recs   Err   Status` summary table) — this notebook doesn't reimplement \
that reporting, it just runs the real CLI and lets its own output stream into the cell.
"""))

# ---------------------------------------------------------------------------
cells.append(md("## Setup — run this first"))
cells.append(code("""\
import os, json, shutil, glob
import pandas as pd

os.chdir(r"C:\\Users\\simionv\\custom_taxonomy_v1")

# Unbuffered + UTF-8 output so the live progress lines (and box-drawing/warning
# characters in run_pipeline.py's log formatting) stream and render correctly —
# without this, Windows defaults to cp1252 and long-running cells can appear to
# "hang" until the process buffer flushes.
os.environ["PYTHONUNBUFFERED"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

print("Working directory:", os.getcwd())
"""))

cells.append(md("""\
### Status dashboard (safe to re-run anytime)
Quick read of where things stand: build staleness, taxonomy sizes, whether the full-run output files already \
exist yet, and the most recent cost report. Doesn't run anything expensive — re-run this cell any time you \
come back to this notebook to re-orient.
"""))
cells.append(code("""\
def status_dashboard():
    print("=== Taxonomy sizes (generated/taxonomies) ===")
    for mod in ("policy_compliance", "policy_rules"):
        p = Path(f"generated/taxonomies/{mod}.json")
        if p.exists():
            tax = json.loads(p.read_text(encoding="utf-8"))
            n_l1 = len(tax)
            n_l2 = sum(len(v.get("children", {})) for v in tax.values())
            print(f"  {mod}: {n_l1} L1 groups, {n_l2} leaf codes")
        else:
            print(f"  {mod}: NOT BUILT YET")

    print()
    print("=== Full-run output files ===")
    for label, path in [
        ("policy_compliance (PA0-18, raw pipeline output)", "runs/output/Scopus_Content_Collapsed_compliance_enriched.xlsx"),
        ("policy_compliance (promoted, read by R script)",   "runs/output/Scopus_Content_Policy_enriched.xlsx"),
        ("policy_rules (new)",                                "runs/output/Scopus_Content_PolicyRules_enriched.xlsx"),
    ]:
        p = Path(path)
        if p.exists():
            mtime = pd.Timestamp(p.stat().st_mtime, unit="s")
            print(f"  [{'x' if p.exists() else ' '}] {label}\\n      {path}  (modified {mtime})")
        else:
            print(f"  [ ] {label} — not created yet\\n      {path}")

    print()
    print("=== Most recent cost report ===")
    reports = sorted(glob.glob("runs/cost_reports/costs_*.json"))
    if reports:
        latest = json.loads(Path(reports[-1]).read_text(encoding="utf-8"))
        print(f"  {reports[-1]}")
        print(f"  Total: ${latest.get('total_cost', 0):.2f}  |  Records: {latest.get('total_records', '?')}")
    else:
        print("  none yet")

from pathlib import Path
status_dashboard()
"""))

# ---------------------------------------------------------------------------
cells.append(md("""\
## Step 0 — Confirm nothing is stale
Read-only, ~5 seconds. Expect `policy_compliance.py is up to date` and `policy_rules.py is up to date`. \
(`contact_reason`/`customer_effort` showing STALE is pre-existing and unrelated to this work — leave them alone.)
"""))
cells.append(code("""\
!uv run python -u build_pipeline.py build --input definitions/scopus_content_pipeline_definition_v2.xlsx --dry-run
"""))

# ---------------------------------------------------------------------------
cells.append(md("""\
## Step 1 — Smoke-test the PA12-18 rebuild on a small sample
~$0.02, ~1 minute. `policy_compliance` is an existing, already-proven module — only its taxonomy grew (PA0-11 \
→ PA0-18) — so this is a lighter check than the full validation done for `policy_rules`, not an iterative one.

Builds a 17-row sample: 5 tickets keyword-targeted at the newest areas (ORCID → PA13, affiliation → PA14, \
patent → PA12, open access → PA15, erratum → PA16) plus 12 random tickets.
"""))
cells.append(code("""\
df = pd.read_excel("data/Scopus_Content_Collapsed.xlsx")

keywords = ["ORCID", "affiliation", "patent", "open access|unpaywall|gold|bronze", "erratum|retract"]
picked = set()
targeted = []
for pat in keywords:
    m = df["Conversation"].str.contains(pat, case=False, regex=True, na=False)
    cand = df[m].index.difference(picked)
    if len(cand) > 0:
        idx = cand[0]
        picked.add(idx)
        targeted.append(idx)

random_rows = df.index.difference(picked).to_series().sample(n=12, random_state=42).index.tolist()
sample = df.loc[list(targeted) + random_rows].reset_index(drop=True)
sample.to_excel("_pc_smoketest_sample.xlsx", index=False)
print(f"Sample: {len(sample)} rows ({len(targeted)} targeted + {len(random_rows)} random)")
"""))
cells.append(code("""\
# NOTE: modules is ["policy_compliance"] only — policy_understanding is disabled in the
# Excel (enabled=False) and its job (customer_understanding_issue / customer_root_cause_code)
# was already merged into policy_compliance itself. Including "policy_understanding" here
# fails with: Module 'policy_understanding' not registered.
scratch_profile = {
    "input":        "_pc_smoketest_sample.xlsx",
    "output":       "_pc_smoketest_enriched.xlsx",
    "text_col":     "Conversation",
    "id_col":       "Integration Id",
    "taxonomy_dir": "generated/taxonomies",
    "modules":      ["policy_compliance"],
    "batch_size":   3,
    "concurrency":  3,
    "retries":      4,
    "run_name":     "SCRATCH - PA12-18 smoketest",
}
Path("profiles/_scratch_pc_smoketest.json").write_text(json.dumps(scratch_profile, indent=2), encoding="utf-8")
print("Wrote profiles/_scratch_pc_smoketest.json")
"""))
cells.append(md("**Live run** — watch for the `Module ... Prev  Done/Todo  Total  Recs  Err  Status` summary at the end."))
cells.append(code("""\
!uv run python -u run_pipeline.py --profile profiles/_scratch_pc_smoketest.json
"""))
cells.append(md("**Spot-check:** look for at least one row showing `PA12`-`PA18` (not just `PA0`-`PA11`), with a label/description that matches the ticket's actual topic."))
cells.append(code("""\
out = pd.read_excel("_pc_smoketest_enriched.xlsx")
cols = ["Integration Id", "Conversation"] + [
    c for c in out.columns
    if c.startswith("applicable_policy") or c in ("agent_response_compliance", "violation_type_code")
]
pd.set_option("display.max_colwidth", 80)
out[cols]
"""))
cells.append(md("**Clean up the scratch files once you're satisfied with the spot-check:**"))
cells.append(code("""\
for f in [
    "_pc_smoketest_sample.xlsx", "_pc_smoketest_enriched.xlsx",
    "profiles/_scratch_pc_smoketest.json",
    "runs/checkpoints/_pc_smoketest_sample_checkpoint.jsonl",
    "runs/checkpoints/_pc_smoketest_sample_bad_uids.txt",
]:
    p = Path(f)
    if p.exists():
        p.unlink()
        print("removed", f)
"""))

# ---------------------------------------------------------------------------
cells.append(md("""\
## Step 2 — FULL CORPUS RUN: `policy_compliance` (activates PA0-18)

**⚠️ Spends real money — expect ~$75-95 for ~8,307 tickets.** Only run this after Step 1 looks good.

**Critical:** `runs/checkpoints/Scopus_Content_Collapsed_checkpoint.jsonl` already has all 8,308 records from \
the original June run marked "done" for `policy_compliance`/`policy_understanding`. The `--checkpoint`/`--bad-uids` \
overrides below point to fresh, uniquely-named files so this run actually reclassifies everyone under the \
PA0-18 taxonomy instead of silently skipping every ticket as already-done. **Do not drop these flags.**

If this cell is interrupted, just re-run it unchanged — it resumes from `policy_compliance_pa18_checkpoint.jsonl` \
rather than starting over and re-spending money on already-completed batches.
"""))
cells.append(code("""\
!uv run python -u run_pipeline.py --profile profiles/scopus_policy_compliance_interactions_profile.json --checkpoint runs/checkpoints/policy_compliance_pa18_checkpoint.jsonl --bad-uids runs/checkpoints/policy_compliance_pa18_bad_uids.txt
"""))

# ---------------------------------------------------------------------------
cells.append(md("""\
## Step 3 — Back up the old file, then promote the new one
Preserves the pre-PA12-18 baseline before overwriting the file `scopus_effort_master_v1.R` reads as `raw_pol_new`.
"""))
cells.append(code("""\
shutil.copy(
    "runs/output/Scopus_Content_Policy_enriched.xlsx",
    "runs/output/Scopus_Content_Policy_enriched_PA0-11_backup.xlsx",
)
shutil.copy(
    "runs/output/Scopus_Content_Collapsed_compliance_enriched.xlsx",
    "runs/output/Scopus_Content_Policy_enriched.xlsx",
)
print("Backed up old PA0-11 file and promoted the new PA0-18 output.")
"""))

# ---------------------------------------------------------------------------
cells.append(md("""\
## Step 4 — Verify PA12-18 actually resolved
Spot-check tickets that previously fell back to `PA0` ("no applicable policy") and mention ORCID, affiliation, \
patents, Open Access, or errata/corrections — confirm they now resolve to PA13 / PA14 / PA12 / PA15 / PA16 \
respectively instead of PA0.
"""))
cells.append(code("""\
full = pd.read_excel("runs/output/Scopus_Content_Policy_enriched.xlsx")

checks = {
    "ORCID (expect PA13)":        "ORCID",
    "affiliation (expect PA14)":  "affiliation",
    "patent (expect PA12)":       "patent",
    "open access (expect PA15)":  "open access|unpaywall",
    "erratum (expect PA16)":      "erratum|retract",
}
policy_cols = [c for c in full.columns if c.startswith("applicable_policy_codes_")]
for label, pat in checks.items():
    m = full["Conversation"].str.contains(pat, case=False, regex=True, na=False) if "Conversation" in full.columns else None
    if m is None or not m.any():
        print(f"{label}: no matching ticket found to check")
        continue
    row = full[m].iloc[0]
    codes = [row[c] for c in policy_cols if pd.notna(row[c]) and row[c]]
    print(f"{label}: uid={row.get('Integration Id', row.get('uid'))}  codes={codes}")
"""))

# ---------------------------------------------------------------------------
cells.append(md("""\
## Step 5 — Create the permanent `policy_rules` profile
Same `batch_size`/`max_tokens` as the validated sample run from Phase D — these were tuned specifically for \
`matched_rules`'s larger per-ticket output (list of `{code, verdict, evidence}` objects, not bare codes). \
Don't change them without re-validating on a sample first.
"""))
cells.append(code("""\
policy_rules_profile = {
    "input":        "data/Scopus_Content_Collapsed.xlsx",
    "output":       "runs/output/Scopus_Content_PolicyRules_enriched.xlsx",
    "text_col":     "Conversation",
    "id_col":       "Integration Id",
    "taxonomy_dir": "generated/taxonomies",
    "modules":      ["policy_rules"],
    "batch_size":   2,
    "concurrency":  3,
    "retries":      4,
    "max_tokens":   8000,
    "run_name":     "Scopus Policy Rules - Full Corpus",
    "track_costs":      True,
    "cost_report_dir":  "runs/cost_reports",
}
Path("profiles/scopus_policy_rules_profile.json").write_text(json.dumps(policy_rules_profile, indent=2), encoding="utf-8")
print("Wrote profiles/scopus_policy_rules_profile.json")
"""))

# ---------------------------------------------------------------------------
cells.append(md("""\
## Step 6 — FULL CORPUS RUN: `policy_rules`

**⚠️ Spends real money — expect ~$135-145 for ~8,307 tickets (measured directly from the validated sample at \
$0.0165/ticket), roughly 70-90 minutes at the sample's observed ~1.8 rec/s.**

Same resume behavior as Step 2 — re-running this cell unchanged after an interruption picks up from \
`policy_rules_checkpoint.jsonl`.
"""))
cells.append(code("""\
!uv run python -u run_pipeline.py --profile profiles/scopus_policy_rules_profile.json --checkpoint runs/checkpoints/policy_rules_checkpoint.jsonl --bad-uids runs/checkpoints/policy_rules_bad_uids.txt
"""))

# ---------------------------------------------------------------------------
cells.append(md("""\
## Step 7 — Verify the `policy_rules` full run

Checks, in order: row count, actual spend vs. estimate, and a fresh look for the "same quote reused across \
every rule in one area" over-inclusion pattern found during sample validation (was down to ~1/25 tickets \
after two rounds of prompt fixes — if it shows up much more often here, that's a signal to tighten the \
prompt again before trusting the aggregate numbers, rather than pushing forward).
"""))
cells.append(code("""\
rules_out = pd.read_excel("runs/output/Scopus_Content_PolicyRules_enriched.xlsx")
print(f"Row count: {len(rules_out)}  (expect 8,307)")
"""))
cells.append(code("""\
reports = sorted(glob.glob("runs/cost_reports/costs_*.json"))
latest = json.loads(Path(reports[-1]).read_text(encoding="utf-8"))
print(f"Cost report: {reports[-1]}")
print(json.dumps(latest, indent=2)[:2000])
"""))
cells.append(code("""\
code_cols = [c for c in rules_out.columns if c.startswith("matched_rules_code_")]
n_rules = rules_out[code_cols].notna().sum(axis=1) if code_cols else pd.Series([0] * len(rules_out))
print("Rules per ticket — mean: {:.2f}, max: {}".format(n_rules.mean(), n_rules.max()))
print(n_rules.value_counts().sort_index())

# Flag tickets where the SAME evidence quote is reused across 2+ matched rules —
# the specific anti-pattern found and mostly-fixed during sample validation.
evidence_cols = [c for c in rules_out.columns if c.startswith("matched_rules_evidence_") and not c.endswith("_grounded")]
suspect_uids = []
for _, row in rules_out.iterrows():
    quotes = [str(row[c]).strip() for c in evidence_cols if pd.notna(row[c]) and str(row[c]).strip()]
    if len(quotes) != len(set(quotes)):
        suspect_uids.append(row.get("Integration Id", row.get("uid")))
print(f"\\nTickets with a duplicated evidence quote across rules: {len(suspect_uids)} / {len(rules_out)}  ({100*len(suspect_uids)/len(rules_out):.1f}%)")
if suspect_uids[:10]:
    print("Sample uids to spot-check:", suspect_uids[:10])
"""))

# ---------------------------------------------------------------------------
cells.append(md("""\
## Step 8 — Wire both outputs into the R analysis layer (manual step)

This is a code change to `runs/output/Scopus effort/scopus_effort_master_v1.R` (not something to run from this \
notebook — it's a large, separate analysis script). Reference for the edit, to add around L178-211 where \
`raw_pol_new`/`raw_pol_old` are currently joined:

```r
raw_pol_rules <- read_excel("../Scopus_Content_PolicyRules_enriched.xlsx")

raw <- raw |>
  left_join(raw_pol_rules |> select(uid, matches("^matched_rules_")), by = "uid")

stopifnot(nrow(raw) == nrow(raw_eff))   # keep the existing 1:1 guard

# Roll rule-level tags up to area-level applicability/compliance, as a derived
# cross-check against policy_compliance's own applicable_policy_codes.
rules_long <- raw |>
  select(uid, matches("^matched_rules_(code|verdict|evidence)_\\\\d+$")) |>
  pivot_longer(
    cols = -uid,
    names_to = c(".value", "slot"),
    names_pattern = "matched_rules_(code|verdict|evidence)_(\\\\d+)"
  ) |>
  filter(!is.na(code), code != "") |>
  mutate(area_code = str_extract(code, "^PA\\\\d+"))

area_rollup <- rules_long |>
  group_by(uid, area_code) |>
  summarise(
    area_compliance = case_when(
      any(verdict == "non_compliant") ~ "non_compliant",
      any(verdict == "partial")       ~ "partial",
      TRUE                             ~ "compliant"
    ),
    n_rules_matched = n(),
    .groups = "drop"
  )
```

`dplyr`/`stringr`/`tidyr` are already imported in that script — no new library needed.
"""))

# ---------------------------------------------------------------------------
notebook = {
    "cells": cells,
    "metadata": KERNELSPEC,
    "nbformat": 4,
    "nbformat_minor": 5,
}

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
if OUT_PATH.exists():
    raise SystemExit(f"Refusing to overwrite existing file: {OUT_PATH}")
OUT_PATH.write_text(json.dumps(notebook, indent=1), encoding="utf-8")
print(f"Wrote {OUT_PATH} ({len(cells)} cells)")
