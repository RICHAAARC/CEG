"""验证 detection event fixed FPR 阈值校准。"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from experiments.detection_event_thresholds import calibrate_detection_event_thresholds
from experiments.protocol_runner import run_paper_protocol


def _event(event_id: str, *, split: str, role: str, score: float, is_watermarked: bool) -> dict[str, object]:
    """构造最小 CEG detection event。"""

    return {
        "event_id": event_id,
        "method_name": "ceg",
        "split": split,
        "sample_role": role,
        "attack_family": "clean",
        "attack_condition": "clean_none",
        "is_watermarked": is_watermarked,
        "payload": {
            "thresholds": {
                "content_threshold": 0.5,
                "attestation_threshold": 0.5,
                "registration_confidence_min": 0.3,
                "anchor_inlier_ratio_min": 0.5,
                "recovered_sync_consistency_min": 0.55,
                "rescue_delta_low": 0.05,
            },
            "content": {
                "content_score_raw": score,
                "content_score_aligned": score,
                "content_fail_reason": "content_chain_scored" if score >= 0.5 else "content_chain_below_threshold",
            },
            "geometry": {
                "registration_confidence": 0.9,
                "anchor_inlier_ratio": 0.9,
                "recovered_sync_consistency": 0.9,
                "alignment_residual": 0.0,
            },
            "attestation": {"attestation_score": 1.0},
            "ceg_ablation_variants": [],
        },
    }


@pytest.mark.quick
def test_calibrated_thresholds_are_written_back_to_event_payload() -> None:
    """校准结果必须回写 payload.thresholds, 否则 formal decision 不会使用 fixed FPR 阈值。"""

    events = [
        _event("cal_neg", split="calibration", role="clean_negative", score=0.31, is_watermarked=False),
        _event("test_neg", split="test", role="clean_negative", score=0.30, is_watermarked=False),
        _event("test_pos", split="test", role="positive_source", score=0.8, is_watermarked=True),
    ]

    result = calibrate_detection_event_thresholds(events, target_fpr=0.01)
    calibrated_events = result["events"]
    threshold = result["thresholds"]["ceg"]

    assert threshold > 0.31
    assert all(event["payload"]["thresholds"]["content_threshold"] == threshold for event in calibrated_events)
    assert all(event["payload"]["detection_source"]["fixed_fpr_calibrated"] is True for event in calibrated_events)

    protocol = run_paper_protocol(
        calibrated_events,
        profile="paper_main_probe",
        content_thresholds=result["thresholds"],
    )
    records = {record["event_id"]: record for record in protocol["records"] if record["method_name"] == "ceg"}
    assert records["test_neg"]["final_decision"] is False
    assert records["test_pos"]["final_decision"] is True
    assert records["test_pos"]["content_margin_raw"] == pytest.approx(0.8 - threshold)


@pytest.mark.quick
def test_calibrate_detection_events_fixed_fpr_cli_writes_outputs(tmp_path: Path) -> None:
    """CLI 应写出 calibrated events、thresholds 和校准报告。"""

    events = [
        _event("cal_neg", split="calibration", role="clean_negative", score=0.21, is_watermarked=False),
        _event("test_pos", split="test", role="positive_source", score=0.7, is_watermarked=True),
    ]
    event_path = tmp_path / "detection_events.json"
    out = tmp_path / "calibrated"
    event_path.write_text(json.dumps(events, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "scripts/calibrate_detection_events_fixed_fpr.py",
            "--events",
            str(event_path),
            "--out",
            str(out),
            "--target-fpr",
            "0.01",
        ],
        cwd=".",
        check=True,
    )

    assert (out / "detection_events_calibrated.json").is_file()
    assert (out / "detection_thresholds_calibrated.json").is_file()
    report = json.loads((out / "detection_event_threshold_calibration_report.json").read_text(encoding="utf-8"))
    assert report["overall_decision"] == "pass"
    assert report["calibrated_event_count"] == 2
