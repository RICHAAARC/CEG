"""汇总 Google Drive 风格 CEG 论文结果目录中的可用产物。

该模块属于实验编排与交付物审计层, 不参与水印嵌入、攻击、检测或指标计算。
通用工程写法是: 在远端运行完成后, 通过 manifest 和 zip 文件反查可复用产物。
项目特定写法是: 识别 CEG 当前约定的 `package_snapshots/`、`package_archives/`、
`package_manifests/` 和 `archives/image_generation_outputs/` 目录。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from main.analysis.result_archive import ARCHIVE_MANIFEST_NAME

INVENTORY_NAME = "drive_result_inventory.json"
DEFAULT_REQUIREMENTS_PATH = Path(__file__).resolve().parents[1] / "configs" / "paper_output_requirements.json"


def _read_json_or_issue(path: Path) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """读取 JSON 对象, 并把失败原因转换为可写入报告的 issue。"""

    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # pragma: no cover - 具体异常类型由文件系统和 JSON 解析器决定
        return None, {"issue_type": "unreadable_json", "path": str(path), "error": f"{type(exc).__name__}: {exc}"}
    if not isinstance(payload, dict):
        return None, {"issue_type": "json_not_object", "path": str(path)}
    return payload, None


def _load_paper_output_requirements() -> dict[str, Any]:
    """读取论文结果包要求。

    该清单属于交付物审计配置, 不参与指标计算。Drive inventory 使用它判断归档包是否已经
    包含论文写作需要的核心表格、图表、LaTeX 表、图像 manifest 和示例图。
    """

    payload, issue = _read_json_or_issue(DEFAULT_REQUIREMENTS_PATH)
    if issue is not None or payload is None:
        return {}
    return payload


def _count_manifest_list(path: Path, field_name: str) -> int:
    """读取 manifest 中的列表字段长度, 读取失败时返回0。"""

    payload, issue = _read_json_or_issue(path)
    if issue is not None or payload is None:
        return 0
    value = payload.get(field_name)
    return len(value) if isinstance(value, list) else 0


def _inspect_package_snapshot(snapshot_root: Path, requirements: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """检查 package snapshot 是否包含论文发表结果包所需的核心文件。

    通用工程写法是只做存在性和数量检查, 不重复计算 TPR、FPR 或图像指标。项目特定写法是
    复用 `configs/paper_output_requirements.json` 中的 CEG 论文产物清单。
    """

    if not snapshot_root.is_dir():
        return {
            "snapshot_quality_decision": "fail",
            "missing_required_artifact_count": 0,
            "missing_required_latex_table_count": 0,
            "missing_required_image_manifest_count": 0,
            "rendered_figure_count": 0,
            "image_example_count": 0,
        }, []

    required_artifacts = [f"artifacts/{name}" for name in requirements.get("required_artifacts", [])]
    required_latex = [f"latex_tables/{name}" for name in requirements.get("required_latex_tables", [])]
    required_image_manifests = [str(name) for name in requirements.get("required_image_manifests", [])]
    missing_artifacts = [relative for relative in required_artifacts if not (snapshot_root / relative).is_file()]
    missing_latex = [relative for relative in required_latex if not (snapshot_root / relative).is_file()]
    missing_image_manifests = [
        relative for relative in required_image_manifests if not (snapshot_root / relative).is_file()
    ]
    rendered_figure_count = _count_manifest_list(
        snapshot_root / "rendered_figures" / "rendered_paper_figures_manifest.json",
        "rendered_figures",
    )
    image_example_count = _count_manifest_list(
        snapshot_root / "image_examples" / "image_example_manifest.json",
        "examples",
    )
    minimum_figure_count = int(requirements.get("minimum_figure_count") or 0)
    minimum_image_example_count = int(requirements.get("minimum_image_example_count") or 0)
    issues: list[dict[str, Any]] = []
    for relative in missing_artifacts:
        issues.append({"issue_type": "missing_required_paper_artifact", "relative_path": relative})
    for relative in missing_latex:
        issues.append({"issue_type": "missing_required_latex_table", "relative_path": relative})
    for relative in missing_image_manifests:
        issues.append({"issue_type": "missing_required_image_manifest", "relative_path": relative})
    if rendered_figure_count < minimum_figure_count:
        issues.append(
            {
                "issue_type": "insufficient_rendered_figures",
                "actual": rendered_figure_count,
                "required": minimum_figure_count,
            }
        )
    if image_example_count < minimum_image_example_count:
        issues.append(
            {
                "issue_type": "insufficient_image_examples",
                "actual": image_example_count,
                "required": minimum_image_example_count,
            }
        )
    summary = {
        "snapshot_quality_decision": "pass" if not issues else "fail",
        "missing_required_artifact_count": len(missing_artifacts),
        "missing_required_latex_table_count": len(missing_latex),
        "missing_required_image_manifest_count": len(missing_image_manifests),
        "rendered_figure_count": rendered_figure_count,
        "minimum_rendered_figure_count": minimum_figure_count,
        "image_example_count": image_example_count,
        "minimum_image_example_count": minimum_image_example_count,
    }
    return summary, issues


def _collect_package_archives(drive_root: Path, requirements: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """收集论文结果包归档 manifest, 并检查其 snapshot 与 zip 是否存在。"""

    records: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    manifest_dir = drive_root / "package_manifests"
    for manifest_path in sorted(manifest_dir.glob("paper_results_package_archive_manifest_*.json")):
        payload, issue = _read_json_or_issue(manifest_path)
        if issue is not None:
            issues.append(issue)
            continue
        assert payload is not None
        snapshot_root = Path(str(payload.get("snapshot_root") or ""))
        archive_path = Path(str(payload.get("archive_path") or ""))
        snapshot_quality, snapshot_issues = _inspect_package_snapshot(snapshot_root, requirements)
        record = {
            "run_id": str(payload.get("run_id") or ""),
            "manifest_path": str(manifest_path),
            "artifact_name": payload.get("artifact_name"),
            "artifact_name_matches": payload.get("artifact_name") == ARCHIVE_MANIFEST_NAME,
            "snapshot_root": str(snapshot_root),
            "snapshot_exists": snapshot_root.is_dir(),
            "archive_path": str(archive_path),
            "archive_exists": archive_path.is_file(),
            "package_validation_decision": payload.get("package_validation_decision"),
            "copied_file_count": int(payload.get("copied_file_count") or 0),
            "archived_file_count": int(payload.get("archived_file_count") or 0),
            "package_digest": payload.get("package_digest"),
            "archive_sha256": payload.get("archive_sha256"),
            "snapshot_quality": snapshot_quality,
        }
        records.append(record)
        if not record["artifact_name_matches"]:
            issues.append({"issue_type": "unexpected_package_archive_manifest_name", "manifest_path": str(manifest_path)})
        if not record["snapshot_exists"]:
            issues.append({"issue_type": "missing_package_snapshot", "run_id": record["run_id"], "path": record["snapshot_root"]})
        if not record["archive_exists"]:
            issues.append({"issue_type": "missing_package_archive_zip", "run_id": record["run_id"], "path": record["archive_path"]})
        for snapshot_issue in snapshot_issues:
            issues.append({"run_id": record["run_id"], "snapshot_root": record["snapshot_root"], **snapshot_issue})
    return records, issues


def _collect_image_archives(drive_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """收集图像生成归档 manifest, 并检查其 zip 是否存在。"""

    records: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    image_archive_dir = drive_root / "archives" / "image_generation_outputs"
    for manifest_path in sorted(image_archive_dir.glob("image_generation_outputs_*_manifest.json")):
        payload, issue = _read_json_or_issue(manifest_path)
        if issue is not None:
            issues.append(issue)
            continue
        assert payload is not None
        archive_path = Path(str(payload.get("archive_zip_path") or ""))
        record = {
            "run_id": str(payload.get("run_id") or ""),
            "manifest_path": str(manifest_path),
            "overall_decision": payload.get("overall_decision"),
            "archive_zip_path": str(archive_path),
            "archive_exists": archive_path.is_file(),
            "archived_file_count": int(payload.get("archived_file_count") or 0),
            "records_digest": payload.get("records_digest"),
        }
        records.append(record)
        if not record["archive_exists"]:
            issues.append({"issue_type": "missing_image_generation_archive_zip", "run_id": record["run_id"], "path": record["archive_zip_path"]})
    return records, issues


def build_drive_result_inventory(drive_root: str | Path) -> dict[str, Any]:
    """构建 Drive 结果目录清单, 用于 Colab 正式运行后快速定位论文产物。"""

    root = Path(drive_root)
    requirements = _load_paper_output_requirements()
    package_archives, package_issues = _collect_package_archives(root, requirements)
    image_archives, image_issues = _collect_image_archives(root)
    issues = [*package_issues, *image_issues]
    pass_package_archives = [
        item
        for item in package_archives
        if item["package_validation_decision"] == "pass"
        and item["snapshot_exists"]
        and item["archive_exists"]
        and item["snapshot_quality"]["snapshot_quality_decision"] == "pass"
    ]
    pass_image_archives = [item for item in image_archives if item["overall_decision"] == "pass" and item["archive_exists"]]
    return {
        "artifact_name": INVENTORY_NAME,
        "drive_root": str(root),
        "overall_decision": "pass" if pass_package_archives and pass_image_archives and not issues else "fail",
        "package_archives": package_archives,
        "image_generation_archives": image_archives,
        "blocking_issues": issues,
        "summary": {
            "package_archive_manifest_count": len(package_archives),
            "valid_package_archive_count": len(pass_package_archives),
            "image_generation_archive_manifest_count": len(image_archives),
            "valid_image_generation_archive_count": len(pass_image_archives),
            "blocking_issue_count": len(issues),
            "paper_output_requirements_loaded": bool(requirements),
        },
    }


def write_drive_result_inventory(drive_root: str | Path, out: str | Path) -> dict[str, Any]:
    """写出 Drive 结果目录清单。"""

    inventory = build_drive_result_inventory(drive_root)
    output_path = Path(out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return inventory
