"""验证图像生成产物 Colab Notebook 边界。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


NOTEBOOK_PATH = Path("paper_workflow/colab_pilot_image_generation_outputs.ipynb")


def _notebook_source() -> str:
    """读取 Notebook 所有 cell 源码。"""
    payload = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    return "\n".join("".join(cell.get("source", [])) for cell in payload.get("cells", []))


@pytest.mark.quick
def test_colab_pilot_image_generation_outputs_notebook_exists_and_calls_governed_scripts() -> None:
    """图像生成产物 Notebook 必须调用仓库脚本, 而不是把正式协议逻辑写在 cell 中。"""
    source = _notebook_source()
    required_scripts = [
        "scripts/apply_pilot_image_generation_backend_command.py",
        "scripts/validate_pilot_image_generation_backend_command.py",
        "scripts/run_pilot_image_generation_backend.py",
        "scripts/validate_pilot_image_generation_outputs.py",
        "scripts/build_pilot_stage_progress_summary.py",
        "scripts/build_pilot_image_generation_resume_plan.py",
    ]
    for script in required_scripts:
        assert script in source
    assert "RUN_IMAGE_GENERATION_OUTPUTS = True" in source
    assert "APPLY_EXTERNAL_COMMAND_FROM_NOTEBOOK = True" in source
    assert "REQUIRE_BACKEND_COMMAND_READY = True" in source
    assert '"ceg_content_chain_embedding"' in source
    assert 'SEMANTIC_MASK_BACKEND = "ceg_inspyrenet_semantic_mask"' in source
    assert "CEG_ATTESTATION_KEY" in source
    assert "ckpt_base.pth" in source
    assert "图像生成产物是否完成只以" in source


@pytest.mark.quick
def test_colab_pilot_image_generation_outputs_notebook_does_not_write_formal_manifests_directly() -> None:
    """Notebook 不得直接手写图像生成正式 manifest 或 image_pairs。"""
    source = _notebook_source()
    forbidden_snippets = [
        "image_pairs.json').write_text",
        'image_pairs.json").write_text',
        "image_generation_manifest.json').write_text",
        'image_generation_manifest.json").write_text',
        "image_pair_manifest.json').write_text",
        'image_pair_manifest.json").write_text',
    ]
    for snippet in forbidden_snippets:
        assert snippet not in source


@pytest.mark.quick
def test_colab_pilot_image_generation_outputs_notebook_uses_semantic_stage_wording() -> None:
    """Notebook 不得使用弱阶段编号描述图像生成任务。"""
    source = _notebook_source()
    forbidden_tokens = ["P" + "2", "p" + "2", "RUN_P" + "2"]
    for token in forbidden_tokens:
        assert token not in source


@pytest.mark.quick
def test_colab_pilot_image_generation_outputs_notebook_enforces_drive_workspace_and_archive() -> None:
    """Notebook 必须以 Google Drive 工作区为正式运行和归档位置。"""
    source = _notebook_source()
    assert "STRICT_GOOGLE_DRIVE_PREFLIGHT = True" in source
    assert "ARCHIVE_IMAGE_GENERATION_OUTPUTS = True" in source
    assert "archives" in source
    assert "ZipFile" in source
    assert "Google Drive 工作区缺少图像生成前置文件" in source


@pytest.mark.quick
def test_colab_pilot_image_generation_outputs_notebook_pulls_code_before_drive_artifacts() -> None:
    """Notebook 的运行顺序必须先更新 GitHub 代码, 再检查 Google Drive 前序产物。"""
    source = _notebook_source()
    assert 'REPO_URL = "https://github.com/RICHAAARC/CEG.git"' in source
    assert "UPDATE_REPO_FROM_GITHUB = True" in source
    assert "pull" in source
    assert source.index('git", "clone') < source.index("从 Google Drive 加载前序产物")
    assert '"archives" / "image_generation_outputs"' in source
