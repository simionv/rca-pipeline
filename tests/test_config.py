"""Tests for rca_pipeline.config — RunConfig defaults and load_pipeline_config."""
import json
import os
import tempfile
from pathlib import Path

import pytest
from rca_pipeline.config import RunConfig, load_pipeline_config


# ---------------------------------------------------------------------------
# RunConfig defaults
# ---------------------------------------------------------------------------

def test_runconfig_default_model():
    cfg = RunConfig()
    assert cfg.model  # non-empty

def test_runconfig_default_batch_size():
    cfg = RunConfig()
    assert cfg.batch_size > 0

def test_runconfig_default_concurrency():
    cfg = RunConfig()
    assert cfg.concurrency > 0

def test_runconfig_default_paths_are_absolute():
    cfg = RunConfig()
    assert Path(cfg.taxonomy_dir).is_absolute()
    assert Path(cfg.feedback_dir).is_absolute()
    assert Path(cfg.cost_report_dir).is_absolute()
    assert Path(cfg.quality_report_dir).is_absolute()

def test_runconfig_taxonomy_dir_points_to_generated():
    cfg = RunConfig()
    assert "generated" in cfg.taxonomy_dir
    assert "taxonomies" in cfg.taxonomy_dir

def test_runconfig_feedback_dir_points_to_runs():
    cfg = RunConfig()
    assert "runs" in cfg.feedback_dir

def test_runconfig_env_override(monkeypatch):
    monkeypatch.setenv("RCA_BATCH_SIZE", "42")
    # RunConfig reads env at class definition time via default values,
    # so we need to re-evaluate the default for this test
    import importlib
    import rca_pipeline.config as cfg_mod
    importlib.reload(cfg_mod)
    cfg = cfg_mod.RunConfig()
    assert cfg.batch_size == 42

def test_runconfig_async_tuning_fields():
    cfg = RunConfig()
    assert cfg.max_workers > 0
    assert cfg.max_in_flight > 0
    assert cfg.checkpoint_every > 0

def test_runconfig_enhancement_defaults_disabled():
    cfg = RunConfig()
    assert cfg.enable_confidence is False
    assert cfg.incremental is False
    assert cfg.track_costs is False
    assert cfg.detect_language is False
    assert cfg.run_quality_check is False


# ---------------------------------------------------------------------------
# load_pipeline_config
# ---------------------------------------------------------------------------

def test_load_pipeline_config_missing_returns_empty(tmp_path):
    result = load_pipeline_config(tmp_path / "nonexistent.json")
    assert result == {}

def test_load_pipeline_config_reads_json(tmp_path):
    cfg_file = tmp_path / "pipeline_config.json"
    data = {"modules": {"contact_reason": {"taxonomy_prefix": "CR"}}}
    cfg_file.write_text(json.dumps(data), encoding="utf-8")
    result = load_pipeline_config(cfg_file)
    assert result["modules"]["contact_reason"]["taxonomy_prefix"] == "CR"

def test_load_pipeline_config_default_path_no_crash():
    # Should not raise even if the file doesn't exist
    result = load_pipeline_config()
    assert isinstance(result, dict)
