"""验证 图像生成 backend 命令草稿生成器。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest


@pytest.mark.quick
def test_scaffold_pilot_image_generation_backend_command_writes_real_backend_contract(tmp_path) -> None:
    """命令文件应指向仓库内真实 backend 入口。"""
    out = tmp_path / "configs" / "image_generation_backend_command.draft.json"

    subprocess.run(
        [
            sys.executable,
            "scripts/scaffold_pilot_image_generation_backend_command.py",
            "--workspace",
            str(tmp_path),
            "--out",
            str(out),
        ],
        cwd=".",
        check=True,
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["artifact_name"] == "image_generation_backend_command.draft.json"
    assert "external_command" in payload
    assert "run_pilot_real_image_generation_backend.py" in payload["external_command"][1]
    assert payload["command_contract"]["must_run_real_sd_backend"] is True
    assert payload["command_contract"]["must_run_real_watermark_backend"] is True
    assert payload["hf_token_status"] == "defined_in_colab_environment_not_written_to_disk"
    assert "image_pairs.json" in payload["required_outputs"]
