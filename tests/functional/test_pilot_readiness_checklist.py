"""验证 pilot readiness checklist 能把 gap 报告转为真实 pilot 启动任务."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from experiments.pilot_readiness_checklist import build_pilot_readiness_checklist


@pytest.mark.quick
def test_build_pilot_readiness_checklist_blocks_dry_run_formal_pilot() -> None:
    """含 dry-run 标记的 gap 报告不能被判定为 ready_for_formal_pilot."""
    gap_report = {
        "artifact_name": "pilot_input_gap_report.json",
        "overall_decision": "pass",
        "pilot_readiness_decision": "rehearsal_or_partial_pilot_only",
        "missing_core_fields": [],
        "dry_run_marker_fields": [
            {
                "field": "events",
                "path": "ceg_detection/detection_events.json",
                "reason": "dry_run_marker_present",
            }
        ],
        "formal_claim_gaps": [
            {
                "field": "metric_execution_manifest",
                "formal_result_claim": False,
                "evidence_path_count": 0,
            }
        ],
    }

    checklist = build_pilot_readiness_checklist(gap_report)

    assert checklist["overall_decision"] == "not_ready_for_formal_pilot"
    assert checklist["recommended_next_stage"] == "real_pilot_input_preparation"
    assert checklist["summary"]["missing_core_field_count"] == 0
    assert checklist["summary"]["dry_run_gap_count"] == 1
    assert any(
        item["requirement_id"] == "dry_run_marker_absent::events"
        and item["blocking_for_formal_pilot"]
        for item in checklist["checklist_items"]
    )


@pytest.mark.quick
def test_build_pilot_readiness_checklist_ready_when_no_blockers() -> None:
    """无核心缺口和 dry-run 标记时, checklist 可进入 formal pilot package build 阶段."""
    gap_report = {
        "artifact_name": "pilot_input_gap_report.json",
        "overall_decision": "pass",
        "pilot_readiness_decision": "ready_for_formal_pilot",
        "missing_core_fields": [],
        "dry_run_marker_fields": [],
        "formal_claim_gaps": [],
    }

    checklist = build_pilot_readiness_checklist(gap_report, require_formal_claims=True)

    assert checklist["overall_decision"] == "ready_for_formal_pilot"
    assert checklist["recommended_next_stage"] == "formal_pilot_package_build"
    assert checklist["summary"]["blocking_item_count"] == 0


@pytest.mark.quick
def test_build_pilot_readiness_checklist_cli_writes_json_and_markdown(tmp_path) -> None:
    """CLI 应同时写出机器可读 JSON 和人类可读 Markdown 清单."""
    gap_report_path = tmp_path / "pilot_input_gap_report.json"
    output_path = tmp_path / "pilot_readiness_checklist.json"
    markdown_path = tmp_path / "pilot_readiness_checklist.md"
    gap_report_path.write_text(
        json.dumps(
            {
                "artifact_name": "pilot_input_gap_report.json",
                "overall_decision": "pass",
                "pilot_readiness_decision": "rehearsal_or_partial_pilot_only",
                "missing_core_fields": ["baseline_observations"],
                "dry_run_marker_fields": [],
                "formal_claim_gaps": [],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "scripts/build_pilot_readiness_checklist.py",
            "--gap-report",
            str(gap_report_path),
            "--out",
            str(output_path),
            "--markdown-out",
            str(markdown_path),
        ],
        cwd=".",
        check=True,
    )

    checklist = json.loads(output_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert checklist["overall_decision"] == "not_ready_for_formal_pilot"
    assert checklist["summary"]["missing_core_field_count"] == 1
    assert "core_input_present::baseline_observations" in markdown
