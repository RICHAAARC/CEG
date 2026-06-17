"""验证图像生成产物 Colab Notebook 的运行边界。"""

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
    assert '"--attestation-key-env"' in source
    assert '"--attestation-key-id"' in source
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
def test_colab_pilot_image_generation_outputs_notebook_creates_workspace_without_drive_input_workspace() -> None:
    """Notebook 必须能在空 Drive 下启动, 即从仓库 prompt plan 创建 Colab 本地运行工作区。"""
    source = _notebook_source()
    assert "STRICT_GOOGLE_DRIVE_PREFLIGHT = True" in source
    assert "ARCHIVE_IMAGE_GENERATION_OUTPUTS = True" in source
    assert 'DRIVE_ROOT = Path("/content/drive/MyDrive/CEG")' in source
    assert 'LOCAL_RUNTIME_ROOT = Path("/content/ceg_runtime")' in source
    assert 'RUN_ID = f"{PROMPT_PLAN_PROFILE}_image_generation_outputs"' in source
    assert "DRIVE_INPUT_WORKSPACE_ROOT" not in source
    assert "real_pilot_input_workspace" not in source
    assert "shutil.copytree(DRIVE_INPUT_WORKSPACE_ROOT, PILOT_WORKSPACE_ROOT)" not in source
    assert "prepare_local_runtime_workspace()" in source
    assert "write_default_model_config()" in source
    assert "MODEL_CONFIG_DEFAULTS" in source
    assert "已创建 Colab 本地运行工作区" in source
    assert "archives" in source
    assert "ZipFile" in source
    assert 'PROMPT_PLAN = REPO_ROOT / "prompts" / "prompt_plans" / f"{PROMPT_PLAN_PROFILE}_prompt_plan.json"' in source
    assert 'PROMPT_PLAN_PROFILE = "paper_main_probe"' in source
    assert "仓库内置 prompt plan" in source


@pytest.mark.quick
def test_colab_pilot_image_generation_outputs_notebook_pulls_code_before_local_workspace() -> None:
    """Notebook 的运行顺序必须先更新 GitHub 代码, 再创建 Colab 本地运行目录。"""
    source = _notebook_source()
    assert 'REPO_URL = "https://github.com/RICHAAARC/CEG.git"' in source
    assert "UPDATE_REPO_FROM_GITHUB = True" in source
    assert "pull" in source
    assert source.index('git", "clone') < source.index("创建 Colab 本地运行目录")
    assert '"archives" / "image_generation_outputs"' in source


@pytest.mark.quick
def test_colab_pilot_image_generation_outputs_notebook_uses_ceg_wm_aligned_inspyrenet_drive_path() -> None:
    """Notebook 必须使用与 CEG-WM paper_workflow 对齐的 InSPyReNet Drive 权重路径, 不保留旧 CEG 子目录 fallback。"""

    source = _notebook_source()
    assert 'INSPYRENET_WEIGHT_DRIVE_PATH = Path("/content/drive/MyDrive/Models/inspyrenet/ckpt_base.pth")' in source
    legacy_ceg_subdir_path = "/content/drive/MyDrive/CEG" + "/Models/inspyrenet/ckpt_base.pth"
    assert legacy_ceg_subdir_path not in source
    assert "INSPYRENET_WEIGHT_FALLBACK_PATHS" not in source
