"""验证外部 baseline 与高级 metric 证据预检."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from experiments.external_result_evidence import validate_external_result_evidence
from experiments.paper_fixture_factory import write_paper_dry_run_inputs


@pytest.mark.quick
def test_external_result_evidence_requires_formal_claims(tmp_path) -> None:
    """正式证据门禁应阻断没有 formal_result_claim 的导入 manifest."""
    input_root = tmp_path / "inputs"
    import_root = tmp_path / "imports"
    manifest = write_paper_dry_run_inputs(input_root)

    subprocess.run(
        [
            sys.executable,
            "scripts/import_baseline_observations.py",
            "--observations",
            str(input_root / manifest["baseline_observations_path"]),
            "--out",
            str(import_root / "baseline"),
        ],
        cwd=".",
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "scripts/import_metric_rows.py",
            "--metric-rows",
            str(input_root / manifest["metric_rows_path"]),
            "--out",
            str(import_root / "metric"),
        ],
        cwd=".",
        check=True,
    )

    report = validate_external_result_evidence(
        baseline_execution_manifest=import_root / "baseline" / "baseline_execution_manifest.json",
        metric_execution_manifest=import_root / "metric" / "metric_execution_manifest.json",
        require_formal_claim=True,
    )

    assert report["overall_decision"] == "fail"
    assert report["summary"]["fail_count"] == 2
    assert all(any(issue["reason"] == "formal_result_claim_not_enabled" for issue in check["issues"]) for check in report["checks"])


@pytest.mark.quick
def test_external_result_evidence_accepts_formal_claims_with_evidence(tmp_path) -> None:
    """提供正式运行证据后, baseline 与 metric manifest 应通过统一证据预检."""
    input_root = tmp_path / "inputs"
    import_root = tmp_path / "imports"
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    baseline_evidence = evidence_root / "baseline_run_log.txt"
    metric_evidence = evidence_root / "metric_run_log.txt"
    baseline_evidence.write_text("baseline backend run log\n", encoding="utf-8")
    metric_evidence.write_text("metric backend run log\n", encoding="utf-8")
    manifest = write_paper_dry_run_inputs(input_root)

    subprocess.run(
        [
            sys.executable,
            "scripts/import_baseline_observations.py",
            "--observations",
            str(input_root / manifest["baseline_observations_path"]),
            "--out",
            str(import_root / "baseline"),
            "--formal-result-claim",
            "--evidence-path",
            str(baseline_evidence),
        ],
        cwd=".",
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "scripts/import_metric_rows.py",
            "--metric-rows",
            str(input_root / manifest["metric_rows_path"]),
            "--out",
            str(import_root / "metric"),
            "--formal-result-claim",
            "--evidence-path",
            str(metric_evidence),
        ],
        cwd=".",
        check=True,
    )

    report_path = tmp_path / "reports" / "external_result_evidence_report.json"
    subprocess.run(
        [
            sys.executable,
            "scripts/validate_external_result_evidence.py",
            "--baseline-execution-manifest",
            str(import_root / "baseline" / "baseline_execution_manifest.json"),
            "--metric-execution-manifest",
            str(import_root / "metric" / "metric_execution_manifest.json"),
            "--require-formal-claim",
            "--out",
            str(report_path),
            "--require-pass",
        ],
        cwd=".",
        check=True,
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["overall_decision"] == "pass"
    assert report["summary"]["pass_count"] == 2
    assert all(check["formal_result_claim"] is True for check in report["checks"])
    assert all(check["evidence_path_count"] == 1 for check in report["checks"])
