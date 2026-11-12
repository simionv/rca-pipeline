"""The manual must mention every command-line flag and every RunConfig setting the code supports."""
import dataclasses
import re
import subprocess
import sys
from pathlib import Path

import pytest

from rca_pipeline.config import RunConfig

REPO = Path(__file__).resolve().parents[1]
MANUAL = REPO / "docs" / "manual.md"


def _flags(*command):
    out = subprocess.run([sys.executable, "-m", "rca_pipeline.cli", *command, "--help"],
                         capture_output=True, text=True, cwd=REPO / "use_cases" / "_template", timeout=120)
    assert out.returncode == 0, out.stderr
    return sorted(set(re.findall(r"(?<![\w-])--[a-z][a-z0-9-]+", out.stdout)) - {"--help"})


@pytest.fixture(scope="module")
def manual():
    if not MANUAL.exists():
        pytest.fail("docs/manual.md is missing")
    return MANUAL.read_text(encoding="utf-8")


@pytest.mark.parametrize("command", [("run",), ("build",), ("discover",), ("promote-drafts",), ("validate",)])
def test_every_flag_is_documented(manual, command):
    missing = [f for f in _flags(*command) if f not in manual]
    assert not missing, f"rca {command[0]}: flags missing from docs/manual.md: {missing}"


def test_every_runconfig_field_is_documented(manual):
    missing = [f.name for f in dataclasses.fields(RunConfig) if f.name not in manual]
    assert not missing, f"RunConfig fields missing from docs/manual.md: {missing}"
