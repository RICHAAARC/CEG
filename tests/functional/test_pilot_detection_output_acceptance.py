"""验证 pilot detection 输出接收门禁。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from experiments.pilot_detection_output_acceptance import build_pilot_detection_output_acceptance_report


def _event(
    event_id: str,
    *,
    split: str,
    sample_role: str,
    is_watermarked: bool,
    score: float,
    attack_family: str = "clean",
    attack_condition: str = "clean_none",
) -> dict[str, object]:
    """构造最小 CEG detection event。"""
    return {
        "event_id": event_id,
        "method_name": "ceg",
        "split": split,
        "sample_role": sample_role,
        "attack_family": attack_family,
        "attack_condition": attack_condition,
        "is_watermarked": is_watermarked,
        "payload": {
            "content": {"content_score_raw": score},
            "thresholds": {"content_threshold": 0.5, "attestation_threshold": 0.5},
            "attestation": {"attestation_score": score},
        },
    }


def _write_detection_outputs(root, events) -> None:
    """写出测试用 detection 输出。"""
    root.mkdir(parents=True, exist_ok=True)
    (root / "detection_events.json").write_text(json.dumps(events, ensure_ascii=False), encoding="utf-8")
    (root / "detection_thresholds.json").write_text(json.dumps({"ceg": 0.5}), encoding="utf-8")
    (root / "ceg_detection_execution_manifest.json").write_text(
        json.dumps(
            {
                "artifact_name": "ceg_detection_execution_manifest.json",
                "producer_id": "test_detector",
                "formal_result_claim": False,
                "events_path": "detection_events.json",
                "thresholds_path": "detection_thresholds.json",
                "event_count": len(events),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


@pytest.mark.quick
def test_detection_output_acceptance_fails_on_empty_output_root(tmp_path) -> None:
    """空 detection 输出目录必须失败, 避免未运行 detector 时进入统计。"""
    report = build_pilot_detection_output_acceptance_report(tmp_path)

    assert report["overall_decision"] == "fail"
    assert report["recommended_next_stage"] == "run_detection_backend_and_fix_outputs"
    assert report["summary"]["missing_required_output_count"] == 2
    assert any(issue["issue_type"] == "missing_detection_run_manifest" for issue in report["blocking_issues"])


@pytest.mark.quick
def test_detection_output_acceptance_passes_fixed_fpr_contract(tmp_path) -> None:
    """包含 calibration / test / attacked 角色的 detection 输出应通过接收门禁。"""
    events = [
        _event("cal_neg_1", split="calibration", sample_role="clean_negative", is_watermarked=False, score=0.1),
        _event("test_neg_1", split="test", sample_role="clean_negative", is_watermarked=False, score=0.2),
        _event("test_pos_1", split="test", sample_role="positive_source", is_watermarked=True, score=0.8),
        _event(
            "attack_pos_1",
            split="test",
            sample_role="attacked_positive",
            is_watermarked=True,
            score=0.7,
            attack_family="brightness_contrast",
            attack_condition="brightness_contrast_default",
        ),
    ]
    _write_detection_outputs(tmp_path, events)

    report = build_pilot_detection_output_acceptance_report(tmp_path)

    assert report["overall_decision"] == "pass"
    assert report["recommended_next_stage"] == "fixed_fpr_statistics_pilot"
    assert report["fixed_fpr_role_counts"]["calibration_clean_negative"] == 1
    assert report["fixed_fpr_role_counts"]["test_clean_negative"] == 1
    assert report["fixed_fpr_role_counts"]["test_attacked_positive"] == 1
    assert report["summary"]["blocking_issue_count"] == 0


@pytest.mark.quick
def test_detection_output_acceptance_fails_without_calibration_negative(tmp_path) -> None:
    """缺少 calibration clean negative 时不能进入 fixed-FPR 统计。"""
    events = [
        _event("test_neg_1", split="test", sample_role="clean_negative", is_watermarked=False, score=0.2),
        _event("test_pos_1", split="test", sample_role="positive_source", is_watermarked=True, score=0.8),
    ]
    _write_detection_outputs(tmp_path, events)

    report = build_pilot_detection_output_acceptance_report(tmp_path)

    assert report["overall_decision"] == "fail"
    assert any(
        issue["issue_type"] == "missing_fixed_fpr_required_role"
        and issue["role_name"] == "calibration_clean_negative"
        for issue in report["blocking_issues"]
    )


@pytest.mark.quick
def test_validate_pilot_detection_outputs_cli_writes_report_on_failure(tmp_path) -> None:
    """CLI 在 require-pass 失败时仍应写出可审计报告。"""
    report_path = tmp_path / "detection_acceptance_report.json"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_pilot_detection_outputs.py",
            "--output-root",
            str(tmp_path / "missing_detection_root"),
            "--out",
            str(report_path),
            "--require-pass",
        ],
        cwd=".",
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert report_path.is_file()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["overall_decision"] == "fail"
    assert report["artifact_name"] == "pilot_detection_output_acceptance_report.json"
