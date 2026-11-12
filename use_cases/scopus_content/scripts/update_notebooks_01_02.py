"""
Insert policy harmonisation documentation cell into notebooks 01 and 02,
and add "policy_compliance" to the MODULES list in notebook 02.
"""
import json
from pathlib import Path

ROOT = Path(r"C:\Users\simionv\custom_taxonomy_v1")

DOC_CELL_LINES = [
    "### Policy taxonomy harmonisation — CAR Manual v3.37 + Content Coverage Guide (June 2026)\n",
    "\n",
    "**New policy codes added:**\n",
    "\n",
    "| Code | Label | Source |\n",
    "|---|---|---|\n",
    "| PA10 | Article-in-Press (AiP) eligibility and processing | CAR Manual §5 |\n",
    "| PA11 | Excluded item types (full CAR §1 exclusion list) | CAR Manual §1 |\n",
    "| PU2.x | Customer root cause | Merged from policy_understanding into policy_compliance |\n",
    "| CR1.8 | AiP visibility or missing (contact reason) | CAR Manual §5 |\n",
    "\n",
    "**Modules changed:**\n",
    "\n",
    "- `policy_compliance`: expanded with PA10/PA11 + customer understanding fields "
    "(`customer_understanding_issue`, `customer_root_cause_code`)\n",
    "- `policy_understanding`: disabled (fields merged into policy_compliance)\n",
    "\n",
    "After updating the Excel, run Section 2 (force-rebuild) to regenerate "
    "`policy_compliance.json` and `policy_compliance.py`.  \n",
    "Use `build_pipeline.py build --force policy_compliance` to regenerate only the "
    "compliance module.\n",
]

DOC_CELL = {
    "cell_type": "markdown",
    "metadata": {},
    "source": DOC_CELL_LINES,
}

# ── 01_build_and_discover.ipynb ─────────────────────────────────────────────
nb01_path = ROOT / "notebooks" / "01_build_and_discover.ipynb"
with open(nb01_path, encoding="utf-8") as f:
    nb01 = json.load(f)

# Insert doc cell after index 6 ("## 2 · Run build_pipeline.py")
assert nb01["cells"][6]["cell_type"] == "markdown"
assert "Run" in "".join(nb01["cells"][6]["source"]) or "build_pipeline" in "".join(nb01["cells"][6]["source"])

nb01["cells"].insert(7, DOC_CELL)
print(f"01: inserted doc cell at index 7 (after '## 2 · Run build_pipeline.py')")
print(f"    new total cells: {len(nb01['cells'])}")

with open(nb01_path, "w", encoding="utf-8") as f:
    json.dump(nb01, f, ensure_ascii=False, indent=1)
print(f"    saved: {nb01_path}")

# ── 02_classification.ipynb ──────────────────────────────────────────────────
nb02_path = ROOT / "notebooks" / "02_classification.ipynb"
with open(nb02_path, encoding="utf-8") as f:
    nb02 = json.load(f)

# 1. Insert doc cell after index 0 (the intro markdown)
assert nb02["cells"][0]["cell_type"] == "markdown"
nb02["cells"].insert(1, DOC_CELL)
print(f"\n02: inserted doc cell at index 1 (after intro)")
print(f"    new total cells: {len(nb02['cells'])}")

# 2. Update MODULES in what is now index 6 (was index 5 before insertion)
cell5 = nb02["cells"][6]
assert cell5["cell_type"] == "code", f"Expected code cell, got {cell5['cell_type']}"
new_source = []
changed = False
for line in cell5["source"]:
    if 'MODULES = ["customer_effort"]' in line:
        line = line.replace(
            'MODULES = ["customer_effort"]',
            'MODULES = ["customer_effort", "policy_compliance"]'
        )
        changed = True
    new_source.append(line)
if not changed:
    raise ValueError("MODULES line not found in cell 6 of notebook 02 — check cell index")
cell5["source"] = new_source
print('    updated MODULES: ["customer_effort"] -> ["customer_effort", "policy_compliance"]')

with open(nb02_path, "w", encoding="utf-8") as f:
    json.dump(nb02, f, ensure_ascii=False, indent=1)
print(f"    saved: {nb02_path}")

print("\nDone.")
