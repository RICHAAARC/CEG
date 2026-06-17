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


def _read_json_or_issue(path: Path) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """读取 JSON 对象, 并把失败原因转换为可写入报告的 issue。"""

    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # pragma: no cover - 具体异常类型由文件系统和 JSON 解析器决定
        return None, {"issue_type": "unreadable_json", "path": str(path), "error": f"{type(exc).__name__}: {exc}"}
    if not isinstance(payload, dict):
        return None, {"issue_type": "json_not_object", "path": str(path)}
    return payload, None


def _collect_package_archives(drive_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
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
        }
        records.append(record)
        if not record["artifact_name_matches"]:
            issues.append({"issue_type": "unexpected_package_archive_manifest_name", "manifest_path": str(manifest_path)})
        if not record["snapshot_exists"]:
            issues.append({"issue_type": "missing_package_snapshot", "run_id": record["run_id"], "path": record["snapshot_root"]})
        if not record["archive_exists"]:
            issues.append({"issue_type": "missing_package_archive_zip", "run_id": record["run_id"], "path": record["archive_path"]})
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
    package_archives, package_issues = _collect_package_archives(root)
    image_archives, image_issues = _collect_image_archives(root)
    issues = [*package_issues, *image_issues]
    pass_package_archives = [item for item in package_archives if item["package_validation_decision"] == "pass" and item["snapshot_exists"] and item["archive_exists"]]
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
        },
    }


def write_drive_result_inventory(drive_root: str | Path, out: str | Path) -> dict[str, Any]:
    """写出 Drive 结果目录清单。"""

    inventory = build_drive_result_inventory(drive_root)
    output_path = Path(out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return inventory
