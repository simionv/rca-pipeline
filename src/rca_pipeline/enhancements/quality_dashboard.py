"""
quality_dashboard.py – Automated Quality Dashboard
=====================================================
Runs after each classification to produce a comprehensive quality report:

  1. Coverage per module (% non-empty codes)
  2. Code distribution (flag codes with <1% or >50% usage)
  3. Evidence type distribution
  4. Error rate and error breakdown
  5. Confidence distribution (if confidence scoring is enabled)
  6. Run-over-run comparison (if a previous run exists)
  7. Language distribution (if language detection is enabled)

Outputs:
  - Structured JSON report  (machine-readable, for CI/CD gating)
  - Human-readable log summary
  - Optional Excel report   (for stakeholder review)

Usage:
  from quality_dashboard import QualityDashboard

  dashboard = QualityDashboard(df_enriched, taxonomies, cfg)
  report = dashboard.generate()
  dashboard.print_summary()
  dashboard.save("output/quality_report.json")
  dashboard.save_excel("output/quality_report.xlsx")
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from ..config import RunConfig, load_pipeline_config as _load_pipeline_config
from ..taxonomy import flatten_taxonomy, leaf_label_lookup

logger = logging.getLogger(__name__)


class QualityDashboard:
    """
    Generates a comprehensive quality report from enriched classification output.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        taxonomies: dict[str, dict],
        cfg: Optional[RunConfig] = None,
        previous_report: Optional[dict] = None,
    ):
        self.df = df
        self.taxonomies = taxonomies
        self.cfg = cfg or RunConfig()
        self.previous = previous_report
        self._pipeline_config = _load_pipeline_config()
        self._report: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Main generation
    # ------------------------------------------------------------------
    def generate(self) -> dict[str, Any]:
        """Generate the full quality report."""
        self._report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_records": len(self.df),
            "coverage": self._compute_coverage(),
            "code_distribution": self._compute_code_distribution(),
            "evidence_quality": self._compute_evidence_quality(),
            "error_rate": self._compute_error_rate(),
            "confidence": self._compute_confidence_stats(),
            "language": self._compute_language_stats(),
            "anomalies": self._detect_anomalies(),
        }

        if self.previous:
            self._report["comparison"] = self._compare_with_previous()

        return self._report

    # ------------------------------------------------------------------
    # 1. Coverage per module
    # ------------------------------------------------------------------
    def _compute_coverage(self) -> dict[str, Any]:
        """Compute % non-empty for each classification field."""
        coverage: dict[str, Any] = {}
        total = len(self.df)
        if total == 0:
            return coverage

        # Find all code and classification columns
        code_cols = [c for c in self.df.columns
                     if c.endswith("_code") or c.endswith("_primary_code")]
        status_cols = [c for c in self.df.columns
                       if c.endswith("_status") or c == "escalated"]
        all_cols = code_cols + status_cols

        for col in all_cols:
            non_empty = self.df[col].notna() & (
                self.df[col].astype(str).str.strip() != ""
            ) & (self.df[col].astype(str).str.strip() != "nan")
            count = non_empty.sum()
            pct = round(count / total * 100, 1)

            coverage[col] = {
                "non_empty": int(count),
                "total": total,
                "coverage_pct": pct,
                "status": (
                    "good" if pct >= 90
                    else "warning" if pct >= 70
                    else "poor"
                ),
            }

        # Summary
        avg_coverage = (
            sum(c["coverage_pct"] for c in coverage.values()) / len(coverage)
            if coverage else 0
        )
        coverage["_summary"] = {
            "avg_coverage_pct": round(avg_coverage, 1),
            "fields_checked": len(coverage),
            "poor_fields": [
                k for k, v in coverage.items()
                if k != "_summary" and v.get("status") == "poor"
            ],
        }

        return coverage

    # ------------------------------------------------------------------
    # 2. Code distribution
    # ------------------------------------------------------------------
    def _compute_code_distribution(self) -> dict[str, Any]:
        """
        Analyse code usage distribution.
        Flags codes with <1% or >50% usage (potential taxonomy issues).
        """
        distribution: dict[str, Any] = {}
        total = len(self.df)
        if total == 0:
            return distribution

        code_cols = [c for c in self.df.columns
                     if c.endswith("_primary_code") or c.endswith("_code")]
        # Exclude positional columns (_code_1, _code_2)
        code_cols = [c for c in code_cols if not re.search(r"_\d+$", c)]

        for col in code_cols:
            valid = self.df[col].dropna().astype(str).str.strip()
            valid = valid[valid != ""].value_counts()

            if valid.empty:
                distribution[col] = {"codes": {}, "alerts": []}
                continue

            codes: dict[str, dict] = {}
            alerts: list[str] = []

            for code, count in valid.items():
                pct = round(count / total * 100, 2)
                label = self._lookup_label(str(code))
                codes[str(code)] = {
                    "count": int(count),
                    "pct": pct,
                    "label": label,
                }

                if pct < 1.0:
                    alerts.append(
                        f"LOW: {code} ({label}) — {pct}% usage (< 1%)"
                    )
                if pct > 50.0:
                    alerts.append(
                        f"HIGH: {code} ({label}) — {pct}% usage (> 50%)"
                    )

            # Check for unused taxonomy codes
            unused = self._find_unused_codes(col, set(valid.index))
            for code, label in unused:
                alerts.append(f"UNUSED: {code} ({label}) — 0% usage")

            distribution[col] = {
                "unique_codes": len(codes),
                "codes": codes,
                "alerts": alerts,
                "alert_count": len(alerts),
            }

        return distribution

    def _lookup_label(self, code: str) -> str:
        """Look up a taxonomy label for a code."""
        lookup = leaf_label_lookup(self.taxonomies)
        return lookup.get(code, "")

    def _find_unused_codes(
        self, col: str, used_codes: set[str]
    ) -> list[tuple[str, str]]:
        """Find taxonomy codes that are defined but never used."""
        unused = []
        lookup = leaf_label_lookup(self.taxonomies)
        # Only check codes whose prefix matches the column
        for code, label in lookup.items():
            if "." in code and code not in used_codes:
                # Heuristic: check if the code prefix matches the column name
                prefix = code.split(".")[0]
                if prefix.isalpha():
                    col_prefix = ""
                    for mod_cfg in self._pipeline_config.get("modules", {}).values():
                        if mod_cfg.get("taxonomy_prefix", ""):
                            # Match prefix to column
                            tf = mod_cfg.get("taxonomy_file", "")
                            key = tf.replace(".json", "") if tf else ""
                            if key and col.startswith(key.replace("_codes", "").replace("_steps", "")):
                                col_prefix = mod_cfg["taxonomy_prefix"]
                                break
                    if col_prefix and prefix.startswith(col_prefix):
                        unused.append((code, label))
        return unused[:20]  # Cap to avoid noise

    # ------------------------------------------------------------------
    # 3. Evidence quality
    # ------------------------------------------------------------------
    def _compute_evidence_quality(self) -> dict[str, Any]:
        """Analyse evidence field quality and grounding rates."""
        quality: dict[str, Any] = {}

        # Evidence type distribution
        etype_cols = [c for c in self.df.columns if c.endswith("_evidence_type")]
        for col in etype_cols:
            valid = self.df[col].dropna().astype(str).str.strip()
            valid = valid[valid != ""]
            counts = valid.value_counts().to_dict()
            quality[col] = {
                "distribution": {str(k): int(v) for k, v in counts.items()},
                "total": int(len(valid)),
            }

        # Grounding rates
        grounded_cols = [c for c in self.df.columns if c.endswith("_grounded")]
        for col in grounded_cols:
            if self.df[col].dtype == bool or set(self.df[col].dropna().unique()) <= {True, False}:
                grounded = self.df[col].sum()
                total = self.df[col].notna().sum()
                rate = round(grounded / total * 100, 1) if total > 0 else 0
                quality[col] = {
                    "grounded": int(grounded),
                    "ungrounded": int(total - grounded),
                    "total": int(total),
                    "grounding_rate_pct": rate,
                    "status": "good" if rate >= 95 else "warning" if rate >= 85 else "poor",
                }

        return quality

    # ------------------------------------------------------------------
    # 4. Error rate
    # ------------------------------------------------------------------
    def _compute_error_rate(self) -> dict[str, Any]:
        """Compute error rate from _error columns."""
        error_cols = [c for c in self.df.columns if c == "_error" or c.endswith("_error")]

        total = len(self.df)
        error_records = set()
        error_types: Counter = Counter()

        for col in error_cols:
            if col not in self.df.columns:
                continue
            errors = self.df[col].notna() & (self.df[col].astype(str).str.strip() != "")
            for idx in self.df.index[errors]:
                error_records.add(idx)
                err_msg = str(self.df.at[idx, col])[:100]
                error_types[err_msg] += 1

        n_errors = len(error_records)
        error_rate = round(n_errors / total * 100, 2) if total > 0 else 0

        return {
            "total_records": total,
            "error_records": n_errors,
            "error_rate_pct": error_rate,
            "status": "good" if error_rate < 2 else "warning" if error_rate < 5 else "poor",
            "top_errors": dict(error_types.most_common(10)),
        }

    # ------------------------------------------------------------------
    # 5. Confidence statistics
    # ------------------------------------------------------------------
    def _compute_confidence_stats(self) -> dict[str, Any]:
        """Compute confidence distribution if confidence scoring is enabled."""
        conf_col = "_confidence"
        if conf_col not in self.df.columns:
            return {"enabled": False}

        valid = pd.to_numeric(self.df[conf_col], errors="coerce").dropna()
        if valid.empty:
            return {"enabled": True, "data": False}

        # Distribution buckets
        buckets = {
            "very_high (0.9-1.0)": int(((valid >= 0.9) & (valid <= 1.0)).sum()),
            "high (0.7-0.9)": int(((valid >= 0.7) & (valid < 0.9)).sum()),
            "moderate (0.5-0.7)": int(((valid >= 0.5) & (valid < 0.7)).sum()),
            "low (0.0-0.5)": int((valid < 0.5).sum()),
        }

        review_col = "_needs_review"
        needs_review = int(self.df[review_col].sum()) if review_col in self.df.columns else 0

        return {
            "enabled": True,
            "mean": round(float(valid.mean()), 4),
            "median": round(float(valid.median()), 4),
            "std": round(float(valid.std()), 4),
            "min": round(float(valid.min()), 4),
            "max": round(float(valid.max()), 4),
            "distribution": buckets,
            "needs_review": needs_review,
            "needs_review_pct": round(needs_review / len(self.df) * 100, 1) if len(self.df) > 0 else 0,
        }

    # ------------------------------------------------------------------
    # 6. Language statistics
    # ------------------------------------------------------------------
    def _compute_language_stats(self) -> dict[str, Any]:
        """Compute language distribution if language detection is enabled."""
        lang_col = "_detected_language"
        if lang_col not in self.df.columns:
            return {"enabled": False}

        counts = self.df[lang_col].value_counts().to_dict()
        total = len(self.df)

        return {
            "enabled": True,
            "distribution": {
                str(k): {"count": int(v), "pct": round(v / total * 100, 1)}
                for k, v in counts.items()
            },
            "non_english_pct": round(
                (total - counts.get("en", 0)) / total * 100, 1
            ) if total > 0 else 0,
        }

    # ------------------------------------------------------------------
    # 7. Anomaly detection
    # ------------------------------------------------------------------
    def _detect_anomalies(self) -> list[dict[str, str]]:
        """Detect common quality anomalies."""
        anomalies: list[dict[str, str]] = []

        total = len(self.df)
        if total == 0:
            return anomalies

        # Check for L1-only codes in primary code fields
        for col in self.df.columns:
            if not col.endswith("_primary_code"):
                continue
            valid = self.df[col].dropna().astype(str).str.strip()
            valid = valid[valid != ""]
            l1_only = valid[~valid.str.contains(r"\.", regex=True)]
            if len(l1_only) > 0:
                pct = round(len(l1_only) / len(valid) * 100, 1) if len(valid) > 0 else 0
                anomalies.append({
                    "type": "l1_only_codes",
                    "severity": "warning" if pct < 5 else "error",
                    "field": col,
                    "message": (
                        f"{len(l1_only)} records ({pct}%) have L1-only codes "
                        f"(no dot) in {col} — LLM should return leaf codes."
                    ),
                    "examples": l1_only.head(5).tolist(),
                })

        # Check for duplicate UIDs
        if "uid" in self.df.columns:
            dup_uids = self.df["uid"].duplicated().sum()
            if dup_uids > 0:
                anomalies.append({
                    "type": "duplicate_uids",
                    "severity": "error",
                    "field": "uid",
                    "message": f"{dup_uids} duplicate UIDs found",
                })

        # Check for suspiciously uniform distributions (LLM mode collapse)
        for col in self.df.columns:
            if not col.endswith("_primary_code"):
                continue
            valid = self.df[col].dropna().astype(str).str.strip()
            valid = valid[valid != ""]
            if len(valid) > 20:
                top_code_pct = valid.value_counts().iloc[0] / len(valid) * 100
                if top_code_pct > 60:
                    anomalies.append({
                        "type": "mode_collapse",
                        "severity": "warning",
                        "field": col,
                        "message": (
                            f"Top code in {col} accounts for {top_code_pct:.1f}% "
                            f"of assignments — possible LLM mode collapse."
                        ),
                    })

        # Check for high blank rate in description fields
        for col in self.df.columns:
            if not col.endswith("_description") and not col.endswith("_summary"):
                continue
            blank = self.df[col].isna() | (self.df[col].astype(str).str.strip() == "")
            blank_pct = blank.sum() / total * 100
            if blank_pct > 20:
                anomalies.append({
                    "type": "high_blank_rate",
                    "severity": "warning",
                    "field": col,
                    "message": f"{col} has {blank_pct:.1f}% blank values",
                })

        return anomalies

    # ------------------------------------------------------------------
    # Run-over-run comparison
    # ------------------------------------------------------------------
    def _compare_with_previous(self) -> dict[str, Any]:
        """Compare current run with a previous report."""
        if not self.previous:
            return {}

        comparison: dict[str, Any] = {
            "previous_generated_at": self.previous.get("generated_at", "unknown"),
        }

        # Coverage comparison
        prev_coverage = self.previous.get("coverage", {})
        curr_coverage = self._report.get("coverage", {})
        coverage_deltas: dict[str, float] = {}

        for col in set(list(prev_coverage.keys()) + list(curr_coverage.keys())):
            if col == "_summary":
                continue
            prev_pct = prev_coverage.get(col, {}).get("coverage_pct", 0)
            curr_pct = curr_coverage.get(col, {}).get("coverage_pct", 0)
            delta = round(curr_pct - prev_pct, 1)
            if abs(delta) > 0.5:
                coverage_deltas[col] = delta

        comparison["coverage_deltas"] = coverage_deltas

        # Error rate comparison
        prev_err = self.previous.get("error_rate", {}).get("error_rate_pct", 0)
        curr_err = self._report.get("error_rate", {}).get("error_rate_pct", 0)
        comparison["error_rate_delta"] = round(curr_err - prev_err, 2)

        # Record count comparison
        prev_total = self.previous.get("total_records", 0)
        curr_total = self._report.get("total_records", 0)
        comparison["record_count_delta"] = curr_total - prev_total

        # Code distribution shifts
        prev_dist = self.previous.get("code_distribution", {})
        curr_dist = self._report.get("code_distribution", {})
        new_alerts: list[str] = []

        for col in curr_dist:
            curr_alerts = set(curr_dist.get(col, {}).get("alerts", []))
            prev_alerts = set(prev_dist.get(col, {}).get("alerts", []))
            new = curr_alerts - prev_alerts
            for alert in new:
                new_alerts.append(f"[{col}] {alert}")

        comparison["new_alerts"] = new_alerts

        return comparison

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------
    def print_summary(self) -> None:
        """Print a formatted quality summary to the log."""
        if not self._report:
            self.generate()

        r = self._report

        logger.info("=" * 70)
        logger.info("QUALITY DASHBOARD")
        logger.info("=" * 70)
        logger.info("Generated: %s", r.get("generated_at", ""))
        logger.info("Records:   %d", r.get("total_records", 0))

        # Coverage
        logger.info("-" * 70)
        logger.info("COVERAGE")
        coverage = r.get("coverage", {})
        for col, stats in sorted(coverage.items()):
            if col == "_summary":
                continue
            status_marker = (
                "✓" if stats["status"] == "good"
                else "⚠" if stats["status"] == "warning"
                else "✗"
            )
            logger.info(
                "  %s %-40s %5.1f%% (%d/%d)",
                status_marker, col, stats["coverage_pct"],
                stats["non_empty"], stats["total"],
            )

        summary = coverage.get("_summary", {})
        logger.info("  Average: %.1f%%", summary.get("avg_coverage_pct", 0))

        # Error rate
        logger.info("-" * 70)
        logger.info("ERROR RATE")
        err = r.get("error_rate", {})
        logger.info(
            "  %s %.2f%% (%d/%d records)",
            "✓" if err.get("status") == "good" else "⚠" if err.get("status") == "warning" else "✗",
            err.get("error_rate_pct", 0),
            err.get("error_records", 0),
            err.get("total_records", 0),
        )

        # Code distribution alerts
        logger.info("-" * 70)
        logger.info("CODE DISTRIBUTION ALERTS")
        dist = r.get("code_distribution", {})
        total_alerts = 0
        for col, info in dist.items():
            for alert in info.get("alerts", []):
                logger.info("  %s", alert)
                total_alerts += 1
        if total_alerts == 0:
            logger.info("  (none)")

        # Anomalies
        anomalies = r.get("anomalies", [])
        if anomalies:
            logger.info("-" * 70)
            logger.info("ANOMALIES")
            for a in anomalies:
                marker = "✗" if a["severity"] == "error" else "⚠"
                logger.info("  %s [%s] %s", marker, a["type"], a["message"])

        # Confidence
        conf = r.get("confidence", {})
        if conf.get("enabled") and conf.get("mean") is not None:
            logger.info("-" * 70)
            logger.info("CONFIDENCE")
            logger.info("  Mean: %.3f  Median: %.3f  Std: %.3f",
                         conf["mean"], conf["median"], conf["std"])
            logger.info("  Needs review: %d (%.1f%%)",
                         conf.get("needs_review", 0),
                         conf.get("needs_review_pct", 0))

        # Comparison
        comp = r.get("comparison", {})
        if comp:
            logger.info("-" * 70)
            logger.info("COMPARISON WITH PREVIOUS RUN")
            logger.info("  Previous: %s", comp.get("previous_generated_at", ""))
            logger.info("  Record delta: %+d", comp.get("record_count_delta", 0))
            logger.info("  Error rate delta: %+.2f%%", comp.get("error_rate_delta", 0))
            for alert in comp.get("new_alerts", []):
                logger.info("  NEW: %s", alert)

        logger.info("=" * 70)

    def save(self, filepath: str | Path) -> None:
        """Save the report as JSON."""
        if not self._report:
            self.generate()

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self._report, f, indent=2, ensure_ascii=False, default=str)
        logger.info("Quality report saved → %s", filepath)

    def save_excel(self, filepath: str | Path) -> None:
        """Save the report as a multi-sheet Excel workbook."""
        if not self._report:
            self.generate()

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            # Summary sheet
            summary_data = {
                "Metric": ["Total Records", "Average Coverage %",
                           "Error Rate %", "Anomaly Count"],
                "Value": [
                    self._report.get("total_records", 0),
                    self._report.get("coverage", {}).get("_summary", {}).get("avg_coverage_pct", 0),
                    self._report.get("error_rate", {}).get("error_rate_pct", 0),
                    len(self._report.get("anomalies", [])),
                ],
            }
            pd.DataFrame(summary_data).to_excel(writer, sheet_name="Summary", index=False)

            # Coverage sheet
            coverage_rows = []
            for col, stats in self._report.get("coverage", {}).items():
                if col == "_summary":
                    continue
                coverage_rows.append({
                    "Field": col,
                    "Non-Empty": stats["non_empty"],
                    "Total": stats["total"],
                    "Coverage %": stats["coverage_pct"],
                    "Status": stats["status"],
                })
            if coverage_rows:
                pd.DataFrame(coverage_rows).to_excel(
                    writer, sheet_name="Coverage", index=False
                )

            # Code distribution sheet
            dist_rows = []
            for col, info in self._report.get("code_distribution", {}).items():
                for code, cinfo in info.get("codes", {}).items():
                    dist_rows.append({
                        "Field": col,
                        "Code": code,
                        "Label": cinfo.get("label", ""),
                        "Count": cinfo["count"],
                        "Percentage": cinfo["pct"],
                    })
            if dist_rows:
                pd.DataFrame(dist_rows).to_excel(
                    writer, sheet_name="Code Distribution", index=False
                )

            # Anomalies sheet
            if self._report.get("anomalies"):
                pd.DataFrame(self._report["anomalies"]).to_excel(
                    writer, sheet_name="Anomalies", index=False
                )

        logger.info("Quality report (Excel) saved → %s", filepath)

    @staticmethod
    def load_previous(filepath: str | Path) -> Optional[dict]:
        """Load a previous report for comparison."""
        filepath = Path(filepath)
        if not filepath.exists():
            return None
        with open(filepath, encoding="utf-8") as f:
            return json.load(f)


# ---------------------------------------------------------------------------
# Convenience function for pipeline integration
# ---------------------------------------------------------------------------
def run_quality_check(
    df: pd.DataFrame,
    taxonomies: dict[str, dict],
    cfg: RunConfig,
    output_dir: str | Path = "output",
    previous_report_path: Optional[str | Path] = None,
) -> dict[str, Any]:
    """
    One-call quality check — generates, prints, and saves the report.

    Returns the report dict for programmatic use.
    """
    output_dir = Path(output_dir)

    previous = None
    if previous_report_path:
        previous = QualityDashboard.load_previous(previous_report_path)

    dashboard = QualityDashboard(df, taxonomies, cfg, previous)
    report = dashboard.generate()
    dashboard.print_summary()

    # Save both formats
    json_path = output_dir / "quality_report.json"
    dashboard.save(json_path)

    try:
        xlsx_path = output_dir / "quality_report.xlsx"
        dashboard.save_excel(xlsx_path)
    except Exception as e:
        logger.warning("Could not save Excel quality report: %s", e)

    return report
