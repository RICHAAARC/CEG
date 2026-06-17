"""测试 Drive 结果目录清单。"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from experiments.drive_result_inventory import build_drive_result_inventory, write_drive_result_inventory

pytestmark = pytest.mark.quick


def _write_json(path: Path, payload: dict) -> None:
    """写出测试 JSON 文件。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_requirements() -> dict:
    """读取真实论文结果包要求, 使测试和正式审计共用同一清单。"""

    return json.loads(Path("configs/paper_output_requirements.json").read_text(encoding="utf-8"))


def _write_formal_package_snapshot(snapshot_root: Path) -> None:
    """写出满足 Drive inventory 深度检查的最小论文结果包 snapshot。"""

    requirements = _load_requirements()
    for artifact_name in requirements["required_artifacts"]:
        path = snapshot_root / "artifacts" / artifact_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("method_name,value\nceg,1\n", encoding="utf-8")
    for latex_name in requirements["required_latex_tables"]:
        path = snapshot_root / "latex_tables" / latex_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("% test table\n", encoding="utf-8")
    for relative in requirements["required_image_manifests"]:
        _write_json(snapshot_root / relative, {"artifact_name": Path(relative).name, "examples": [{"relative_path": "image_examples/clean/example.png"}]})
    figure_count = int(requirements["minimum_figure_count"])
    _write_json(
        snapshot_root / "rendered_figures" / "rendered_paper_figures_manifest.json",
        {
            "artifact_name": "rendered_paper_figures_manifest.json",
            "rendered_figures": [{"figure_id": f"figure_{index:02d}"} for index in range(figure_count)],
        },
    )
    _write_json(
        snapshot_root / "image_examples" / "image_example_manifest.json",
        {
            "artifact_name": "image_example_manifest.json",
            "examples": [{"relative_path": "image_examples/clean/example.png"}],
        },
    )


def test_build_drive_result_inventory_passes_for_complete_drive_layout(tmp_path) -> None:
    """完整 Drive 目录应被识别为可用于论文写作的结果目录。"""

    drive_root = tmp_path / "CEG"
    run_id = "run_001"
    snapshot_root = drive_root / "package_snapshots" / run_id / "paper_results_package"
    snapshot_root.mkdir(parents=True)
    _write_formal_package_snapshot(snapshot_root)
    archive_path = drive_root / "package_archives" / f"paper_results_package_{run_id}.zip"
    archive_path.parent.mkdir(parents=True)
    archive_path.write_bytes(b"zip-placeholder")
    _write_json(
        drive_root / "package_manifests" / f"paper_results_package_archive_manifest_{run_id}.json",
        {
            "artifact_name": "paper_results_package_archive_manifest.json",
            "run_id": run_id,
            "snapshot_root": str(snapshot_root),
            "archive_path": str(archive_path),
            "package_validation_decision": "pass",
            "copied_file_count": 3,
            "archived_file_count": 3,
            "package_digest": "package-digest",
            "archive_sha256": "archive-sha256",
        },
    )
    image_archive_path = drive_root / "archives" / "image_generation_outputs" / f"image_generation_outputs_{run_id}.zip"
    image_archive_path.parent.mkdir(parents=True)
    image_archive_path.write_bytes(b"image-zip-placeholder")
    _write_json(
        drive_root / "archives" / "image_generation_outputs" / f"image_generation_outputs_{run_id}_manifest.json",
        {
            "artifact_name": "image_generation_outputs_archive_manifest.json",
            "overall_decision": "pass",
            "run_id": run_id,
            "archive_zip_path": str(image_archive_path),
            "archived_file_count": 5,
            "records_digest": "records-digest",
        },
    )

    inventory = build_drive_result_inventory(drive_root)

    assert inventory["overall_decision"] == "pass"
    assert inventory["summary"]["valid_package_archive_count"] == 1
    assert inventory["summary"]["valid_image_generation_archive_count"] == 1
    assert inventory["blocking_issues"] == []


def test_write_drive_result_inventory_reports_missing_archives(tmp_path) -> None:
    """缺失 zip 或 snapshot 时应产生阻塞问题。"""

    drive_root = tmp_path / "CEG"
    run_id = "run_002"
    _write_json(
        drive_root / "package_manifests" / f"paper_results_package_archive_manifest_{run_id}.json",
        {
            "artifact_name": "paper_results_package_archive_manifest.json",
            "run_id": run_id,
            "snapshot_root": str(drive_root / "missing_snapshot"),
            "archive_path": str(drive_root / "missing.zip"),
            "package_validation_decision": "pass",
        },
    )
    out = tmp_path / "inventory.json"

    inventory = write_drive_result_inventory(drive_root, out)

    assert out.is_file()
    assert inventory["overall_decision"] == "fail"
    assert {issue["issue_type"] for issue in inventory["blocking_issues"]} >= {
        "missing_package_snapshot",
        "missing_package_archive_zip",
    }


def test_build_drive_result_inventory_requires_image_archive_for_pass(tmp_path) -> None:
    """只有论文结果包而没有图像生成归档时不能判定为完整 pass。"""

    drive_root = tmp_path / "CEG"
    run_id = "run_003"
    snapshot_root = drive_root / "package_snapshots" / run_id / "paper_results_package"
    snapshot_root.mkdir(parents=True)
    _write_formal_package_snapshot(snapshot_root)
    archive_path = drive_root / "package_archives" / f"paper_results_package_{run_id}.zip"
    archive_path.parent.mkdir(parents=True)
    archive_path.write_bytes(b"zip-placeholder")
    _write_json(
        drive_root / "package_manifests" / f"paper_results_package_archive_manifest_{run_id}.json",
        {
            "artifact_name": "paper_results_package_archive_manifest.json",
            "run_id": run_id,
            "snapshot_root": str(snapshot_root),
            "archive_path": str(archive_path),
            "package_validation_decision": "pass",
        },
    )

    inventory = build_drive_result_inventory(drive_root)

    assert inventory["overall_decision"] == "fail"
    assert inventory["summary"]["valid_package_archive_count"] == 1
    assert inventory["summary"]["valid_image_generation_archive_count"] == 0


def test_build_drive_result_inventory_fails_when_package_snapshot_lacks_paper_artifacts(tmp_path) -> None:
    """归档 zip 存在但 snapshot 缺少论文核心产物时不能判定为 pass。"""

    drive_root = tmp_path / "CEG"
    run_id = "run_004"
    snapshot_root = drive_root / "package_snapshots" / run_id / "paper_results_package"
    snapshot_root.mkdir(parents=True)
    archive_path = drive_root / "package_archives" / f"paper_results_package_{run_id}.zip"
    archive_path.parent.mkdir(parents=True)
    archive_path.write_bytes(b"zip-placeholder")
    _write_json(
        drive_root / "package_manifests" / f"paper_results_package_archive_manifest_{run_id}.json",
        {
            "artifact_name": "paper_results_package_archive_manifest.json",
            "run_id": run_id,
            "snapshot_root": str(snapshot_root),
            "archive_path": str(archive_path),
            "package_validation_decision": "pass",
        },
    )
    image_archive_path = drive_root / "archives" / "image_generation_outputs" / f"image_generation_outputs_{run_id}.zip"
    image_archive_path.parent.mkdir(parents=True)
    image_archive_path.write_bytes(b"image-zip-placeholder")
    _write_json(
        drive_root / "archives" / "image_generation_outputs" / f"image_generation_outputs_{run_id}_manifest.json",
        {
            "artifact_name": "image_generation_outputs_archive_manifest.json",
            "overall_decision": "pass",
            "run_id": run_id,
            "archive_zip_path": str(image_archive_path),
        },
    )

    inventory = build_drive_result_inventory(drive_root)

    assert inventory["overall_decision"] == "fail"
    assert inventory["package_archives"][0]["snapshot_quality"]["snapshot_quality_decision"] == "fail"
    issue_types = {issue["issue_type"] for issue in inventory["blocking_issues"]}
    assert "missing_required_paper_artifact" in issue_types


def test_build_drive_result_inventory_cli_require_pass_fails_for_empty_drive(tmp_path) -> None:
    """空 Drive 目录配合 require-pass 时应返回非零退出码。"""

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_drive_result_inventory.py",
            "--drive-root",
            str(tmp_path / "CEG"),
            "--out",
            str(tmp_path / "inventory.json"),
            "--require-pass",
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 1

