"""
Link each use case's data folders to the local data archive.

Customer data (raw inputs, run outputs, human corrections) is never committed.
It lives in a separate local folder, the data archive, with one sub-folder per
use case.  This script creates, inside every use_cases/<name>/ folder, links
called data/, runs/, output/ and feedback/ that point into that archive, so the
paths in each profile ("data/...", "runs/output/...") work unchanged.

usage:  python tools/link_archive.py /path/to/rca-data-archive
"""
import sys
from pathlib import Path

LINKED = ("data", "runs", "output", "feedback")


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    archive = Path(sys.argv[1]).expanduser().resolve()
    if not archive.is_dir():
        sys.exit(f"archive folder not found: {archive}")
    use_cases = Path(__file__).resolve().parents[1] / "use_cases"
    for uc in sorted(p for p in use_cases.iterdir() if p.is_dir() and not p.name.startswith("_")):
        for name in LINKED:
            link, target = uc / name, archive / uc.name / name
            if link.is_symlink():
                link.unlink()
            elif link.exists():
                print(f"skip {link} (a real folder is already there)")
                continue
            target.mkdir(parents=True, exist_ok=True)
            link.symlink_to(target, target_is_directory=True)
        print(f"linked {uc.name}")


if __name__ == "__main__":
    main()
