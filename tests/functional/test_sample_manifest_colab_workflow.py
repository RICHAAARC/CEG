"""验证真实实验样本清单到 Colab 论文链路的转换能力。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from experiments.sample_manifest import build_image_pair_rows, build_protocol_events_from_sample_rows
from experiments.threshold_calibration import build_threshold_calibration_report, threshold_for_target_fpr
from paper_workflow.colab_utils.cold_start import build_colab_command_plan, build_colab_input_manifest


def _sample_rows(tmp_path):
    reference = tmp_path / "reference.ppm"
    watermarked = tmp_path / "watermarked.ppm"
    reference.write_text("P3\n1 1\n255\n10 20 30\n", encoding="ascii")
    watermarked.write_text("P3\n1 1\n255\n12 21 29\n", encoding="ascii")
    return [
        {
            "event_id": "sample_001",
            "split": "test",
            "sample_role": "positive_source",
            "attack_family": "clean",
            "attack_condition": "clean_none",
            "is_watermarked": True,
            "content_score_raw": 0.72,
            "content_score_aligned": 0.74,
            "attestation_score": 0.91,
            "registration_confidence": 0.9,
            "anchor_inlier_ratio": 0.84,
            "recovered_sync_consistency": 0.88,
            "reference_path": str(reference),
            "watermarked_path": str(watermarked),
        }
    ]


@pytest.mark.quick
def test_sample_manifest_rows_build_protocol_events_and_image_pairs(tmp_path) -> None:
    """样本清单应能转换为 CEG 协议事件和图像质量指标配对。"""
    rows = _sample_rows(tmp_path)
    events = build_protocol_events_from_sample_rows(rows, {"ceg": 0.5})
    pairs = build_image_pair_rows(rows)

    assert events[0]["event_id"] == "sample_001"
    assert events[0]["payload"]["thresholds"]["content_threshold"] == 0.5
    assert events[0]["payload"]["content"]["content_score_raw"] == 0.72
    assert "Full" in events[0]["payload"]["ceg_ablation_variants"]
    assert pairs[0]["event_id"] == "sample_001"
    assert pairs[0]["method_name"] == "ceg"


@pytest.mark.quick
def test_build_protocol_events_from_sample_manifest_cli_writes_events_and_pairs(tmp_path) -> None:
    """CLI 应写出 events.json、image_pairs.json 和转换 manifest。"""
    sample_path = tmp_path / "samples.json"
    threshold_path = tmp_path / "thresholds.json"
    output_root = tmp_path / "prepared_inputs"
    sample_path.write_text(json.dumps(_sample_rows(tmp_path), ensure_ascii=False), encoding="utf-8")
    threshold_path.write_text(json.dumps({"ceg": 0.5}), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "scripts/build_protocol_events_from_sample_manifest.py",
            "--samples",
            str(sample_path),
            "--thresholds",
            str(threshold_path),
            "--out",
            str(output_root),
        ],
        cwd=".",
        check=True,
        text=True,
        capture_output=True,
    )

    manifest = json.loads((output_root / "sample_event_build_manifest.json").read_text(encoding="utf-8"))
    events = json.loads((output_root / "events.json").read_text(encoding="utf-8"))
    pairs = json.loads((output_root / "image_pairs.json").read_text(encoding="utf-8"))
    assert manifest["event_count"] == 1
    assert manifest["image_pair_count"] == 1
    assert events[0]["event_id"] == "sample_001"
    assert pairs[0]["reference_path"].endswith("reference.ppm")


@pytest.mark.quick
def test_colab_plan_accepts_sample_manifest_and_basic_image_metrics(tmp_path) -> None:
    """真实实验模式可由样本清单生成 events, 并接入轻量图像质量指标命令。"""
    sample_path = tmp_path / "samples.json"
    threshold_path = tmp_path / "thresholds.json"
    sample_path.write_text(json.dumps(_sample_rows(tmp_path), ensure_ascii=False), encoding="utf-8")
    threshold_path.write_text(json.dumps({"ceg": 0.5}), encoding="utf-8")

    plan = build_colab_command_plan(
        ".",
        tmp_path / "workspace",
        use_dry_run_inputs=False,
        sample_manifest_path=sample_path,
        thresholds_path=threshold_path,
        compute_basic_image_metrics=True,
    )
    input_manifest = build_colab_input_manifest(plan)

    assert "build_protocol_events_from_sample_manifest.py" in " ".join(plan["prepare_command"])
    assert "compute_image_quality_metrics.py" in " ".join(plan["basic_metric_command"])
    assert "--metric-rows" in plan["build_command"]
    assert plan["generated_image_pairs_path"].endswith("image_pairs.json")
    assert input_manifest["missing_required_inputs"] == []


@pytest.mark.quick
def test_threshold_calibration_uses_calibration_clean_negatives() -> None:
    """阈值校准应只使用 calibration split 的 clean negative 分数。"""
    rows = [
        {
            "event_id": "cal_neg_1",
            "split": "calibration",
            "sample_role": "clean_negative",
            "attack_family": "clean",
            "attack_condition": "clean_none",
            "is_watermarked": False,
            "content_score_raw": 0.2,
            "attestation_score": 0.1,
        },
        {
            "event_id": "cal_neg_2",
            "split": "calibration",
            "sample_role": "clean_negative",
            "attack_family": "clean",
            "attack_condition": "clean_none",
            "is_watermarked": False,
            "content_score_raw": 0.4,
            "attestation_score": 0.1,
        },
        {
            "event_id": "test_neg_ignored",
            "split": "test",
            "sample_role": "clean_negative",
            "attack_family": "clean",
            "attack_condition": "clean_none",
            "is_watermarked": False,
            "content_score_raw": 0.99,
            "attestation_score": 0.1,
        },
    ]

    report = build_threshold_calibration_report(rows, target_fpr=0.01)

    assert report["overall_decision"] == "pass"
    assert report["thresholds"]["ceg"] > 0.4
    assert report["by_method"]["ceg"]["negative_score_count"] == 2
    assert report["by_method"]["ceg"]["observed_false_positive_count"] == 0
    assert "ceg_full" in report["thresholds"]


@pytest.mark.quick
def test_threshold_calibration_cli_writes_thresholds(tmp_path) -> None:
    """阈值校准 CLI 应写出 thresholds.json 和审计报告。"""
    sample_path = tmp_path / "samples.json"
    output_root = tmp_path / "thresholds"
    rows = _sample_rows(tmp_path)
    rows.append(
        {
            "event_id": "sample_calibration_negative",
            "split": "calibration",
            "sample_role": "clean_negative",
            "attack_family": "clean",
            "attack_condition": "clean_none",
            "is_watermarked": False,
            "content_score_raw": 0.31,
            "attestation_score": 0.1,
        }
    )
    sample_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "scripts/calibrate_thresholds_from_sample_manifest.py",
            "--samples",
            str(sample_path),
            "--out",
            str(output_root),
        ],
        cwd=".",
        check=True,
        text=True,
        capture_output=True,
    )

    thresholds = json.loads((output_root / "thresholds.json").read_text(encoding="utf-8"))
    report = json.loads((output_root / "threshold_calibration_report.json").read_text(encoding="utf-8"))
    assert thresholds["ceg"] > 0.31
    assert report["artifact_name"] == "threshold_calibration_report.json"


@pytest.mark.quick
def test_colab_plan_can_calibrate_thresholds_from_sample_manifest(tmp_path) -> None:
    """Colab 真实实验模式应能在没有 thresholds.json 时先校准阈值。"""
    sample_path = tmp_path / "samples.json"
    rows = _sample_rows(tmp_path)
    rows.append(
        {
            "event_id": "sample_calibration_negative",
            "split": "calibration",
            "sample_role": "clean_negative",
            "attack_family": "clean",
            "attack_condition": "clean_none",
            "is_watermarked": False,
            "content_score_raw": 0.31,
            "attestation_score": 0.1,
        }
    )
    sample_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    plan = build_colab_command_plan(
        ".",
        tmp_path / "workspace",
        use_dry_run_inputs=False,
        sample_manifest_path=sample_path,
        calibrate_thresholds=True,
    )
    input_manifest = build_colab_input_manifest(plan)

    assert "calibrate_thresholds_from_sample_manifest.py" in " ".join(plan["threshold_calibration_command"])
    assert "threshold_calibration" in plan["calibrated_thresholds_path"]
    assert "--thresholds" in plan["prepare_command"]
    assert input_manifest["missing_required_inputs"] == []
