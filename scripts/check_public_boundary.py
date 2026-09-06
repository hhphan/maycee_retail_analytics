from __future__ import annotations

import json
import re
import subprocess
from datetime import date
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FREE_START = date(2017, 1, 1)
FREE_END = date(2019, 12, 31)
IGNORED_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", "reports"}
TEXT_SUFFIXES = {".env", ".example", ".gitignore", ".md", ".py", ".txt", ".toml", ""}
BLOCKED_PATTERNS = [
    re.compile(r"dt=202[0-9]-"),
    re.compile(r"premium", re.IGNORECASE),
    re.compile(r"s3://", re.IGNORECASE),
    re.compile(r"aws_access_key_id", re.IGNORECASE),
    re.compile(r"aws_secret_access_key", re.IGNORECASE),
    re.compile(r"MAYCEE_LICEN[CS]E_KEY", re.IGNORECASE),
    re.compile(r"licen[cs]e[-_ ]?manifest", re.IGNORECASE),
    re.compile(r"licensed_data_adapter", re.IGNORECASE),
    re.compile(r"fulfilment", re.IGNORECASE),
    re.compile(r"private retrieval", re.IGNORECASE),
]
ALLOWED_PATTERN_FILES = {
    Path("docs/public_boundary.md"),
    Path("scripts/check_public_boundary.py"),
    Path("tests/test_public_boundary.py"),
}
SECRET_LIKE_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)(secret|token|password)\s*=\s*['\"]?[A-Za-z0-9_./+=-]{16,}"),
]


def iter_text_files(root: Path = REPO_ROOT) -> list[Path]:
    paths: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            paths.append(path)
    return paths


def check_blocked_terms(root: Path = REPO_ROOT) -> list[str]:
    errors: list[str] = []
    for path in iter_text_files(root):
        relative = path.relative_to(root)
        text = path.read_text(encoding="utf-8", errors="ignore")
        if relative not in ALLOWED_PATTERN_FILES:
            for pattern in BLOCKED_PATTERNS:
                if pattern.search(text):
                    errors.append(f"{relative}: blocked term matched {pattern.pattern}")
        for pattern in SECRET_LIKE_PATTERNS:
            if pattern.search(text):
                errors.append(f"{relative}: possible secret matched {pattern.pattern}")
    return errors


def check_tracked_data(root: Path = REPO_ROOT) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--", "data"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    tracked = [line for line in result.stdout.splitlines() if Path(line).suffix.lower() in {".csv", ".json", ".parquet"}]
    return [f"{path}: downloaded data must not be tracked" for path in tracked]


def check_local_metadata(root: Path = REPO_ROOT) -> list[str]:
    metadata_path = root / "data" / "free_v1_0" / "metadata.json"
    if not metadata_path.exists():
        return []
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    partition_range = metadata.get("partition_range", {})
    expected = {
        "tier": "free",
        "first": FREE_START.isoformat(),
        "last": FREE_END.isoformat(),
        "partition_count": 1095,
    }
    actual = {
        "tier": metadata.get("tier"),
        "first": partition_range.get("first"),
        "last": partition_range.get("last"),
        "partition_count": metadata.get("partition_count"),
    }
    return [f"{metadata_path.relative_to(root)}: {key} must be {value}" for key, value in expected.items() if actual[key] != value]


def run_checks(root: Path = REPO_ROOT) -> list[str]:
    return check_blocked_terms(root) + check_tracked_data(root) + check_local_metadata(root)


if __name__ == "__main__":
    failures = run_checks()
    if failures:
        print("Public boundary check failed:")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)
    print("Public boundary check passed.")
