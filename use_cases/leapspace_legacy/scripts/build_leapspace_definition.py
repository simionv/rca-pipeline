"""
Build definitions/leapspace_pipeline_definition.xlsx from the LeapSpace hierarchy.

The taxonomy is TWO-LEVEL and hierarchical:
  L1 = Contact Reason  (11 groups)
  L2 = Root Cause valid for that Contact Reason  (3-6 per group, 35 total)

This single `contact_reason` module replaces the old flat contact_reason +
root_cause modules.  The pipeline auto-derives:
  contact_reason_class_l1_label  → Contact Reason  (L1 group)
  contact_reason_primary_label   → Root Cause      (L2 leaf)

Usage (from project root):
    python scripts/build_leapspace_definition.py
    python build_pipeline.py --input definitions/leapspace_pipeline_definition.xlsx --force contact_reason

Writes:
    definitions/leapspace_pipeline_definition.xlsx
    data/leapspace_code_map.json   — hierarchy dict for FeedbackStore and eval
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

BASE     = Path(__file__).parent.parent
GOLD_SET = BASE / "data/leapspace_gold_set.xlsx"
OUT_DEFN = BASE / "definitions/leapspace_pipeline_definition.xlsx"
OUT_MAP  = BASE / "data/leapspace_code_map.json"

# ── Authoritative CR → RC hierarchy ──────────────────────────────────────────
# Root causes are ONLY valid under the contact reason they are listed under.
# Synced with the user's Excel edits (Other leaves) on 2026-06-04 and extended
# with the SME review categories on 2026-06-12.
CR_RC_HIERARCHY: dict[str, list[str]] = {
    "Billing": [
        "Invoice request",
        "Payment issues",
        "Payment method update",
        "Other",
    ],
    "General info about access": [
        "Using LeapSpace anonymously",
        "Other",
    ],
    "General info not access related": [
        "Continue using ScienceDirect AI",
        "Difference between LeapSpace and Scopus AI",
        "Questions about LeapSpace features",
        "Security info",
        "Other",
    ],
    "Institutional access issues": [
        "Elsevier ID+ SSO access denied error",
        "Entitlement provisioning error",
        "Guidance on individual subscription / free trial access",
        "LeapSpace trial had not been enabled",
        "Not enough info",
    ],
    "Institutional user cannot access": [
        "Access method unavailable",
        "Change-org feature error",
        "Entitlement provisioning error",
        "Incorrect organisation chosen",
        "Session data conflict",
        "User not entitled",
        "Not enough info",
        "Other",
    ],
    "Internal staff access": [
        "Change-org feature error",
        "Not enough info",
        "Other",
    ],
    "Not enough info": [
        "Not enough info",
    ],
    "Other not access related": [
        "Content format",
        "LeapSpace result inconsistency",
        "unable to access full-text articles",
        "Other",
    ],
    "Subscription cancellation and (or) refund": [
        "Billing was too early",
        "Cancellation and or refund service request",
        "Confusion with grace period",
        "Forgot to cancel",
        "Two accounts were billed",
        "Unable to locate the self-service cancellation option",
        "Other",
    ],
    "Subscription renewal": [
        "Billing",
        "Other",
    ],
    "Subscription request (incl. resub)": [
        "Subscription info request",
        "Subscription service request",
        "Other",
    ],
    "Trial inquiry": [
        "Customer blocked because of a lack of credit card",
        "Service request for trial",
        "Want to access trial without inputing credit card info",
        "Other",
    ],
    "Trial testing": [
        "Access methods flows clarification",
        "Other",
    ],
    "User not able to access": [
        "Entitlement provisioning error",
        "Not enough info",
        "Personal account being recognized as institutional",
        "Session data conflict",
        "User not entitled",
        "Other",
    ],
}


def _first_explanation(gold: pd.DataFrame, cr: str, rc: str) -> str:
    """First non-empty Explanation for a given (CR, RC) pair."""
    mask = (gold["Contact Reason"].str.strip() == cr) & (gold["Root Cause"].str.strip() == rc)
    for val in gold.loc[mask, "Explanations"].dropna():
        s = str(val).strip()
        if s and s.lower() not in ("nan", "none", ""):
            return s
    return ""


def main() -> None:
    gold = pd.read_excel(GOLD_SET)
    print(f"Loaded {len(gold)} gold set rows")

    # ── Build code map: hierarchy[cr][rc] → L2 code ──────────────────────────
    # CR1 = first L1, CR1.1 = first L2 under CR1, etc.
    hierarchy_codes: dict[str, dict[str, str]] = {}
    for l1_idx, (cr_label, rc_labels) in enumerate(CR_RC_HIERARCHY.items(), start=1):
        l1_code = f"CR{l1_idx}"
        hierarchy_codes[cr_label] = {}
        for l2_idx, rc_label in enumerate(rc_labels, start=1):
            hierarchy_codes[cr_label][rc_label] = f"{l1_code}.{l2_idx}"

    n_l2 = sum(len(v) for v in hierarchy_codes.values())
    print(f"  Hierarchy: {len(CR_RC_HIERARCHY)} CR groups, {n_l2} CR->RC leaf codes")

    # Save code map for notebook use
    with open(OUT_MAP, "w", encoding="utf-8") as f:
        json.dump({"hierarchy": hierarchy_codes}, f, indent=2, ensure_ascii=False)
    print(f"  Code map written to {OUT_MAP.name}")

    # ── Validate gold set against hierarchy ───────────────────────────────────
    missing = []
    for _, row in gold.iterrows():
        cr = str(row["Contact Reason"]).strip()
        rc = str(row["Root Cause"]).strip()
        if cr not in hierarchy_codes or rc not in hierarchy_codes.get(cr, {}):
            missing.append((cr, rc))
    if missing:
        print(f"\n  WARNING: {len(missing)} gold tickets have CR→RC pairs not in hierarchy:")
        for cr, rc in missing[:10]:
            print(f"    '{cr}' → '{rc}'")
    else:
        print("  All gold set CR->RC pairs are valid in the hierarchy.")

    # ── Modules sheet ─────────────────────────────────────────────────────────
    modules_df = pd.DataFrame([{
        "module_name":    "contact_reason",
        "taxonomy_prefix": "CR",
        "taxonomy_file":  "contact_reason.json",
        "reorder_group":  "A",
        "reorder_order":  1,
        "enabled":        True,
        "description": (
            "Hierarchical classification of the customer's contact reason AND root cause "
            "for LeapSpace support tickets. The L1 level is the Contact Reason category; "
            "the L2 level is the specific Root Cause valid within that category. "
            "Assign the single best-fitting LEAF code (e.g. CR4.2). "
            "Only root causes listed under the chosen contact reason are valid — "
            "the taxonomy enforces the valid combinations."
        ),
        "notes": "Hierarchical: L1=Contact Reason, L2=Root Cause",
    }])

    # ── Fields sheet ──────────────────────────────────────────────────────────
    fields_df = pd.DataFrame([
        {
            "module_name":       "contact_reason",
            "field_name":        "contact_reason_primary_code",
            "field_type":        "code",
            "description":       "Leaf code encoding both contact reason (L1) and root cause (L2)",
            "prompt_instruction": (
                "Assign the single leaf-level code (e.g. CR4.2) that best describes "
                "the contact reason AND root cause for this ticket. "
                "The L1 group is the Contact Reason; the L2 leaf is the Root Cause "
                "within that Contact Reason. Only use codes from the taxonomy."
            ),
            "in_output":    True,
            "explode_list": False,
            "validate_enum": True,
            "notes": "",
        },
        {
            "module_name":       "contact_reason",
            "field_name":        "contact_reason_primary_description",
            "field_type":        "str",
            "description":       "Brief justification for the chosen code",
            "prompt_instruction": (
                "In one sentence, describe in your own words why this contact reason and "
                "root cause apply to this ticket. Do not quote directly from the transcript "
                "and do not use apostrophes or quotation marks in your answer."
            ),
            "in_output":    True,
            "explode_list": False,
            "validate_enum": False,
            "notes": "",
        },
    ])

    # ── Taxonomy sheet ────────────────────────────────────────────────────────
    taxonomy_rows: list[dict] = []
    for cr_label, rc_labels in CR_RC_HIERARCHY.items():
        taxonomy_rows.append({
            "module_name": "contact_reason",
            "level":       "L1",
            "label":       cr_label,
            "description": f"Contact reason: {cr_label}",
            "notes":       "",
        })
        for rc_label in rc_labels:
            taxonomy_rows.append({
                "module_name": "contact_reason",
                "level":       "L2",
                "label":       rc_label,
                "description": _first_explanation(gold, cr_label, rc_label),
                "notes":       "",
            })
    taxonomy_df = pd.DataFrame(taxonomy_rows)

    # ── Write Excel ───────────────────────────────────────────────────────────
    OUT_DEFN.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(str(OUT_DEFN), engine="openpyxl") as writer:
        modules_df.to_excel(writer, sheet_name="modules",   index=False)
        fields_df.to_excel( writer, sheet_name="fields",    index=False)
        taxonomy_df.to_excel(writer, sheet_name="taxonomy", index=False)
    print(f"  Definition written to {OUT_DEFN.name}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\nHierarchy codes:")
    for cr, rc_map in hierarchy_codes.items():
        l1_code = next(iter(rc_map.values())).split(".")[0]
        print(f"  {l1_code}  {cr}")
        for rc, code in rc_map.items():
            print(f"    {code:8s}  {rc}")

    print(
        f"\nNext steps:\n"
        f"  python build_pipeline.py --input definitions/leapspace_pipeline_definition.xlsx"
        f" --force contact_reason --taxonomy-dir data/leapspace_taxonomies\n"
        f"  Then re-run the notebook from cell 5 onwards."
    )


if __name__ == "__main__":
    main()
