"""
taxonomy_diff.py — Taxonomy Version Comparator
===============================================
Compare two taxonomy JSON files and show what was added, removed, or relabelled.
Useful when iterating on a taxonomy between build runs to spot unintended changes.

USAGE:
  python scripts/taxonomy_diff.py <old.json> <new.json>
  python scripts/taxonomy_diff.py generated/taxonomies/contact_reason.json \\
      generated/taxonomies/product_specific/taxonomies_scopus_content/contact_reason.json
  python scripts/taxonomy_diff.py old.json new.json --output diff_report.xlsx
  python scripts/taxonomy_diff.py old.json new.json --codes-only
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import NamedTuple


class TaxNode(NamedTuple):
    code: str
    label: str
    description: str
    parent: str  # empty for L1


def _flatten(tax: dict) -> dict[str, TaxNode]:
    """Flatten a 2-level taxonomy dict into {code: TaxNode}."""
    nodes: dict[str, TaxNode] = {}
    for l1_code, l1_node in tax.items():
        if not isinstance(l1_node, dict):
            continue
        nodes[l1_code] = TaxNode(
            code=l1_code,
            label=l1_node.get("label", ""),
            description=l1_node.get("description", ""),
            parent="",
        )
        for l2_code, l2_node in l1_node.get("children", {}).items():
            if not isinstance(l2_node, dict):
                continue
            nodes[l2_code] = TaxNode(
                code=l2_code,
                label=l2_node.get("label", ""),
                description=l2_node.get("description", ""),
                parent=l1_code,
            )
    return nodes


def diff_taxonomies(old: dict, new: dict) -> dict:
    old_flat = _flatten(old)
    new_flat = _flatten(new)

    old_codes = set(old_flat)
    new_codes = set(new_flat)

    added   = sorted(new_codes - old_codes)
    removed = sorted(old_codes - new_codes)
    shared  = old_codes & new_codes

    relabelled   = []
    redescribed  = []
    reparented   = []

    for code in sorted(shared):
        o, n = old_flat[code], new_flat[code]
        if o.label != n.label:
            relabelled.append((code, o.label, n.label))
        if o.description != n.description:
            redescribed.append((code, o.description, n.description))
        if o.parent != n.parent:
            reparented.append((code, o.parent, n.parent))

    return {
        "added":        [(c, new_flat[c]) for c in added],
        "removed":      [(c, old_flat[c]) for c in removed],
        "relabelled":   relabelled,
        "redescribed":  redescribed,
        "reparented":   reparented,
        "unchanged":    len(shared) - len(relabelled) - len(redescribed) - len(reparented),
        "old_total":    len(old_flat),
        "new_total":    len(new_flat),
    }


def print_diff(diff: dict, old_path: str, new_path: str, codes_only: bool = False) -> None:
    sep = "=" * 72
    print(f"\n{sep}")
    print(f"  TAXONOMY DIFF")
    print(f"  OLD: {old_path}  ({diff['old_total']} codes)")
    print(f"  NEW: {new_path}  ({diff['new_total']} codes)")
    print(sep)

    delta = diff["new_total"] - diff["old_total"]
    delta_str = f"+{delta}" if delta >= 0 else str(delta)
    print(f"\n  Summary:  {delta_str} codes  |  "
          f"+{len(diff['added'])} added  "
          f"-{len(diff['removed'])} removed  "
          f"~{len(diff['relabelled'])} relabelled  "
          f"{diff['unchanged']} unchanged")

    if diff["added"]:
        print(f"\n  ADDED ({len(diff['added'])})")
        print("  " + "─" * 60)
        for code, node in diff["added"]:
            if codes_only:
                print(f"    + {code}")
            else:
                parent_str = f"  [under {node.parent}]" if node.parent else "  [L1]"
                print(f"    + {code:<12}  {node.label}{parent_str}")
                if node.description:
                    print(f"      {'':12}  {node.description[:70]}")

    if diff["removed"]:
        print(f"\n  REMOVED ({len(diff['removed'])})")
        print("  " + "─" * 60)
        for code, node in diff["removed"]:
            if codes_only:
                print(f"    - {code}")
            else:
                print(f"    - {code:<12}  {node.label}")

    if diff["relabelled"]:
        print(f"\n  RELABELLED ({len(diff['relabelled'])})")
        print("  " + "─" * 60)
        for code, old_label, new_label in diff["relabelled"]:
            print(f"    ~ {code:<12}  \"{old_label}\" → \"{new_label}\"")

    if diff["redescribed"] and not codes_only:
        print(f"\n  DESCRIPTION CHANGED ({len(diff['redescribed'])})")
        print("  " + "─" * 60)
        for code, old_desc, new_desc in diff["redescribed"]:
            old_short = (old_desc or "(none)")[:50]
            new_short = (new_desc or "(none)")[:50]
            print(f"    ~ {code:<12}  \"{old_short}\" → \"{new_short}\"")

    if diff["reparented"]:
        print(f"\n  REPARENTED ({len(diff['reparented'])})")
        print("  " + "─" * 60)
        for code, old_p, new_p in diff["reparented"]:
            print(f"    ~ {code:<12}  parent {old_p or '(root)'} → {new_p or '(root)'}")

    if not any([diff["added"], diff["removed"], diff["relabelled"], diff["redescribed"], diff["reparented"]]):
        print("\n  No differences found.")

    print(f"\n{sep}\n")


def save_excel(diff: dict, output_path: Path) -> None:
    try:
        import pandas as pd
    except ImportError:
        print("pandas not available — skipping Excel export")
        return

    sheets = {}

    if diff["added"]:
        sheets["Added"] = pd.DataFrame(
            [{"code": c, "label": n.label, "parent": n.parent, "description": n.description}
             for c, n in diff["added"]]
        )
    if diff["removed"]:
        sheets["Removed"] = pd.DataFrame(
            [{"code": c, "label": n.label, "parent": n.parent, "description": n.description}
             for c, n in diff["removed"]]
        )
    if diff["relabelled"]:
        sheets["Relabelled"] = pd.DataFrame(
            [{"code": c, "old_label": o, "new_label": n} for c, o, n in diff["relabelled"]]
        )
    if diff["redescribed"]:
        sheets["Redescribed"] = pd.DataFrame(
            [{"code": c, "old_description": o, "new_description": n}
             for c, o, n in diff["redescribed"]]
        )

    if not sheets:
        print("No differences to write.")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    print(f"  Saved: {output_path}")


def main() -> None:
    p = argparse.ArgumentParser(
        description="Compare two taxonomy JSON files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/taxonomy_diff.py old/contact_reason.json generated/taxonomies/contact_reason.json
  python scripts/taxonomy_diff.py v1.json v2.json --codes-only
  python scripts/taxonomy_diff.py v1.json v2.json --output diff.xlsx
        """,
    )
    p.add_argument("old", help="Old taxonomy JSON file")
    p.add_argument("new", help="New taxonomy JSON file")
    p.add_argument("--codes-only", action="store_true", help="Show code changes only, no labels/descriptions")
    p.add_argument("--output", default=None, help="Save diff to Excel file")
    args = p.parse_args()

    old_path = Path(args.old)
    new_path = Path(args.new)

    for path in (old_path, new_path):
        if not path.exists():
            p.error(f"File not found: {path}")

    old_tax = json.loads(old_path.read_text(encoding="utf-8"))
    new_tax = json.loads(new_path.read_text(encoding="utf-8"))

    diff = diff_taxonomies(old_tax, new_tax)
    print_diff(diff, str(old_path), str(new_path), codes_only=args.codes_only)

    if args.output:
        save_excel(diff, Path(args.output))


if __name__ == "__main__":
    main()
