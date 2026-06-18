"""验证 T2SMark adapter baseline plan 生成脚本。"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.quick
def test_build_t2smark_adapter_baseline_plan_writes_executable_plan(tmp_path) -> None:
    """脚本应把真实输入路径转换为 run_baseline_plan 可消费的单条 T2SMark plan。"""

    image_pairs = tmp_path / "image_pairs.json"
    results = tmp_path / "results.json"
    plan_path = tmp_path / "plans" / "t2smark_baseline_plan.json"
    observation_output = tmp_path / "external_baselines" / "t2smark_observations.json"
    image_pairs.write_text(
        json.dumps([{"image_id": "img_1", "split": "test", "prompt_id": "prompt_1"}]) + "\n",
        encoding="utf-8",
    )
    results.write_text(
        json.dumps({"0": {"robustness": {"norm1_no_w": 0.1, "norm1_w": 0.9}}}) + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_t2smark_adapter_baseline_plan.py",
            "--repo-root",
            ".",
            "--image-pairs",
            str(image_pairs),
            "--t2smark-results",
            str(results),
            "--out",
            str(plan_path),
            "--observation-output",
            str(observation_output),
            "--working-directory",
            ".",
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert len(plan) == 1
    row = plan[0]
    assert row["baseline_id"] == "t2smark"
    assert row["output_path"] == str(observation_output.resolve())
    assert row["working_directory"] == str(Path(".").resolve())
    command = row["command"]
    assert "external_baselines" in " ".join(command)
    assert "--image-pairs" in command
    assert str(image_pairs.resolve()) in command
    assert "--t2smark-results" in command
    assert str(results.resolve()) in command
    assert "--out" in command
    assert str(observation_output.resolve()) in command


@pytest.mark.quick
def test_build_t2smark_adapter_baseline_plan_rejects_missing_results(tmp_path) -> None:
    """缺少 T2SMark results.json 时应在生成 plan 阶段提前失败。"""

    image_pairs = tmp_path / "image_pairs.json"
    image_pairs.write_text("[]\n", encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_t2smark_adapter_baseline_plan.py",
            "--repo-root",
            ".",
            "--image-pairs",
            str(image_pairs),
            "--t2smark-results",
            str(tmp_path / "missing_results.json"),
            "--out",
            str(tmp_path / "plan.json"),
            "--observation-output",
            str(tmp_path / "observations.json"),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "T2SMark results.json" in completed.stderr
