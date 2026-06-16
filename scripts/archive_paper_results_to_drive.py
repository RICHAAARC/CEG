"""把论文结果包归档到 MyDrive 风格的分类目录."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main.analysis.result_archive import archive_paper_results_package


def build_parser() -> argparse.ArgumentParser:
    """构造结果包归档命令行参数."""
    parser = argparse.ArgumentParser(description="归档 CEG paper_results_package 到 Drive 分类目录.")
    parser.add_argument("--package-root", required=True, help="已由 export_paper_results_package.py 导出的结果包目录.")
    parser.add_argument(
        "--drive-root",
        default="/content/drive/MyDrive/CEG",
        help="Drive 归档根目录. Windows 本地可传入 D:\\content\\drive\\MyDrive\\CEG.",
    )
    parser.add_argument("--run-id", default=None, help="可选运行标识, 用于稳定生成归档目录和 zip 文件名.")
    parser.add_argument(
        "--allow-invalid-package",
        action="store_true",
        help="允许 validation 未通过的调试结果包进入归档. 默认要求 validation pass.",
    )
    return parser


def main() -> None:
    """CLI 入口."""
    parser = build_parser()
    args = parser.parse_args()
    manifest = archive_paper_results_package(
        args.package_root,
        args.drive_root,
        run_id=args.run_id,
        require_validation=not args.allow_invalid_package,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
