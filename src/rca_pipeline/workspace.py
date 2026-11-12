"""
workspace.py – where a use case's files live
=============================================
Every use case is a folder ("workspace") with the same layout:

    <workspace>/
        definitions/   the Excel pipeline definition(s)
        profiles/      run profiles (JSON)
        generated/     build output: modules/, taxonomies/, pipeline_config.json
        runs/          checkpoints, outputs, cost reports
        feedback/      human corrections (JSONL)

The workspace is the RCA_WORKSPACE environment variable if set, otherwise the
current working directory.  The `rca --workspace DIR ...` CLI option sets both.
"""
from __future__ import annotations

import os
from pathlib import Path


def root() -> Path:
    return Path(os.environ.get("RCA_WORKSPACE", ".")).resolve()


def generated_dir() -> Path:
    return root() / "generated"
