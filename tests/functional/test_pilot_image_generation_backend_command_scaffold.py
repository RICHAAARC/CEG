"""验证 P2 外部 backend 命令草稿生成器。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest


@pytest.mark.quick
def test_scaffold_pilot_image_generation_backend_command_writes_placeholder_contract(tmp_path) -> None:
    """命令草稿应明确要求用户替换为真实 backend 命令。"""
    out = tmp_path / "configs" / "p2_external_backend_command.draft.json"

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
    assert payload["artifact_name"] == "p2_external_backend_command.draft.json"
    assert "external_command_placeholder" in payload
    assert payload["required_replacement"]["with_field"] == "external_command"
    assert payload["hf_token_status"] == "defined_in_colab_environment_not_written_to_disk"
    assert "image_pairs.json" in payload["required_outputs"]
