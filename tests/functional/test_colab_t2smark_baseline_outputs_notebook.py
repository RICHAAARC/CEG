"""验证 T2SMark 外部 baseline 原生结果 Notebook 的边界。"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest


NOTEBOOK_PATH = Path("paper_workflow/baselines/colab_t2smark_baseline_outputs.ipynb")


def _notebook_source() -> str:
    """读取 Notebook 所有 cell 源码, 用于静态边界检查。"""

    payload = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    return "\n".join("".join(cell.get("source", [])) for cell in payload.get("cells", []))


@pytest.mark.quick
def test_colab_t2smark_baseline_outputs_notebook_exists_and_uses_t2smark_backend() -> None:
    """T2SMark Notebook 应运行外部 T2SMark 本体并写出 results.json。"""

    source = _notebook_source()
    assert NOTEBOOK_PATH.is_file()
    assert "https://github.com/0xD009/T2SMark.git" in source
    assert "run_sd35.py" in source
    assert "stabilityai/stable-diffusion-3.5-medium" in source
    assert "PROMPT_PLAN_PROFILE = \"paper_main_probe\"" in source
    assert "Our GT caption" in source
    assert "external_baseline_inputs\" / \"t2smark\" / \"results.json\"" in source
    assert "archive_group=\"t2smark_baseline_outputs\"" in source
    assert "t2smark_prompt_alignment_manifest.json" in source
    assert "t2smark_backend_run_manifest.json" in source
    assert "t2smark_baseline_output_acceptance_report.json" in source


@pytest.mark.quick
def test_colab_t2smark_baseline_outputs_notebook_keeps_ceg_method_out_of_external_baseline() -> None:
    """T2SMark Notebook 不应调用 CEG 主方法、CEG detection 或 CEG-WM。"""

    source = _notebook_source()
    forbidden_snippets = [
        "RICHAAARC/CEG-WM",
        "D:\\Code\\CEG-WM",
        "run_pilot_real_image_generation_backend.py",
        "run_ceg_detection_producer.py",
        "scripts/run_colab_paper_results_pipeline.py",
        "scripts/build_paper_outputs.py",
        "scripts/run_baseline_plan.py",
    ]
    for snippet in forbidden_snippets:
        assert snippet not in source


@pytest.mark.quick
def test_colab_t2smark_baseline_outputs_notebook_code_cells_parse() -> None:
    """T2SMark Notebook 的代码 cell 必须是可解析 Python, 避免 Colab 运行时语法错误。"""

    payload = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    for index, cell in enumerate(payload.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue
        ast.parse("".join(cell.get("source", [])), filename=f"{NOTEBOOK_PATH}:cell-{index}")
