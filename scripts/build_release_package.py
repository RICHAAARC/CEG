"""构建 CEG 论文发布候选包。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.extract_minimal_paper_package import extract_profile


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="构建 CEG 论文发布候选包。")
    parser.add_argument("--profile", choices=("minimal_method_package", "paper_artifact_rebuild_package"), required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()
    manifest = extract_profile(args.root, args.output, args.profile, dry_run=args.dry_run)
    manifest["release_package_status"] = "dry_run" if args.dry_run else "materialized"
    manifest["release_package_boundary"] = {
        "excluded_governance_roots": [".codex", "tools", "audit_reports", "outputs"],
        "profile": args.profile,
    }
    if not args.dry_run:
        output_path = Path(args.output)
        (output_path / "release_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
