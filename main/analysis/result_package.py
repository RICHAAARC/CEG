"""导出和校验论文结果输出包。

该模块把 `scripts/build_paper_outputs.py` 生成的 records、tables、figures、reports、LaTeX、PDF、readiness 和 claim audit 复制到一个独立结果包目录。
它不重新计算指标, 只做可复现交付层的文件收集、完整性摘要和 manifest 校验。
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from main.core.digest import build_stable_digest

PACKAGE_MANIFEST_NAME = "paper_results_package_manifest.json"

CORE_OUTPUT_FILES = (
    "event_records.json",
    "paper_outputs_summary.json",
    "paper_readiness_report.json",
    "paper_results_report.md",
    "paper_results_report_manifest.json",
)

SOURCE_MANIFEST_FILES = (
    "artifacts/artifact_manifest.json",
    "rendered_figures/rendered_paper_figures_manifest.json",
    "latex_tables/latex_tables_manifest.json",
    "pdf_figures/paper_figures_pdf_manifest.json",
    "paper_results_report_manifest.json",
    "image_manifests/image_generation_manifest.json",
    "image_manifests/image_pair_manifest.json",
    "image_examples/image_example_manifest.json",
    "baseline_results/baseline_execution_manifest.json",
)


def _read_json(path: Path) -> Any:
    """读取 JSON 文件, 支持带 BOM 的 UTF-8。"""
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _file_sha256(path: Path) -> str:
    """计算单个文件的 SHA-256 摘要。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_files(output_root: Path) -> list[str]:
    """从 artifact manifest 收集核心 JSON / CSV 产物。"""
    manifest_path = output_root / "artifacts" / "artifact_manifest.json"
    if not manifest_path.exists():
        return ["artifacts/artifact_manifest.json"]
    manifest = _read_json(manifest_path)
    names = manifest.get("artifact_names", []) if isinstance(manifest, dict) else []
    return ["artifacts/artifact_manifest.json", *[f"artifacts/{name}" for name in names]]


def _rendered_figure_files(output_root: Path) -> list[str]:
    """从 rendered figure manifest 收集 HTML 和 SVG 图表。"""
    manifest_path = output_root / "rendered_figures" / "rendered_paper_figures_manifest.json"
    if not manifest_path.exists():
        return ["rendered_figures/rendered_paper_figures_manifest.json"]
    manifest = _read_json(manifest_path)
    files = ["rendered_figures/rendered_paper_figures_manifest.json"]
    if isinstance(manifest, dict):
        report_path = str(manifest.get("report_path", "paper_figures_report.html"))
        files.append(f"rendered_figures/{report_path}")
        for item in manifest.get("rendered_figures", []):
            if isinstance(item, dict) and item.get("svg_path"):
                files.append(f"rendered_figures/{item['svg_path']}")
    return files


def _latex_files(output_root: Path) -> list[str]:
    """从 LaTeX manifest 收集 LaTeX 表格。"""
    manifest_path = output_root / "latex_tables" / "latex_tables_manifest.json"
    if not manifest_path.exists():
        return ["latex_tables/latex_tables_manifest.json"]
    manifest = _read_json(manifest_path)
    names = manifest.get("latex_tables", []) if isinstance(manifest, dict) else []
    return ["latex_tables/latex_tables_manifest.json", *[f"latex_tables/{name}" for name in names]]


def _pdf_files(output_root: Path) -> list[str]:
    """从 PDF manifest 收集 PDF 图表预览。"""
    manifest_path = output_root / "pdf_figures" / "paper_figures_pdf_manifest.json"
    if not manifest_path.exists():
        return ["pdf_figures/paper_figures_pdf_manifest.json"]
    manifest = _read_json(manifest_path)
    pdf_name = str(manifest.get("pdf_path", "paper_figures_preview.pdf")) if isinstance(manifest, dict) else "paper_figures_preview.pdf"
    return ["pdf_figures/paper_figures_pdf_manifest.json", f"pdf_figures/{pdf_name}"]


def _image_manifest_files(output_root: Path) -> list[str]:
    """收集可选图像 provenance manifest。"""
    candidates = [
        "image_manifests/image_generation_manifest.json",
        "image_manifests/image_pair_manifest.json",
        "image_examples/image_example_manifest.json",
        "image_manifests/attacked_image_manifest.json",
        "image_manifests/attack_shard_manifest.json",
    ]
    return [relative for relative in candidates if (output_root / relative).is_file()]


def _image_example_files(output_root: Path) -> list[str]:
    """从 image_example_manifest 收集示例图文件。"""
    manifest_path = output_root / "image_examples" / "image_example_manifest.json"
    if not manifest_path.exists():
        return []
    manifest = _read_json(manifest_path)
    files = ["image_examples/image_example_manifest.json"]
    if isinstance(manifest, dict):
        for item in manifest.get("examples", []):
            if isinstance(item, dict) and item.get("relative_path"):
                files.append(str(item["relative_path"]))
    return files


def _baseline_result_files(output_root: Path) -> list[str]:
    """收集可选外部 baseline observation 和执行 manifest。"""
    candidates = [
        "baseline_results/baseline_observations.json",
        "baseline_results/baseline_execution_manifest.json",
    ]
    return [relative for relative in candidates if (output_root / relative).is_file()]


def collect_paper_result_files(output_root: str | Path) -> list[str]:
    """收集一个完整论文结果输出目录中应进入交付包的相对路径。"""
    root = Path(output_root)
    candidates = [
        *CORE_OUTPUT_FILES,
        *_artifact_files(root),
        *_rendered_figure_files(root),
        *_latex_files(root),
        *_pdf_files(root),
        *_image_manifest_files(root),
        *_image_example_files(root),
        *_baseline_result_files(root),
    ]
    return sorted(dict.fromkeys(str(path).replace("\\", "/") for path in candidates))


def _readiness_decision(output_root: Path) -> str | None:
    """读取 readiness 总体结论。"""
    path = output_root / "paper_readiness_report.json"
    if not path.exists():
        return None
    payload = _read_json(path)
    return str(payload.get("overall_decision")) if isinstance(payload, dict) else None


def _claim_audit_decision(output_root: Path) -> str | None:
    """读取 claim audit 总体结论。"""
    path = output_root / "artifacts" / "paper_claim_audit.json"
    if not path.exists():
        return None
    payload = _read_json(path)
    return str(payload.get("overall_decision")) if isinstance(payload, dict) else None


def build_paper_results_package_manifest(
    source_output_root: str | Path,
    copied_files: list[str],
    *,
    missing_files: list[str] | None = None,
) -> dict[str, Any]:
    """构建结果包 manifest, 记录文件摘要和来源 manifest。"""
    source_root = Path(source_output_root)
    file_entries = []
    for relative in copied_files:
        source_path = source_root / relative
        file_entries.append(
            {
                "relative_path": relative,
                "byte_count": source_path.stat().st_size,
                "sha256": _file_sha256(source_path),
            }
        )
    return {
        "artifact_name": PACKAGE_MANIFEST_NAME,
        "package_status": "complete" if not missing_files else "incomplete",
        "source_output_root": str(source_root),
        "copied_files": copied_files,
        "missing_files": list(missing_files or []),
        "file_count": len(copied_files),
        "package_digest": build_stable_digest(file_entries),
        "source_manifests": list(SOURCE_MANIFEST_FILES),
        "readiness_decision": _readiness_decision(source_root),
        "claim_audit_decision": _claim_audit_decision(source_root),
        "files": file_entries,
    }


def export_paper_results_package(
    source_output_root: str | Path,
    package_root: str | Path,
    *,
    require_readiness: bool = True,
) -> dict[str, Any]:
    """把论文输出目录导出为独立结果包并写出 manifest。"""
    source_root = Path(source_output_root)
    target_root = Path(package_root)
    readiness_decision = _readiness_decision(source_root)
    if require_readiness and readiness_decision != "pass":
        raise ValueError(f"paper outputs are not readiness-pass: {readiness_decision}")
    relative_files = collect_paper_result_files(source_root)
    missing = sorted(relative for relative in relative_files if not (source_root / relative).is_file())
    if missing:
        raise FileNotFoundError(f"paper output files missing: {missing}")
    if target_root.exists():
        shutil.rmtree(target_root)
    target_root.mkdir(parents=True, exist_ok=True)
    for relative in relative_files:
        source_path = source_root / relative
        target_path = target_root / relative
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
    manifest = build_paper_results_package_manifest(source_root, relative_files, missing_files=[])
    (target_root / PACKAGE_MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def validate_paper_results_package(package_root: str | Path) -> dict[str, Any]:
    """校验导出的结果包文件是否与 manifest 摘要一致。"""
    root = Path(package_root)
    manifest_path = root / PACKAGE_MANIFEST_NAME
    if not manifest_path.exists():
        return {
            "artifact_name": "paper_results_package_validation.json",
            "overall_decision": "fail",
            "checks": [{"requirement": "package_manifest_present", "status": "fail", "evidence": "missing"}],
            "summary": {"total": 1, "fail_count": 1, "pass_count": 0},
        }
    manifest = _read_json(manifest_path)
    checks: list[dict[str, Any]] = []
    if not isinstance(manifest, dict):
        checks.append({"requirement": "package_manifest_parseable", "status": "fail", "evidence": "not_object"})
    else:
        checks.append({"requirement": "package_manifest_parseable", "status": "pass", "evidence": PACKAGE_MANIFEST_NAME})
        file_entries = manifest.get("files", [])
        mismatches = []
        for item in file_entries:
            if not isinstance(item, dict):
                mismatches.append({"reason": "file_entry_not_object"})
                continue
            relative = str(item.get("relative_path"))
            path = root / relative
            if not path.exists():
                mismatches.append({"relative_path": relative, "reason": "missing"})
                continue
            if path.stat().st_size != int(item.get("byte_count", -1)) or _file_sha256(path) != item.get("sha256"):
                mismatches.append({"relative_path": relative, "reason": "digest_or_size_mismatch"})
        status = "fail" if mismatches else "pass"
        checks.append({"requirement": "package_files_match_manifest", "status": status, "evidence": mismatches or len(file_entries)})
        checks.append(
            {
                "requirement": "package_readiness_and_claims_passed",
                "status": "pass" if manifest.get("readiness_decision") == "pass" and manifest.get("claim_audit_decision") == "pass" else "fail",
                "evidence": {
                    "readiness_decision": manifest.get("readiness_decision"),
                    "claim_audit_decision": manifest.get("claim_audit_decision"),
                },
            }
        )
    fail_count = sum(1 for item in checks if item["status"] != "pass")
    return {
        "artifact_name": "paper_results_package_validation.json",
        "overall_decision": "fail" if fail_count else "pass",
        "checks": checks,
        "summary": {"total": len(checks), "fail_count": fail_count, "pass_count": len(checks) - fail_count},
    }
