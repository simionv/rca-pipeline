"""
aggregate_costs.py — Cost Report Aggregator
============================================
Reads all cost_*.json files from runs/cost_reports/ and prints a summary
table of total spend, records processed, and per-module breakdown.

USAGE:
  python scripts/aggregate_costs.py
  python scripts/aggregate_costs.py --dir runs/cost_reports
  python scripts/aggregate_costs.py --dir runs/cost_reports --since 2025-05-01
  python scripts/aggregate_costs.py --output summary.xlsx
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def load_reports(report_dir: Path, since: datetime | None = None) -> list[dict]:
    reports = []
    for p in sorted(report_dir.glob("cost_*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if since:
                ts_str = data.get("timestamp") or data.get("run_id", "")
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if ts < since:
                        continue
                except (ValueError, AttributeError):
                    pass
            data["_file"] = p.name
            reports.append(data)
        except Exception as e:
            print(f"  Warning: could not read {p.name}: {e}")
    return reports


def aggregate(reports: list[dict]) -> dict:
    totals = {
        "runs": len(reports),
        "total_cost_usd": 0.0,
        "total_records": 0,
        "total_tokens": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "by_module": defaultdict(lambda: {
            "runs": 0, "cost_usd": 0.0, "records": 0, "tokens": 0
        }),
    }

    for r in reports:
        totals["total_cost_usd"]      += r.get("total_cost_usd", 0) or 0
        totals["total_records"]       += r.get("total_records", 0) or 0
        totals["total_tokens"]        += r.get("total_tokens", 0) or 0
        totals["prompt_tokens"]       += r.get("prompt_tokens", 0) or 0
        totals["completion_tokens"]   += r.get("completion_tokens", 0) or 0

        for mod_name, mod_data in (r.get("by_module") or {}).items():
            m = totals["by_module"][mod_name]
            m["runs"]     += 1
            m["cost_usd"] += mod_data.get("cost_usd", 0) or 0
            m["records"]  += mod_data.get("records", 0) or 0
            m["tokens"]   += mod_data.get("tokens", 0) or 0

    return totals


def print_summary(totals: dict, reports: list[dict]) -> None:
    sep = "=" * 72
    print(f"\n{sep}")
    print(f"  COST REPORT SUMMARY  ({totals['runs']} run{'s' if totals['runs'] != 1 else ''})")
    print(sep)
    print(f"  Total cost:          ${totals['total_cost_usd']:.4f} USD")
    print(f"  Total records:       {totals['total_records']:,}")
    print(f"  Total tokens:        {totals['total_tokens']:,}")
    if totals["total_records"] > 0:
        print(f"  Cost per record:     ${totals['total_cost_usd'] / totals['total_records']:.6f}")
    if totals["prompt_tokens"] or totals["completion_tokens"]:
        print(f"  Prompt tokens:       {totals['prompt_tokens']:,}")
        print(f"  Completion tokens:   {totals['completion_tokens']:,}")

    if totals["by_module"]:
        print(f"\n  {'Module':<26}  {'Runs':>4}  {'Cost USD':>10}  {'Records':>8}  {'Tokens':>10}")
        print("  " + "─" * 64)
        for mod, m in sorted(totals["by_module"].items()):
            print(f"  {mod:<26}  {m['runs']:4}  ${m['cost_usd']:9.4f}  {m['records']:8,}  {m['tokens']:10,}")

    if reports:
        dates = []
        for r in reports:
            ts_str = r.get("timestamp") or r.get("run_id", "")
            try:
                dates.append(datetime.fromisoformat(ts_str.replace("Z", "+00:00")))
            except (ValueError, AttributeError):
                pass
        if dates:
            print(f"\n  Date range:  {min(dates).strftime('%Y-%m-%d')} → {max(dates).strftime('%Y-%m-%d')}")

    print(sep + "\n")


def save_excel(totals: dict, reports: list[dict], output_path: Path) -> None:
    try:
        import pandas as pd
    except ImportError:
        print("pandas not available — skipping Excel export")
        return

    rows = []
    for r in reports:
        rows.append({
            "file":               r.get("_file", ""),
            "timestamp":          r.get("timestamp") or r.get("run_id", ""),
            "total_cost_usd":     r.get("total_cost_usd", 0),
            "total_records":      r.get("total_records", 0),
            "total_tokens":       r.get("total_tokens", 0),
            "prompt_tokens":      r.get("prompt_tokens", 0),
            "completion_tokens":  r.get("completion_tokens", 0),
        })

    module_rows = []
    for mod, m in sorted(totals["by_module"].items()):
        module_rows.append({
            "module":    mod,
            "runs":      m["runs"],
            "cost_usd":  m["cost_usd"],
            "records":   m["records"],
            "tokens":    m["tokens"],
            "cost_per_record": m["cost_usd"] / m["records"] if m["records"] else 0,
        })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name="Runs", index=False)
        pd.DataFrame(module_rows).to_excel(writer, sheet_name="By Module", index=False)

    print(f"  Saved: {output_path}")


def main() -> None:
    p = argparse.ArgumentParser(description="Aggregate cost reports from runs/cost_reports/")
    p.add_argument("--dir", default="runs/cost_reports", help="Directory of cost_*.json files")
    p.add_argument("--since", default=None, help="Only include runs after this date (YYYY-MM-DD)")
    p.add_argument("--output", default=None, help="Save summary to Excel file (optional)")
    args = p.parse_args()

    report_dir = Path(args.dir)
    if not report_dir.exists():
        print(f"Directory not found: {report_dir}")
        return

    since = None
    if args.since:
        since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)

    reports = load_reports(report_dir, since)
    if not reports:
        print(f"No cost_*.json files found in {report_dir}")
        return

    totals = aggregate(reports)
    print_summary(totals, reports)

    if args.output:
        save_excel(totals, reports, Path(args.output))


if __name__ == "__main__":
    main()
