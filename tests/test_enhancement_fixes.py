"""Regression tests for three reported issues:

1. aggregate_costs.py reported $0 (wrong file pattern, wrong JSON keys)
2. --eval-gold-test crashed without --output, and ran (paid) after --dry-run
3. `rca run` ignored the enhancement settings (feedback, confidence, quality, …)
"""
import argparse
import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "use_cases" / "_template"


# ---------------------------------------------------------------------------
# 1. Cost aggregation
# ---------------------------------------------------------------------------
def _cost_report(run_id, cost, records, module="contact_reason"):
    return {
        "summary": {"run_id": run_id, "total_records": records, "total_prompt_tokens": 900,
                    "total_completion_tokens": 100, "total_tokens": 1000, "total_cost_usd": cost},
        "by_module": {module: {"total_records": records, "total_tokens": 1000, "total_cost_usd": cost}},
        "calls": [],
    }


def test_aggregate_costs_reads_summary_and_both_file_names(tmp_path):
    from rca_pipeline.tools.aggregate_costs import aggregate, load_reports

    (tmp_path / "costs_20260604_090535.json").write_text(json.dumps(_cost_report("20260604_090535", 4.0, 100)))
    (tmp_path / "cost_20260623_125640.json").write_text(json.dumps(_cost_report("20260623_125640", 2.0, 50, "root_cause")))
    totals = aggregate(load_reports(tmp_path))

    assert totals["runs"] == 2
    assert totals["total_cost_usd"] == pytest.approx(6.0)
    assert totals["total_records"] == 150
    assert totals["total_tokens"] == 2000
    assert totals["prompt_tokens"] == 1800
    assert totals["by_module"]["contact_reason"]["cost_usd"] == pytest.approx(4.0)
    assert totals["by_module"]["root_cause"]["records"] == 50


def test_aggregate_costs_since_filter_uses_run_id(tmp_path):
    from datetime import datetime, timezone
    from rca_pipeline.tools.aggregate_costs import load_reports

    (tmp_path / "costs_20260101_000000.json").write_text(json.dumps(_cost_report("20260101_000000", 1.0, 1)))
    (tmp_path / "costs_20260701_000000.json").write_text(json.dumps(_cost_report("20260701_000000", 1.0, 1)))
    since = datetime(2026, 6, 1, tzinfo=timezone.utc)
    assert len(load_reports(tmp_path, since)) == 1


# ---------------------------------------------------------------------------
# 2. Gold-set evaluation
# ---------------------------------------------------------------------------
def test_gold_eval_output_defaults_like_the_run():
    from rca_pipeline.runner import _resolve_output

    args = argparse.Namespace(input="data/tickets.csv", output=None)
    assert _resolve_output(args) == str(Path("data") / "tickets_enriched.xlsx")
    args.output = "runs/out.xlsx"
    assert _resolve_output(args) == "runs/out.xlsx"


def test_gold_eval_does_not_run_after_dry_run(monkeypatch):
    from rca_pipeline import runner

    calls = []

    async def fake_run(args):
        return None

    monkeypatch.setattr(runner, "_parse_args",
                        lambda: argparse.Namespace(dry_run=True, eval_gold_test="gold.csv", output=None))
    monkeypatch.setattr(runner, "run", fake_run)
    monkeypatch.setattr(runner, "_run_gold_eval", lambda args: calls.append(args))
    runner.main()
    assert calls == []


# ---------------------------------------------------------------------------
# 3a. Prompt suffix and cost label are per task, so concurrent modules don't mix
# ---------------------------------------------------------------------------
def test_prompt_suffix_is_isolated_per_concurrent_task():
    from rca_pipeline import llm_client

    async def worker(suffix):
        llm_client.set_system_prompt_suffix(suffix)
        llm_client.set_cost_tracker_module(suffix)
        await asyncio.sleep(0.01)  # let the other task run and set its own value
        return llm_client.get_system_prompt_suffix(), llm_client.get_cost_tracker_module()

    async def main():
        return await asyncio.gather(worker("A"), worker("B"))

    assert asyncio.run(main()) == [("A", "A"), ("B", "B")]


# ---------------------------------------------------------------------------
# Shared fixture: a built copy of the template use case
# ---------------------------------------------------------------------------
@pytest.fixture
def built_workspace(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(TEMPLATE, ws)
    r = subprocess.run([sys.executable, "-m", "rca_pipeline.cli", "build"], cwd=ws,
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    return ws


# ---------------------------------------------------------------------------
# 3b. Hierarchical L2 step loads the generated module from the workspace
# ---------------------------------------------------------------------------
def test_hierarchical_loads_generated_module_from_workspace(built_workspace, monkeypatch):
    from rca_pipeline.enhancements.hierarchical import _load_generated_module

    monkeypatch.setenv("RCA_WORKSPACE", str(built_workspace))
    mod = _load_generated_module("contact_reason")
    assert hasattr(mod, "_build_system_prompt")
    assert hasattr(mod, "_USER_PROMPT_TEMPLATE")


# ---------------------------------------------------------------------------
# 3c. `rca run` applies feedback, confidence, review queue and quality report
# ---------------------------------------------------------------------------
def test_rca_run_applies_enhancements(built_workspace, monkeypatch):
    from rca_pipeline import llm_client, pipeline, runner
    from rca_pipeline.enhancements.feedback import FeedbackStore

    ws = built_workspace
    FeedbackStore(ws / "feedback").add_correction(
        "contact_reason", uid="demo-001", text="Customer: I forgot my password.",
        original={"cr_code": "CR3.1"}, corrected={"cr_code": "CR1.1"},
        reason="Password problems are access, not product use")

    seen_suffixes = []

    async def fake_classify(batches, taxonomies, cfg):
        seen_suffixes.append(llm_client.get_system_prompt_suffix())
        out = []
        for batch in batches:
            for i, rec in enumerate(batch):
                out.append({"uid": rec["uid"], "cr_code": "CR1.1", "cr_summary": "x", "cr_evidence": "",
                            "cr_resolved": "yes", "confidence": 0.95 if i % 2 else 0.3})
        return out

    monkeypatch.setitem(pipeline.MODULE_REGISTRY, "contact_reason", fake_classify)
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    monkeypatch.chdir(ws)
    monkeypatch.setenv("RCA_WORKSPACE", str(ws))
    out = ws / "runs" / "output" / "result.xlsx"
    monkeypatch.setattr(sys, "argv", [
        "rca run", "--input", "data/sample_transcripts.csv", "--output", str(out),
        "--text-col", "conversation", "--id-col", "uid", "--modules", "contact_reason",
        "--taxonomy-dir", "generated/taxonomies", "--log-file", str(ws / "run.log"),
        "--checkpoint", str(ws / "runs" / "ckpt.jsonl"), "--bad-uids", str(ws / "runs" / "bad.txt"),
        "--feedback-dir", "feedback", "--enable-confidence", "--export-review-queue",
        "--run-quality-check", "--quality-report-dir", "runs/quality",
    ])
    asyncio.run(runner.run(runner._parse_args()))

    # feedback few-shot examples and the confidence instruction reached the prompt
    assert seen_suffixes and all("Password problems are access" in s for s in seen_suffixes)
    assert all("confidence" in s.lower() for s in seen_suffixes)
    # confidence columns and review queue
    df = pd.read_excel(out)
    assert {"_confidence", "_needs_review"} <= set(df.columns)
    assert df["_needs_review"].sum() == (df["_confidence"] < 0.7).sum() > 0
    assert (out.parent / "review_queue.xlsx").exists()
    # quality report
    assert any((ws / "runs" / "quality").glob("quality_report*.json"))
