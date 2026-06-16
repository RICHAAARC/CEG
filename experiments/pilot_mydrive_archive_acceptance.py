"""校验 MyDrive 风格 paper_results_package 归档是否可作为论文结果交付物。

该模块位于 experiments 层, 用于接收 `archive_paper_results_to_drive.py` 已经写出的归档产物。
它不重新构建论文结果包, 只检查 Drive 分类目录中的 snapshot、zip 和 archive manifest 是否一致。

通用工程写法是: 归档后同时校验目录快照、压缩包和 manifest 摘要。项目特定写法是: 固定使用
`package_snapshots/`、`package_archives/` 和 `package_manifests/` 三类目录, 确保论文写作证据可以
从 MyDrive 直接复核。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from main.analysis.result_archive import ARCHIVE_MANIFEST_NAME
from main.analysis.result_package import PACKAGE_MANIFEST_NAME, validate_paper_results_package

REPORT_NAME = "pilot_mydrive_archive_acceptance_report.json"
NEXT_STAGE_ON_PASS = "paper_writing_ready_pilot"
NEXT_STAGE_ON_FAIL = "archive_paper_results_package_and_fix_outputs"


def _read_json(path: Path) -> tuple[Any | None, str | None]:
    """读取 JSON 文件, 返回 payload 与错误信息。"""
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")), None
    except Exception as exc:  # pragma: no cover - 错误类型由底层 JSON / IO 决定
        return None, f"{type(exc).__name__}: {exc}"


def _file_sha256(path: Path) -> str:
    """计算单个文件的 SHA-256 摘要。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _find_manifest_path(drive_root: Path, run_id: str | None, manifest_path: str | Path | None) -> tuple[Path, str | None]:
    """定位 archive manifest, 支持显式路径、run_id 或最新 manifest。"""
    if manifest_path is not None:
        return Path(manifest_path), None
    manifest_dir = drive_root / "package_manifests"
    if run_id:
        return manifest_dir / f"paper_results_package_archive_manifest_{run_id}.json", None
    candidates = sorted(manifest_dir.glob("paper_results_package_archive_manifest_*.json"), key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)
    if not candidates:
        return manifest_dir / "paper_results_package_archive_manifest_<missing>.json", "missing_archive_manifest_candidates"
    return candidates[0], None


def _zip_entries(path: Path) -> tuple[list[str], str | None]:
    """读取 zip 内部文件列表。"""
    try:
        with ZipFile(path) as handle:
            return sorted(handle.namelist()), None
    except Exception as exc:  # pragma: no cover - 错误类型由 zipfile / IO 决定
        return [], f"{type(exc).__name__}: {exc}"


def _snapshot_file_checks(snapshot_root: Path, copied_files: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """检查 snapshot 目录中的 copied_files 是否真实存在。"""
    checks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for relative in copied_files:
        path = snapshot_root / relative
        exists = path.is_file()
        checks.append({"relative_path": relative, "path": str(path), "exists": exists, "byte_count": path.stat().st_size if exists else 0})
        if not exists:
            issues.append({"issue_type": "missing_snapshot_file", "relative_path": relative})
    return checks, issues


def build_pilot_mydrive_archive_acceptance_report(
    drive_root: str | Path,
    *,
    run_id: str | None = None,
    manifest_path: str | Path | None = None,
    require_package_validation: bool = True,
) -> dict[str, Any]:
    """构建 MyDrive 归档输出接收门禁报告。"""
    root = Path(drive_root)
    selected_manifest_path, selection_error = _find_manifest_path(root, run_id, manifest_path)
    manifest_payload, manifest_error = _read_json(selected_manifest_path) if selected_manifest_path.is_file() else (None, selection_error or "missing_archive_manifest")
    issues: list[dict[str, Any]] = []
    if manifest_error is not None:
        issues.append({"issue_type": "unreadable_or_missing_archive_manifest", "path": str(selected_manifest_path), "error": manifest_error})

    manifest_checks: list[dict[str, Any]] = []
    snapshot_checks: list[dict[str, Any]] = []
    zip_checks: list[dict[str, Any]] = []
    snapshot_validation: dict[str, Any] | None = None
    summary = {
        "run_id": run_id,
        "copied_file_count": 0,
        "archived_file_count": 0,
        "zip_entry_count": 0,
        "snapshot_missing_file_count": 0,
        "package_validation_decision": None,
    }

    if isinstance(manifest_payload, dict):
        artifact_name = manifest_payload.get("artifact_name")
        effective_run_id = str(manifest_payload.get("run_id") or run_id or "")
        snapshot_root = Path(str(manifest_payload.get("snapshot_root") or ""))
        archive_path = Path(str(manifest_payload.get("archive_path") or ""))
        copied_files = [str(item) for item in manifest_payload.get("copied_files", [])] if isinstance(manifest_payload.get("copied_files"), list) else []
        archived_files = [str(item) for item in manifest_payload.get("archived_files", [])] if isinstance(manifest_payload.get("archived_files"), list) else []
        summary.update(
            {
                "run_id": effective_run_id,
                "copied_file_count": len(copied_files),
                "archived_file_count": len(archived_files),
                "package_validation_decision": manifest_payload.get("package_validation_decision"),
            }
        )
        manifest_checks.extend(
            [
                {"check_name": "artifact_name_matches", "passes": artifact_name == ARCHIVE_MANIFEST_NAME, "actual": artifact_name},
                {"check_name": "package_validation_pass", "passes": manifest_payload.get("package_validation_decision") == "pass", "actual": manifest_payload.get("package_validation_decision")},
                {"check_name": "snapshot_root_exists", "passes": snapshot_root.is_dir(), "path": str(snapshot_root)},
                {"check_name": "archive_zip_exists", "passes": archive_path.is_file(), "path": str(archive_path)},
                {"check_name": "copied_and_archived_counts_match", "passes": len(copied_files) == len(archived_files), "copied_file_count": len(copied_files), "archived_file_count": len(archived_files)},
                {"check_name": "package_manifest_in_snapshot", "passes": (snapshot_root / PACKAGE_MANIFEST_NAME).is_file(), "path": str(snapshot_root / PACKAGE_MANIFEST_NAME)},
            ]
        )
        if require_package_validation and manifest_payload.get("package_validation_decision") != "pass":
            issues.append({"issue_type": "archive_package_validation_not_pass", "actual": manifest_payload.get("package_validation_decision")})
        if archive_path.is_file():
            actual_sha256 = _file_sha256(archive_path)
            manifest_sha256 = manifest_payload.get("archive_sha256")
            zip_entries, zip_error = _zip_entries(archive_path)
            summary["zip_entry_count"] = len(zip_entries)
            zip_checks.extend(
                [
                    {"check_name": "archive_sha256_matches", "passes": actual_sha256 == manifest_sha256, "actual": actual_sha256, "expected": manifest_sha256},
                    {"check_name": "zip_readable", "passes": zip_error is None, "zip_error": zip_error},
                    {"check_name": "zip_entries_match_manifest", "passes": zip_entries == sorted(archived_files), "zip_entry_count": len(zip_entries), "archived_file_count": len(archived_files)},
                    {"check_name": "package_manifest_in_zip", "passes": PACKAGE_MANIFEST_NAME in zip_entries},
                ]
            )
            if zip_error is not None:
                issues.append({"issue_type": "archive_zip_unreadable", "error": zip_error})
            if zip_entries != sorted(archived_files):
                issues.append({"issue_type": "archive_zip_entries_mismatch"})
            if actual_sha256 != manifest_sha256:
                issues.append({"issue_type": "archive_sha256_mismatch", "actual": actual_sha256, "expected": manifest_sha256})
        snapshot_checks, snapshot_issues = _snapshot_file_checks(snapshot_root, copied_files) if snapshot_root.is_dir() else ([], [])
        summary["snapshot_missing_file_count"] = len(snapshot_issues)
        issues.extend(snapshot_issues)
        if snapshot_root.is_dir():
            snapshot_validation = validate_paper_results_package(snapshot_root)
            manifest_checks.append({"check_name": "snapshot_package_validation_pass", "passes": snapshot_validation.get("overall_decision") == "pass", "overall_decision": snapshot_validation.get("overall_decision")})
            if require_package_validation and snapshot_validation.get("overall_decision") != "pass":
                issues.append({"issue_type": "snapshot_package_validation_not_pass", "overall_decision": snapshot_validation.get("overall_decision")})
        for check in [*manifest_checks, *zip_checks]:
            if not check.get("passes"):
                issues.append({"issue_type": "archive_manifest_check_failed", "check_name": check.get("check_name"), "actual": check.get("actual"), "path": check.get("path")})
    elif manifest_payload is not None:
        issues.append({"issue_type": "archive_manifest_not_object"})

    overall_decision = "pass" if not issues else "fail"
    return {
        "artifact_name": REPORT_NAME,
        "drive_root": str(root),
        "selected_archive_manifest_path": str(selected_manifest_path),
        "overall_decision": overall_decision,
        "recommended_next_stage": NEXT_STAGE_ON_PASS if overall_decision == "pass" else NEXT_STAGE_ON_FAIL,
        "require_package_validation": bool(require_package_validation),
        "manifest_checks": manifest_checks,
        "zip_checks": zip_checks,
        "snapshot_file_checks": snapshot_checks,
        "snapshot_package_validation": snapshot_validation,
        "blocking_issues": issues,
        "summary": {
            **summary,
            "blocking_issue_count": len(issues),
        },
    }


def write_pilot_mydrive_archive_acceptance_report(
    drive_root: str | Path,
    out: str | Path,
    *,
    run_id: str | None = None,
    manifest_path: str | Path | None = None,
    require_package_validation: bool = True,
) -> dict[str, Any]:
    """写出 MyDrive 归档输出接收门禁报告。"""
    report = build_pilot_mydrive_archive_acceptance_report(
        drive_root,
        run_id=run_id,
        manifest_path=manifest_path,
        require_package_validation=require_package_validation,
    )
    output_path = Path(out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
