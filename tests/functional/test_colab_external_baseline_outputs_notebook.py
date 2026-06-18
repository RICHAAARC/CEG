"""验证外部 baseline 产物 Colab Notebook 边界。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


NOTEBOOK_PATH = Path("paper_workflow/colab_external_baseline_outputs.ipynb")


def _notebook_source() -> str:
    """读取 Notebook 全部 cell 源码, 用于检查它只调度仓库脚本。"""

    payload = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    return "\n".join("".join(cell.get("source", [])) for cell in payload.get("cells", []))


@pytest.mark.quick
def test_colab_external_baseline_outputs_notebook_runs_baseline_plan_only() -> None:
    """外部 baseline Notebook 应运行 baseline plan, 不实现 CEG 主方法或调用 CEG-WM。"""

    source = _notebook_source()
    assert "scripts/build_t2smark_adapter_baseline_plan.py" in source
    assert "scripts/run_baseline_plan.py" in source
    assert "t2smark_baseline_plan.json" in source
    assert "T2SMARK_RESULTS" in source
    assert "external_baseline_inputs" in source
    assert "baseline_observations.json" in source
    assert "baseline_execution_manifest.json" in source
    assert 'REPO_URL = "https://github.com/RICHAAARC/CEG.git"' in source
    assert "RUN_EXTERNAL_BASELINES = True" in source
    assert "RICHAAARC/CEG-WM" not in source
    assert "D:\\Code\\CEG-WM" not in source
    assert "run_pilot_real_image_generation_backend.py" not in source
    assert "run_ceg_detection_producer.py" not in source
