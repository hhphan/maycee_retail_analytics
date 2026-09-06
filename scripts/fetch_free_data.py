from __future__ import annotations

import argparse
from pathlib import Path


DEFAULT_REPO_ID = "SDataPro/maycee-retail-dataset"
DEFAULT_OUTPUT_DIR = Path("data/free_v1_0")
ALLOWED_TABLES = {
    "categories",
    "customers",
    "date_dim",
    "districts",
    "items",
    "products",
    "promotions",
    "regions",
    "returns",
    "stores",
    "suppliers",
    "transactions",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch the public/free Maycee Hugging Face dataset.")
    parser.add_argument("--repo-id", default=DEFAULT_REPO_ID)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--table", action="append", choices=sorted(ALLOWED_TABLES), help="Limit download to a table. Repeatable.")
    parser.add_argument("--dry-run", action="store_true", help="Print the planned fetch without network access.")
    return parser.parse_args()


def planned_patterns(tables: list[str] | None) -> list[str]:
    selected = tables or sorted(ALLOWED_TABLES)
    return [f"data/{table}/*" for table in selected]


def main() -> int:
    args = parse_args()
    patterns = planned_patterns(args.table)
    print(f"Repository: {args.repo_id}")
    print(f"Output directory: {args.output_dir}")
    print("Allowed patterns:")
    for pattern in patterns:
        print(f"- {pattern}")
    print("Boundary: published Hugging Face free dataset only, currently 2017-01-01 through 2019-12-31.")

    if args.dry_run:
        return 0

    from huggingface_hub import snapshot_download

    snapshot_download(
        repo_id=args.repo_id,
        repo_type="dataset",
        local_dir=args.output_dir,
        allow_patterns=patterns,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
