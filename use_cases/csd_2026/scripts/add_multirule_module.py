"""Add the csd_multi_rule module to definitions/csd_2026_pipeline_definition.xlsx.

The original rule classifier is single-label: one code per ticket, and its prompt
asks the model to rule alternatives OUT. That design cannot answer "how often is a
ticket failed by more than one rule", so this module asks the question directly and
independently - it lists every rule that applies rather than choosing the best one.

Field names are all mr_* because run_pipeline merges module outputs by column name
with no collision check, so a repeated name would silently clobber the other module.

Idempotent: re-running replaces the module's rows rather than duplicating them.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
XLSX = BASE / "definitions" / "csd_2026_pipeline_definition.xlsx"
MODULE = "csd_multi_rule"

DESCRIPTION = (
    "List EVERY Scopus content validation rule that this rejected support request "
    "violates. There are 24 numbered rules from the CSD triangulation matrix, plus "
    "CSDVR4.1 for 'no rule applies'. This is deliberately a MULTI-LABEL task: a "
    "ticket may violate one rule or several, and which is more common is not known "
    "in advance - establishing that is the whole point of this pass, so do not "
    "assume either way. Judge each rule "
    "independently on its own condition, as a separate yes/no decision. The question "
    "is which rules APPLY, not which applies best, so never drop a rule merely "
    "because another one fits the ticket better. A rule applies "
    "only when the transcript contains explicit evidence for its condition; a "
    "standing disclaimer, a generic timeline sentence, or a possibility raised and "
    "then dismissed is not evidence. If no rule applies, return CSDVR4.1 alone."
)

MODULE_ROW = {
    "module_name": MODULE,
    "taxonomy_prefix": "CSDVR",
    "taxonomy_file": "csd_validation_rule.json",
    "reorder_group": "E",
    "reorder_order": 5,
    "enabled": True,
    "discovery_mode": None,
    "extract_prompt": None,
    "description": DESCRIPTION,
    "notes": "Multi-label re-read of the same taxonomy as csd_validation_rule. "
             "Measures how often a ticket is failed by more than one rule.",
}

FIELD_ROWS = [
    {
        "field_name": "mr_codes",
        "field_type": "list",
        "description": "Every validation rule leaf code that applies",
        "prompt_instruction": (
            "REQUIRED. Return a JSON list of every validation rule leaf code that applies "
            "to this ticket, for example [\"CSDVR1.5\"] or [\"CSDVR1.5\", \"CSDVR1.7\"]. "
            "Use leaf codes exactly as they appear in the taxonomy. Work through the rules and "
            "include every one whose own condition is explicitly evidenced in the transcript, "
            "and only those. Do not add a rule that lacks its own evidence, and do not leave "
            "out a rule that has it. If nothing applies, return "
            "[\"CSDVR4.1\"] on its own and never combine CSDVR4.1 with another code."
        ),
        "in_output": True,
        "explode_list": True,
        "validate_enum": None,
        "notes": None,
        "explode_keys": None,
    },
    {
        "field_name": "mr_primary",
        "field_type": "code",
        "description": "The single strongest rule among those listed",
        "prompt_instruction": (
            "Of the rules you listed in mr_codes, give the single leaf code that fits best. "
            "It must be one of the codes you listed. This is used to check this pass against "
            "the original single-label run, so answer it independently of what any earlier "
            "classification might have said."
        ),
        "in_output": True,
        "explode_list": None,
        "validate_enum": None,
        "notes": None,
        "explode_keys": None,
    },
    {
        "field_name": "mr_secondary_evidence",
        "field_type": "str",
        "description": "Verbatim quote supporting the SECOND rule, when there is one",
        "prompt_instruction": (
            "If mr_codes contains more than one rule, quote verbatim from the transcript the "
            "sentence that satisfies the SECOND rule - not the first. This is the evidence "
            "that the ticket really does break more than one rule, so it must be a direct "
            "quote and must be about a different condition from the primary rule. If only "
            "one rule applies, return an empty string."
        ),
        "in_output": True,
        "explode_list": None,
        "validate_enum": None,
        "notes": None,
        "explode_keys": None,
    },
    {
        "field_name": "mr_justification",
        "field_type": "str",
        "description": "Why each listed rule applies",
        "prompt_instruction": (
            "In at most 40 words, say why each listed rule applies. Where you listed only one "
            "rule, say briefly which rule was the closest runner-up and what evidence it "
            "lacked."
        ),
        "in_output": True,
        "explode_list": None,
        "validate_enum": None,
        "notes": None,
        "explode_keys": None,
    },
]

sheets = pd.read_excel(XLSX, sheet_name=None)
mods, flds = sheets["modules"], sheets["fields"]

before = (len(mods), len(flds))
mods = mods[mods["module_name"] != MODULE].copy()
flds = flds[flds["module_name"] != MODULE].copy()

mods = pd.concat([mods, pd.DataFrame([MODULE_ROW])[mods.columns]], ignore_index=True)
new_fields = pd.DataFrame([{**{"module_name": MODULE}, **f} for f in FIELD_ROWS])
flds = pd.concat([flds, new_fields[flds.columns]], ignore_index=True)

# A repeated field name across modules is merged by column name with no collision
# check, so the second module silently overwrites the first.
dupes = flds[flds.duplicated("field_name", keep=False)]
assert dupes.empty, f"field name collision across modules:\n{dupes[['module_name', 'field_name']]}"

sheets["modules"], sheets["fields"] = mods, flds
with pd.ExcelWriter(XLSX, engine="openpyxl") as xl:
    for name, df in sheets.items():
        df.to_excel(xl, sheet_name=name, index=False)

print(f"modules {before[0]} -> {len(mods)}   fields {before[1]} -> {len(flds)}")
print("modules now:", list(mods["module_name"]))
