"""验证 T2SMark 外部 baseline adapter 的 observation 契约。"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest


ADAPTER_PATH = Path("external_baselines/main_table/t2smark/adapter/run_ceg_eval.py")


@pytest.mark.quick
def test_t2smark_adapter_maps_results_to_ceg_observations(tmp_path: Path) -> None:
    """T2SMark results.json 应能映射为 paper_results 可读取的 baseline observations。"""

    image_pairs = tmp_path / "image_pairs.json"
    results = tmp_path / "results.json"
    output = tmp_path / "t2smark_observations.json"
    image_pairs.write_text(
        json.dumps(
            [
                {
                    "image_id": "image_001",
                    "prompt_id": "prompt_001",
                    "split": "calibration",
                    "prompt_text": "a small prompt",
                },
                {
                    "image_id": "image_002",
                    "prompt_id": "prompt_002",
                    "split": "test",
                    "prompt_text": "another small prompt",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    results.write_text(
        json.dumps(
            {
                "0": {"robustness": {"norm1_no_w": 0.2, "norm1_w": 0.8, "acc_key": 1.0, "acc_msg": 0.9}},
                "1": {"robustness": {"norm1_no_w": 0.25, "norm1_w": 0.75, "acc_key": 1.0, "acc_msg": 0.85}},
                "tpr": 1.0,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            str(ADAPTER_PATH),
            "--image-pairs",
            str(image_pairs),
            "--t2smark-results",
            str(results),
            "--out",
            str(output),
        ],
        cwd=".",
        check=True,
    )

    rows = json.loads(output.read_text(encoding="utf-8"))
    manifest = json.loads((tmp_path / "t2smark_ceg_adapter_manifest.json").read_text(encoding="utf-8"))
    assert len(rows) == 4
    assert {row["baseline_id"] for row in rows} == {"t2smark"}
    assert {row["event_id"] for row in rows} == {
        "image_001__clean_negative",
        "image_001__positive_source",
        "image_002__clean_negative",
        "image_002__positive_source",
    }
    assert {row["sample_role"] for row in rows} == {"clean_negative", "positive_source"}
    assert manifest["threshold_source"] == "midpoint_between_min_positive_and_max_negative"
    assert manifest["formal_result_claim"] is False


@pytest.mark.quick
def test_t2smark_adapter_maps_attacked_manifest_roles(tmp_path: Path) -> None:
    """提供 attack manifest 时, adapter 应写出 attacked_positive 和 attacked_negative。"""

    image_pairs = tmp_path / "image_pairs.json"
    results = tmp_path / "results.json"
    attacked_manifest = tmp_path / "attacked_image_manifest.json"
    output = tmp_path / "observations.json"
    image_pairs.write_text(
        json.dumps([{"image_id": "image_001", "prompt_id": "prompt_001", "split": "test"}], ensure_ascii=False),
        encoding="utf-8",
    )
    results.write_text(
        json.dumps({"0": {"robustness": {"norm1_no_w": 0.1, "norm1_w": 0.9}}}, ensure_ascii=False),
        encoding="utf-8",
    )
    attacked_manifest.write_text(
        json.dumps(
            {
                "attacked_images": [
                    {
                        "attacked_image_id": "image_001_brightness",
                        "source_image_id": "image_001",
                        "is_watermarked": True,
                        "attack_family": "brightness_contrast",
                        "attack_condition": "brightness_contrast_light",
                    },
                    {
                        "attacked_image_id": "image_001_clean_brightness",
                        "source_image_id": "image_001",
                        "is_watermarked": False,
                        "attack_family": "brightness_contrast",
                        "attack_condition": "brightness_contrast_light",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            str(ADAPTER_PATH),
            "--image-pairs",
            str(image_pairs),
            "--t2smark-results",
            str(results),
            "--attacked-image-manifest",
            str(attacked_manifest),
            "--out",
            str(output),
            "--threshold",
            "0.5",
        ],
        cwd=".",
        check=True,
    )

    rows = json.loads(output.read_text(encoding="utf-8"))
    attacked_rows = [row for row in rows if str(row["sample_role"]).startswith("attacked_")]
    assert {row["sample_role"] for row in attacked_rows} == {"attacked_positive", "attacked_negative"}
    assert {row["attack_family"] for row in attacked_rows} == {"brightness_contrast"}
    assert all(row["threshold"] == 0.5 for row in rows)
