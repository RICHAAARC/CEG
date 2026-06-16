"""将论文结果包归档到 Drive 风格的分类目录."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from main.analysis.result_package import PACKAGE_MANIFEST_NAME, validate_paper_results_package
from main.core.digest import build_stable_digest

ARCHIVE_MANIFEST_NAME = "paper_results_package_archive_manifest.json"


def _read_json(path: Path) -> Any:
    """读取 UTF-8 JSON 文件."""
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _file_sha256(path: Path) -> str:
    """计算单个文件的 SHA-256 摘要."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_run_id() -> str:
    """生成适合目录名和文件名的 UTC 运行标识."""
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _copy_tree(source_root: Path, target_root: Path) -> list[str]:
    """复制结果包目录并返回复制后的相对文件路径列表."""
    if target_root.exists():
        shutil.rmtree(target_root)
    target_root.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for source_path in sorted(path for path in source_root.rglob("*") if path.is_file()):
        relative = source_path.relative_to(source_root).as_posix()
        target_path = target_root / relative
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        copied.append(relative)
    return copied


def _write_zip(source_root: Path, archive_path: Path) -> list[str]:
    """将结果包目录写入 zip, 并返回 zip 内部文件路径列表."""
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    if archive_path.exists():
        archive_path.unlink()
    archived: list[str] = []
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as handle:
        for source_path in sorted(path for path in source_root.rglob("*") if path.is_file()):
            relative = source_path.relative_to(source_root).as_posix()
            handle.write(source_path, relative)
            archived.append(relative)
    return archived


def archive_paper_results_package(
    package_root: str | Path,
    drive_root: str | Path,
    *,
    run_id: str | None = None,
    require_validation: bool = True,
) -> dict[str, Any]:
    """把已导出的 paper_results_package 归档到按结果类型区分的 Drive 目录.

    通用工程写法:
    - `package_snapshots/` 保存可直接浏览的目录副本.
    - `package_archives/` 保存便于上传和共享的 zip 文件.
    - `package_manifests/` 保存归档 manifest, 记录输入输出和摘要.

    项目特定写法:
    - 该函数不重新计算论文指标, 只归档已经由 governed records 和 manifests 重建的结果包.
    - 默认要求结果包 validation 通过, 防止把未验证产物误作为论文写作证据。
    """
    source_root = Path(package_root)
    target_drive_root = Path(drive_root)
    if not source_root.is_dir():
        raise FileNotFoundError(f"paper results package directory missing: {source_root}")
    validation = validate_paper_results_package(source_root)
    if require_validation and validation["overall_decision"] != "pass":
        raise ValueError(f"paper results package validation failed: {validation['overall_decision']}")
    package_manifest_path = source_root / PACKAGE_MANIFEST_NAME
    if not package_manifest_path.is_file():
        raise FileNotFoundError(f"paper results package manifest missing: {package_manifest_path}")
    package_manifest = _read_json(package_manifest_path)
    effective_run_id = run_id or _utc_run_id()
    snapshot_root = target_drive_root / "package_snapshots" / effective_run_id / "paper_results_package"
    archive_path = target_drive_root / "package_archives" / f"paper_results_package_{effective_run_id}.zip"
    manifest_path = target_drive_root / "package_manifests" / f"paper_results_package_archive_manifest_{effective_run_id}.json"
    copied_files = _copy_tree(source_root, snapshot_root)
    archived_files = _write_zip(source_root, archive_path)
    manifest = {
        "artifact_name": ARCHIVE_MANIFEST_NAME,
        "run_id": effective_run_id,
        "source_package_root": str(source_root),
        "drive_root": str(target_drive_root),
        "snapshot_root": str(snapshot_root),
        "archive_path": str(archive_path),
        "archive_sha256": _file_sha256(archive_path),
        "archive_byte_count": archive_path.stat().st_size,
        "manifest_path": str(manifest_path),
        "copied_file_count": len(copied_files),
        "archived_file_count": len(archived_files),
        "copied_files": copied_files,
        "archived_files": archived_files,
        "package_digest": package_manifest.get("package_digest") if isinstance(package_manifest, dict) else None,
        "package_validation_decision": validation["overall_decision"],
        "archive_digest": build_stable_digest(
            {
                "run_id": effective_run_id,
                "copied_files": copied_files,
                "archived_files": archived_files,
                "archive_sha256": _file_sha256(archive_path),
            }
        ),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
