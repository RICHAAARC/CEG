"""验证真实 pilot 阶段进度汇总。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from experiments.pilot_stage_progress_summary import build_pilot_stage_progress_summary, write_pilot_stage_progress_summary


def _write_report(path, decision: str, next_stage: str, blocking_count: int = 0) -> None:
    """写出测试用门禁报告。"""
    path.write_text(
        json.dumps(
            {
                "artifact_name": path.name,
                "overall_decision": decision,
                "recommended_next_stage": next_stage,
                "summary": {"blocking_issue_count": blocking_count},
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


@pytest.mark.quick
def test_stage_progress_summary_marks_first_missing_stage(tmp_path) -> None:
    """缺失首个门禁报告时, 汇总应把该阶段标为当前阻断点。"""
    summary = build_pilot_stage_progress_summary(tmp_path)

    assert summary["overall_decision"] == "fail"
    assert summary["current_stage"] == "p0_input_preflight"
    assert summary["summary"]["missing_count"] >= 1


@pytest.mark.quick
def test_stage_progress_summary_finds_first_failed_stage_after_passes(tmp_path) -> None:
    """前置门禁通过后, 第一个 fail 阶段应成为推荐行动入口。"""
    _write_report(tmp_path / "pilot_input_plan_preflight_report.json", "pass", "value_pack", 0)
    _write_report(tmp_path / "pilot_input_value_pack_application_report.json", "fail", "fill_values", 3)

    summary = build_pilot_stage_progress_summary(tmp_path)

    assert summary["current_stage"] == "p0_value_pack"
    assert summary["first_blocking_stage"]["blocking_issue_count"] == 3
    assert "pilot_input_value_pack.draft.json" in summary["recommended_next_action"]


@pytest.mark.quick
def test_stage_progress_summary_writes_json_and_markdown(tmp_path) -> None:
    """汇总 CLI 所需的 JSON 与 Markdown 产物应同时写出。"""
    out_json = tmp_path / "summary.json"
    out_md = tmp_path / "summary.md"

    summary = write_pilot_stage_progress_summary(tmp_path, out_json, out_md)

    assert out_json.is_file()
    assert out_md.is_file()
    assert json.loads(out_json.read_text(encoding="utf-8"))["artifact_name"] == "pilot_stage_progress_summary.json"
    assert "CEG pilot 阶段进度汇总" in out_md.read_text(encoding="utf-8")
    assert summary["overall_decision"] == "fail"


@pytest.mark.quick
def test_build_pilot_stage_progress_summary_cli_writes_outputs(tmp_path) -> None:
    """CLI 在存在阻断时应写出报告, require-pass 时返回非零退出码。"""
    out_json = tmp_path / "progress.json"
    out_md = tmp_path / "progress.md"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_pilot_stage_progress_summary.py",
            "--workspace",
            str(tmp_path),
            "--out-json",
            str(out_json),
            "--out-markdown",
            str(out_md),
            "--require-pass",
        ],
        cwd=".",
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert out_json.is_file()
    assert out_md.is_file()
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["overall_decision"] == "fail"
