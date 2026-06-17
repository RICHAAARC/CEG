"""验证 P2 真实图像生成 backend 包装入口。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest


@pytest.mark.quick
def test_pilot_image_generation_backend_wrapper_requires_external_command(tmp_path) -> None:
    """包装入口不得在缺少真实 backend 时伪造 P2 图像输出。"""
    prompt_plan = tmp_path / "prompt_plan.json"
    model_config = tmp_path / "model_config.json"
    output_root = tmp_path / "images"
    prompt_plan.write_text(json.dumps({"prompts": []}), encoding="utf-8")
    model_config.write_text(json.dumps({"model_id": "test"}), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_pilot_image_generation_backend.py",
            "--prompt-plan",
            str(prompt_plan),
            "--out",
            str(output_root),
            "--model-config",
            str(model_config),
            "--require-pass",
        ],
        cwd=".",
        check=False,
        text=True,
        capture_output=True,
    )

    report = json.loads((output_root / "pilot_image_generation_backend_wrapper_report.json").read_text(encoding="utf-8"))
    assert completed.returncode == 1
    assert report["overall_decision"] == "fail"
    assert report["blocking_issue"] == "missing_external_backend_command"
    assert report["implementation_boundary"]["runs_stable_diffusion_itself"] is False
    assert not (output_root / "image_pairs.json").exists()


@pytest.mark.quick
def test_pilot_image_generation_backend_wrapper_rejects_placeholder_command_file(tmp_path) -> None:
    """包装入口读取命令文件时, 必须拒绝尚未替换的 placeholder 草稿。"""
    prompt_plan = tmp_path / "prompt_plan.json"
    model_config = tmp_path / "model_config.json"
    command_file = tmp_path / "p2_external_backend_command.draft.json"
    output_root = tmp_path / "images"
    prompt_plan.write_text(json.dumps({"prompts": []}), encoding="utf-8")
    model_config.write_text(json.dumps({"model_id": "test"}), encoding="utf-8")
    command_file.write_text(
        json.dumps({"external_command_placeholder": ["python", "/content/replace_with_backend.py"]}),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_pilot_image_generation_backend.py",
            "--prompt-plan",
            str(prompt_plan),
            "--out",
            str(output_root),
            "--model-config",
            str(model_config),
            "--external-command-json-file",
            str(command_file),
            "--require-pass",
        ],
        cwd=".",
        check=False,
        text=True,
        capture_output=True,
    )

    report = json.loads((output_root / "pilot_image_generation_backend_wrapper_report.json").read_text(encoding="utf-8"))
    assert completed.returncode == 1
    assert report["blocking_issue"] == "external_command_json_file_placeholder_not_replaced"


@pytest.mark.quick
def test_pilot_image_generation_backend_wrapper_accepts_real_backend_outputs(tmp_path) -> None:
    """真实 backend 写出契约文件后, 包装入口应运行 P2 接收门禁。"""
    prompt_plan = tmp_path / "prompt_plan.json"
    model_config = tmp_path / "model_config.json"
    output_root = tmp_path / "images"
    prompt_plan.write_text(json.dumps({"prompts": [{"prompt_id": "p1", "prompt_text": "test"}]}), encoding="utf-8")
    model_config.write_text(json.dumps({"model_id": "test"}), encoding="utf-8")
    producer_code = r'''
from pathlib import Path
import json
import sys
root = Path(sys.argv[1])
(root / "clean").mkdir(parents=True, exist_ok=True)
(root / "watermarked").mkdir(parents=True, exist_ok=True)
(root / "image_manifests").mkdir(parents=True, exist_ok=True)
(root / "prompt_plan.json").write_text(json.dumps({"prompts": [{"prompt_id": "p1"}]}), encoding="utf-8")
(root / "clean" / "image_0001.png").write_bytes(b"clean-image-bytes")
(root / "watermarked" / "image_0001.png").write_bytes(b"watermarked-image-bytes")
(root / "image_pairs.json").write_text(json.dumps([{"image_id": "image_0001", "clean_image_path": "clean/image_0001.png", "watermarked_image_path": "watermarked/image_0001.png"}]), encoding="utf-8")
(root / "image_manifests" / "image_generation_manifest.json").write_text(json.dumps({"record_count": 1}), encoding="utf-8")
(root / "image_manifests" / "image_pair_manifest.json").write_text(json.dumps({"image_pair_count": 1}), encoding="utf-8")
'''

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_pilot_image_generation_backend.py",
            "--prompt-plan",
            str(prompt_plan),
            "--out",
            str(output_root),
            "--model-config",
            str(model_config),
            "--require-pass",
            "--external-command",
            sys.executable,
            "-c",
            producer_code,
            str(output_root),
        ],
        cwd=".",
        check=False,
        text=True,
        capture_output=True,
    )

    wrapper_report = json.loads((output_root / "pilot_image_generation_backend_wrapper_report.json").read_text(encoding="utf-8"))
    acceptance_report = json.loads((output_root / "pilot_image_generation_output_acceptance_report.json").read_text(encoding="utf-8"))
    assert completed.returncode == 0, completed.stderr
    assert wrapper_report["overall_decision"] == "pass"
    assert wrapper_report["external_command_returncode"] == 0
    assert acceptance_report["overall_decision"] == "pass"
    assert acceptance_report["summary"]["image_pair_count"] == 1
