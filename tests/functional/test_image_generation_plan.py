"""验证外部图像生成命令计划接口。"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from experiments.image_generation_plan import load_image_generation_command_plan, validate_image_generation_output_root


@pytest.mark.quick
def test_run_image_generation_plan_accepts_mock_backend_command(tmp_path) -> None:
    """外部图像生成 runner 应能执行命令并校验阶段 2 必需输出。"""
    prompt_plan = tmp_path / "prompt_plan.json"
    backend_output = tmp_path / "backend_output"
    runner_output = tmp_path / "runner_output"
    plan_path = tmp_path / "image_generation_plan.json"
    prompt_plan.write_text(
        json.dumps(
            [
                {
                    "prompt_id": "prompt_001",
                    "prompt_text": "external command plan dry-run prompt",
                    "event_id": "event_001",
                    "seed": 3,
                }
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    plan_path.write_text(
        json.dumps(
            [
                {
                    "backend_id": "mock_external_image_generation",
                    "command": [
                        sys.executable,
                        "scripts/generate_mock_image_generation.py",
                        "--prompt-plan",
                        str(prompt_plan),
                        "--out",
                        str(backend_output),
                    ],
                    "output_root": str(backend_output),
                    "timeout_seconds": 60,
                }
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "scripts/run_image_generation_plan.py",
            "--plan",
            str(plan_path),
            "--out",
            str(runner_output),
            "--require-pass",
        ],
        cwd=".",
        check=True,
    )

    specs = load_image_generation_command_plan(plan_path)
    results = json.loads((runner_output / "image_generation_command_results.json").read_text(encoding="utf-8"))
    contract = validate_image_generation_output_root(backend_output)
    assert specs[0].backend_id == "mock_external_image_generation"
    assert results["pass_count"] == 1
    assert results["results"][0]["output_contract"]["overall_decision"] == "pass"
    assert contract["overall_decision"] == "pass"
    assert (backend_output / "image_pairs.json").is_file()
    assert (backend_output / "image_manifests" / "image_generation_manifest.json").is_file()


@pytest.mark.quick
def test_materialize_image_generation_command_template_outputs_plan(tmp_path) -> None:
    """命令模板物化器应支持 image_generation 类型。"""
    plan_path = tmp_path / "image_generation_command_plan.json"
    subprocess.run(
        [
            sys.executable,
            "scripts/materialize_command_templates.py",
            "--templates",
            "configs/external_image_generation_command_templates.json",
            "--kind",
            "image_generation",
            "--out",
            str(plan_path),
            "--var",
            "image_generation_root=D:/external/sd_backend",
            "--var",
            "prompt_plan_path=D:/data/prompt_plan.json",
            "--var",
            f"output_root={tmp_path / 'generated_images'}",
            "--var",
            "model_config_path=D:/data/model_config.json",
            "--var",
            "external_backend_command_json_path=D:/data/p2_external_backend_command.json",
        ],
        cwd=".",
        check=True,
    )

    rows = json.loads(plan_path.read_text(encoding="utf-8"))
    assert rows[0]["backend_id"] == "external_sd_watermark_backend"
    assert rows[0]["output_root"] == str(tmp_path / "generated_images")
    assert "--prompt-plan" in rows[0]["command"]
