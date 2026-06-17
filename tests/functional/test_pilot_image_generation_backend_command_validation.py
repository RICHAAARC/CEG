"""验证 P2 外部 backend 命令文件治理。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from experiments.pilot_image_generation_backend_command import build_backend_command_validation_report


@pytest.mark.quick
def test_backend_command_validation_rejects_placeholder(tmp_path) -> None:
    """校验器必须拒绝仍含 placeholder 的命令草稿。"""
    command_file = tmp_path / "p2_external_backend_command.draft.json"
    command_file.write_text(
        json.dumps({"external_command_placeholder": ["python", "/content/replace_with_backend.py"]}),
        encoding="utf-8",
    )

    report = build_backend_command_validation_report(command_file)

    assert report["overall_decision"] == "fail"
    assert any(issue["issue_type"] == "placeholder_not_replaced" for issue in report["blocking_issues"])


@pytest.mark.quick
def test_apply_backend_command_cli_writes_ready_command_file(tmp_path) -> None:
    """apply CLI 应把真实 argv 写成 external_command 并生成通过的校验报告。"""
    command_file = tmp_path / "p2_external_backend_command.draft.json"
    command_file.write_text(
        json.dumps({"external_command_placeholder": ["python", "/content/replace_with_backend.py"]}),
        encoding="utf-8",
    )
    command = ["python", "/content/backend.py", "--out", "/content/drive/MyDrive/CEG/images"]

    subprocess.run(
        [
            sys.executable,
            "scripts/apply_pilot_image_generation_backend_command.py",
            "--command-file",
            str(command_file),
            "--external-command-json",
            json.dumps(command),
            "--require-ready",
        ],
        cwd=".",
        check=True,
    )

    payload = json.loads(command_file.read_text(encoding="utf-8"))
    report = json.loads((tmp_path / "p2_external_backend_command_validation_report.json").read_text(encoding="utf-8"))
    assert payload["external_command"] == command
    assert "external_command_placeholder" not in payload
    assert payload["manifest_status"] == "ready_for_colab_gpu_execution_unverified"
    assert report["overall_decision"] == "pass"


@pytest.mark.quick
def test_validate_backend_command_cli_fails_for_secret_like_value(tmp_path) -> None:
    """命令文件中不得直接写入疑似 Hugging Face token。"""
    command_file = tmp_path / "p2_external_backend_command.json"
    command_file.write_text(json.dumps({"external_command": ["python", "backend.py", "hf_fake_secret_value"]}), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_pilot_image_generation_backend_command.py",
            "--command-file",
            str(command_file),
            "--require-ready",
        ],
        cwd=".",
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    report = json.loads((tmp_path / "p2_external_backend_command_validation_report.json").read_text(encoding="utf-8"))
    assert any(issue["issue_type"] == "possible_secret_written_to_command" for issue in report["blocking_issues"])
