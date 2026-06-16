"""运行 Colab bundle 最终验收命令的独立 CLI。

该脚本只读取已经生成的 `colab_run_bundle/` 目录或 `ceg_colab_run_bundle.zip`, 并串联已有的
`validate_colab_run_bundle.py` 与 `validate_paper_result_evidence.py`。它不重新生成 records、tables、figures
或 reports, 因此可用于 Colab 下载后的本地 / CI 离线复核。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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


def _run_command(command: list[str], *, cwd: Path, timeout_seconds: int | None) -> dict[str, Any]:
    """执行一个验收命令并返回结构化结果, 便于写入最终 acceptance report。"""
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    return {
        "command": command,
        "working_directory": str(cwd),
        "return_code": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


def _read_json_report(path: Path) -> dict[str, Any]:
    """读取验收子报告, 缺失或解析失败时返回 fail 结构。"""
    if not path.is_file():
        return {"overall_decision": "fail", "reason": "missing_report", "path": str(path)}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        return {"overall_decision": "fail", "reason": "json_parse_failed", "path": str(path), "error": str(exc)}
    if not isinstance(payload, dict):
        return {"overall_decision": "fail", "reason": "report_not_object", "path": str(path)}
    return payload


def build_acceptance_report(
    bundle_path: str | Path,
    *,
    repo_root: str | Path = ROOT,
    out: str | Path | None = None,
    allow_dry_run: bool = False,
    require_experiment_coverage: bool = True,
    require_external_command_results: bool = False,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    """对目录或 zip 形式的 Colab bundle 运行最终验收并返回报告。"""
    root = Path(repo_root).resolve()
    source_bundle_path = Path(bundle_path).resolve()
    if not source_bundle_path.exists():
        raise FileNotFoundError(f"bundle 路径不存在: {source_bundle_path}")

    with tempfile.TemporaryDirectory(prefix="ceg_acceptance_") as temp_dir:
        temp_root = Path(temp_dir)
        if source_bundle_path.is_file() and zipfile.is_zipfile(source_bundle_path):
            with zipfile.ZipFile(source_bundle_path, "r") as archive:
                archive.extractall(temp_root)
            bundle_root = _find_bundle_root(temp_root)
            bundle_argument = source_bundle_path
            validated_archive_path: str | None = str(source_bundle_path)
        elif source_bundle_path.is_dir():
            bundle_root = _find_bundle_root(source_bundle_path)
            bundle_argument = bundle_root
            validated_archive_path = None
        else:
            raise FileNotFoundError(f"bundle 路径不是目录或 zip 文件: {source_bundle_path}")

        output_path = Path(out).resolve() if out else None
        if output_path is not None:
            acceptance_root = output_path.parent / "acceptance"
        elif source_bundle_path.is_dir():
            acceptance_root = bundle_root / "acceptance"
            output_path = bundle_root / "colab_acceptance_report.json"
        else:
            acceptance_root = temp_root / "acceptance"
        acceptance_root.mkdir(parents=True, exist_ok=True)

        bundle_report_path = acceptance_root / "colab_run_bundle_validation_cli.json"
        evidence_report_path = acceptance_root / "paper_result_evidence_cli.json"
        bundle_validation_command = [
            sys.executable,
            str(root / "scripts" / "validate_colab_run_bundle.py"),
            "--bundle",
            str(bundle_argument),
            "--out",
            str(bundle_report_path),
            "--require-pass",
        ]
        evidence_command = [
            sys.executable,
            str(root / "scripts" / "validate_paper_result_evidence.py"),
            "--target",
            str(bundle_root),
            "--out",
            str(evidence_report_path),
            "--require-pass",
        ]
        if allow_dry_run:
            evidence_command.insert(-1, "--allow-dry-run")
        if not require_experiment_coverage:
            evidence_command.insert(-1, "--allow-missing-experiment-coverage")
        if require_external_command_results:
            evidence_command.insert(-1, "--require-external-command-results")

        command_results = [
            _run_command(bundle_validation_command, cwd=root, timeout_seconds=timeout_seconds),
            _run_command(evidence_command, cwd=root, timeout_seconds=timeout_seconds),
        ]
        parsed_reports = {
            "colab_run_bundle_validation": _read_json_report(bundle_report_path),
            "paper_result_evidence": _read_json_report(evidence_report_path),
        }
        report_decisions = {name: payload.get("overall_decision") for name, payload in parsed_reports.items()}
        all_commands_passed = all(item["return_code"] == 0 for item in command_results)
        all_reports_passed = all(decision == "pass" for decision in report_decisions.values())
        acceptance_report = {
            "artifact_name": "colab_acceptance_report.json",
            "overall_decision": "pass" if all_commands_passed and all_reports_passed else "fail",
            "source_bundle_path": str(source_bundle_path),
            "validated_bundle_path": str(bundle_root),
            "validated_archive_path": validated_archive_path,
            "acceptance_root": str(acceptance_root),
            "allow_dry_run": allow_dry_run,
            "require_experiment_coverage": require_experiment_coverage,
            "require_external_command_results": require_external_command_results,
            "report_decisions": report_decisions,
            "command_results": command_results,
            "report_paths": {
                "colab_run_bundle_validation": str(bundle_report_path),
                "paper_result_evidence": str(evidence_report_path),
            },
        }
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(acceptance_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return acceptance_report


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="运行 Colab bundle 最终验收命令并输出 acceptance report。")
    parser.add_argument("--bundle", required=True, help="colab_run_bundle 目录或 ceg_colab_run_bundle.zip 文件。")
    parser.add_argument("--repo-root", default=str(ROOT), help="CEG 仓库根目录。")
    parser.add_argument("--out", default=None, help="可选 acceptance report 输出路径。未设置且输入是目录时写回 bundle 根目录。")
    parser.add_argument("--allow-dry-run", action="store_true", help="允许 dry-run 调试链路通过 evidence 门禁。")
    parser.add_argument(
        "--allow-missing-experiment-coverage",
        action="store_true",
        help="不要求实验矩阵覆盖率通过。仅用于 dry-run 或 pilot 验证。",
    )
    parser.add_argument(
        "--require-external-command-results",
        action="store_true",
        help="要求外部 baseline 和高级指标命令结果存在且通过。",
    )
    parser.add_argument("--timeout-seconds", type=int, default=None, help="单个验收子命令的超时时间。")
    parser.add_argument("--require-pass", action="store_true", help="若 acceptance report 未通过, 返回非零退出码。")
    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()
    report = build_acceptance_report(
        args.bundle,
        repo_root=args.repo_root,
        out=args.out,
        allow_dry_run=args.allow_dry_run,
        require_experiment_coverage=not args.allow_missing_experiment_coverage,
        require_external_command_results=args.require_external_command_results,
        timeout_seconds=args.timeout_seconds,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(rendered, end="")
    if args.require_pass and report.get("overall_decision") != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
