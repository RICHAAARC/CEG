"""验证 pilot external baseline 输出接收门禁。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from experiments.baseline_pilot_producer import write_baseline_pilot_outputs
from experiments.pilot_baseline_output_acceptance import build_pilot_baseline_output_acceptance_report


def _events() -> list[dict[str, object]]:
    """构造测试用 detection events。"""
    return [
        {
            "event_id": "test_neg_1",
            "method_name": "ceg",
            "split": "test",
            "sample_role": "clean_negative",
            "attack_family": "clean",
            "attack_condition": "clean_none",
            "is_watermarked": False,
            "payload": {},
        },
        {
            "event_id": "test_pos_1",
            "method_name": "ceg",
            "split": "test",
            "sample_role": "positive_source",
            "attack_family": "clean",
            "attack_condition": "clean_none",
            "is_watermarked": True,
            "payload": {},
        },
        {
            "event_id": "attack_pos_1",
            "method_name": "ceg",
            "split": "test",
            "sample_role": "attacked_positive",
            "attack_family": "brightness_contrast",
            "attack_condition": "brightness_contrast_default",
            "is_watermarked": True,
            "payload": {},
        },
    ]


@pytest.mark.quick
def test_baseline_output_acceptance_fails_on_empty_output_root(tmp_path) -> None:
    """空 baseline 输出目录必须失败, 避免未运行 baseline 时进入论文对比表。"""
    report = build_pilot_baseline_output_acceptance_report(tmp_path)

    assert report["overall_decision"] == "fail"
    assert report["recommended_next_stage"] == "run_baseline_backend_and_fix_outputs"
    assert report["summary"]["missing_required_output_count"] == 2
    assert report["summary"]["blocking_issue_count"] >= 2


@pytest.mark.quick
def test_baseline_output_acceptance_passes_pilot_contract(tmp_path) -> None:
    """baseline pilot producer 产出的契约完整文件应通过接收门禁。"""
    events_path = tmp_path / "detection_events.json"
    events = _events()
    events_path.write_text(json.dumps(events, ensure_ascii=False), encoding="utf-8")
    write_baseline_pilot_outputs(events, tmp_path, events_path=events_path, baseline_ids=["tree_ring"])

    report = build_pilot_baseline_output_acceptance_report(tmp_path)

    assert report["overall_decision"] == "pass"
    assert report["recommended_next_stage"] == "quality_metric_pilot"
    assert report["observation_summary"]["baseline_ids"] == ["tree_ring"]
    assert report["observation_summary"]["event_count"] == 3
    assert report["observation_summary"]["attacked_observation_count"] == 1
    assert report["summary"]["blocking_issue_count"] == 0


@pytest.mark.quick
def test_baseline_output_acceptance_fails_for_unregistered_baseline(tmp_path) -> None:
    """未注册 baseline_id 必须失败, 避免生成不可解释对比表。"""
    observations = [
        {
            "event_id": "event_001",
            "baseline_id": "unknown_baseline",
            "score": 0.7,
            "threshold": 0.5,
            "higher_is_positive": True,
            "split": "test",
            "sample_role": "positive_source",
            "attack_family": "clean",
            "attack_condition": "clean_none",
        }
    ]
    (tmp_path / "baseline_observations.json").write_text(json.dumps(observations), encoding="utf-8")
    (tmp_path / "baseline_execution_manifest.json").write_text(
        json.dumps(
            {
                "artifact_name": "baseline_execution_manifest.json",
                "producer_id": "test",
                "producer_role": "test",
                "formal_result_claim": False,
                "baseline_observations_path": "baseline_observations.json",
                "observation_count": 1,
                "baseline_ids": ["unknown_baseline"],
            }
        ),
        encoding="utf-8",
    )

    report = build_pilot_baseline_output_acceptance_report(tmp_path)

    assert report["overall_decision"] == "fail"
    assert any(issue["issue_type"] == "unregistered_baseline_id" for issue in report["blocking_issues"])


@pytest.mark.quick
def test_baseline_output_acceptance_requires_formal_evidence_when_requested(tmp_path) -> None:
    """启用正式证据要求时, 缺少 external evidence report 必须失败。"""
    events_path = tmp_path / "detection_events.json"
    events = _events()
    events_path.write_text(json.dumps(events, ensure_ascii=False), encoding="utf-8")
    write_baseline_pilot_outputs(events, tmp_path, events_path=events_path, baseline_ids=["tree_ring"])

    report = build_pilot_baseline_output_acceptance_report(tmp_path, require_formal_evidence=True)

    assert report["overall_decision"] == "fail"
    assert any(issue["issue_type"] == "missing_required_external_evidence_report" for issue in report["blocking_issues"])


@pytest.mark.quick
def test_validate_pilot_baseline_outputs_cli_writes_report_on_failure(tmp_path) -> None:
    """CLI 在 require-pass 失败时仍应写出可审计报告。"""
    report_path = tmp_path / "baseline_acceptance_report.json"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_pilot_baseline_outputs.py",
            "--output-root",
            str(tmp_path / "missing_baseline_root"),
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
    assert report["artifact_name"] == "pilot_baseline_output_acceptance_report.json"
