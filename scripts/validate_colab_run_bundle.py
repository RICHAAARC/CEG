"""校验 Colab 运行级 bundle 的独立命令行入口。

该脚本只负责读取已经生成的 `colab_run_bundle/` 目录或 `ceg_colab_run_bundle.zip`,
并复用 `paper_workflow.colab_utils.cold_start.validate_colab_run_bundle` 中的正式校验逻辑。
这样 Notebook 仍然只是入口, 校验语义保留在 repository module 中, 便于本地和 Colab 之间复用。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
import zipfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from paper_workflow.colab_utils.cold_start import validate_colab_run_bundle


def _find_bundle_root(candidate_root: Path) -> Path:
    """在目录中定位包含 `colab_run_bundle_manifest.json` 的 bundle 根目录。"""
    direct_manifest = candidate_root / "colab_run_bundle_manifest.json"
    if direct_manifest.is_file():
        return candidate_root

    manifest_paths = sorted(candidate_root.rglob("colab_run_bundle_manifest.json"))
    if not manifest_paths:
        raise FileNotFoundError(f"未找到 colab_run_bundle_manifest.json: {candidate_root}")

    parent_roots = sorted({path.parent for path in manifest_paths})
    if len(parent_roots) == 1:
        return parent_roots[0]

    named_roots = [path for path in parent_roots if path.name == "colab_run_bundle"]
    if len(named_roots) == 1:
        return named_roots[0]

    candidates = [path.as_posix() for path in parent_roots]
    raise ValueError(f"发现多个候选 bundle 根目录, 无法自动选择: {candidates}")


def _validate_directory(bundle_path: Path) -> dict[str, Any]:
    """校验目录形式的 Colab bundle, 并在报告中记录实际校验根目录。"""
    bundle_root = _find_bundle_root(bundle_path.resolve())
    report = validate_colab_run_bundle(bundle_root)
    report["validated_bundle_path"] = str(bundle_root)
    return report


def _validate_zip(bundle_path: Path) -> dict[str, Any]:
    """校验 zip 形式的 Colab bundle, 解压到临时目录后复用目录校验逻辑。"""
    with tempfile.TemporaryDirectory(prefix="ceg_colab_bundle_") as temp_dir:
        extraction_root = Path(temp_dir)
        with zipfile.ZipFile(bundle_path, "r") as archive:
            archive.extractall(extraction_root)
        bundle_root = _find_bundle_root(extraction_root)
        report = validate_colab_run_bundle(bundle_root)
        report["validated_bundle_path"] = str(bundle_root)
        report["validated_archive_path"] = str(bundle_path.resolve())
        return report


def validate_bundle_path(bundle_path: str | Path) -> dict[str, Any]:
    """根据输入路径类型校验目录或 zip 压缩包形式的 Colab bundle。"""
    path = Path(bundle_path)
    if path.is_dir():
        return _validate_directory(path)
    if path.is_file() and zipfile.is_zipfile(path):
        return _validate_zip(path)
    raise FileNotFoundError(f"bundle 路径不是目录或 zip 文件: {path}")


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="校验 Colab 运行级 bundle 目录或 zip 压缩包。")
    parser.add_argument(
        "--bundle",
        required=True,
        help="待校验的 colab_run_bundle 目录或 ceg_colab_run_bundle.zip 文件。",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="可选的 JSON 校验报告输出路径。未设置时只打印到标准输出。",
    )
    parser.add_argument(
        "--require-pass",
        action="store_true",
        help="如果校验结果不是 pass, 使用非零退出码阻断流水线。",
    )
    return parser


def main() -> None:
    """CLI 入口, 输出结构化 JSON 报告并按需要返回失败退出码。"""
    parser = build_parser()
    args = parser.parse_args()
    report = validate_bundle_path(args.bundle)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if args.require_pass and report.get("overall_decision") != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
