"""验证 pilot paper_results_package 输出接收门禁。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from experiments.pilot_paper_results_package_acceptance import build_pilot_paper_results_package_acceptance_report
from main.analysis.result_package import build_paper_results_package_manifest, validate_paper_results_package, write_paper_writing_index


def _write(path, text: str = "ok") -> None:
    """写出测试用普通文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path, payload: object) -> None:
    """写出测试用 JSON 文件。"""
    _write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _write_minimal_package(root, *, with_evidence: bool = True, with_image_examples: bool = False) -> None:
    """写出满足结果包接收门禁的最小可验证 package。"""
    files = [
        "event_records.json",
        "paper_outputs_summary.json",
        "paper_readiness_report.json",
        "paper_results_report.md",
        "paper_results_report_manifest.json",
        "artifacts/artifact_manifest.json",
        "artifacts/paper_claim_audit.json",
        "artifacts/fixed_fpr_threshold_table.csv",
        "artifacts/tpr_at_fixed_fpr_table.csv",
        "artifacts/attack_tpr_at_fixed_fpr_table.csv",
        "artifacts/baseline_comparison_table.csv",
        "latex_tables/latex_tables_manifest.json",
        "rendered_figures/rendered_paper_figures_manifest.json",
        "pdf_figures/paper_figures_pdf_manifest.json",
    ]
    _write_json(root / "event_records.json", [])
    _write_json(root / "paper_outputs_summary.json", {"artifact_count": 4})
    _write_json(root / "paper_readiness_report.json", {"artifact_name": "paper_readiness_report.json", "overall_decision": "pass"})
    _write(root / "paper_results_report.md", "# paper results\n")
    _write_json(root / "paper_results_report_manifest.json", {"artifact_name": "paper_results_report_manifest.json"})
    _write_json(
        root / "artifacts/artifact_manifest.json",
        {
            "artifact_name": "artifact_manifest.json",
            "artifact_names": [
                "paper_claim_audit.json",
                "fixed_fpr_threshold_table.csv",
                "tpr_at_fixed_fpr_table.csv",
                "attack_tpr_at_fixed_fpr_table.csv",
                "baseline_comparison_table.csv",
            ],
        },
    )
    _write_json(root / "artifacts/paper_claim_audit.json", {"artifact_name": "paper_claim_audit.json", "overall_decision": "pass"})
    for relative in files:
        if relative.endswith(".csv"):
            _write(root / relative, "method_name,target_fpr\nceg,0.01\n")
    _write_json(root / "latex_tables/latex_tables_manifest.json", {"table_count": 1})
    _write_json(root / "rendered_figures/rendered_paper_figures_manifest.json", {"figure_count": 1})
    _write_json(root / "pdf_figures/paper_figures_pdf_manifest.json", {"pdf_path": "paper_figures_preview.pdf"})
    if with_evidence:
        _write_json(root / "paper_result_evidence_report.json", {"artifact_name": "paper_result_evidence_report.json", "overall_decision": "pass"})
        _write_json(root / "external_result_evidence_report.json", {"artifact_name": "external_result_evidence_report.json", "overall_decision": "pass"})
        files.extend(["paper_result_evidence_report.json", "external_result_evidence_report.json"])
    if with_image_examples:
        _write(root / "image_examples/example_001.png", "not really png")
        _write_json(
            root / "image_examples/image_example_manifest.json",
            {"artifact_name": "image_example_manifest.json", "examples": [{"relative_path": "image_examples/example_001.png"}]},
        )
        files.extend(["image_examples/image_example_manifest.json", "image_examples/example_001.png"])
    files.extend(["paper_writing_index.json", "paper_writing_index.md"])
    write_paper_writing_index(root, root, sorted(files))
    manifest = build_paper_results_package_manifest(root, sorted(files), missing_files=[], package_root=root)
    _write_json(root / "paper_results_package_manifest.json", manifest)
    validation = validate_paper_results_package(root)
    _write_json(root / "paper_results_package_validation.json", validation)


@pytest.mark.quick
def test_paper_results_package_acceptance_fails_on_empty_package_root(tmp_path) -> None:
    """空结果包目录必须失败, 避免未导出结果包时进入 MyDrive 归档。"""
    report = build_pilot_paper_results_package_acceptance_report(tmp_path)

    assert report["overall_decision"] == "fail"
    assert report["recommended_next_stage"] == "export_paper_results_package_and_fix_outputs"
    assert report["summary"]["missing_required_file_count"] >= 1
    assert report["summary"]["blocking_issue_count"] >= 1


@pytest.mark.quick
def test_paper_results_package_acceptance_passes_minimal_package(tmp_path) -> None:
    """包含核心 records、表格、图表 manifest、readiness 和 claim audit 的结果包应通过门禁。"""
    _write_minimal_package(tmp_path)

    report = build_pilot_paper_results_package_acceptance_report(tmp_path)

    assert report["overall_decision"] == "pass"
    assert report["recommended_next_stage"] == "mydrive_archive_pilot"
    assert report["summary"]["fresh_validation_decision"] == "pass"
    assert report["summary"]["blocking_issue_count"] == 0


@pytest.mark.quick
def test_paper_results_package_acceptance_requires_evidence_when_requested(tmp_path) -> None:
    """正式论文结果包声明应能要求 paper 和 external evidence reports。"""
    _write_minimal_package(tmp_path, with_evidence=False)

    report = build_pilot_paper_results_package_acceptance_report(tmp_path, require_evidence=True)

    assert report["overall_decision"] == "fail"
    assert any(issue["issue_type"] == "missing_required_package_evidence" for issue in report["blocking_issues"])


@pytest.mark.quick
def test_paper_results_package_acceptance_requires_image_examples_when_requested(tmp_path) -> None:
    """论文示例图为可选门禁项, 启用后必须存在 image_example_manifest 和示例文件。"""
    _write_minimal_package(tmp_path, with_image_examples=False)

    report = build_pilot_paper_results_package_acceptance_report(tmp_path, require_image_examples=True)

    assert report["overall_decision"] == "fail"
    assert any(issue["issue_type"] == "empty_image_example_manifest" for issue in report["blocking_issues"])


@pytest.mark.quick
def test_paper_results_package_acceptance_passes_with_required_image_examples(tmp_path) -> None:
    """启用示例图要求时, 带有可追溯示例图的结果包应通过。"""
    _write_minimal_package(tmp_path, with_image_examples=True)

    report = build_pilot_paper_results_package_acceptance_report(tmp_path, require_image_examples=True)

    assert report["overall_decision"] == "pass"
    assert report["summary"]["image_example_count"] == 1


@pytest.mark.quick
def test_validate_pilot_paper_results_package_cli_writes_report_on_failure(tmp_path) -> None:
    """CLI 在 require-pass 失败时仍应写出可审计报告。"""
    report_path = tmp_path / "package_acceptance_report.json"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_pilot_paper_results_package.py",
            "--package-root",
            str(tmp_path / "missing_package_root"),
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
    assert report["artifact_name"] == "pilot_paper_results_package_acceptance_report.json"
