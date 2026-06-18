"""验证 paper_workflow 独立 Colab 会话契约。"""

from __future__ import annotations

import ast
import json
from pathlib import Path

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

