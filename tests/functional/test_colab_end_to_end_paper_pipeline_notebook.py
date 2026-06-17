"""验证端到端论文结果包 Colab Notebook 边界。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


NOTEBOOK_PATH = Path("paper_workflow/colab_end_to_end_paper_pipeline.ipynb")


def _notebook_source() -> str:
    """读取 Notebook 所有 cell 源码。"""

    payload = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    return "\n".join("".join(cell.get("source", [])) for cell in payload.get("cells", []))


@pytest.mark.quick
def test_colab_end_to_end_notebook_calls_single_repo_entrypoint() -> None:
    """Notebook 应调用仓库端到端脚本, 而不是把主流程逻辑写在 cell 中。"""

    source = _notebook_source()
    assert "scripts/run_colab_end_to_end_paper_pipeline.py" in source
    assert "scripts/run_pilot_real_image_generation_backend.py" not in source
    assert "scripts/run_colab_paper_results_pipeline.py" not in source
    assert 'REPO_URL = "https://github.com/RICHAAARC/CEG.git"' in source
    assert "git\", \"clone" in source
    assert "git\", \"-C\", str(REPO_DIR), \"pull" in source


@pytest.mark.quick
def test_colab_end_to_end_notebook_uses_formal_generation_defaults() -> None:
    """Notebook 的默认配置应面向正式图像生成, 并使用 CEG 项目内水印 backend。"""

    source = _notebook_source()
    assert "RUN_IMAGE_GENERATION = True" in source
    assert 'SD_MODEL_ID = "stabilityai/stable-diffusion-3.5-medium"' in source
    assert 'HF_TOKEN_ENV = "HF_TOKEN"' in source
    assert 'WATERMARK_BACKEND = "ceg_content_chain_embedding"' in source
    assert 'SEMANTIC_MASK_BACKEND = "ceg_inspyrenet_semantic_mask"' in source
    assert 'ATTESTATION_KEY_ENV = "CEG_ATTESTATION_KEY"' in source
    assert "ckpt_base.pth" in source
    assert "--semantic-mask-backend" in source
    assert "--detection-formal-result-claim" in source
    assert "CEG-WM" not in source
    assert 'PROMPT_PLAN = REPO_DIR / "prompts" / "prompt_plans" / f"{PROFILE}_prompt_plan.json"' in source


@pytest.mark.quick
def test_colab_end_to_end_notebook_uses_drive_archive_outputs() -> None:
    """Notebook 应把最终产物落在 Google Drive CEG 目录, 并读取统一 manifest。"""

    source = _notebook_source()
    assert 'DRIVE_ROOT = Path("/content/drive/MyDrive/CEG")' in source
    assert "image_generation_archive_zip" in source
    assert "paper_results_package_root" in source
    assert "colab_end_to_end_paper_pipeline_manifest.json" in source
    assert "scripts/validate_colab_end_to_end_formal_run.py" in source
    assert "--require-evidence" in source
    assert "--require-image-examples" in source


@pytest.mark.quick
def test_colab_end_to_end_notebook_uses_ceg_wm_aligned_inspyrenet_drive_path() -> None:
    """Notebook 必须使用与 CEG-WM paper_workflow 对齐的 InSPyReNet Drive 权重路径, 不保留旧 CEG 子目录 fallback。"""

    source = _notebook_source()
    assert 'INSPYRENET_WEIGHT_DRIVE_PATH = Path("/content/drive/MyDrive/Models/inspyrenet/ckpt_base.pth")' in source
    legacy_ceg_subdir_path = "/content/drive/MyDrive/CEG" + "/Models/inspyrenet/ckpt_base.pth"
    assert legacy_ceg_subdir_path not in source
    assert "INSPYRENET_WEIGHT_FALLBACK_PATHS" not in source
