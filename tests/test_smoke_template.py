"""End-to-end smoke test: copy use_cases/_template, then validate, build and dry-run it (no LLM calls)."""
import shutil
import subprocess
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / "use_cases" / "_template"


def _rca(cwd, *args):
    return subprocess.run([sys.executable, "-m", "rca_pipeline.cli", *args], cwd=cwd,
                          capture_output=True, text=True, timeout=300)


def test_template_validates_builds_and_dry_runs(tmp_path):
    ws = tmp_path / "my_usecase"
    shutil.copytree(TEMPLATE, ws)

    r = _rca(ws, "validate")
    assert r.returncode == 0, r.stdout + r.stderr

    r = _rca(ws, "build")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (ws / "generated/modules/contact_reason.py").exists()
    assert (ws / "generated/taxonomies/contact_reason.json").exists()

    r = _rca(ws, "run", "--profile", "profiles/example.json", "--dry-run", "--log-file", str(tmp_path / "run.log"))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "20 records" in r.stdout + r.stderr
