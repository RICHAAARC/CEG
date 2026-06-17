"""校验 Colab 端到端论文结果包运行是否满足正式交付条件。

该脚本不重新运行 GPU 图像生成、攻击或检测。它读取
`colab_end_to_end_paper_pipeline_manifest.json`, 然后串联项目内已有验收脚本, 检查:

1. 端到端流水线 manifest 是否通过。
2. 图像生成产物是否通过 image generation acceptance。
3. 图像生成 zip 归档是否存在。
4. paper_results_package 是否通过结果包验收。
5. MyDrive 风格 paper_results_package 归档是否通过验收。

通用工程写法是把“正式运行验收”设计成只读聚合检查, 使 GPU 任务完成后可在 Colab 或本地
复核同一批落盘产物。项目特定写法是默认要求 `run_image_generation=True`, 即正式论文结果包
必须来自真实 SD 与 CEG watermark backend 的同次端到端运行。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main.core.digest import build_stable_digest


REPORT_NAME = "colab_end_to_end_formal_run_acceptance_report.json"


def _read_json(path: Path) -> Any:
    """读取 UTF-8 或带 BOM 的 JSON 文件。"""

    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    """写出 UTF-8 JSON 报告。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run_command(command: list[str]) -> dict[str, Any]:
    """执行验收子命令并返回结构化摘要。"""

    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    return {
        "command": command,
        "return_code": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


def _read_report_decision(path: Path) -> tuple[str, dict[str, Any] | None, str | None]:
    """读取子验收报告的 overall_decision。"""

    if not path.is_file():
        return "fail", None, "report_missing"
    try:
        payload = _read_json(path)
    except Exception as exc:  # pragma: no cover - 具体异常由底层 JSON / IO 决定
        return "fail", None, f"{type(exc).__name__}: {exc}"
    if not isinstance(payload, dict):
        return "fail", None, "report_not_object"
    return str(payload.get("overall_decision")), payload, None


def _check_existing_file(path_value: str | None, *, label: str) -> dict[str, Any]:
    """检查 manifest 中声明的文件路径是否存在。"""

    if path_value is None or str(path_value).strip() == "":
        return {"label": label, "status": "fail", "reason": "path_absent", "path": None}
    path = Path(path_value)
    return {
        "label": label,
        "status": "pass" if path.is_file() else "fail",
        "reason": None if path.is_file() else "file_missing",
        "path": str(path),
        "byte_count": path.stat().st_size if path.is_file() else 0,
    }


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""

    parser = argparse.ArgumentParser(description="校验 CEG Colab 端到端正式论文结果包运行。")
    parser.add_argument("--manifest", required=True, help="colab_end_to_end_paper_pipeline_manifest.json 路径。")
    parser.add_argument("--out", required=True, help="正式运行验收报告输出路径。")
    parser.add_argument("--allow-existing-image-generation", action="store_true", help="允许使用已存在图像生成产物续跑。正式 GPU 验收默认不允许。")
    parser.add_argument("--allow-incomplete-package", action="store_true", help="允许调试结果包未通过严格 readiness。")
    parser.add_argument("--allow-invalid-archive", action="store_true", help="允许调试归档未通过严格 package validation。")
    parser.add_argument("--require-evidence", action="store_true", help="要求 paper / external evidence reports 存在且通过。")
    parser.add_argument("--require-image-examples", action="store_true", help="要求论文示例图 manifest 与文件存在。")
    parser.add_argument("--require-pass", action="store_true", help="验收失败时返回非零退出码。")
    return parser


def main() -> None:
    """CLI 入口。"""

    args = build_parser().parse_args()
    manifest_path = Path(args.manifest).resolve()
    output_path = Path(args.out).resolve()
    manifest = _read_json(manifest_path)
    if not isinstance(manifest, dict):
        raise TypeError(f"end-to-end manifest must be object: {manifest_path}")

    output_root = output_path.parent
    image_acceptance_report = output_root / "formal_image_generation_acceptance_report.json"
    package_acceptance_report = output_root / "formal_paper_results_package_acceptance_report.json"
    archive_acceptance_report = output_root / "formal_mydrive_archive_acceptance_report.json"

    image_output_root = Path(str(manifest.get("image_output_root") or ""))
    paper_package_root = Path(str(manifest.get("paper_results_package_root") or ""))
    drive_root = Path(str(manifest.get("drive_root") or ""))
    run_id = str(manifest.get("run_id") or "")

    checks: list[dict[str, Any]] = []
    command_results: dict[str, dict[str, Any]] = {}

    checks.append(
        {
            "check_name": "end_to_end_manifest_pass",
            "status": "pass" if manifest.get("overall_decision") == "pass" else "fail",
            "actual": manifest.get("overall_decision"),
        }
    )
    checks.append(
        {
            "check_name": "real_image_generation_run",
            "status": "pass" if manifest.get("run_image_generation") is True or args.allow_existing_image_generation else "fail",
            "actual": manifest.get("run_image_generation"),
            "allow_existing_image_generation": bool(args.allow_existing_image_generation),
        }
    )

    for label, value in (
        ("image_generation_archive_zip", manifest.get("image_generation_archive_zip")),
        ("image_generation_archive_manifest", manifest.get("image_generation_archive_manifest")),
        ("paper_pipeline_manifest", manifest.get("paper_pipeline_manifest")),
    ):
        file_check = _check_existing_file(str(value) if value is not None else None, label=label)
        checks.append({"check_name": f"{label}_exists", **file_check})

    image_command = [
        sys.executable,
        str(ROOT / "scripts" / "validate_pilot_image_generation_outputs.py"),
        "--output-root",
        str(image_output_root),
        "--out",
        str(image_acceptance_report),
        "--require-pass",
    ]
    command_results["image_generation_acceptance"] = _run_command(image_command)
    image_decision, image_report, image_error = _read_report_decision(image_acceptance_report)
    checks.append(
        {
            "check_name": "image_generation_acceptance_pass",
            "status": "pass" if image_decision == "pass" else "fail",
            "overall_decision": image_decision,
            "error": image_error,
            "image_pair_count": image_report.get("summary", {}).get("image_pair_count") if image_report else None,
        }
    )

    package_command = [
        sys.executable,
        str(ROOT / "scripts" / "validate_pilot_paper_results_package.py"),
        "--package-root",
        str(paper_package_root),
        "--out",
        str(package_acceptance_report),
        "--require-pass",
    ]
    if args.require_evidence:
        package_command.append("--require-evidence")
    if args.require_image_examples:
        package_command.append("--require-image-examples")
    if args.allow_incomplete_package:
        package_command.remove("--require-pass")
    command_results["paper_results_package_acceptance"] = _run_command(package_command)
    package_decision, package_report, package_error = _read_report_decision(package_acceptance_report)
    checks.append(
        {
            "check_name": "paper_results_package_acceptance_pass",
            "status": "pass" if package_decision == "pass" or args.allow_incomplete_package else "fail",
            "overall_decision": package_decision,
            "error": package_error,
            "allow_incomplete_package": bool(args.allow_incomplete_package),
            "blocking_issue_count": package_report.get("summary", {}).get("blocking_issue_count") if package_report else None,
        }
    )

    archive_command = [
        sys.executable,
        str(ROOT / "scripts" / "validate_pilot_mydrive_archive.py"),
        "--drive-root",
        str(drive_root),
        "--run-id",
        run_id,
        "--out",
        str(archive_acceptance_report),
        "--require-pass",
    ]
    if args.allow_invalid_archive:
        archive_command.insert(-1, "--allow-invalid-package")
    command_results["mydrive_archive_acceptance"] = _run_command(archive_command)
    archive_decision, archive_report, archive_error = _read_report_decision(archive_acceptance_report)
    checks.append(
        {
            "check_name": "mydrive_archive_acceptance_pass",
            "status": "pass" if archive_decision == "pass" or args.allow_invalid_archive else "fail",
            "overall_decision": archive_decision,
            "error": archive_error,
            "allow_invalid_archive": bool(args.allow_invalid_archive),
            "blocking_issue_count": archive_report.get("summary", {}).get("blocking_issue_count") if archive_report else None,
        }
    )

    failing_checks = [check for check in checks if check.get("status") != "pass"]
    report = {
        "artifact_name": REPORT_NAME,
        "overall_decision": "pass" if not failing_checks else "fail",
        "source_manifest_path": str(manifest_path),
        "workspace": manifest.get("workspace"),
        "run_id": run_id,
        "run_image_generation": manifest.get("run_image_generation"),
        "allow_existing_image_generation": bool(args.allow_existing_image_generation),
        "allow_incomplete_package": bool(args.allow_incomplete_package),
        "allow_invalid_archive": bool(args.allow_invalid_archive),
        "require_evidence": bool(args.require_evidence),
        "require_image_examples": bool(args.require_image_examples),
        "image_output_root": str(image_output_root),
        "paper_results_package_root": str(paper_package_root),
        "drive_root": str(drive_root),
        "subreport_paths": {
            "image_generation_acceptance": str(image_acceptance_report),
            "paper_results_package_acceptance": str(package_acceptance_report),
            "mydrive_archive_acceptance": str(archive_acceptance_report),
        },
        "checks": checks,
        "command_results": command_results,
        "summary": {
            "check_count": len(checks),
            "failing_check_count": len(failing_checks),
            "image_pair_count": image_report.get("summary", {}).get("image_pair_count") if image_report else None,
            "package_blocking_issue_count": package_report.get("summary", {}).get("blocking_issue_count") if package_report else None,
            "archive_blocking_issue_count": archive_report.get("summary", {}).get("blocking_issue_count") if archive_report else None,
        },
        "acceptance_digest": build_stable_digest({"manifest": manifest, "checks": checks}),
    }
    _write_json(output_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_pass and report["overall_decision"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
