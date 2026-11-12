"""
Guard-rail checks run before every commit (pre-commit) and in CI.

Fails when the repository would publish something it must not:
  * notebooks with saved outputs (outputs can contain customer transcripts)
  * e-mail addresses or hard-coded passwords in text files
  * very large files (customer data exports usually are)

usage:  python tools/check_repo.py [files...]   (default: all files tracked by git)
"""
import json
import re
import subprocess
import zipfile
import sys
from pathlib import Path

MAX_BYTES = 5_000_000
TEXT_SUFFIXES = {".py", ".md", ".json", ".txt", ".toml", ".yaml", ".yml", ".csv", ".R", ".ipynb", ".cfg", ".ini"}
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
EMAIL_OK = re.compile(r"noreply@|example\.(com|org)|@users\.noreply\.github\.com")
OFFICE_SUFFIXES = {".docx", ".pptx", ".xlsx", ".xlsm"}
PASSWORD = re.compile(r"""password\s*=\s*['"](?!bar['"]|['"])[^'"]{4,}['"]""", re.I)


def office_text(p: Path) -> str:
    """Plain text inside an Office file (they are zip archives of XML)."""
    try:
        with zipfile.ZipFile(p) as z:
            xml = " ".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist() if n.endswith(".xml"))
    except zipfile.BadZipFile:
        return ""
    return re.sub(r"<[^>]+>", " ", xml)


def tracked_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout
    return [Path(p) for p in out.splitlines()]


def check(paths: list[Path]) -> list[str]:
    problems = []
    for p in paths:
        if not p.is_file():
            continue
        size = p.stat().st_size
        if size > MAX_BYTES:
            problems.append(f"{p}: {size / 1e6:.1f} MB — too large; data belongs in the local data archive")
        if p.suffix == ".ipynb":
            try:
                cells = json.loads(p.read_text(encoding="utf-8")).get("cells", [])
            except (json.JSONDecodeError, UnicodeDecodeError):
                problems.append(f"{p}: not a readable notebook")
                continue
            if any(c.get("outputs") for c in cells if c.get("cell_type") == "code"):
                problems.append(f"{p}: has saved outputs — clear them (Jupyter: Edit > Clear All Outputs)")
        text = None
        if p.suffix in TEXT_SUFFIXES and size <= MAX_BYTES:
            text = p.read_text(encoding="utf-8", errors="ignore")
        elif p.suffix in OFFICE_SUFFIXES:
            text = office_text(p)
        if text is not None:
            emails = sorted({e for e in EMAIL.findall(text) if not EMAIL_OK.search(e)})
            if emails:
                problems.append(f"{p}: contains e-mail address(es) {emails[:3]} — remove personal data")
            if PASSWORD.search(text):
                problems.append(f"{p}: looks like a hard-coded password — read it from an environment variable")
    return problems


def main() -> None:
    paths = [Path(a) for a in sys.argv[1:]] or tracked_files()
    problems = check(paths)
    for line in problems:
        print(line)
    if problems:
        sys.exit(f"\n{len(problems)} problem(s) found — nothing that could contain customer data may be committed.")
    print(f"check_repo: {len(paths)} file(s) OK")


if __name__ == "__main__":
    main()
