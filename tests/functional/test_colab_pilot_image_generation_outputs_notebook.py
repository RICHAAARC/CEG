"""验证 P2 专用 Colab Notebook 边界。"""

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
    """P2 Notebook 必须调用仓库脚本, 而不是把正式协议逻辑写在 cell 中。"""
    source = _notebook_source()
    required_scripts = [
        "scripts/apply_pilot_image_generation_backend_command.py",
        "scripts/validate_pilot_image_generation_backend_command.py",
        "scripts/run_pilot_image_generation_backend.py",
        "scripts/validate_pilot_image_generation_outputs.py",
        "scripts/build_pilot_stage_progress_summary.py",
        "scripts/build_pilot_post_p2_resume_plan.py",
    ]
    for script in required_scripts:
        assert script in source
    assert "RUN_P2_IMAGE_GENERATION = False" in source
    assert "P2 是否完成只以" in source


@pytest.mark.quick
def test_colab_pilot_image_generation_outputs_notebook_does_not_write_formal_manifests_directly() -> None:
    """Notebook 不得直接手写 P2 正式 manifest 或 image_pairs。"""
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
