"""验证 paper_workflow 独立 Colab 会话契约。"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from zipfile import ZipFile

import pytest


CONTRACT_PATH = Path("configs/paper_workflow_notebook_contract.json")
NOTEBOOK_ROOT = Path("paper_workflow")


def _notebook_source(path: Path) -> str:
    """读取 Notebook 全部源码, 用于静态边界检查。"""

    payload = json.loads(path.read_text(encoding="utf-8"))
    return "\n".join("".join(cell.get("source", [])) for cell in payload.get("cells", []))


@pytest.mark.quick
def test_paper_workflow_notebook_contract_exists_and_declares_all_notebooks() -> None:
    """机器可读契约必须列出所有正式 paper_workflow Notebook。"""

    payload = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    notebooks = {item["notebook"] for item in payload["notebooks"]}
    expected = {
        "paper_workflow/colab_pilot_image_generation_outputs.ipynb",
        "paper_workflow/baselines/colab_t2smark_baseline_outputs.ipynb",
        "paper_workflow/colab_external_baseline_outputs.ipynb",
        "paper_workflow/colab_paper_results_pipeline.ipynb",
        "paper_workflow/colab_end_to_end_paper_pipeline.ipynb",
        "paper_workflow/colab_ceg_cold_start.ipynb",
    }
    assert expected <= notebooks
    assert "跨会话只能通过 Google Drive 阶段归档 zip" in payload["global_rule"]


@pytest.mark.quick
def test_paper_workflow_code_cells_are_valid_python() -> None:
    """所有 Notebook 代码 cell 必须能被 Python 解析, 避免 Colab 中途暴露语法错误。"""

    for notebook_path in NOTEBOOK_ROOT.glob("*.ipynb"):
        payload = json.loads(notebook_path.read_text(encoding="utf-8"))
        for index, cell in enumerate(payload.get("cells", [])):
            if cell.get("cell_type") != "code":
                continue
            source = "".join(cell.get("source", []))
            ast.parse(source, filename=f"{notebook_path}:cell-{index}")


@pytest.mark.quick
def test_stage_notebooks_do_not_depend_on_legacy_drive_workspace() -> None:
    """分阶段 Notebook 不得依赖固定旧 Drive 工作区, 必须通过阶段归档接续。"""

    checked_notebooks = [
        "colab_paper_results_pipeline.ipynb",
        "colab_external_baseline_outputs.ipynb",
        "colab_end_to_end_paper_pipeline.ipynb",
    ]
    for notebook_name in checked_notebooks:
        source = _notebook_source(NOTEBOOK_ROOT / notebook_name)
        assert "real_pilot_input_workspace_20260617_034500" not in source
        assert "DRIVE_INPUT_WORKSPACE_ROOT" not in source
        assert "shutil.copytree(DRIVE_INPUT_WORKSPACE_ROOT" not in source


@pytest.mark.quick
def test_stage_notebooks_use_drive_archives_for_cross_session_handoff() -> None:
    """跨 Colab 会话的 Notebook 必须显式读取或写出 Drive 阶段归档。"""

    paper_results_source = _notebook_source(NOTEBOOK_ROOT / "colab_paper_results_pipeline.ipynb")
    assert "IMAGE_GENERATION_ARCHIVE" in paper_results_source
    assert "extract_stage_archive" in paper_results_source
    assert "rewrite_image_pairs_for_restored_archive" in paper_results_source
    assert "print_paper_pipeline_failure_reports" in paper_results_source
    assert 'archives" / "image_generation_outputs"' in paper_results_source

    baseline_source = _notebook_source(NOTEBOOK_ROOT / "colab_external_baseline_outputs.ipynb")
    assert "archive_directory_to_drive" in baseline_source
    assert 'archive_group="external_baseline_outputs"' in baseline_source

    image_source = _notebook_source(NOTEBOOK_ROOT / "colab_pilot_image_generation_outputs.ipynb")
    assert "PREPARE_HUGGINGFACE_MODEL_SNAPSHOT = True" in image_source
    assert "prepare_huggingface_snapshot" in image_source
    assert "hf_snapshot_path" in image_source


@pytest.mark.quick
def test_colab_runtime_helper_keeps_environment_logic_outside_main_method() -> None:
    """Colab 环境准备应位于 paper_workflow, 不污染 main 方法包。"""

    helper_source = Path("paper_workflow/colab_utils/runtime.py").read_text(encoding="utf-8")
    assert "prepare_huggingface_snapshot" in helper_source
    assert "archive_directory_to_drive" in helper_source
    assert "extract_stage_archive" in helper_source
    assert "不实现 CEG 主方法" in helper_source



@pytest.mark.quick
def test_extract_stage_archive_strips_legacy_inputs_images_prefix(tmp_path) -> None:
    """阶段恢复工具应兼容已经落盘的旧图像生成 zip 内部路径。"""
    from paper_workflow.colab_utils.runtime import extract_stage_archive

    archive_path = tmp_path / "image_generation_outputs.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("inputs/images/image_pairs.json", "[]")
        archive.writestr("inputs/images/clean/example.png", b"clean")
        archive.writestr("inputs/images/watermarked/example.png", b"watermarked")
        archive.writestr("pilot_stage_progress_summary.json", "{}")

    destination = tmp_path / "workspace" / "inputs" / "images"
    extract_stage_archive(archive_zip_path=archive_path, destination_root=destination)

    assert (destination / "image_pairs.json").is_file()
    assert (destination / "clean" / "example.png").is_file()
    assert (destination / "watermarked" / "example.png").is_file()
    assert not (destination / "inputs" / "images" / "image_pairs.json").exists()
    assert not (destination / "pilot_stage_progress_summary.json").exists()


@pytest.mark.quick
def test_rewrite_image_pairs_for_restored_archive_points_to_current_workspace(tmp_path) -> None:
    """恢复图像归档后, image_pairs.json 中的旧绝对路径应被改写到当前 workspace。"""
    from paper_workflow.colab_utils.runtime import rewrite_image_pairs_for_restored_archive

    image_root = tmp_path / "workspace" / "inputs" / "images"
    (image_root / "clean").mkdir(parents=True)
    (image_root / "watermarked").mkdir(parents=True)
    (image_root / "clean" / "sample_000001.png").write_bytes(b"clean")
    (image_root / "watermarked" / "sample_000001.png").write_bytes(b"watermarked")
    image_pairs_path = image_root / "image_pairs.json"
    image_pairs_path.write_text(
        json.dumps(
            [
                {
                    "image_id": "sample_000001",
                    "clean_image_path": "/content/ceg_runtime/old_run/inputs/images/clean/sample_000001.png",
                    "reference_path": "/content/ceg_runtime/old_run/inputs/images/clean/sample_000001.png",
                    "watermarked_image_path": "/content/ceg_runtime/old_run/inputs/images/watermarked/sample_000001.png",
                    "watermarked_path": "/content/ceg_runtime/old_run/inputs/images/watermarked/sample_000001.png",
                    "clean_sha256": "clean-sha",
                    "watermarked_sha256": "watermarked-sha",
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    report = rewrite_image_pairs_for_restored_archive(
        image_pairs_path=image_pairs_path,
        image_output_root=image_root,
    )

    rewritten = json.loads(image_pairs_path.read_text(encoding="utf-8"))
    row = rewritten[0]
    assert report["overall_decision"] == "pass"
    assert report["rewritten_field_count"] == 4
    assert Path(row["clean_image_path"]).is_file()
    assert Path(row["reference_path"]).is_file()
    assert Path(row["watermarked_image_path"]).is_file()
    assert Path(row["watermarked_path"]).is_file()
    assert str(tmp_path / "workspace") in row["clean_image_path"]
    assert row["clean_sha256"] == "clean-sha"
    assert (image_root / "image_pairs_restored_path_rewrite_report.json").is_file()
