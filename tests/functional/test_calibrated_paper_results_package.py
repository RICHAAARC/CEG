"""验证 fixed-FPR 校准后结果包流水线入口。"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest


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
def test_build_calibrated_paper_results_package_cli(tmp_path: Path) -> None:
    """一条命令应完成 detection event 校准、paper outputs 和结果包导出。"""

    events = [
        _event("cal_neg", split="calibration", role="clean_negative", score=0.22, is_watermarked=False),
        _event("test_neg", split="test", role="clean_negative", score=0.20, is_watermarked=False),
        _event("test_pos", split="test", role="positive_source", score=0.72, is_watermarked=True),
    ]
    events_path = tmp_path / "detection_events.json"
    out = tmp_path / "package_run"
    events_path.write_text(json.dumps(events, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "scripts/build_calibrated_paper_results_package.py",
            "--detection-events",
            str(events_path),
            "--out",
            str(out),
            "--target-fpr",
            "0.01",
            "--allow-incomplete-package",
        ],
        cwd=".",
        check=True,
    )

    manifest = json.loads((out / "calibrated_paper_results_package_build_manifest.json").read_text(encoding="utf-8"))
    calibrated_events = json.loads((out / "calibrated_detection" / "detection_events_calibrated.json").read_text(encoding="utf-8"))
    assert manifest["overall_decision"] == "pass"
    assert (out / "paper_outputs" / "event_records.json").is_file()
    assert (out / "paper_results_package" / "paper_results_package_manifest.json").is_file()
    assert all(event["payload"]["detection_source"]["fixed_fpr_calibrated"] is True for event in calibrated_events)
