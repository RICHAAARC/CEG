"""验证真实 pilot 输入计划模板生成."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from experiments.pilot_input_plan_templates import scaffold_pilot_input_plan_templates


@pytest.mark.quick
def test_scaffold_pilot_input_plan_templates_writes_placeholder_governed_files(tmp_path) -> None:
    """模板应写入工作区, 且待替换字段必须使用 _placeholder 后缀."""
    manifest = scaffold_pilot_input_plan_templates(
        workspace_root=tmp_path,
        run_id="pilot_plan_templates",
    )

    prompt_plan = json.loads((tmp_path / "inputs" / "prompts" / "prompt_plan.draft.json").read_text(encoding="utf-8"))
    model_config = json.loads((tmp_path / "configs" / "model_config.draft.json").read_text(encoding="utf-8"))

    assert manifest["template_status"] == "draft_requires_real_inputs"
    assert prompt_plan["prompts"][0]["prompt_text_placeholder"] == "replace_with_real_prompt_text"
    assert model_config["model_id_placeholder"] == "replace_with_sd_model_id_or_local_path"
    assert (tmp_path / "pilot_input_plan_template_manifest.json").is_file()


@pytest.mark.quick
def test_scaffold_pilot_input_plan_templates_cli(tmp_path) -> None:
    """CLI 应生成 prompt、split、seed、model 和 watermark 配置草稿."""
    subprocess.run(
        [
            sys.executable,
            "scripts/scaffold_pilot_input_plan_templates.py",
            "--workspace",
            str(tmp_path),
            "--run-id",
            "pilot_cli_templates",
        ],
        cwd=".",
        check=True,
    )

    expected = [
        tmp_path / "inputs" / "prompts" / "prompt_plan.draft.json",
        tmp_path / "inputs" / "prompts" / "split_plan.draft.json",
        tmp_path / "inputs" / "prompts" / "seed_plan.draft.json",
        tmp_path / "configs" / "model_config.draft.json",
        tmp_path / "configs" / "watermark_config.draft.json",
        tmp_path / "pilot_input_plan_template_manifest.json",
    ]

    assert all(path.is_file() for path in expected)
