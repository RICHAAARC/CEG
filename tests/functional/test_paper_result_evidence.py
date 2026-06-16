"""验证正式论文结果证据完整性审计。"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from typing import Any

import pytest

from experiments.paper_fixture_factory import write_paper_dry_run_inputs
from main.analysis.paper_result_evidence import validate_paper_result_evidence
from paper_workflow.colab_utils.cold_start import run_colab_cold_start_pipeline


def _replace_dry_run_markers(value: Any) -> Any:
    """把 dry-run fixture 标记替换成 formal probe 标记, 用于构造轻量正式形态输入。"""
    if isinstance(value, str):
        return value.replace("dry_run", "formal_probe").replace("dry-run", "formal-probe")
    if isinstance(value, list):
        return [_replace_dry_run_markers(item) for item in value]
    if isinstance(value, dict):
        return {key: _replace_dry_run_markers(item) for key, item in value.items()}
    return value


def _build_outputs_from_manifest(input_root, output_root, manifest, *, require_readiness: bool = True) -> None:
    """调用正式构建脚本生成受治理论文输出目录。"""
    command = [
        sys.executable,
        "scripts/build_paper_outputs.py",
        "--events",
        str(input_root / manifest["events_path"]),
        "--thresholds",
        str(input_root / manifest["thresholds_path"]),
        "--baseline-observations",
        str(input_root / manifest["baseline_observations_path"]),
        "--metric-rows",
        str(input_root / manifest["metric_rows_path"]),
        "--out",
        str(output_root),
    ]
    if require_readiness:
        command.append("--require-paper-readiness")
    subprocess.run(command, cwd=".", check=True, text=True, capture_output=True)


@pytest.mark.quick
def test_formal_result_evidence_passes_for_non_dry_run_probe_outputs(tmp_path) -> None:
    """无 dry-run 标记且具备完整指标覆盖的输出, 应通过正式证据的非矩阵调试模式。"""
    source_root = tmp_path / "source_inputs"
    input_root = tmp_path / "formal_inputs"
    output_root = tmp_path / "paper_outputs"
    manifest = write_paper_dry_run_inputs(source_root)
    input_root.mkdir()
    for key in ("events_path", "baseline_observations_path", "metric_rows_path", "thresholds_path"):
        payload = json.loads((source_root / manifest[key]).read_text(encoding="utf-8"))
        (input_root / manifest[key]).write_text(
            json.dumps(_replace_dry_run_markers(payload), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    _build_outputs_from_manifest(input_root, output_root, manifest)
    report = validate_paper_result_evidence(output_root, require_experiment_coverage=False)

    assert report["overall_decision"] == "pass"
    assert report["target_kind"] == "paper_output_directory"
    assert next(item for item in report["checks"] if item["requirement"] == "dry_run_markers_absent")["status"] == "pass"
    assert next(item for item in report["checks"] if item["requirement"] == "standard_quality_metrics_complete")["status"] == "pass"


@pytest.mark.quick
def test_formal_result_evidence_rejects_incomplete_baseline_and_ablation_coverage(tmp_path) -> None:
    """正式证据门禁应拒绝缺少外部 baseline 或内部消融行的结果表。"""
    source_root = tmp_path / "source_inputs"
    input_root = tmp_path / "formal_inputs"
    output_root = tmp_path / "paper_outputs"
    manifest = write_paper_dry_run_inputs(source_root)
    input_root.mkdir()
    for key in ("events_path", "baseline_observations_path", "metric_rows_path", "thresholds_path"):
        payload = json.loads((source_root / manifest[key]).read_text(encoding="utf-8"))
        (input_root / manifest[key]).write_text(
            json.dumps(_replace_dry_run_markers(payload), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    _build_outputs_from_manifest(input_root, output_root, manifest)
    baseline_table = output_root / "artifacts" / "baseline_comparison_table.csv"
    baseline_lines = baseline_table.read_text(encoding="utf-8").splitlines()
    baseline_table.write_text("\n".join(line for line in baseline_lines if line.startswith("clean_fpr") or ",ceg," in line) + "\n", encoding="utf-8")

    report = validate_paper_result_evidence(output_root, require_experiment_coverage=False)
    coverage_check = next(
        item for item in report["checks"] if item["requirement"] == "baseline_and_ablation_semantic_coverage_complete"
    )

    assert report["overall_decision"] == "fail"
    assert coverage_check["status"] == "fail"
    assert any(item["reason"] == "missing_method_row" for item in coverage_check["evidence"]["violations"])


@pytest.mark.quick
def test_formal_result_evidence_rejects_dry_run_outputs_by_default(tmp_path) -> None:
    """dry-run 输出即使 readiness 通过, 也不能默认冒充正式论文实验结果。"""
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "paper_outputs"
    manifest = write_paper_dry_run_inputs(input_root)
    _build_outputs_from_manifest(input_root, output_root, manifest)

    report = validate_paper_result_evidence(output_root, require_experiment_coverage=False)

    assert report["overall_decision"] == "fail"
    dry_run_check = next(item for item in report["checks"] if item["requirement"] == "dry_run_markers_absent")
    assert dry_run_check["status"] == "fail"
    assert dry_run_check["evidence"]


@pytest.mark.quick
def test_validate_paper_result_evidence_cli_writes_report_and_blocks_failure(tmp_path) -> None:
    """CLI 应能写出正式证据报告, 并在 require-pass 时阻断 dry-run 结果。"""
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "paper_outputs"
    report_path = tmp_path / "paper_result_evidence_report.json"
    manifest = write_paper_dry_run_inputs(input_root)
    _build_outputs_from_manifest(input_root, output_root, manifest)

    failed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_paper_result_evidence.py",
            "--target",
            str(output_root),
            "--out",
            str(report_path),
            "--allow-missing-experiment-coverage",
            "--require-pass",
        ],
        cwd=".",
        check=False,
        text=True,
        capture_output=True,
    )

    assert failed.returncode == 1
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["overall_decision"] == "fail"

    passed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_paper_result_evidence.py",
            "--target",
            str(output_root),
            "--out",
            str(report_path),
            "--allow-dry-run",
            "--allow-missing-experiment-coverage",
            "--require-pass",
        ],
        cwd=".",
        check=False,
        text=True,
        capture_output=True,
    )

    assert passed.returncode == 0, passed.stderr
    allowed_report = json.loads(report_path.read_text(encoding="utf-8"))
    assert allowed_report["overall_decision"] == "pass"

@pytest.mark.quick
def test_formal_result_evidence_checks_colab_formal_run_checklist(tmp_path) -> None:
    """Colab bundle 的正式证据门禁应读取正式运行清单并阻断未通过清单的结果。"""
    run_colab_cold_start_pipeline(".", tmp_path / "colab_workspace", repetitions=1)
    bundle_root = tmp_path / "colab_workspace" / "colab_run_bundle"

    strict_report = validate_paper_result_evidence(bundle_root, require_experiment_coverage=False)
    strict_check = next(item for item in strict_report["checks"] if item["requirement"] == "colab_formal_run_checklist_passed")

    assert strict_report["overall_decision"] == "fail"
    assert strict_check["status"] == "fail"
    assert strict_check["evidence"]["checklist_decision"] == "fail"
    assert strict_check["evidence"]["blocking_issue_count"] > 0

    dry_run_allowed_report = validate_paper_result_evidence(
        bundle_root,
        allow_dry_run=True,
        require_experiment_coverage=False,
    )
    dry_run_allowed_check = next(
        item for item in dry_run_allowed_report["checks"] if item["requirement"] == "colab_formal_run_checklist_passed"
    )

    assert dry_run_allowed_report["overall_decision"] == "pass"
    assert dry_run_allowed_check["status"] == "pass"
    assert dry_run_allowed_check["evidence"]["reason"] == "allow_dry_run_enabled"


def _write_external_command_evidence(bundle_root, *, advanced_metrics: bool) -> None:
    """写出轻量外部命令结果证据, 用于验证正式 evidence 门禁。"""
    baseline_root = bundle_root / "external_baselines"
    metric_root = bundle_root / "external_metrics"
    baseline_root.mkdir(parents=True, exist_ok=True)
    metric_root.mkdir(parents=True, exist_ok=True)
    (baseline_root / "baseline_command_results.json").write_text(
        json.dumps([{"return_code": 0, "command": ["baseline"], "stdout": "", "stderr": ""}], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (baseline_root / "baseline_observations.json").write_text(
        json.dumps([{"event_id": "formal_e1", "baseline_id": "tree_ring", "score": 0.8, "threshold": 0.5}], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (metric_root / "metric_command_results.json").write_text(
        json.dumps([{"return_code": 0, "command": ["metric"], "stdout": "", "stderr": ""}], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    metric_row = {"event_id": "formal_e1", "method_name": "ceg", "psnr": 32.0}
    if advanced_metrics:
        metric_row.update({"lpips": 0.04, "fid": 8.0, "clip_score": 0.31})
    (metric_root / "metric_rows.json").write_text(
        json.dumps([metric_row], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


@pytest.mark.quick
def test_formal_result_evidence_validates_external_result_payloads(tmp_path) -> None:
    """外部命令返回码成功后, evidence 门禁还应校验实际输出结果文件结构。"""
    run_colab_cold_start_pipeline(".", tmp_path / "colab_workspace", repetitions=1)
    bundle_root = tmp_path / "colab_workspace" / "colab_run_bundle"

    _write_external_command_evidence(bundle_root, advanced_metrics=False)
    missing_advanced_report = validate_paper_result_evidence(
        bundle_root,
        allow_dry_run=True,
        require_experiment_coverage=False,
        require_external_command_results=True,
    )
    missing_advanced_check = next(
        item for item in missing_advanced_report["checks"] if item["requirement"] == "external_command_results_passed"
    )

    assert missing_advanced_report["overall_decision"] == "fail"
    assert missing_advanced_check["status"] == "fail"
    failure_reasons = {item["reason"] for item in missing_advanced_check["evidence"]["failures"]}
    assert "advanced_metric_fields_missing" in failure_reasons

    _write_external_command_evidence(bundle_root, advanced_metrics=True)
    passed_report = validate_paper_result_evidence(
        bundle_root,
        allow_dry_run=True,
        require_experiment_coverage=False,
        require_external_command_results=True,
    )
    passed_check = next(item for item in passed_report["checks"] if item["requirement"] == "external_command_results_passed")

    assert passed_report["overall_decision"] == "pass"
    assert passed_check["status"] == "pass"
    assert passed_check["evidence"]["baseline_observation_count"] == 1
    assert passed_check["evidence"]["external_metric_row_count"] == 1
    assert set(passed_check["evidence"]["external_advanced_metric_fields"]) == {"clip_score", "fid", "lpips"}




def _sha256(path) -> str:
    """计算测试文件摘要, 与 Colab bundle provenance 结构保持一致。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_provided_result_manifest(bundle_root) -> None:
    """写入直接提供结果文件副本 manifest, 用于验证 evidence 门禁。"""
    provided_root = bundle_root / "provided_results"
    provided_root.mkdir(parents=True, exist_ok=True)
    baseline_path = provided_root / "baseline_observations.json"
    metric_path = provided_root / "metric_rows.json"
    baseline_path.write_text(
        json.dumps([{"event_id": "formal_e1", "baseline_id": "tree_ring", "score": 0.8, "threshold": 0.5}], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    metric_path.write_text(
        json.dumps([{"event_id": "formal_e1", "baseline_id": "tree_ring", "lpips": 0.04}], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "artifact_name": "provided_result_files_manifest.json",
        "overall_decision": "pass",
        "workspace_root": str(bundle_root.parent),
        "provided_results_root": str(provided_root),
        "copied_files": [
            {
                "role": "baseline_observations",
                "source_path": "source/baseline_observations.json",
                "target_path": str(baseline_path),
                "relative_target_path": "provided_results/baseline_observations.json",
                "byte_count": baseline_path.stat().st_size,
                "sha256": _sha256(baseline_path),
            },
            {
                "role": "metric_rows",
                "source_path": "source/metric_rows.json",
                "target_path": str(metric_path),
                "relative_target_path": "provided_results/metric_rows.json",
                "byte_count": metric_path.stat().st_size,
                "sha256": _sha256(metric_path),
            },
        ],
        "missing_sources": [],
        "copied_file_count": 2,
    }
    (provided_root / "provided_result_files_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


@pytest.mark.quick
def test_formal_result_evidence_validates_provided_result_file_manifest(tmp_path) -> None:
    """Colab bundle 使用直接提供结果文件时, evidence 门禁应校验副本 manifest 和文件摘要。"""
    run_colab_cold_start_pipeline(".", tmp_path / "colab_workspace", repetitions=1)
    bundle_root = tmp_path / "colab_workspace" / "colab_run_bundle"
    _write_provided_result_manifest(bundle_root)

    passed_report = validate_paper_result_evidence(bundle_root, allow_dry_run=True, require_experiment_coverage=False)
    passed_check = next(item for item in passed_report["checks"] if item["requirement"] == "provided_result_files_manifest_valid")

    assert passed_report["overall_decision"] == "pass"
    assert passed_check["status"] == "pass"
    assert set(passed_check["evidence"]["copied_roles"]) == {"baseline_observations", "metric_rows"}

    (bundle_root / "provided_results" / "metric_rows.json").write_text("[]\n", encoding="utf-8")
    failed_report = validate_paper_result_evidence(bundle_root, allow_dry_run=True, require_experiment_coverage=False)
    failed_check = next(item for item in failed_report["checks"] if item["requirement"] == "provided_result_files_manifest_valid")

    assert failed_report["overall_decision"] == "fail"
    assert failed_check["status"] == "fail"
    assert any(item["reason"] == "digest_or_size_mismatch" for item in failed_check["evidence"]["failures"])


@pytest.mark.quick
def test_formal_result_evidence_requires_provided_manifest_when_checklist_uses_provided_files(tmp_path) -> None:
    """正式运行清单声明 provided_file 来源时, 缺少 provided_results manifest 应被阻断。"""
    run_colab_cold_start_pipeline(".", tmp_path / "colab_workspace", repetitions=1)
    bundle_root = tmp_path / "colab_workspace" / "colab_run_bundle"
    checklist_path = bundle_root / "colab_formal_run_checklist.json"
    checklist = json.loads(checklist_path.read_text(encoding="utf-8"))
    checklist["baseline_source_mode"] = "provided_file"
    checklist["metric_source_mode"] = "provided_file"
    checklist_path.write_text(json.dumps(checklist, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = validate_paper_result_evidence(bundle_root, allow_dry_run=True, require_experiment_coverage=False)
    check = next(item for item in report["checks"] if item["requirement"] == "provided_result_files_manifest_valid")

    assert report["overall_decision"] == "fail"
    assert check["status"] == "fail"
    assert check["evidence"]["reason"] == "missing"
