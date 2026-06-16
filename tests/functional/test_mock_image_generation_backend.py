"""验证 prompt plan 到 mock 图像 manifest 的生成链路。"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from experiments.image_generation_backend import write_mock_image_generation_from_prompt_plan
from main.analysis.attack_images import run_attack_workflow


@pytest.mark.quick
def test_mock_image_generation_backend_writes_prompt_and_image_manifests(tmp_path) -> None:
    """mock backend 应从 prompt plan 生成图像、image_pairs 和可复核 manifests。"""
    prompt_rows = [
        {
            "prompt_id": "prompt_001",
            "prompt_text": "a small dry-run prompt",
            "event_id": "event_001",
            "seed": 7,
            "split": "test",
            "sample_role": "positive_source",
        }
    ]

    manifest = write_mock_image_generation_from_prompt_plan(prompt_rows, tmp_path)

    image_pairs = json.loads((tmp_path / "image_pairs.json").read_text(encoding="utf-8"))
    generation_manifest = json.loads(
        (tmp_path / "image_manifests" / "image_generation_manifest.json").read_text(encoding="utf-8")
    )
    pair_manifest = json.loads((tmp_path / "image_manifests" / "image_pair_manifest.json").read_text(encoding="utf-8"))
    assert manifest["backend_role"] == "mock_backend"
    assert manifest["formal_result_claim"] is False
    assert manifest["prompt_count"] == 1
    assert manifest["image_pair_count"] == 1
    assert generation_manifest["record_count"] == 1
    assert pair_manifest["image_pair_count"] == 1
    assert Path(image_pairs[0]["clean_image_path"]).is_file()
    assert Path(image_pairs[0]["watermarked_image_path"]).is_file()


@pytest.mark.quick
def test_mock_image_generation_cli_outputs_feed_attack_workflow(tmp_path) -> None:
    """CLI 生成的 image_pairs 应能直接进入 attack workflow。"""
    prompt_plan = tmp_path / "prompt_plan_source.json"
    prompt_plan.write_text(
        json.dumps(
            [
                {
                    "prompt_id": "prompt_001",
                    "prompt_text": "a mock image for attack flow",
                    "event_id": "event_001",
                    "seed": 11,
                }
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    generation_root = tmp_path / "generation"
    attack_root = tmp_path / "attack"

    subprocess.run(
        [
            sys.executable,
            "scripts/generate_mock_image_generation.py",
            "--prompt-plan",
            str(prompt_plan),
            "--out",
            str(generation_root),
        ],
        cwd=".",
        check=True,
    )
    image_pairs = json.loads((generation_root / "image_pairs.json").read_text(encoding="utf-8"))
    shard_manifest = run_attack_workflow(image_pairs, attack_root, attack_families=("brightness_contrast",))

    attacked_manifest = json.loads(
        (attack_root / "image_manifests" / "attacked_image_manifest.json").read_text(encoding="utf-8")
    )
    assert shard_manifest["input_image_pair_count"] == 1
    assert attacked_manifest["attacked_image_count"] == 1
    assert Path(attacked_manifest["attacked_images"][0]["attacked_image_path"]).is_file()
