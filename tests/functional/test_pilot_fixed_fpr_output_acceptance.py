"""验证 pilot fixed-FPR / TPR@FPR 统计输出接收门禁。"""

from __future__ import annotations

import csv
import json
import subprocess
import sys

import pytest

from experiments.pilot_fixed_fpr_output_acceptance import build_pilot_fixed_fpr_output_acceptance_report


def _write_csv(path, rows: list[dict[str, object]]) -> None:
    """写出测试用 CSV 表格。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_fixed_fpr_outputs(root) -> None:
    """写出完整的 fixed-FPR 测试输出。"""
    _write_csv(
        root / "fixed_fpr_threshold_table.csv",
        [
            {
                "method_name": "ceg",
                "target_fpr": 0.01,
                "threshold_value": 0.5,
                "calibration_source": "calibration_clean_negative",
                "calibration_negative_count": 10,
                "calibration_false_positive_count": 0,
                "calibration_observed_fpr": 0.0,
            }
        ],
    )
    _write_csv(
        root / "tpr_at_fixed_fpr_table.csv",
        [
            {
                "method_name": "ceg",
                "target_fpr": 0.01,
                "threshold_value": 0.5,
                "test_clean_negative_count": 10,
                "test_false_positive_count": 0,
                "test_fpr_at_threshold": 0.0,
                "test_positive_count": 8,
                "test_true_positive_count": 7,
                "tpr_at_fixed_fpr": 0.875,
            }
        ],
    )
    _write_csv(
        root / "attack_tpr_at_fixed_fpr_table.csv",
        [
            {
                "method_name": "ceg",
                "target_fpr": 0.01,
                "threshold_value": 0.5,
                "attack_family": "jpeg",
                "attacked_positive_count": 8,
                "attacked_true_positive_count": 6,
                "attack_tpr_at_fixed_fpr": 0.75,
            }
        ],
    )
    _write_csv(
        root / "baseline_comparison_table.csv",
        [{"method_name": "ceg", "sample_count": 18}],
    )


@pytest.mark.quick
def test_fixed_fpr_output_acceptance_fails_on_empty_output_root(tmp_path) -> None:
    """空 fixed-FPR 输出目录必须失败, 避免未统计时进入论文结果包阶段。"""
    report = build_pilot_fixed_fpr_output_acceptance_report(tmp_path)

    assert report["overall_decision"] == "fail"
    assert report["recommended_next_stage"] == "run_fixed_fpr_statistics_and_fix_outputs"
    assert report["summary"]["missing_required_output_count"] == 4
    assert report["summary"]["blocking_issue_count"] >= 4


@pytest.mark.quick
def test_fixed_fpr_output_acceptance_passes_complete_contract(tmp_path) -> None:
    """完整 fixed-FPR 统计表应通过接收门禁。"""
    _write_fixed_fpr_outputs(tmp_path)

    report = build_pilot_fixed_fpr_output_acceptance_report(tmp_path)

    assert report["overall_decision"] == "pass"
    assert report["recommended_next_stage"] == "paper_result_package_pilot"
    assert report["summary"]["threshold_row_count"] == 1
    assert report["summary"]["tpr_row_count"] == 1
    assert report["summary"]["attack_tpr_row_count"] == 1
    assert report["summary"]["blocking_issue_count"] == 0


@pytest.mark.quick
def test_fixed_fpr_output_acceptance_fails_for_fallback_calibration_source(tmp_path) -> None:
    """论文统计不能使用 fallback clean negative 作为阈值来源。"""
    _write_fixed_fpr_outputs(tmp_path)
    text = (tmp_path / "fixed_fpr_threshold_table.csv").read_text(encoding="utf-8")
    (tmp_path / "fixed_fpr_threshold_table.csv").write_text(
        text.replace("calibration_clean_negative", "fallback_all_clean_negative"),
        encoding="utf-8",
    )

    report = build_pilot_fixed_fpr_output_acceptance_report(tmp_path)

    assert report["overall_decision"] == "fail"
    assert any(issue["issue_type"] == "non_calibration_threshold_source" for issue in report["blocking_issues"])


@pytest.mark.quick
def test_fixed_fpr_output_acceptance_fails_for_rate_out_of_range(tmp_path) -> None:
    """TPR / FPR 等 rate 字段必须位于 0 到 1 之间。"""
    _write_fixed_fpr_outputs(tmp_path)
    text = (tmp_path / "tpr_at_fixed_fpr_table.csv").read_text(encoding="utf-8")
    (tmp_path / "tpr_at_fixed_fpr_table.csv").write_text(text.replace("0.875", "1.5"), encoding="utf-8")

    report = build_pilot_fixed_fpr_output_acceptance_report(tmp_path)

    assert report["overall_decision"] == "fail"
    assert any(issue["issue_type"] == "fixed_fpr_rate_out_of_range" for issue in report["blocking_issues"])


@pytest.mark.quick
def test_fixed_fpr_output_acceptance_requires_statistical_report_when_requested(tmp_path) -> None:
    """启用统计检验报告要求时, 缺少 statistical_test_report.json 必须失败。"""
    _write_fixed_fpr_outputs(tmp_path)

    report = build_pilot_fixed_fpr_output_acceptance_report(tmp_path, require_statistical_report=True)

    assert report["overall_decision"] == "fail"
    assert any(issue["issue_type"] == "missing_required_statistical_test_report" for issue in report["blocking_issues"])


@pytest.mark.quick
def test_validate_pilot_fixed_fpr_outputs_cli_writes_report_on_failure(tmp_path) -> None:
    """CLI 在 require-pass 失败时仍应写出可审计报告。"""
    report_path = tmp_path / "fixed_fpr_acceptance_report.json"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_pilot_fixed_fpr_outputs.py",
            "--output-root",
            str(tmp_path / "missing_fixed_fpr_root"),
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
    assert report["artifact_name"] == "pilot_fixed_fpr_output_acceptance_report.json"
