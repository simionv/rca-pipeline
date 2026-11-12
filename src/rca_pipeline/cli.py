"""
cli.py – the `rca` command
===========================
    rca [--workspace DIR] validate [options]   check the Excel definition, explain problems in plain words
    rca [--workspace DIR] build    [options]   build modules/taxonomies from the Excel definition (validates first)
    rca [--workspace DIR] discover [options]   draft a taxonomy from a sample of your data
    rca [--workspace DIR] promote-drafts ...   accept reviewed draft taxonomies
    rca [--workspace DIR] run      [options]   classify transcripts
    rca catalog                                rebuild CATALOG.md from the use-case pages

DIR is a use-case folder (default: the current directory).  Every relative path
(profiles, data, runs, generated) is resolved from there.
Use `rca <command> --help` for the options of each command.
"""
from __future__ import annotations

import os
import sys

BUILD_COMMANDS = {"build", "discover", "promote-drafts"}
COMMANDS = BUILD_COMMANDS | {"run", "validate", "catalog"}


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)

    if args[:1] in (["--workspace"], ["-w"]):
        if len(args) < 2:
            sys.exit("rca: --workspace needs a folder")
        workspace = os.path.abspath(args[1])
        if not os.path.isdir(workspace):
            sys.exit(f"rca: workspace folder not found: {workspace}")
        os.environ["RCA_WORKSPACE"] = workspace
        os.chdir(workspace)
        args = args[2:]

    if not args or args[0] in ("-h", "--help") or args[0] not in COMMANDS:
        print(__doc__)
        sys.exit(0 if not args or args[0] in ("-h", "--help") else f"rca: unknown command '{args[0]}'")

    command, rest = args[0], args[1:]
    # The workspace must be fixed before the pipeline modules are imported:
    # they resolve generated/ and runs/ paths at import time.
    os.environ["RCA_WORKSPACE"] = os.getcwd()  # always the folder we run in (or --workspace)

    if command == "catalog":
        from rca_pipeline import catalog
        catalog.main(rest)
    elif command == "validate":
        from rca_pipeline import validate
        validate.main(rest)
    elif command in BUILD_COMMANDS:
        if command == "build" and "-h" not in rest and "--help" not in rest:
            _validate_before_build(rest)
        from rca_pipeline import build
        sys.argv = ["rca", command, *rest]
        build.main()
    else:
        from rca_pipeline import runner
        sys.argv = ["rca run", *rest]
        runner.main()


def _validate_before_build(rest: list[str]) -> None:
    from pathlib import Path
    from rca_pipeline import validate
    path = None
    for i, arg in enumerate(rest):
        if arg in ("--input", "-i") and i + 1 < len(rest):
            path = Path(rest[i + 1])
        elif arg.startswith("--input="):
            path = Path(arg.split("=", 1)[1])
    path = path or validate.default_definition()
    if path is not None and not validate.run(path, quiet_ok=True):
        sys.exit("rca build: stopped — fix the errors above first.")


if __name__ == "__main__":
    main()
